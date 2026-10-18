"""End-to-end regression against the original pinned EV4 CE validator fixture."""
from __future__ import annotations
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from run_ce import run  # noqa: E402

class CEServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from restore_ce_source import restore
        restore()
        cls.fixtures=ROOT/'.runtime'/'ce-source'/'fixtures'/'chain'

    def make_submission(self, base):
        submission=base/'submissions'/'case001'
        submission.mkdir(parents=True)
        shutil.copyfile(self.fixtures/'ARCHITECT_HANDOFF.json',submission/'architect-handoff.json')
        shutil.copyfile(self.fixtures/'CE_CANDIDATE_HANDOFF.json',submission/'ce-candidate.json')
        return submission

    def test_real_validator_accepts_original_fixture(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); self.make_submission(root)
            code=run(root/'submissions',root/'out',head_sha='test-head',service_sha='test-service',run_id='fixture')
            result=json.loads((root/'out'/'result.json').read_text())
            self.assertEqual(code,0)
            self.assertEqual(result['state'],'VALIDATOR_PASS')
            self.assertEqual(result['canonical_status'],'OFFICIAL_ACCEPTED')
            self.assertTrue((root/'out'/'official-ce-handoff.json').is_file())
            self.assertEqual(result['official_handoff_sha256'], __import__('hashlib').sha256((root/'out'/'official-ce-handoff.json').read_bytes()).hexdigest())
            if os.environ.get('CE_FIXTURE_EVIDENCE_DIR'):
                shutil.copytree(root/'out',Path(os.environ['CE_FIXTURE_EVIDENCE_DIR'])/'known-valid',dirs_exist_ok=True)

    def test_real_validator_rejects_changed_candidate_without_handoff(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); p=self.make_submission(root)/'ce-candidate.json'
            obj=json.loads(p.read_text());obj['candidate_status']='QUALIFIED_OFFICIAL'
            p.write_text(json.dumps(obj,ensure_ascii=False),encoding='utf-8')
            code=run(root/'submissions',root/'out',head_sha='test-head',service_sha='test-service',run_id='fixture')
            result=json.loads((root/'out'/'result.json').read_text())
            self.assertEqual(code,1)
            self.assertEqual(result['state'],'VALIDATOR_FAIL')
            self.assertIn('CANDIDATE_STATUS_REQUIRED',result['errors'])
            self.assertFalse((root/'out'/'official-ce-handoff.json').exists())
            if os.environ.get('CE_FIXTURE_EVIDENCE_DIR'):
                shutil.copytree(root/'out',Path(os.environ['CE_FIXTURE_EVIDENCE_DIR'])/'deliberately-invalid',dirs_exist_ok=True)

    def test_missing_inputs_are_not_claimed_as_validator_fail(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'submissions').mkdir()
            code=run(root/'submissions',root/'out',head_sha='test-head',service_sha='test-service',run_id='fixture')
            self.assertEqual(code,2)
            self.assertEqual(json.loads((root/'out'/'result.json').read_text())['state'],'NOT_EXECUTED')

    def test_stale_official_output_is_removed_on_fail(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);self.make_submission(root)
            out=root/'out';out.mkdir();(out/'official-ce-handoff.json').write_text('OLD FALSE HANDOFF')
            obj=json.loads((root/'submissions'/'case001'/'ce-candidate.json').read_text());obj['candidate_status']='QUALIFIED_OFFICIAL'
            (root/'submissions'/'case001'/'ce-candidate.json').write_text(json.dumps(obj))
            self.assertEqual(run(root/'submissions',out,head_sha='h',service_sha='s',run_id='r'),1)
            self.assertFalse((out/'official-ce-handoff.json').exists())


    def test_deeply_nested_architect_input_stays_not_executed(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            submission=self.make_submission(root)
            # Valid JSON, below the 5 MB limit, but above Python's JSON recursion limit.
            payload='[' * 15000 + '0' + ']' * 15000
            self.assertLess(len(payload.encode('utf-8')),5_000_000)
            (submission/'architect-handoff.json').write_text(payload,encoding='utf-8')
            out=root/'out'
            self.assertEqual(run(root/'submissions',out,head_sha='h',service_sha='s',run_id='r'),2)
            report=json.loads((out/'result.json').read_text(encoding='utf-8'))
            self.assertEqual(report['state'],'NOT_EXECUTED')
            self.assertTrue(any('RecursionError' in e for e in report['errors']))
            self.assertFalse((out/'canonical-result.json').exists())
            self.assertFalse((out/'official-ce-handoff.json').exists())

    def test_deeply_nested_candidate_input_stays_not_executed(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); submission=self.make_submission(root)
            (submission/'ce-candidate.json').write_text('[' * 15000 + '0' + ']' * 15000,encoding='utf-8')
            out=root/'out'; out.mkdir()
            (out/'official-ce-handoff.json').write_text('stale handoff',encoding='utf-8')
            self.assertEqual(run(root/'submissions',out,head_sha='h',service_sha='s',run_id='r'),2)
            report=json.loads((out/'result.json').read_text(encoding='utf-8'))
            self.assertEqual(report['state'],'NOT_EXECUTED')
            self.assertTrue(any('RecursionError' in e for e in report['errors']))
            self.assertFalse((out/'canonical-result.json').exists())
            self.assertFalse((out/'official-ce-handoff.json').exists())

    def test_other_input_decode_failures_remain_not_executed(self):
        variants=[('malformed-json',b'{"broken":'),('invalid-utf8',b'\\xff\\xfe{')]
        for label,payload in variants:
            with self.subTest(label=label), tempfile.TemporaryDirectory() as d:
                root=Path(d); submission=self.make_submission(root)
                (submission/'ce-candidate.json').write_bytes(payload)
                code=run(root/'submissions',root/'out',head_sha='h',service_sha='s',run_id='r')
                report=json.loads((root/'out'/'result.json').read_text(encoding='utf-8'))
                self.assertEqual(code,2)
                self.assertEqual(report['state'],'NOT_EXECUTED')
                self.assertFalse((root/'out'/'canonical-result.json').exists())
                self.assertFalse((root/'out'/'official-ce-handoff.json').exists())

    def test_missing_trusted_validator_is_execution_unavailable(self):
        from unittest.mock import patch
        import run_ce
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); self.make_submission(root)
            with patch.object(run_ce,'VALIDATOR',root/'no-trusted-validator.py'):
                code=run(root/'submissions',root/'out',head_sha='h',service_sha='s',run_id='r')
            report=json.loads((root/'out'/'result.json').read_text(encoding='utf-8'))
            self.assertEqual(code,2)
            self.assertEqual(report['state'],'EXECUTION_UNAVAILABLE')
            self.assertFalse((root/'out'/'official-ce-handoff.json').exists())

    def test_subprocess_launch_failure_is_execution_unavailable(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); self.make_submission(root)
            with patch('run_ce.subprocess.run',side_effect=FileNotFoundError('trusted runner unavailable')):
                code=run(root/'submissions',root/'out',head_sha='h',service_sha='s',run_id='r')
            report=json.loads((root/'out'/'result.json').read_text(encoding='utf-8'))
            self.assertEqual(code,2)
            self.assertEqual(report['state'],'EXECUTION_UNAVAILABLE')
            self.assertFalse((root/'out'/'official-ce-handoff.json').exists())

    def test_subprocess_timeout_is_execution_unavailable(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); self.make_submission(root)
            with patch('run_ce.subprocess.run',side_effect=subprocess.TimeoutExpired(cmd='ce',timeout=90)):
                code=run(root/'submissions',root/'out',head_sha='h',service_sha='s',run_id='r')
            report=json.loads((root/'out'/'result.json').read_text(encoding='utf-8'))
            self.assertEqual(code,2)
            self.assertEqual(report['state'],'EXECUTION_UNAVAILABLE')
            self.assertFalse((root/'out'/'official-ce-handoff.json').exists())

    def test_unparseable_canonical_result_is_execution_unavailable(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); self.make_submission(root); out=root/'out'
            def invalid_result(command,**kwargs):
                (out/'canonical-result.json').write_text('{"unfinished":',encoding='utf-8')
                return subprocess.CompletedProcess(command,1,stdout='',stderr='')
            with patch('run_ce.subprocess.run',side_effect=invalid_result):
                code=run(root/'submissions',out,head_sha='h',service_sha='s',run_id='r')
            report=json.loads((out/'result.json').read_text(encoding='utf-8'))
            self.assertEqual(code,2)
            self.assertEqual(report['state'],'EXECUTION_UNAVAILABLE')
            self.assertFalse((out/'official-ce-handoff.json').exists())


    def test_deeply_nested_canonical_result_is_execution_unavailable(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); self.make_submission(root); out=root/'out'
            def invalid_result(command,**kwargs):
                (out/'canonical-result.json').write_text('[' * 15000 + '0' + ']' * 15000,encoding='utf-8')
                return subprocess.CompletedProcess(command,1,stdout='',stderr='')
            with patch('run_ce.subprocess.run',side_effect=invalid_result):
                code=run(root/'submissions',out,head_sha='h',service_sha='s',run_id='r')
            report=json.loads((out/'result.json').read_text(encoding='utf-8'))
            self.assertEqual(code,2)
            self.assertEqual(report['state'],'EXECUTION_UNAVAILABLE')
            self.assertTrue(any('RecursionError' in e for e in report['errors']))
            self.assertFalse((out/'official-ce-handoff.json').exists())


    def test_canonical_result_falsification_matrix(self):
        """Malformed or contradictory trusted results never escape or become PASS."""
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            self.make_submission(root)
            accepted_out=root/'accepted'
            self.assertEqual(run(root/'submissions',accepted_out,head_sha='h',service_sha='s',run_id='r'),0)
            accepted=json.loads((accepted_out/'canonical-result.json').read_text(encoding='utf-8'))
            official_bytes=(accepted_out/'official-ce-handoff.json').read_bytes()
            # The pinned canonical CE receipt is admissible only with no blocking errors.
            self.assertEqual(accepted['status'],'OFFICIAL_ACCEPTED')
            self.assertEqual(accepted['errors'],[])
            rejected={'status':'REJECTED',
                      'validator_version':accepted['validator_version'],
                      'errors':['CANDIDATE_STATUS_REQUIRED'],'official_handoff':None}
            cases=[
                ('top-level-array',[],0,official_bytes),
                ('top-level-scalar',42,0,official_bytes),
                ('top-level-null',None,0,official_bytes),
                ('errors-null',{**accepted,'errors':None},0,official_bytes),
                ('errors-string',{**accepted,'errors':'bad'},0,official_bytes),
                ('errors-number',{**accepted,'errors':17},0,official_bytes),
                ('errors-nonstring-entry',{**accepted,'errors':['x',{'not':'a string'}]},0,official_bytes),
                ('invalid-version',{**accepted,'validator_version':None},0,official_bytes),
                ('wrong-validator-version',{**accepted,'validator_version':'UNPINNED'},0,official_bytes),
                ('accepted-with-errors',{**accepted,'errors':['CANONICAL_BLOCKER']},0,official_bytes),
                ('accepted-receipt-forbidden',{**accepted,'completion_receipt':{**accepted['completion_receipt'],'final_handoff':'FORBIDDEN'}},0,official_bytes),
                ('accepted-receipt-error-count',{**accepted,'completion_receipt':{**accepted['completion_receipt'],'validation_error_count':1}},0,official_bytes),
                ('accepted-qualification-status',{**accepted,'official_handoff':{**accepted['official_handoff'],'qualification':{**accepted['official_handoff']['qualification'],'status':'REJECTED'}}},0,official_bytes),
                ('status-not-string',{**accepted,'status':['OFFICIAL_ACCEPTED']},0,official_bytes),
                ('errors-absent',{k:v for k,v in accepted.items() if k!='errors'},0,official_bytes),
                ('accepted-exit-mismatch',accepted,1,official_bytes),
                ('accepted-no-output',accepted,0,None),
                ('accepted-output-mismatch',accepted,0,b'{}'),
                ('accepted-hash-mismatch',{**accepted,'official_handoff_sha256':'0'*64},0,official_bytes),
                ('accepted-missing-payload',{**accepted,'official_handoff':None},0,official_bytes),
                ('rejected-exit-mismatch',rejected,0,None),
                ('rejected-has-file',rejected,1,official_bytes),
                ('rejected-has-payload',{**rejected,'official_handoff':{}},1,None),
                ('rejected-has-hash',{**rejected,'official_handoff_sha256':'f'*64},1,None),
                ('rejected-with-invalid-errors',{**rejected,'errors':None},1,None),
            ]
            for label,payload,exit_status,official in cases:
                with self.subTest(label=label):
                    out=root/('case-'+label)
                    def simulated_validator(command,**kwargs):
                        out.mkdir(parents=True,exist_ok=True)
                        (out/'canonical-result.json').write_text(
                            json.dumps(payload,ensure_ascii=False),encoding='utf-8')
                        if official is not None:
                            (out/'official-ce-handoff.json').write_bytes(official)
                        return subprocess.CompletedProcess(command,exit_status,stdout='',stderr='')
                    with patch('run_ce.subprocess.run',side_effect=simulated_validator):
                        result_code=run(root/'submissions',out,head_sha='h',service_sha='s',run_id='r')
                    report=json.loads((out/'result.json').read_text(encoding='utf-8'))
                    self.assertEqual(result_code,2)
                    self.assertEqual(report['state'],'EXECUTION_UNAVAILABLE')
                    self.assertIsInstance(report['errors'],list)
                    self.assertTrue(all(isinstance(error,str) for error in report['errors']))
                    self.assertTrue(report['errors'])
                    self.assertFalse((out/'official-ce-handoff.json').exists())

    def test_canonical_rejection_with_empty_diagnostics_preserves_contract(self):
        """A forbidden receipt may reject without a blocking error list."""
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); self.make_submission(root); out=root/'out'
            result={'status':'REJECTED',
                    'validator_version':'EV4_CE_QUALIFICATION_RUNNER_1.1.0',
                    'errors':[],'official_handoff':None}
            def simulated_validator(command,**kwargs):
                out.mkdir(parents=True,exist_ok=True)
                (out/'canonical-result.json').write_text(json.dumps(result),encoding='utf-8')
                return subprocess.CompletedProcess(command,1,stdout='',stderr='')
            with patch('run_ce.subprocess.run',side_effect=simulated_validator):
                code=run(root/'submissions',out,head_sha='h',service_sha='s',run_id='r')
            report=json.loads((out/'result.json').read_text(encoding='utf-8'))
            self.assertEqual(code,1)
            self.assertEqual(report['state'],'VALIDATOR_FAIL')
            self.assertFalse((out/'official-ce-handoff.json').exists())

if __name__=='__main__':unittest.main()