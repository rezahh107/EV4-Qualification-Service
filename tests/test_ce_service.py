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

if __name__=='__main__':unittest.main()