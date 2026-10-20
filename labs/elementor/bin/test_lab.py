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
    def test_assertion_origin_not_error_text(self):
        identity = 'L:contrast-aa-default-button'
        def result_with_step(status, step, message='AssertionError expect(locator)'):
            return {'suites': [{'specs': [{'title': '[' + identity + '] check',
                'tests': [{'results': [{'status': status,
                    'errors': [{'message': message}],
                    'steps': [step] if step is not None else []}]}]}]}]}
        def target():
            return lab.template(lab.profile(lab.ROOT/'profiles/core-4.3.5.json'), 'L')
        def status_of(candidate):
            return next(x['status'] for x in candidate['scenarios']
                        if x['test_identity'] == identity)

        # Harness-level expect() error cannot impersonate a product assertion.
        without = target()
        lab.classify_playwright(result_with_step('failed', {
            'title': 'Harness prerequisite', 'category': 'test.step',
            'error': {'message': 'expect() failed in initialization'}}), without)
        self.assertEqual(status_of(without), 'NOT_PROVEN')

        with_step = target()
        qualified = {'title': lab.QUALIFIED_STEP_PREFIX + identity,
                     'category': 'test.step',
                     'error': {'message': 'Measured contrast 1.99 < 4.5'}}
        # Actual Playwright JSONReportTestStep does not serialize category.
        qualified.pop('category')
        lab.classify_playwright(result_with_step('failed', qualified), with_step)
        self.assertEqual(status_of(with_step), 'VERIFIED_FAIL')
        self.assertEqual(next(x['observed']['assertion_origin'] for x in with_step['scenarios']
                              if x['test_identity'] == identity), 'EXPLICIT_PLAYWRIGHT_STEP')

        # A successful product assertion followed by a harness crash is unproven.
        late = target()
        lab.classify_playwright(result_with_step('failed', {
            'title': lab.QUALIFIED_STEP_PREFIX + identity, 'category': 'test.step'
        }), late)
        self.assertEqual(status_of(late), 'NOT_PROVEN')

    def test_targeted_execution_includes_authoring_dependency(self):
        p = lab.profile(lab.ROOT/'profiles/core-4.3.5.json')
        responsive = lab.template(p, 'K')
        cases = {(x['capability'], x['scenario']) for x in responsive['scenarios']}
        self.assertIn(('M', 'native-editor-create-reopen'), cases)
        self.assertIn(('K', 'ten-viewport-geometry'), cases)
        login = lab.template(p, 'O')
        self.assertTrue(all(x['capability'] == 'O' for x in login['scenarios']))

    def test_helper_change_invalidates_evidence_fingerprint(self):
        # A helper mutation must invalidate historical test identity.
        with tempfile.NamedTemporaryFile(
            mode='w+', dir=lab.ROOT / 'tests', suffix='.mjs'
        ) as helper:
            helper.write('export const sentinel = 1;')
            helper.flush()
            before = lab.test_hash()
            helper.seek(0)
            helper.truncate()
            helper.write('export const sentinel = 2;')
            helper.flush()
            self.assertNotEqual(before, lab.test_hash())

    def test_exact_head_checkout_falsifies_equal_tree_different_commit(self):
        import subprocess
        with tempfile.TemporaryDirectory() as td:
            def git(*args):
                return subprocess.check_output(['git', *args], cwd=td, text=True).strip()
            git('init')
            git('config', 'user.name', 'EV4 Test')
            git('config', 'user.email', 'ev4-test@example.invalid')
            (Path(td) / 'fixture.txt').write_text('unchanged')
            git('add', 'fixture.txt')
            git('commit', '-m', 'first')
            first = lab.actual_git_checkout(Path(td))
            tree_first = git('rev-parse', 'HEAD^{tree}')
            git('commit', '--allow-empty', '-m', 'second')
            second = lab.actual_git_checkout(Path(td))
            self.assertNotEqual(first, second)
            self.assertEqual(tree_first, git('rev-parse', 'HEAD^{tree}'))
            self.assertEqual(lab.require_exact_checkout(second, second), second)
            with self.assertRaisesRegex(RuntimeError, 'does not match'):
                lab.require_exact_checkout(first, second)
            with self.assertRaisesRegex(RuntimeError, 'absent or invalid'):
                lab.require_exact_checkout(None, second)

    def test_workflow_binds_expected_and_actual_head(self):
        flow = (lab.ROOT.parent.parent / '.github/workflows/elementor-lab.yml').read_text()
        self.assertIn('ref: ${{ github.event.pull_request.head.sha || github.sha }}', flow)
        self.assertIn('verify-checkout --expected "$EXPECTED_SOURCE_SHA"', flow)
        self.assertIn('EXPECTED_SOURCE_SHA: ${{ github.event.pull_request.head.sha || github.sha }}', flow)

    def test_catalog_qualified_assertion_coverage(self):
        expected = {s['test'] for d in lab.catalog()['domains']
                    for s in d['scenarios'] if s['test']}
        self.assertEqual(set(lab.validate_qualification_coverage()), expected)
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / 'tests').mkdir()
            original = (lab.ROOT / 'tests/native.spec.mjs').read_text()
            corrupted = original.replace(
                "await productAssertion('L:contrast-aa-default-button'",
                "await unqualifiedAssertion('L:contrast-aa-default-button'", 1)
            (root / 'tests/native.spec.mjs').write_text(corrupted)
            for support in ('helpers.mjs', 'qualification.mjs'):
                (root / 'tests' / support).write_text(
                    (lab.ROOT / 'tests' / support).read_text()
                )
            with patch.object(lab, 'ROOT', root):
                with self.assertRaisesRegex(ValueError, 'Structural source qualification failed'):
                    lab.validate_qualification_coverage()

    def test_storage_probe_unavailable_is_not_mismatch(self):
        def broken(*args):
            raise RuntimeError('WP-CLI transport error')
        self.assertEqual(lab.probe_wordpress_persistence('123', broken)['state'], 'UNAVAILABLE')
        def mismatched(*args):
            return '[{"widgetType":"e-heading","text":"EV4 Atomic Heading"}]' if 'meta' in args else 'draft'
        self.assertEqual(lab.probe_wordpress_persistence('123', mismatched)['state'], 'MISMATCH')
        def valid(*args):
            return '[{"widgetType":"e-heading","text":"EV4 Atomic Heading"}]' if 'meta' in args else 'publish\n'
        self.assertEqual(lab.probe_wordpress_persistence('123', valid)['state'], 'VERIFIED')

    def test_fixture_finalization_downgrades_all_dependent_passes_and_keeps_browser_facts(self):
        p = lab.profile(lab.ROOT / 'profiles/core-4.3.5.json')
        for storage, final in (({'state':'UNAVAILABLE','error':'WP-CLI failed'}, 'NOT_PROVEN'),
                               ({'state':'MISMATCH','atomic_data':False,'published':True}, 'VERIFIED_FAIL')):
            r = lab.template(p,'all')
            r['installed'] = {'wordpress':'7.1.3'}
            for item in r['scenarios']:
                if item['test_identity'] and (item['capability'] in lab.FIXTURE_DEPENDENTS
                                               or item['test_identity'] == 'M:native-editor-create-reopen'):
                    item['status'] = 'VERIFIED_PASS'
                    item['observed'] = {'browser_assertion':'passed'}
                if item['test_identity'] == 'O:installed-runtime-browser':
                    item['status'] = 'VERIFIED_PASS'
            lab.finalize_fixture_evidence(r, storage)
            fixture = next(x for x in r['scenarios'] if x['test_identity'] == 'M:native-editor-create-reopen')
            self.assertEqual(fixture['status'], final)
            self.assertEqual(fixture['observed']['browser_status'], 'VERIFIED_PASS')
            dependents = [x for x in r['scenarios'] if x['capability'] in lab.FIXTURE_DEPENDENTS and x['test_identity']]
            self.assertTrue(all(x['status'] == 'NOT_PROVEN' for x in dependents))
            self.assertTrue(all(x['observed']['browser_status'] == 'VERIFIED_PASS' for x in dependents))
            self.assertNotIn('elementor_storage', r)
            self.assertNotIn('atomic_editor_observed', r['installed'])
            self.assertEqual(next(x['status'] for x in r['scenarios']
                                  if x['test_identity']=='O:installed-runtime-browser'), 'VERIFIED_PASS')

    def test_valid_fixture_does_not_hide_independent_accessibility_failure(self):
        r = lab.template(lab.profile(lab.ROOT / 'profiles/core-4.3.5.json'),'all')
        r['installed'] = {'wordpress':'7.1.3'}
        for item in r['scenarios']:
            if item['test_identity']:
                item['status'] = ('VERIFIED_FAIL' if item['test_identity']=='L:contrast-aa-default-button'
                                  else 'VERIFIED_PASS')
                item['observed'] = {'browser_assertion':'measured'}
        lab.finalize_fixture_evidence(r, {'state':'VERIFIED','published':True,'atomic_data':True})
        self.assertEqual(next(x['status'] for x in r['scenarios']
                              if x['test_identity']=='L:contrast-aa-default-button'), 'VERIFIED_FAIL')
        self.assertTrue(all(x['status']=='VERIFIED_PASS' for x in r['scenarios']
                            if x['test_identity'] and x['test_identity'] != 'L:contrast-aa-default-button'))
        self.assertTrue(r['installed']['atomic_editor_observed'])
        self.assertIn('elementor_storage',r)

    def test_structural_spoof_falsification(self):
        from unittest.mock import patch
        original = (lab.ROOT / 'tests/native.spec.mjs').read_text()
        call = """await productAssertion('C:measured-geometry', async () => {
   expect(rect.height).toBeGreaterThan(5);
  });"""
        self.assertIn(call, original)

        def check(corrupted):
            with tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                (root / 'tests').mkdir()
                (root / 'tests/native.spec.mjs').write_text(corrupted)
                for support in ('helpers.mjs', 'qualification.mjs'):
                    (root / 'tests' / support).write_text(
                        (lab.ROOT / 'tests' / support).read_text()
                    )
                with patch.object(lab, 'ROOT', root):
                    with self.assertRaisesRegex(ValueError, 'Structural source qualification failed'):
                        lab.validate_qualification_coverage()

        # Comment contains exact old string marker, but no authorized executable call.
        check(original.replace(call, """/* await productAssertion('C:measured-geometry' */
  expect(rect.height).toBeGreaterThan(5);""", 1))

        # A fake raw Playwright step cannot borrow an authorized source contract.
        check(original.replace(call, """await test.step('EV4_PRODUCT_ASSERTION:C:measured-geometry', async () => {
   expect(rect.height).toBeGreaterThan(5);
  });""", 1))

        # Indirect alias and computed property must fail (not merely literal title matching).
        check(original.replace(call, """const forged = test['step'];
  await forged('EV4_' + 'PRODUCT_ASSERTION:C:measured-geometry', async () => {
    expect(rect.height).toBeGreaterThan(5);
  });""", 1))

        # Extra authorized invocation under same scenario is ambiguous.
        check(original.replace(call, call + '\n ' + call, 1))
        # The only invocation now carries a different identity.
        check(original.replace("productAssertion('C:measured-geometry'",
                               "productAssertion('D:atomic-semantic-heading'", 1))

    def test_reserved_runtime_step_ambiguity_fails_closed(self):
        identity = 'L:contrast-aa-default-button'
        def classify(state, steps):
            result = lab.template(lab.profile(lab.ROOT / 'profiles/core-4.3.5.json'), 'L')
            report = {'suites': [{'specs': [{'title': '[' + identity + '] measured',
                       'tests': [{'results': [{'status': state, 'steps': steps}]}]}]}]}
            lab.classify_playwright(report, result)
            return next(x for x in result['scenarios'] if x['test_identity'] == identity)

        marker = {'title': lab.QUALIFIED_STEP_PREFIX + identity,
                  'error': {'message': 'real contrast below 4.5'}}
        other = {'title': lab.QUALIFIED_STEP_PREFIX + 'A:native-parent-child',
                 'error': {'message': 'forged'}}
        self.assertEqual(classify('failed', [marker])['status'], 'VERIFIED_FAIL')
        self.assertEqual(classify('passed', [{'title': marker['title']}])['status'], 'VERIFIED_PASS')
        self.assertEqual(classify('failed', [marker, marker])['status'], 'NOT_PROVEN')
        self.assertEqual(classify('failed', [marker, other])['status'], 'NOT_PROVEN')
        self.assertEqual(classify('failed', [other])['status'], 'NOT_PROVEN')
        self.assertEqual(classify('failed', [{'title': marker['title']},
                       {'title': 'Harness assertion', 'error': {'message': 'expect()'}}])['status'],
                       'NOT_PROVEN')

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
