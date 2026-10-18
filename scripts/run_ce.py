#!/usr/bin/env python3
"""Run the unchanged canonical CE CLI against submission data (never as code)."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / '.runtime' / 'ce-source'
VALIDATOR = RUNTIME / 'validators' / 'qualify_ce_handoff.py'
PROFILE = RUNTIME / 'source' / 'style' / 'EV4_PERSONAL_STYLE_PROFILE_NUURO_v1.0.1.json'
CONTRACT = RUNTIME / 'source' / 'style' / 'EV4_PROJECT_CONTEXT_STYLE_CONTRACT_v1.2.1.json'
ARCHITECT = 'architect-handoff.json'
CANDIDATE = 'ce-candidate.json'

def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def safe_file(p):
    if p.is_symlink() or not p.is_file() or p.stat().st_size > 5_000_000:
        raise ValueError(f'INPUT_FILE_MISSING_UNSAFE_OR_TOO_LARGE:{p.name}')
    json.loads(p.read_text(encoding='utf-8'))

def run(submissions: Path, output: Path, *, head_sha: str, service_sha: str, run_id: str):
    output.mkdir(parents=True, exist_ok=True)
    # If reused, stale official outputs must never survive a failure.
    (output / 'official-ce-handoff.json').unlink(missing_ok=True)
    (output / 'canonical-result.json').unlink(missing_ok=True)
    report = {'schema':'ev4-ce-ci-result@1', 'workflow_run_attempt':os.environ.get('GITHUB_RUN_ATTEMPT',''), 'state':'NOT_EXECUTED',
              'validator':'EV4_CE_QUALIFICATION_RUNNER_1.1.0',
              'input_commit':head_sha, 'trusted_service_commit':service_sha,
              'workflow_run_id':run_id, 'errors':[], 'inputs':{}}
    exit_code=2
    try:
        if submissions.is_symlink():
            raise ValueError('SUBMISSIONS_ROOT_SYMLINK_FORBIDDEN')
        paths = sorted(x for x in submissions.iterdir() if x.is_dir() and not x.is_symlink())
        if len(paths) != 1:
            raise ValueError('EXACTLY_ONE_SUBMISSION_DIRECTORY_REQUIRED')
        submission = paths[0]
        report['submission_id']=submission.name
        if not submission.name.replace('-', '').replace('_','').isalnum() or len(submission.name) > 80:
            raise ValueError('SUBMISSION_ID_INVALID')
        architect = submission / ARCHITECT
        candidate = submission / CANDIDATE
        for label,p in [('architect',architect),('candidate',candidate)]:
            safe_file(p)
            report['inputs'][label]={'sha256':digest(p),'bytes':p.stat().st_size}
        # Trusted source is verified at restore time; the submission cannot supply it.
        for label,p in [('validator',VALIDATOR),('profile',PROFILE),('contract',CONTRACT)]:
            if not p.is_file():
                raise RuntimeError('TRUSTED_CE_SOURCE_MISSING:'+label)
            report['inputs'][label]={'sha256':digest(p),'bytes':p.stat().st_size}
        command=[sys.executable,str(VALIDATOR),'--architect',str(architect),'--candidate',str(candidate),
                 '--profile',str(PROFILE),'--contract',str(CONTRACT),
                 '--result',str(output/'canonical-result.json'),
                 '--official-output',str(output/'official-ce-handoff.json')]
        done=subprocess.run(command,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                            text=True,timeout=90,check=False)
        (output/'validator-stderr.txt').write_text(done.stderr[-12000:],encoding='utf-8')
        result_path=output/'canonical-result.json'
        if not result_path.is_file():
            raise RuntimeError('VALIDATOR_DID_NOT_PRODUCE_RESULT:exit='+str(done.returncode))
        raw=json.loads(result_path.read_text(encoding='utf-8'))
        report['errors']=raw.get('errors',[])
        report['canonical_status']=raw.get('status')
        report['validator_version']=raw.get('validator_version')
        official=output/'official-ce-handoff.json'
        if done.returncode==0 and raw.get('status')=='OFFICIAL_ACCEPTED' and official.is_file():
            report['state']='VALIDATOR_PASS'
            report['official_handoff_sha256']=digest(official)
            exit_code=0
        elif done.returncode==1 and raw.get('status')=='REJECTED' and not official.exists():
            report['state']='VALIDATOR_FAIL'
            exit_code=1
        else:
            raise RuntimeError('VALIDATOR_STATUS_EXIT_OUTPUT_DISAGREEMENT')
    except (FileNotFoundError, OSError, ValueError, json.JSONDecodeError) as exc:
        report['errors'].append(type(exc).__name__+':'+str(exc))
        report['state']='NOT_EXECUTED'
    except (RuntimeError, subprocess.TimeoutExpired) as exc:
        report['errors'].append(type(exc).__name__+':'+str(exc))
        report['state']='EXECUTION_UNAVAILABLE'
    finally:
        if report['state']!='VALIDATOR_PASS':
            (output/'official-ce-handoff.json').unlink(missing_ok=True)
        (output/'result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    return exit_code

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--submissions',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--head-sha',default=os.environ.get('INPUT_SHA',''))
    p.add_argument('--service-sha',default=os.environ.get('SERVICE_SHA',''))
    p.add_argument('--run-id',default=os.environ.get('GITHUB_RUN_ID',''))
    a=p.parse_args()
    return run(a.submissions,a.output,head_sha=a.head_sha,service_sha=a.service_sha,run_id=a.run_id)

if __name__=='__main__':
    raise SystemExit(main())