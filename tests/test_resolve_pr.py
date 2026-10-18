import sys
from pathlib import Path
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from resolve_pr import resolve

class ResolvePRTests(unittest.TestCase):
    def valid(self):
        return {'head':{'sha':'a'*40,'repo':{'full_name':'owner/service'}},'base':{'ref':'main','repo':{'full_name':'owner/service'}}}
    def test_valid(self):
        self.assertEqual(resolve(self.valid(),'owner/service')['head_sha'],'a'*40)
    def test_other_target_rejected(self):
        obj=self.valid();obj['base']['repo']['full_name']='attacker/other'
        with self.assertRaises(ValueError):resolve(obj,'owner/service')
    def test_injection_head_repo_rejected(self):
        obj=self.valid();obj['head']['repo']['full_name']='other/name\nworkflow=true'
        with self.assertRaises(ValueError):resolve(obj,'owner/service')
    def test_malformed_sha_rejected(self):
        obj=self.valid();obj['head']['sha']='$(touch gotcha)'
        with self.assertRaises(ValueError):resolve(obj,'owner/service')

if __name__=='__main__':unittest.main()