"""Contract tests. These do not stand in for real browser evidence."""
import json
from pathlib import Path
import tempfile
import unittest
import lab

class LabTests(unittest.TestCase):
    def test_pinned_profile(self):
        p=lab.profile(lab.ROOT/'profiles/core-4.3.5.json')
        c=lab.wp_env_profile(p)
        self.assertIn('wordpress-7.1.3.zip',c['core'])
        self.assertIn('elementor.4.3.5.zip',c['plugins'][0])
        self.assertNotIn('ELEMENTOR_SHOW_HIDDEN_EXPERIMENTS',c['config'])
    def test_catalog_has_no_fabricated_pass(self):
        self.assertEqual(len(lab.catalog()['domains']),15)
        r=lab.template(lab.profile(lab.ROOT/'profiles/core-4.3.5.json'),'all')
        self.assertTrue(all(s['status']!='VERIFIED_PASS' for s in r['scenarios']))
        self.assertIn('PRO_OR_LICENSE_UNAVAILABLE',[s['status'] for s in r['scenarios']])
    def test_reject_external_profile(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'profile.json'
            path.write_text((lab.ROOT/'profiles/core-4.3.5.json').read_text())
            with self.assertRaises(ValueError):
                lab.profile(path)
    def test_qualify_assertion_not_harness_crash(self):
        def report(message):
            return {'suites':[{'specs':[{'title':'[D:atomic-semantic-heading] test',
                'tests':[{'results':[{'status':'failed','errors':[{'message':message}]}]}]}]}]}
        make=lambda:lab.template(lab.profile(lab.ROOT/'profiles/core-4.3.5.json'),'D')
        a=make()
        lab.classify_playwright(report('AssertionError expect(locator)'),a)
        self.assertEqual(a['scenarios'][0]['status'],'VERIFIED_FAIL')
        b=make()
        lab.classify_playwright(report('Browser context crashed'),b)
        self.assertEqual(b['scenarios'][0]['status'],'NOT_PROVEN')
    def test_targeted_execution_includes_authoring_dependency(self):
        p = lab.profile(lab.ROOT/'profiles/core-4.3.5.json')
        responsive = lab.template(p, 'K')
        cases = {(x['capability'], x['scenario']) for x in responsive['scenarios']}
        self.assertIn(('M', 'native-editor-create-reopen'), cases)
        self.assertIn(('K', 'ten-viewport-geometry'), cases)
        login = lab.template(p, 'O')
        self.assertEqual([x['capability'] for x in login['scenarios']], ['O'])

    def test_refuse_unlicensed_pro_override(self):
        p=lab.profile(lab.ROOT/'profiles/core-4.3.5.json')
        p['plugins']=[{'slug':'elementor-pro','version':'4.3.5'}]
        with tempfile.TemporaryDirectory(dir=lab.ROOT/'profiles') as d:
            path=Path(d)/'profile.json'
            path.write_text(json.dumps(p))
            with self.assertRaises(ValueError):
                lab.profile(path)

if __name__=='__main__':
    unittest.main()
