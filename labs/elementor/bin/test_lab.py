"""Contract tests. These do not stand in for real browser evidence."""
import json
from pathlib import Path
import tempfile
import unittest
import lab

def classify_synthetic_report(report, evidence):
    """Unit-only: explicitly furnish simulated completed observation provenance."""
    from unittest.mock import patch
    def simulated_receipt(identity):
        for suite in report.get('suites', []):
            for spec in suite.get('specs', []):
                if spec.get('title','').startswith('[' + identity + ']'):
                    attempts = spec['tests'][0].get('results', [])
                    steps = attempts[-1].get('steps', []) if attempts else []
                    failed = any(step.get('error') for step in steps)
                    return {'observation_state':'COMPLETE',
                            'assertion_state':'PRODUCT_FAIL' if failed else 'PRODUCT_PASS',
                            'observation_sha256':'synthetic-unit-evidence'}
        return {'observation_state':'NOT_PROVEN', 'assertion_state':'NOT_PROVEN'}
    with patch.object(lab,'read_qualification_receipts',side_effect=simulated_receipt):
        return lab.classify_playwright(report,evidence)


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
        classify_synthetic_report(result_with_step('failed', {
            'title': 'Harness prerequisite', 'category': 'test.step',
            'error': {'message': 'expect() failed in initialization'}}), without)
        self.assertEqual(status_of(without), 'NOT_PROVEN')

        with_step = target()
        qualified = {'title': lab.QUALIFIED_STEP_PREFIX + identity,
                     'category': 'test.step',
                     'error': {'message': 'Measured contrast 1.99 < 4.5'}}
        # Actual Playwright JSONReportTestStep does not serialize category.
        qualified.pop('category')
        classify_synthetic_report(result_with_step('failed', qualified), with_step)
        self.assertEqual(status_of(with_step), 'VERIFIED_FAIL')
        self.assertEqual(next(x['observed']['assertion_origin'] for x in with_step['scenarios']
                              if x['test_identity'] == identity), 'EXPLICIT_PLAYWRIGHT_STEP')

        # A successful product assertion followed by a harness crash is unproven.
        late = target()
        classify_synthetic_report(result_with_step('failed', {
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

    def test_real_git_clean_and_dirty_exact_source_provenance(self):
        import subprocess
        import sys

        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            lab_root = repo / 'labs' / 'elementor'
            (lab_root / 'bin').mkdir(parents=True)
            (lab_root / 'tests').mkdir()
            (lab_root / '.gitignore').write_text(
                'artifacts/\nnode_modules/\npackage-lock.json\n.wp-env.json\n.lab-state/\n')
            files = {
                'bin/lab.py': (lab.ROOT / 'bin/lab.py').read_bytes(),
                'bin/validate-source.mjs': b'const validated = true;\n',
                'tests/native.spec.mjs': b'// original tested source\n',
                'catalog.json': b'{"schema_version":1}\n',
            }
            for name, data in files.items():
                dest = lab_root / name
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(data)

            def git(*args):
                return subprocess.run(['git', *args], cwd=repo, check=True,
                                      text=True, capture_output=True).stdout.strip()
            git('init')
            git('config', 'user.name', 'EV4 Test')
            git('config', 'user.email', 'ev4-test@example.invalid')
            git('add', '.')
            git('commit', '-m', 'initial source')
            head = git('rev-parse', 'HEAD')
            self.assertEqual(lab.require_exact_source(head, lab_root), head)

            def run_cli(expected):
                return subprocess.run(
                    [sys.executable, str(lab_root / 'bin/lab.py'),
                     'verify-checkout', '--expected', expected],
                    cwd=lab_root, capture_output=True, text=True)
            self.assertEqual(run_cli(head).returncode, 0)

            # Commit identity stays constant even when running bytes change.
            for name, original in files.items():
                path = lab_root / name
                path.write_bytes(original + b'# changed without commit\n')
                with self.subTest(dirty=name):
                    self.assertEqual(git('rev-parse', 'HEAD'), head)
                    with self.assertRaisesRegex(RuntimeError, 'differs from HEAD'):
                        lab.require_exact_source(head, lab_root)
                    result = run_cli(head)
                    self.assertEqual(result.returncode, 2, result.stdout)
                    self.assertIn('NOT_PROVEN', result.stdout)
                path.write_bytes(original)

            # Staged edits and misleading Git index cache flags are not trusted.
            tracked = lab_root / 'catalog.json'
            tracked.write_text('{"schema_version":2}\n')
            git('add', 'labs/elementor/catalog.json')
            with self.assertRaisesRegex(RuntimeError, 'differs from HEAD'):
                lab.require_exact_source(head, lab_root)
            git('reset', 'HEAD', '--', 'labs/elementor/catalog.json')
            tracked.write_bytes(files['catalog.json'])
            git('update-index', '--assume-unchanged', 'labs/elementor/catalog.json')
            tracked.write_text('{"schema_version":99}\n')
            with self.assertRaisesRegex(RuntimeError, 'differs from HEAD'):
                lab.require_exact_source(head, lab_root)
            git('update-index', '--no-assume-unchanged', 'labs/elementor/catalog.json')
            tracked.write_bytes(files['catalog.json'])

            # New nested executable source cannot hide behind an unchanged HEAD.
            extra = lab_root / 'tests' / 'nested' / 'forged.spec.mjs'
            extra.parent.mkdir()
            extra.write_text('import {test} from "@playwright/test";\n'
                             'test("unauthorized",()=>{});\n')
            with self.assertRaisesRegex(RuntimeError, 'Unreviewed untracked source'):
                lab.require_exact_source(head, lab_root)
            self.assertEqual(run_cli(head).returncode, 2)
            extra.unlink()
            extra.parent.rmdir()

            # Legitimately ignored/generated output does not invalidate provenance.
            for name in ('artifacts/result.json', '.lab-state/state.json',
                         'node_modules/runtime.js', 'package-lock.json', '.wp-env.json'):
                output = lab_root / name
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text('{}')
            self.assertEqual(lab.require_exact_source(head, lab_root), head)
            self.assertEqual(run_cli(head).returncode, 0)

            # Equal source tree is not enough if the immutable HEAD differs.
            git('commit', '--allow-empty', '-m', 'new commit with identical tree')
            second = git('rev-parse', 'HEAD')
            self.assertNotEqual(second, head)
            with self.assertRaisesRegex(RuntimeError, 'does not match expected'):
                lab.require_exact_source(head, lab_root)
            self.assertEqual(lab.require_exact_source(second, lab_root), second)

    def test_provenance_rejection_precedes_wordpress_provisioning(self):
        import os
        from unittest.mock import patch
        p = lab.profile(lab.ROOT / 'profiles/core-4.3.5.json')
        with tempfile.TemporaryDirectory() as td:
            artifacts = Path(td) / 'artifacts'
            with patch.object(lab, 'ART', artifacts), \
                 patch.object(lab, 'require_exact_source',
                              side_effect=RuntimeError('Tracked working-tree source differs from HEAD')), \
                 patch.object(lab, 'wp_env_profile') as provisioning, \
                 patch.dict(os.environ, {'EXPECTED_SOURCE_SHA': lab.actual_git_checkout()}):
                self.assertEqual(lab.execute(p, 'O'), 2)
                provisioning.assert_not_called()
                evidence = json.loads((artifacts / 'result.json').read_text())
                self.assertFalse(evidence['provenance_verified'])
                self.assertEqual(evidence['execution'], 'NOT_PROVEN')
                self.assertEqual(evidence['teardown'], 'NOT_STARTED')
                self.assertIn('differs from HEAD', evidence['setup_error'])

    def test_acorn_pre_admission_value_error_finalizes_without_provisioning(self):
        """Execute the actual Acorn validator on a mutated source copy."""
        import os
        import shutil
        from unittest.mock import patch

        p = lab.profile(lab.ROOT / 'profiles/core-4.3.5.json')
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'lab'
            shutil.copytree(lab.ROOT / 'tests', root / 'tests')
            for name in ('predicate-contract.json', 'playwright.config.mjs'):
                shutil.copyfile(lab.ROOT / name, root / name)
            bad = root / 'tests/native.spec.mjs'
            bad.write_text(bad.read_text().replace(
                "await productAssertion('C:measured-geometry'",
                "await unauthorizedAssertion('C:measured-geometry'", 1))
            artifacts = root / 'artifacts'
            artifacts.mkdir()
            (artifacts / 'result.json').write_text('{"stale": true}')
            # The real parser is used. Only checkout/fingerprint acquisition is
            # simulated because this copy is deliberately not a Git checkout.
            with patch.object(lab, 'ROOT', root), \
                 patch.object(lab, 'ART', artifacts), \
                 patch.object(lab, 'test_hash', return_value='fixture-test-hash'), \
                 patch.object(lab, 'actual_git_checkout',
                              return_value='a' * 40), \
                 patch.object(lab, 'require_exact_source',
                              return_value='a' * 40), \
                 patch.object(lab, 'wp_env_profile') as provisioning, \
                 patch.dict(os.environ, {'EXPECTED_SOURCE_SHA': 'a' * 40}):
                self.assertEqual(lab.execute(p, 'C'), 2)
                provisioning.assert_not_called()
                evidence = json.loads((artifacts / 'result.json').read_text())
                self.assertNotIn('stale', evidence)
                self.assertEqual(evidence['execution'], 'NOT_PROVEN')
                self.assertFalse(evidence['provenance_verified'])
                self.assertIn('source_contract_error', evidence)
                self.assertEqual(evidence['source_commit'], 'UNBOUND')
                self.assertNotIn('provenance_error', evidence)
                self.assertIn('Structural source qualification failed',
                              evidence['source_contract_error'])
                self.assertEqual(evidence['teardown'], 'NOT_STARTED')
                self.assertIsNone(evidence['installed'])
                self.assertTrue(all(s['status'] == 'NOT_PROVEN'
                                    for s in evidence['scenarios'] if s['test_identity']))
                self.assertNotIn('playwright.json',
                                 [x.name for x in artifacts.iterdir()])

    def test_unavailable_test_fingerprint_never_reuses_stale_evidence(self):
        import os
        from unittest.mock import patch
        p = lab.profile(lab.ROOT / 'profiles/core-4.3.5.json')
        with tempfile.TemporaryDirectory() as td:
            artifacts = Path(td) / 'artifacts'
            artifacts.mkdir()
            (artifacts / 'result.json').write_text('{"execution":"VERIFIED_PASS"}')
            (artifacts / 'playwright.json').write_text('{"previous":true}')
            with patch.object(lab, 'ART', artifacts), \
                 patch.object(lab, 'test_hash',
                              side_effect=ValueError('symlinked test source')), \
                 patch.object(lab, 'wp_env_profile') as provisioning, \
                 patch.dict(os.environ, {'EXPECTED_SOURCE_SHA': 'a' * 40}):
                self.assertEqual(lab.execute(p, 'O'), 2)
                provisioning.assert_not_called()
                evidence = json.loads((artifacts / 'result.json').read_text())
                self.assertIsNone(evidence['test_sha256'])
                self.assertEqual(evidence['source_commit'], 'UNBOUND')
                self.assertFalse(evidence['provenance_verified'])
                self.assertEqual(evidence['execution'], 'NOT_PROVEN')
                self.assertIn('Source fingerprint unavailable',
                              evidence['provenance_error'])
                self.assertNotIn('source_contract_error', evidence)
                self.assertEqual(evidence['teardown'], 'NOT_STARTED')
                self.assertFalse((artifacts / 'playwright.json').exists())
                self.assertTrue(all(item['status'] == 'NOT_PROVEN'
                                    for item in evidence['scenarios']
                                    if item['test_identity']))

    def test_invalid_catalog_does_not_fabricate_scenario_roster(self):
        import os
        from unittest.mock import patch
        p = lab.profile(lab.ROOT / 'profiles/core-4.3.5.json')
        with tempfile.TemporaryDirectory() as td:
            artifacts = Path(td) / 'artifacts'
            with patch.object(lab, 'ART', artifacts), \
                 patch.object(lab, 'catalog',
                              side_effect=ValueError('Invalid catalog structure')), \
                 patch.object(lab, 'wp_env_profile') as provisioning, \
                 patch.dict(os.environ, {'EXPECTED_SOURCE_SHA': 'a' * 40}):
                self.assertEqual(lab.execute(p, 'all'), 2)
                provisioning.assert_not_called()
                evidence = json.loads((artifacts / 'result.json').read_text())
                self.assertIsNone(evidence['test_sha256'])
                self.assertEqual(evidence['source_commit'], 'UNBOUND')
                self.assertEqual(evidence['scenarios'], [])
                self.assertEqual(evidence['execution'], 'NOT_PROVEN')
                self.assertIn('source_contract_error', evidence)
                self.assertIsNone(evidence['environment_fingerprint'])

    def test_integrity_and_structural_failure_diagnostics_do_not_collapse(self):
        from unittest.mock import patch
        import os
        p = lab.profile(lab.ROOT / 'profiles/core-4.3.5.json')
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            with patch.object(lab, 'ART', root / 'artifacts'), \
                 patch.object(lab, 'require_exact_source',
                              side_effect=RuntimeError('Dirty tracked source')), \
                 patch.object(lab, 'validate_qualification_coverage') as validate, \
                 patch.object(lab, 'wp_env_profile') as provisioning, \
                 patch.dict(os.environ, {'EXPECTED_SOURCE_SHA': lab.actual_git_checkout()}):
                self.assertEqual(lab.execute(p, 'O'), 2)
                provisioning.assert_not_called()
                validate.assert_not_called()
                result = json.loads((root / 'artifacts/result.json').read_text())
                self.assertIn('provenance_error', result)
                self.assertNotIn('source_contract_error', result)
                self.assertEqual(result['execution'], 'NOT_PROVEN')

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
            (root / 'predicate-contract.json').write_text(
                (lab.ROOT / 'predicate-contract.json').read_text()
            )
            for support in ('helpers.mjs', 'qualification.mjs', 'observation.mjs'):
                (root / 'tests' / support).write_text(
                    (lab.ROOT / 'tests' / support).read_text()
                )
            (root / 'playwright.config.mjs').write_text(
                (lab.ROOT / 'playwright.config.mjs').read_text()
            )
            with patch.object(lab, 'ROOT', root):
                with self.assertRaisesRegex(ValueError, 'Structural source qualification failed'):
                    lab.validate_qualification_coverage()

    def test_storage_probe_unavailable_is_not_mismatch(self):
        from unittest.mock import patch
        ids = {'atomic':'2eb52f4', 'container':'5509617'}
        good = json.dumps([{'id':'5509617','elType':'container','elements':[
            {'id':'2eb52f4','elType':'widget','widgetType':'e-heading',
             'settings':{'title':{'$$type':'escaped-html','value':'EV4 Atomic Heading'}}}
        ]}])
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root/'element-ids.json').write_text(json.dumps(ids))
            with patch.object(lab,'ART',root):
                def transport(*args):
                    raise RuntimeError('WP-CLI transport error')
                self.assertEqual(lab.probe_wordpress_persistence('5',transport)['state'],'UNAVAILABLE')
                def backend(raw,status='publish'):
                    return lambda *args: raw if 'meta' in args else status
                self.assertEqual(lab.probe_wordpress_persistence('5',backend(good))['state'],'VERIFIED')
                self.assertEqual(lab.probe_wordpress_persistence('5',backend(good,'draft'))['state'],'MISMATCH')
                self.assertEqual(lab.probe_wordpress_persistence('5',backend('junk e-heading title EV4 Atomic Heading'))['state'],'MISMATCH')
                unrelated = json.dumps([
                    {'id':'5509617','elements':[{'id':'2eb52f4','elType':'widget',
                     'widgetType':'e-heading','settings':{'title':{'$$type':'escaped-html','value':'Other'}}}]},
                    {'id':'zzzzzzz','elType':'widget','widgetType':'heading',
                     'settings':{'title':'EV4 Atomic Heading'}}
                ])
                self.assertEqual(lab.probe_wordpress_persistence('5',backend(unrelated))['state'],'MISMATCH')
                self.assertEqual(lab.probe_wordpress_persistence('5',backend(good.replace('2eb52f4','aaaaaaa')))['state'],'MISMATCH')
                unsupported = good.replace('escaped-html','html')
                self.assertEqual(lab.probe_wordpress_persistence('5',backend(unsupported))['state'],'UNSUPPORTED')
                self.assertEqual(lab.probe_wordpress_persistence('5',backend(good.replace('e-heading','heading')))['state'],'MISMATCH')
                self.assertEqual(lab.probe_wordpress_persistence('5',backend(good.replace('EV4 Atomic Heading','Changed')))['state'],'MISMATCH')

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
        marker = "await productAssertion('C:measured-geometry',observation,snapshot=>{"
        self.assertIn(marker, original)
        def reject(mutant):
            with tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                (root/'tests').mkdir()
                (root/'tests/native.spec.mjs').write_text(mutant)
                (root/'predicate-contract.json').write_text(
                    (lab.ROOT/'predicate-contract.json').read_text()
                )
                for name in ('helpers.mjs','qualification.mjs','observation.mjs'):
                    (root/'tests'/name).write_text((lab.ROOT/'tests'/name).read_text())
                (root / 'playwright.config.mjs').write_text(
                    (lab.ROOT / 'playwright.config.mjs').read_text()
                )
                with patch.object(lab,'ROOT',root):
                    with self.assertRaisesRegex(ValueError,'Structural source qualification failed'):
                        lab.validate_qualification_coverage()
        reject(original.replace(marker, '// '+marker, 1))
        reject(original.replace(marker, marker + "\n   await page.locator('h2').count();",1))
        reject(original.replace(marker, marker + "\n   await page.locator('h2').first().evaluate(x=>x.innerText);",1))
        reject(original.replace(marker, marker + "\n   await page['goto'](frontend);",1))
        reject(original.replace(marker, marker + "\n   const indirect = () => page.locator('h2').count(); indirect();",1))
        reject(original.replace(marker, marker + "\n   expect(snapshot.width).toBe(0); " + marker,1))
        reject(original.replace("productAssertion('C:measured-geometry'",
                                "productAssertion('D:atomic-semantic-heading'",1))
        # Unsupported callbacks must fail closed, including pure JS computation.
        reject(original.replace(marker, marker + "\n   throw new Error('unexpected');",1))

    def test_reserved_runtime_step_ambiguity_fails_closed(self):
        identity = 'L:contrast-aa-default-button'
        def classify(state, steps):
            result = lab.template(lab.profile(lab.ROOT / 'profiles/core-4.3.5.json'), 'L')
            report = {'suites': [{'specs': [{'title': '[' + identity + '] measured',
                       'tests': [{'results': [{'status': state, 'steps': steps}]}]}]}]}
            classify_synthetic_report(report, result)
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

    def test_ambiguous_report_and_source_contract_fail_closed(self):
        from unittest.mock import patch
        p = lab.profile(lab.ROOT / 'profiles/core-4.3.5.json')
        r = lab.template(p, 'L')
        identity = 'L:contrast-aa-default-button'
        spec = {'title': '[' + identity + '] qualified',
                'tests': [{'results': [{'status':'failed','steps':[{
                    'title':lab.QUALIFIED_STEP_PREFIX + identity,
                    'error': {'message':'4.5 required'}}]}]}]}
        report = {'suites':[{'specs':[spec, spec]}]}
        self.assertEqual(classify_synthetic_report(report, r), 0)
        self.assertEqual(r['assertion_origin_error'].split(':')[0],
                         'Duplicate Playwright scenario result')
        self.assertTrue(all(x['status'] == 'NOT_PROVEN' for x in r['scenarios']
                            if x['test_identity']))
        r['provenance_verified'] = True
        r['installed'] = {'wordpress':'7.1.3'}
        r['teardown'] = 'VERIFIED'
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(lab, 'ART', Path(temp)):
                lab.finish(r)
        self.assertEqual(r['execution'], 'NOT_PROVEN')

    def test_responsive_preparation_vs_qualified_geometry(self):
        """Synthetic reporter inputs falsify origin classification, not real browser behavior."""
        identity = 'K:ten-viewport-geometry'
        widths = [320, 360, 375, 390, 412, 414, 768, 1024, 1440, 1920]

        def classification(browser_state, steps, message=None):
            report = {'suites': [{'specs': [{
                'title': '[' + identity + '] responsive measurement',
                'tests': [{'results': [{
                    'status': browser_state, 'steps': steps,
                    'errors': [{'message': message}] if message else [],
                }]}],
            }]}]}
            evidence = lab.template(lab.profile(lab.ROOT / 'profiles/core-4.3.5.json'), 'K')
            classify_synthetic_report(report, evidence)
            return next(x for x in evidence['scenarios'] if x['test_identity'] == identity)

        # The operation never reached the authorized step. Error wording is irrelevant.
        self.assertEqual(classification('failed', [], 'page.goto navigation error expect()')['status'],
                         'NOT_PROVEN')
        self.assertEqual(classification('failed', [], 'locator.evaluate measurement error')['status'],
                         'NOT_PROVEN')

        valid = [{'width': width, 'height': 25, 'x': 1, 'right': width - 1,
                  'documentWidth': width} for width in widths]
        self.assertEqual(len(valid), 10)
        self.assertTrue(all(x['height'] > 0 and x['x'] >= -1 and
                            x['right'] <= x['width'] + 1 and
                            x['documentWidth'] <= x['width'] + 1 for x in valid))
        step = {'title': lab.QUALIFIED_STEP_PREFIX + identity}
        passed = classification('passed', [step])
        self.assertEqual(passed['status'], 'VERIFIED_PASS')
        self.assertEqual(passed['observed']['qualified_step_count'], 1)

        invalid = [dict(x) for x in valid]
        invalid[3]['documentWidth'] = invalid[3]['width'] + 20
        self.assertFalse(all(x['documentWidth'] <= x['width'] + 1 for x in invalid))
        failure = classification('failed', [dict(step, error={
            'message': 'Observed overflow in completed 390px measurement'})])
        self.assertEqual(failure['status'], 'VERIFIED_FAIL')
        self.assertEqual(failure['observed']['qualified_step_count'], 1)

    def test_no_setup_navigation_or_measurement_inside_any_qualified_callback(self):
        from unittest.mock import patch
        original = (lab.ROOT / 'tests/native.spec.mjs').read_text()
        calls = [
            ("K:ten-viewport-geometry", "await page.goto(frontend);"),
            ("K:ten-viewport-geometry", "await page.setViewportSize({width:320,height:900});"),
            ("K:ten-viewport-geometry", "await page.locator('h2').first().evaluate(n=>n.textContent);"),
            ("K:ten-viewport-geometry", "await page.locator('h2').first().boundingBox();"),
            ("L:semantic-heading-name", "await page.goto(frontend);"),
            ("C:measured-geometry", "await page['goto'](frontend);"),
            ("E:native-global-class-persistence", "await page.locator('h2').first().evaluate(n=>n.textContent);"),
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'tests').mkdir()
            (root / 'predicate-contract.json').write_text(
                (lab.ROOT / 'predicate-contract.json').read_text()
            )
            for support in ('helpers.mjs', 'qualification.mjs', 'observation.mjs'):
                (root / 'tests' / support).write_text(
                    (lab.ROOT / 'tests' / support).read_text()
                )
            (root / 'playwright.config.mjs').write_text(
                (lab.ROOT / 'playwright.config.mjs').read_text()
            )
            with patch.object(lab, 'ROOT', root):
                for identity, operation in calls:
                    marker = "await productAssertion('" + identity + "',observation,snapshot=>{"
                    self.assertIn(marker, original)
                    modified = original.replace(marker, marker + '\n' + operation, 1)
                    (root / 'tests/native.spec.mjs').write_text(modified)
                    with self.subTest(identity=identity, operation=operation):
                        with self.assertRaisesRegex(
                            ValueError, 'Structural source qualification failed'
                        ):
                            lab.validate_qualification_coverage()
                (root / 'tests/native.spec.mjs').write_text(original)
                self.assertEqual(len(lab.validate_qualification_coverage()), 16)

    def test_provenance_gates_generic_callback_and_transport_errors(self):
        from unittest.mock import patch
        identity='C:measured-geometry'
        p=lab.profile(lab.ROOT/'profiles/core-4.3.5.json')
        def outcome(browser_status, marker_error, assertion_state, observation_state='COMPLETE'):
            candidate=lab.template(p,'C')
            step={'title':lab.QUALIFIED_STEP_PREFIX + identity}
            if marker_error: step['error']={'message':'simulated error'}
            report={'suites':[{'specs':[{'title':'['+identity+'] geometry',
                'tests':[{'results':[{'status':browser_status,'steps':[step]}]}]}]}]}
            with patch.object(lab,'read_qualification_receipts',return_value={
                'observation_state':observation_state,'assertion_state':assertion_state,
                'observation_sha256':'falsification'}):
                lab.classify_playwright(report,candidate)
            return next(x['status'] for x in candidate['scenarios']
                        if x['test_identity']==identity)
        self.assertEqual(outcome('passed',False,'PRODUCT_PASS'),'VERIFIED_PASS')
        self.assertEqual(outcome('failed',True,'PRODUCT_FAIL'),'VERIFIED_FAIL')
        self.assertEqual(outcome('failed',True,'UNPROVEN'),'NOT_PROVEN')
        self.assertEqual(outcome('failed',True,'PRODUCT_PASS'),'NOT_PROVEN')
        self.assertEqual(outcome('failed',True,'PRODUCT_FAIL','NOT_PROVEN'),'NOT_PROVEN')
        self.assertEqual(outcome('failed',False,'PRODUCT_PASS'),'NOT_PROVEN')

    def test_receipts_bind_to_completed_data_and_identity(self):
        from unittest.mock import patch
        import hashlib
        from unittest.mock import patch
        value={'count':2,'width':4}
        packed=json.dumps(value,separators=(',',':'),ensure_ascii=False)
        checksum=hashlib.sha256(packed.encode()).hexdigest()
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            directory=root/'observation-provenance'
            directory.mkdir()
            key='C__measured-geometry'
            o=directory/(key+'.observation.json')
            a=directory/(key+'.assertion.json')
            o.write_text(json.dumps({'state':'COMPLETE','identity':'C:measured-geometry',
                                     'sha256':checksum,'value':value}))
            a.write_text(json.dumps({'state':'PRODUCT_FAIL','identity':'C:measured-geometry',
                                     'observation_sha256':checksum}))
            with patch.object(lab,'ART',root):
                self.assertEqual(lab.read_qualification_receipts('C:measured-geometry')['assertion_state'],'PRODUCT_FAIL')
                o.write_text(json.dumps({'state':'COMPLETE','identity':'C:measured-geometry',
                                         'sha256':checksum,'value':{'count':1}}))
                self.assertEqual(lab.read_qualification_receipts('C:measured-geometry')['assertion_state'],'NOT_PROVEN')

    def test_approved_predicate_completeness_manifest_falsification(self):
        from unittest.mock import patch
        original=(lab.ROOT/'tests/native.spec.mjs').read_text()
        changes=[
            ("expect(snapshot?.width).toBeGreaterThan(5);","expect(snapshot?.width).toBeGreaterThan(0);"),
            ("expect(snapshot.afterDuplicate).toBe(2);","expect(snapshot.afterDuplicate).toBe(1);"),
            ("expect(measurement.documentWidth).toBeLessThanOrEqual(measurement.width+1);",
             "expect(measurement.documentWidth).toBeLessThanOrEqual(measurement.width+50);"),
            ("toBeGreaterThanOrEqual(4.5);","toBeGreaterThanOrEqual(2.0);"),
            ("expect(snapshot.httpStatus).toBe(200);","expect(snapshot.httpStatus).toBe(201);"),
        ]
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/'tests').mkdir()
            (root/'predicate-contract.json').write_text(
                (lab.ROOT/'predicate-contract.json').read_text())
            for name in ('helpers.mjs','qualification.mjs','observation.mjs'):
                (root/'tests'/name).write_text((lab.ROOT/'tests'/name).read_text())
            (root / 'playwright.config.mjs').write_text(
                (lab.ROOT / 'playwright.config.mjs').read_text()
            )
            with patch.object(lab,'ROOT',root):
                for before,after in changes:
                    self.assertIn(before,original)
                    (root/'tests/native.spec.mjs').write_text(original.replace(before,after,1))
                    with self.subTest(before=before):
                        with self.assertRaisesRegex(ValueError,'Structural source qualification failed'):
                            lab.validate_qualification_coverage()
                (root/'tests/native.spec.mjs').write_text(original)
                self.assertEqual(len(lab.validate_qualification_coverage()), 16)
                path=root/'tests/qualification.mjs'
                source=path.read_text()
                path.write_text(source.replace('PRODUCT_FAIL','PRODUCT_PASS'))
                with self.assertRaisesRegex(ValueError,'Structural source qualification failed'):
                    lab.validate_qualification_coverage()

    def test_observation_source_substitution_fails_closed(self):
        """Even intact predicates must not qualify a fabricated acquisition."""
        from unittest.mock import patch

        original = (lab.ROOT / 'tests/native.spec.mjs').read_text()
        changes = [
            ("return await page.locator('h2.e-heading-base').first().boundingBox();",
             "return {width:200,height:200,x:0,y:0};"),
            ("return {httpStatus:response?.status()??null,",
             "return {httpStatus:200,"),
            ("const afterDuplicate=await settledCount(headings,2);",
             "const afterDuplicate=2;"),
            ("records.push({width,...measurement});",
             "records.push({width,x:0,right:width,height:20,viewport:width,documentWidth:width});"),
        ]
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'tests').mkdir()
            (root / 'predicate-contract.json').write_text(
                (lab.ROOT / 'predicate-contract.json').read_text()
            )
            for name in ('helpers.mjs', 'qualification.mjs', 'observation.mjs'):
                (root / 'tests' / name).write_text(
                    (lab.ROOT / 'tests' / name).read_text()
                )
            (root / 'playwright.config.mjs').write_text(
                (lab.ROOT / 'playwright.config.mjs').read_text()
            )
            with patch.object(lab, 'ROOT', root):
                for original_code, fake_code in changes:
                    self.assertIn(original_code, original)
                    mutant = original.replace(original_code, fake_code, 1)
                    (root / 'tests/native.spec.mjs').write_text(mutant)
                    with self.subTest(change=original_code):
                        with self.assertRaisesRegex(
                            ValueError, 'Structural source qualification failed'
                        ):
                            lab.validate_qualification_coverage()
                (root / 'tests/native.spec.mjs').write_text(original)
                self.assertEqual(len(lab.validate_qualification_coverage()), 16)
                helper = root / 'tests/helpers.mjs'
                helper.write_text(helper.read_text().replace(
                    'return {root,ids};',
                    'return {root,ids:{...ids,atomic:"fake123"}};'
                ))
                with self.assertRaisesRegex(
                    ValueError, 'Structural source qualification failed'
                ):
                    lab.validate_qualification_coverage()

    def test_recursive_playwright_discovery_is_source_authorized(self):
        """Playwright --list sees nested runnable specs; the AST gate must reject
        them *before* any browser fixture or test-body side effect is executed."""
        import subprocess
        import shutil
        from unittest.mock import patch
        from pathlib import Path

        def clone(root):
            shutil.copytree(lab.ROOT / 'tests', root / 'tests')
            for name in ('predicate-contract.json', 'playwright.config.mjs'):
                shutil.copyfile(lab.ROOT / name, root / name)

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            clone(root)
            with patch.object(lab, 'ROOT', root):
                self.assertEqual(len(lab.validate_qualification_coverage()), 16)
                nested = root / 'tests' / 'subfolder'
                nested.mkdir()
                (nested / 'forged.spec.mjs').write_text(
                    'import {test} from "@playwright/test";\n'
                    'import fs from "node:fs";\n'
                    'test("PRI-FND-001-NESTED-EXECUTABLE",async()=>{\n'
                    '  fs.writeFileSync("artifacts/forged-qualification.txt","forged");\n'
                    '  await test.step("EV4_PRODUCT_ASSERTION:O:installed-runtime-browser",'
                    'async()=>{});\n'
                    '});\n'
                )
                with self.assertRaisesRegex(ValueError,
                        'Unreviewed Playwright-discoverable or test source path'):
                    lab.validate_qualification_coverage()
                # Historical immediate-child source enumeration misses this.
                self.assertNotIn('forged.spec.mjs',
                    [p.name for p in root.joinpath('tests').iterdir() if p.is_file()])

        # Exercise the actual Playwright 1.58.2 discovery on a temporary
        # nested spec under the *real* testDir (no browser test is executed).
        if not (lab.ROOT / 'node_modules' / '.bin' / 'playwright').is_file():
            self.skipTest('Playwright binary unavailable: discovery execution NOT_PROVEN')
        with tempfile.TemporaryDirectory(prefix='pri-fnd-001-',
                                         dir=lab.ROOT / 'tests') as nested_dir:
            specimen = Path(nested_dir) / 'nested.spec.mjs'
            specimen.write_text(
                'import {test} from "@playwright/test";\n'
                'test("PRI-FND-001-NESTED-DISCOVERED",async()=>{\n'
                '  throw Error("must not execute before qualification");\n'
                '});\n'
            )
            listed = subprocess.run(
                [lab.binary('playwright'), 'test',
                 '--config=playwright.config.mjs', '--list'],
                cwd=lab.ROOT, text=True, capture_output=True, timeout=50
            )
            self.assertEqual(listed.returncode, 0, listed.stderr[-1200:])
            self.assertIn('PRI-FND-001-NESTED-DISCOVERED', listed.stdout)
            with self.assertRaisesRegex(ValueError,
                    'Unreviewed Playwright-discoverable or test source path'):
                lab.validate_qualification_coverage()

    def test_discovery_configuration_and_source_shapes_fail_closed(self):
        import shutil
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            shutil.copytree(lab.ROOT / 'tests', root / 'tests')
            shutil.copyfile(lab.ROOT / 'predicate-contract.json',
                            root / 'predicate-contract.json')
            original = (lab.ROOT / 'playwright.config.mjs').read_text()
            configuration = root / 'playwright.config.mjs'
            configuration.write_text(original)
            with patch.object(lab, 'ROOT', root):
                self.assertEqual(len(lab.validate_qualification_coverage()), 16)
                # Comments/formatting do not affect semantic AST identity.
                configuration.write_text(original.replace(
                    "testMatch: '**/*.spec.mjs'",
                    "testMatch: /* harmless formatting */ '**/*.spec.mjs'"))
                self.assertEqual(len(lab.validate_qualification_coverage()), 16)
                mutations = {
                    'testMatch_wider': original.replace(
                        "'**/*.spec.mjs'", "'**/*.{spec,test}.mjs'"),
                    'testMatch_narrower': original.replace(
                        "'**/*.spec.mjs'", "'*.spec.mjs'"),
                    'testDir_outside': original.replace(
                        "testDir: './tests'", "testDir: '.'"),
                    'unreviewed_testIgnore': original.replace(
                        "workers: 1,", "testIgnore: '**/nested/**', workers: 1,"),
                    'dynamic_discovery': original.replace(
                        "testMatch: '**/*.spec.mjs'",
                        "testMatch: process.env.ANY_TEST_GLOB"),
                }
                for name, altered in mutations.items():
                    with self.subTest(name=name):
                        self.assertNotEqual(original, altered)
                        configuration.write_text(altered)
                        with self.assertRaisesRegex(
                                ValueError, 'Structural source qualification failed'):
                            lab.validate_qualification_coverage()
                configuration.write_text(original)
                self.assertEqual(len(lab.validate_qualification_coverage()), 16)
                # A symlinked source/directory, even if targeting a real approved
                # source, must never silently enter the authorized tree.
                target = root / 'tests' / 'helpers.mjs'
                link = root / 'tests' / 'linked.spec.mjs'
                link.symlink_to(target)
                with self.assertRaisesRegex(
                        ValueError, 'Symlinked Playwright test source'):
                    lab.validate_qualification_coverage()
                link.unlink()
                link.symlink_to(root / 'tests', target_is_directory=True)
                with self.assertRaisesRegex(
                        ValueError, 'Symlinked Playwright test source'):
                    lab.validate_qualification_coverage()
                link.unlink()
                # Unexpected executable representations fail closed too.
                (root / 'tests' / 'unauthorized.test.ts').write_text(
                    'export const unknown = 1;')
                with self.assertRaisesRegex(ValueError,
                        'Unreviewed Playwright-discoverable or test source path'):
                    lab.validate_qualification_coverage()

    def test_nested_executable_mutation_changes_source_fingerprint(self):
        with tempfile.TemporaryDirectory(prefix='pri-fnd-001-hash-',
                                         dir=lab.ROOT / 'tests') as subdir:
            nested = Path(subdir) / 'nested.spec.mjs'
            nested.write_text('export const scenario = 1;\n')
            original = lab.test_hash()
            nested.write_text('export const scenario = 2;\n')
            self.assertNotEqual(original, lab.test_hash())

    def test_module_observation_binding_is_canonical_and_closed(self):
        """Pinned Acorn rejects source-level observation substitution even if
        every reviewed scenario and predicate callback is unchanged."""
        from unittest.mock import patch
        original = (lab.ROOT / 'tests/native.spec.mjs').read_text()
        canonical = "import { observe, settledCount } from './observation.mjs';"
        self.assertIn(canonical, original)
        mutations = {
            'aliased_observe_wrapper': original.replace(canonical,
                """import { observe as authenticObserve, settledCount } from './observation.mjs';
const observe = (identity, acquire) => identity === 'O:installed-runtime-browser'
  ? authenticObserve(identity, async () => ({
    httpStatus:200, loginVisible:true, passwordVisible:true
  })) : authenticObserve(identity, acquire);""", 1),
            'direct_observe_substitution': original.replace(canonical,
                """import { settledCount } from './observation.mjs';
const observe = async (_identity, _acquire) => ({
 httpStatus:200,loginVisible:true,passwordVisible:true
});""", 1),
            'indirect_helper_wrapper': original.replace(canonical,
                canonical + "\nfunction fakeObservation(identity, collect) { return observe(identity, collect); }", 1),
            'module_shadowing': original.replace(canonical,
                canonical + "\nconst observeOverride = (...args) => observe(...args);", 1),
            'binding_reassignment': original.replace(canonical,
                canonical + "\nobserve = async () => null;", 1),
            'unexpected_top_level_io': original.replace(canonical,
                canonical + "\nfs.writeFileSync('artifacts/forged.json', '{}');", 1),
            'computed_member_mutation': original.replace(canonical,
                canonical + "\nconst redirect = globalThis['observe'];", 1),
            'changed_approved_const': original.replace(
                "const title = 'EV4 Atomic Heading';",
                "const title = 'Synthetic Heading';", 1),
            'extra_import': original.replace(canonical,
                canonical + "\nimport * as io from './observation.mjs';", 1),
        }
        harmless = original.replace("const title = 'EV4 Atomic Heading';",
                                    "const title = /* formatting */ 'EV4 Atomic Heading' ;", 1)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'tests').mkdir()
            (root / 'predicate-contract.json').write_text(
                (lab.ROOT / 'predicate-contract.json').read_text())
            for name in ('helpers.mjs', 'qualification.mjs', 'observation.mjs'):
                (root / 'tests' / name).write_text(
                    (lab.ROOT / 'tests' / name).read_text())
            path = root / 'tests/native.spec.mjs'
            (root / 'playwright.config.mjs').write_text(
                (lab.ROOT / 'playwright.config.mjs').read_text()
            )
            with patch.object(lab, 'ROOT', root):
                path.write_text(original)
                self.assertEqual(len(lab.validate_qualification_coverage()), 16)
                path.write_text(harmless)
                self.assertEqual(len(lab.validate_qualification_coverage()), 16)
                for name, mutation in mutations.items():
                    with self.subTest(name=name):
                        path.write_text(mutation)
                        with self.assertRaisesRegex(
                            ValueError, 'Structural source qualification failed'
                        ):
                            lab.validate_qualification_coverage()

    def test_native_partial_heading_topology_and_color_mutations(self):
        ids = {'post_id':'6', 'container':'ba12345', 'heading':'bc12345',
               'atomic_attempt':'bb12345', 'chosen_variant':'legacy',
               'expected_markup':lab.PARTIAL_MARKUP}
        def node(title=lab.PARTIAL_MARKUP, kind='heading'):
            return {'id':'bc12345','elType':'widget','widgetType':kind,
                    'settings':{'title':title},'elements':[]}
        def doc(children):
            return json.dumps([{'id':'ba12345','elType':'container',
                                'elements':children}])
        self.assertEqual(lab._inspect_partial_heading_document(
            doc([node()]), ids)['state'],'VERIFIED')
        for name, candidate in {
            'wrong_color':doc([node(lab.PARTIAL_MARKUP.replace('#b4234e','#ffffff'))]),
            'wrong_period':doc([node(lab.PARTIAL_MARKUP.replace('Intelligence.','Intelligence'))]),
            'wrong_widget':doc([node(kind='e-heading')]),
            'duplicate_heading':doc([node(),node()]),
            'wrong_direct_parent':json.dumps([node()]),
            'missing_heading':doc([]),
            'malformed':'invalid',
        }.items():
            with self.subTest(case=name):
                self.assertEqual(lab._inspect_partial_heading_document(
                    candidate,ids)['state'],'MISMATCH')
        self.assertEqual(lab._inspect_partial_heading_document(
            doc([node()]),{**ids,'chosen_variant':'atomic'})['state'],'MISMATCH')

    def test_native_atomic_container_topology_is_unique_and_direct(self):
        """Exercise production parser; browser and storage states are separate."""
        ids = {'atomic': '2eb52f4', 'container': '5509617'}
        expected_title = {'$$type': 'escaped-html', 'value': 'EV4 Atomic Heading'}
        def heading():
            return {'id': ids['atomic'], 'elType': 'widget',
                    'widgetType': 'e-heading',
                    'settings': {'title': expected_title}, 'elements': []}
        def container(children=None, element_id=None, element_type='container'):
            return {'id': element_id or ids['container'], 'elType': element_type,
                    'elements': [heading()] if children is None else children}
        cases = {
            'valid_unique_container': ([container()], 'VERIFIED'),
            'parent_wrong_element_type': ([container(element_type='widget')], 'MISMATCH'),
            'duplicate_parent_in_other_branch': ([container(), container([])], 'MISMATCH'),
            'duplicate_parent_in_ancestor_chain': (
                [container([container([heading()])])], 'MISMATCH'),
            'wrong_direct_parent': ([container(element_id='aaaaaaa')], 'MISMATCH'),
            'heading_not_direct_child': (
                [container([container([heading()], element_id='bbbbbbb')])], 'MISMATCH'),
            'duplicate_heading_identity': (
                [container([heading(), heading()])], 'MISMATCH'),
            'unknown_title_encoding': (
                [container([{**heading(), 'settings': {'title': {
                    '$$type': 'html', 'value': 'EV4 Atomic Heading'}}}])], 'UNSUPPORTED'),
            'wrong_heading_type': (
                [container([{**heading(), 'widgetType': 'heading'}])], 'MISMATCH'),
        }
        for name, (document, expected) in cases.items():
            with self.subTest(name=name):
                actual = lab._inspect_atomic_document(json.dumps(document), ids)
                self.assertEqual(actual['state'], expected)
        self.assertEqual(lab._inspect_atomic_document('{invalid', ids)['state'], 'MISMATCH')
        self.assertEqual(lab._inspect_atomic_document(json.dumps([container()]),
                                                       {'atomic':None,'container':'5509617'})['state'],
                         'UNSUPPORTED')
        # The post-status and WP-CLI branches are already exercised by the
        # existing storage transport/publication regression test.

    def _build_ci_gate_fixture(self, root, *, contrast_fail=True):
        """Synthetic current-run catalog/Playwright/receipt fixture; not runtime proof."""
        import hashlib
        import os
        p = lab.profile(lab.ROOT / 'profiles/core-4.3.5.json')
        head = lab.actual_git_checkout()
        result = lab.template(p, 'all')
        result.update(
            source_commit=head, checkout_commit=head, actual_checkout_commit=head,
            expected_source_commit=head, provenance_verified=True,
            github_run='ci-gate-test-run', github_attempt='1',
            teardown='VERIFIED', setup_error=None, fixture_post_id='5',
            execution='VERIFIED_FAIL' if contrast_fail else 'INCOMPLETE'
        )
        installed = {
            'wordpress': '7.1.3', 'elementor': '4.3.5',
            'theme': '3.5.1', 'php': '8.3.35', 'mariadb': '11.4.13',
            'atomic_editor_option': '',
            'browser': {'engine': 'chromium', 'version': '145.0.7632.6'},
        }
        result['environment_fingerprint'] = lab.digest({
            'requested': p, 'installed': installed,
            'test_sha256': result['test_sha256'],
            'catalog_sha256': lab.digest(lab.CAT.read_bytes())
        })
        installed['atomic_editor_observed'] = True
        result['installed'] = installed
        atomic, container = '2eb52f4', '5509617'
        ids = {'atomic': atomic, 'container': container}
        root.mkdir(parents=True, exist_ok=True)
        (root / 'element-ids.json').write_text(json.dumps(ids))
        native = json.dumps([{'id': container, 'elType':'container', 'elements':[
            {'id':atomic, 'elType':'widget', 'widgetType':'e-heading',
             'settings':{'title':{chr(36) * 2 + 'type':'escaped-html','value':'EV4 Atomic Heading'}}}
        ]}])
        (root / 'native-storage-sample.json').write_text(json.dumps({
            'fixture_post_id':'5', 'generated_element_ids':ids,
            'raw_elementor_data':native, 'post_status':'publish'
        }))
        # The new independent page is not the canonical M fixture.
        result['partial_heading_post_id'] = '6'
        result['partial_heading_capability'] = {
            'atomic_v4': 'NOT_PROVEN', 'legacy': 'VERIFIED_PASS',
            'method': 'native-legacy-heading-title-control',
            'qualified_identity': lab.PARTIAL_ID,
            'storage_probe': 'VERIFIED', 'target_site': 'NOT_PROVEN'
        }
        partial_ids = {'post_id':'6', 'container':'ba12345',
                       'atomic_attempt':'bb12345', 'heading':'bc12345',
                       'chosen_variant':'legacy', 'expected_markup':lab.PARTIAL_MARKUP}
        partial_data = json.dumps([{'id':'ba12345', 'elType':'container', 'elements':[
            {'id':'bc12345', 'elType':'widget', 'widgetType':'heading',
             'settings':{'title':lab.PARTIAL_MARKUP}, 'elements':[]}
        ]}])
        (root/'partial-heading-ids.json').write_text(json.dumps(partial_ids))
        (root/'partial-heading-storage.json').write_text(json.dumps({
            'post_id':'6', 'identity':partial_ids,
            'raw_elementor_data':partial_data, 'post_status':'publish'
        }))
        result['partial_heading_storage_probe'] = {
            'state':'VERIFIED', 'published':True, 'variant':'legacy',
            'saved_title':lab.PARTIAL_MARKUP,
            'generated_heading_id':'bc12345', 'generated_container_id':'ba12345'
        }
        result['fixture_storage_probe'] = {
            'state':'VERIFIED', 'published':True, 'atomic_data':True,
            'generated_atomic_id':atomic, 'generated_container_id':container,
            'title_type':'escaped-html'
        }
        result['elementor_storage'] = 'Verified native _elementor_data and publication'
        ratio = 1.9866101561483547 if contrast_fail else 7.2
        (root / 'accessibility-contrast.json').write_text(
            json.dumps({'contrast':ratio, 'foreground':'rgb(255,255,255)',
                        'background':'rgb(97,206,112)'}))
        receipts = root / 'observation-provenance'
        receipts.mkdir()
        specs = []
        for n,item in enumerate(result['scenarios']):
            identity = item['test_identity']
            if not identity:
                continue
            failure = contrast_fail and identity == lab.CI_INFORMATIONAL
            item['status'] = 'VERIFIED_FAIL' if failure else 'VERIFIED_PASS'
            observation = {'fixture_measurement': n, 'identity':identity}
            if identity == lab.PARTIAL_ID:
                observation = {
                    'atomic':{'qualification':'NOT_PROVEN','selection':lab.PARTIAL_ACCENT},
                    'legacy':{'authoredVia':'native-title-control',
                              'editorTitle':lab.PARTIAL_MARKUP},
                    'published':{'text':lab.PARTIAL_TEXT}
                }
            sha = hashlib.sha256(json.dumps(
                observation, separators=(',', ':'), ensure_ascii=False
            ).encode()).hexdigest()
            name = identity.replace(':','__')
            (receipts / (name+'.observation.json')).write_text(json.dumps({
                'state':'COMPLETE', 'identity':identity, 'sha256':sha,
                'value':observation
            }))
            (receipts / (name+'.assertion.json')).write_text(json.dumps({
                'state':'PRODUCT_FAIL' if failure else 'PRODUCT_PASS',
                'identity':identity,'observation_sha256':sha
            }))
            item['observed'] = {
                'assertion_origin':'EXPLICIT_PLAYWRIGHT_STEP',
                'qualified_step_count':1, 'qualified_step_failed':failure,
                'observation_state':'COMPLETE',
                'product_assertion_state':'PRODUCT_FAIL' if failure else 'PRODUCT_PASS',
                'observation_sha256':sha,
            }
            if identity == lab.CI_INFORMATIONAL:
                item['expected'] = {'minimum_normal_text_contrast_ratio':4.5}
                item['observed']['measured_css'] = {'contrast': ratio}
            step = {'title': lab.QUALIFIED_STEP_PREFIX + identity}
            attempt_errors = []
            attempt_detail = {}
            if failure:
                # Actual Playwright 1.58.2 JSON reporter shape: step.error
                # and attempt.error match; errors[0] includes a code frame
                # interpolated between the same error message and stack.
                location = {'file':'/lab/tests/native.spec.mjs',
                            'line':313, 'column':69}
                message = 'Error: measured AA contrast 1.9866 below 4.5'
                snippet = '> 313 | expect(contrast).toBeGreaterThanOrEqual(4.5);'
                stack = message + '\n    at assertProduct (/lab/tests/native.spec.mjs:313:69)'
                structured = {'message':message, 'stack':stack,
                              'location':location, 'snippet':snippet}
                step['error'] = structured
                attempt_errors = [{'location':location, 'message':
                                   message + '\n\n' + snippet + stack[len(message):]}]
                attempt_detail = {'error':structured, 'errorLocation':location}
            attempt = {
                'status':'failed' if failure else 'passed',
                'errors':attempt_errors, 'annotations':[], 'stderr':[],
                'retry':0, 'steps':[step], **attempt_detail
            }
            specs.append({'title':'['+identity+'] native scenario',
                          'file':'native.spec.mjs', 'ok': not failure,
                          'tests':[{'expectedStatus':'passed',
                                    'status':'unexpected' if failure else 'expected',
                                    'results':[attempt]}]})
        report = {'errors':[], 'suites':[{'specs':specs}],
                  'stats':{'expected':15 if contrast_fail else 16,
                           'unexpected':1 if contrast_fail else 0,
                           'skipped':0, 'flaky':0}}
        (root/'result.json').write_text(json.dumps(result))
        (root/'playwright.json').write_text(json.dumps(report))
        return p,head,result,report

    def test_ci_admission_summary_tracks_validated_roster_and_catalog_successors(self):
        """Unit-only successors; no synthetic runtime evidence is product proof."""
        import copy
        import os
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            p, head, baseline, report = self._build_ci_gate_fixture(root)
            env = {'EXPECTED_SOURCE_SHA': head, 'GITHUB_RUN_ID': 'ci-gate-test-run',
                   'GITHUB_RUN_ATTEMPT': '1'}
            base_catalog = lab.catalog()
            self.assertEqual(sum(len(d['scenarios']) for d in base_catalog['domains']), 28)
            self.assertEqual(sum(s['test'] is not None for d in base_catalog['domains']
                                 for s in d['scenarios']), 16)

            def validate(candidate, *, cat=None):
                # Source identities are fixed in this *unit fixture*. A real
                # successor must still pass exact-Head/source AST admission.
                effective_catalog = cat or lab.CAT
                with patch.object(lab, 'ART', root), patch.object(lab, 'CAT', effective_catalog), \
                        patch.object(lab, 'test_hash', return_value=baseline['test_sha256']), \
                        patch.dict(os.environ, env):
                    return lab.verify_ci_acceptance(
                        candidate, report, p, selected='all', lab_exit=2, expected=head
                    )

            base_summary = validate(baseline)
            self.assertEqual({k: base_summary[k] for k in
                              ('mandatory_verified', 'not_executed', 'pro_unavailable')},
                             {'mandatory_verified': 15, 'not_executed': 11,
                              'pro_unavailable': 1})
            # The persisted public admission JSON must agree with its source roster,
            # not merely the in-memory return value.
            with patch.object(lab, 'ART', root), patch.dict(os.environ, env), \
                    patch.object(lab, 'require_exact_source', return_value=head), \
                    patch.object(lab, 'validate_qualification_coverage',
                                 return_value={'unit-only': True}):
                self.assertEqual(lab.ci_acceptance_command(p, 'all', 2, head), 0)
            recorded = json.loads((root / 'ci-acceptance.json').read_text())
            self.assertEqual({k: recorded[k] for k in
                              ('mandatory_verified', 'not_executed', 'pro_unavailable')},
                             {k: base_summary[k] for k in
                              ('mandatory_verified', 'not_executed', 'pro_unavailable')})
            self.assertEqual(sum(s['status']=='NOT_EXECUTED' for s in baseline['scenarios']), 11)
            self.assertEqual(sum(s['status']=='PRO_OR_LICENSE_UNAVAILABLE'
                                 for s in baseline['scenarios']), 1)

            # The canonical roster, never manually maintained summary values,
            # must determine the counts after an admitted catalog successor.
            successor = copy.deepcopy(base_catalog)
            successor['domains'][-1]['scenarios'].extend([
                {'id': 'successor-unexecuted', 'test': None},
                {'id': 'successor-pro-only', 'test': None, 'requires_pro': True}
            ])
            successor_path = root / 'successor-catalog.json'
            successor_path.write_text(json.dumps(successor))
            extra = [
                {'capability': 'O', 'scenario': 'successor-unexecuted',
                 'test_identity': None, 'status': 'NOT_EXECUTED', 'observed': None},
                {'capability': 'O', 'scenario': 'successor-pro-only',
                 'test_identity': None, 'status': 'PRO_OR_LICENSE_UNAVAILABLE',
                 'observed': None}
            ]

            # A mutated catalog with the *old* evidence fingerprint is not a
            # legitimate successor and cannot be admitted.
            with self.assertRaisesRegex(ValueError, 'environment fingerprint'):
                validate(baseline, cat=successor_path)

            candidate = copy.deepcopy(baseline)
            installed = dict(candidate['installed'])
            installed.pop('atomic_editor_observed')
            with patch.object(lab, 'ART', root), patch.object(lab, 'CAT', successor_path), \
                    patch.object(lab, 'test_hash', return_value=baseline['test_sha256']), \
                    patch.dict(os.environ, env):
                for item in extra:
                    candidate['scenarios'].append(copy.deepcopy(item))
                candidate['environment_fingerprint'] = lab.digest({
                    'requested': p, 'installed': installed,
                    'test_sha256': candidate['test_sha256'],
                    'catalog_sha256': lab.digest(lab.CAT.read_bytes())
                })
                revised = lab.verify_ci_acceptance(
                    candidate, report, p, selected='all', lab_exit=2, expected=head)
                self.assertEqual((revised['mandatory_verified'], revised['not_executed'],
                                  revised['pro_unavailable']), (15, 12, 2))
                self.assertEqual(len(candidate['scenarios']), 30)

                mismatched = copy.deepcopy(candidate)
                mismatched['scenarios'][-1]['scenario'] = 'wrong-identity'
                with self.assertRaisesRegex(ValueError, 'roster identity'):
                    lab.verify_ci_acceptance(
                        mismatched, report, p, selected='all', lab_exit=2, expected=head)
                invalid = copy.deepcopy(candidate)
                invalid['scenarios'][-2]['status'] = 'VERIFIED_PASS'
                with self.assertRaisesRegex(ValueError, 'improperly promoted'):
                    lab.verify_ci_acceptance(
                        invalid, report, p, selected='all', lab_exit=2, expected=head)
                missing = copy.deepcopy(candidate)
                missing['scenarios'].pop()
                with self.assertRaisesRegex(ValueError, 'roster differs'):
                    lab.verify_ci_acceptance(
                        missing, report, p, selected='all', lab_exit=2, expected=head)

    def test_explicit_ci_gate_admits_only_complete_current_run_evidence(self):
        import copy
        import os
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            p,head,positive,report = self._build_ci_gate_fixture(root)
            env={'EXPECTED_SOURCE_SHA':head, 'GITHUB_RUN_ID':'ci-gate-test-run',
                 'GITHUB_RUN_ATTEMPT':'1'}
            with patch.object(lab,'ART',root), patch.dict(os.environ,env):
                verdict = lab.verify_ci_acceptance(
                    positive,report,p,selected='all',lab_exit=2,expected=head)
                self.assertEqual(verdict['ci_acceptance'],'PASS')
                self.assertEqual(verdict['product_execution'],'VERIFIED_FAIL')
                self.assertEqual(positive['execution'],'VERIFIED_FAIL')
                self.assertEqual(positive['scenarios'][22]['status'],'VERIFIED_FAIL')

                def rejected(result=None, playwright=None, **kwargs):
                    with self.assertRaises(ValueError):
                        lab.verify_ci_acceptance(
                            result if result is not None else copy.deepcopy(positive),
                            playwright if playwright is not None else copy.deepcopy(report),
                            p,selected=kwargs.get('selected','all'),
                            lab_exit=kwargs.get('lab_exit',2),
                            expected=kwargs.get('expected',head))

                # A different failing executable test can never be informational.
                altered = copy.deepcopy(positive)
                altered['scenarios'][0]['status'] = 'VERIFIED_FAIL'
                rejected(result=altered)
                altered = copy.deepcopy(positive)
                contrast = next(i for i in altered['scenarios']
                    if i['test_identity']==lab.CI_INFORMATIONAL)
                contrast['status'] = 'NOT_PROVEN'
                rejected(result=altered)
                altered = copy.deepcopy(positive)
                altered['teardown']='NOT_PROVEN: cleanup error'
                rejected(result=altered)
                altered = copy.deepcopy(positive)
                altered['setup_error']='WordPress provisioning failed'
                rejected(result=altered)
                altered = copy.deepcopy(positive)
                altered['fixture_storage_probe']['state']='MISMATCH'
                rejected(result=altered)
                altered = copy.deepcopy(positive)
                altered['fixture_storage_probe']['state']='UNAVAILABLE'
                rejected(result=altered)
                altered = copy.deepcopy(positive)
                altered['partial_heading_capability']['legacy']='NOT_PROVEN'
                rejected(result=altered)
                altered = copy.deepcopy(positive)
                altered['partial_heading_storage_probe']['state']='UNAVAILABLE'
                rejected(result=altered)
                altered = copy.deepcopy(positive)
                next(x for x in altered['scenarios']
                     if x['test_identity'] == lab.PARTIAL_ID)['status'] = 'NOT_PROVEN'
                rejected(result=altered)
                altered = copy.deepcopy(positive)
                altered['scenarios'][next(n for n,x in enumerate(altered['scenarios'])
                    if x['test_identity']==lab.PARTIAL_ID)]['status']='VERIFIED_FAIL'
                rejected(result=altered)
                altered = copy.deepcopy(positive)
                altered['partial_heading_post_id']='wrong'
                rejected(result=altered)
                altered = copy.deepcopy(positive)
                altered['installed']=None
                rejected(result=altered)
                altered = copy.deepcopy(positive)
                altered['provenance_verified']=False
                rejected(result=altered)
                altered = copy.deepcopy(positive)
                altered['source_contract_error']='AST mismatch'
                rejected(result=altered)
                altered = copy.deepcopy(positive)
                altered['test_sha256']='tampered'
                rejected(result=altered)
                altered = copy.deepcopy(positive)
                altered['github_run']='previous-ci-run'
                rejected(result=altered)
                altered = copy.deepcopy(positive)
                altered['actual_checkout_commit']='0'*40
                rejected(result=altered)
                altered = copy.deepcopy(positive)
                altered['scenarios'][1]['status']='VERIFIED_PASS'
                rejected(result=altered)
                altered = copy.deepcopy(report)
                altered['errors']=[{'message':'Unexpected failure'}]
                rejected(playwright=altered)
                altered = copy.deepcopy(report)
                altered['suites'][0]['specs'].pop()
                rejected(playwright=altered)
                altered = copy.deepcopy(report)
                altered['suites'][0]['specs'].append({
                    'title':'Unclassified failure', 'file':'nested.spec.mjs',
                    'tests':[{'status':'unexpected', 'results':[{'status':'failed'}]}]})
                rejected(playwright=altered)
                altered = copy.deepcopy(report)
                altered['stats']['unexpected'] = 2
                rejected(playwright=altered)
                altered = copy.deepcopy(report)
                altered['suites'][0]['specs'][0]['tests'][0]['results'][0]['status']='failed'
                rejected(playwright=altered)
                rejected(selected='C')
                rejected(expected='0'*40)
                rejected(lab_exit=1)
                (root/'native-storage-sample.json').write_text('{"malformed":true}')
                rejected()
                self.assertEqual(positive['execution'],'VERIFIED_FAIL')

    def test_error_attribution_excludes_all_independent_reporter_failures(self):
        """Playwright 1.58.2 structured attempt/step error attribution.

        These mutations were admitted by the previous bool(errors) check;
        no product/source/receipt metadata is otherwise modified.
        """
        import copy
        import os
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            p,head,product,report = self._build_ci_gate_fixture(root)
            environment = {
                'EXPECTED_SOURCE_SHA':head, 'GITHUB_RUN_ID':'ci-gate-test-run',
                'GITHUB_RUN_ATTEMPT':'1',
            }
            def contrast_case(payload):
                return next(spec for spec in payload['suites'][0]['specs']
                            if spec['title'].startswith('[L:contrast-aa-default-button]'))
            def independent_error():
                return {'message':'Error: unrelated failure from teardown',
                        'location':{'file':'/lab/tests/native.spec.mjs',
                                    'line':400, 'column':1}}
            with patch.object(lab,'ART',root), patch.dict(os.environ,environment):
                self.assertEqual(lab.verify_ci_acceptance(
                    product,report,p,selected='all',lab_exit=2,expected=head
                )['ci_acceptance'],'PASS')
                def rejected(name, mutation):
                    changed=copy.deepcopy(report)
                    spec=contrast_case(changed)
                    attempt=spec['tests'][0]['results'][0]
                    step=attempt['steps'][0]
                    mutation(changed,spec,attempt,step)
                    with self.subTest(name=name):
                        with self.assertRaisesRegex(ValueError,
                                'failure|Playwright|Browser|mismatch|unclassified'):
                            lab.verify_ci_acceptance(
                                copy.deepcopy(product), changed, p, selected='all',
                                lab_exit=2,expected=head)
                cases = {
                    'second_independent_attempt_error':
                        lambda r,s,a,st:a['errors'].append(independent_error()),
                    'independent_top_level_attempt_error':
                        lambda r,s,a,st:a.update(error=independent_error()),
                    'additional_failed_after_hook':
                        lambda r,s,a,st:a['steps'].append({
                            'title':'After Hooks','error':independent_error()}),
                    'additional_failed_before_hook':
                        lambda r,s,a,st:a['steps'].insert(0,{
                            'title':'Before Hooks','error':independent_error()}),
                    'nested_teardown_failure':
                        lambda r,s,a,st:st.update(steps=[{
                            'title':'Fixture cleanup','error':independent_error()}]),
                    'missing_authorized_product_error':
                        lambda r,s,a,st:st.pop('error'),
                    'altered_authorized_product_error':
                        lambda r,s,a,st:st['error'].update(location={
                            'file':'/lab/tests/native.spec.mjs','line':412,'column':1}),
                    'corrupt_attempt_reported_error':
                        lambda r,s,a,st:a['errors'][0].update(message='Other error'),
                    'corrupt_source_frame':
                        lambda r,s,a,st:a['errors'][0].update(
                            message=a['errors'][0]['message']+'\nAnother hidden error'),
                    'missing_attempt_error':
                        lambda r,s,a,st:a.pop('error'),
                    'missing_attempt_error_location':
                        lambda r,s,a,st:a.pop('errorLocation'),
                    'unrelated_attempt_location':
                        lambda r,s,a,st:a.update(errorLocation=independent_error()['location']),
                    'ambiguous_error_array':
                        lambda r,s,a,st:a.update(errors=[a['errors'][0],a['errors'][0]]),
                    'unsupported_error_record_shape':
                        lambda r,s,a,st:a['errors'][0].update(extra='unknown error source'),
                    'unclassified_spec_error':
                        lambda r,s,a,st:s.update(errors=[independent_error()]),
                    'unclassified_suite_error':
                        lambda r,s,a,st:r['suites'][0].update(errors=[independent_error()]),
                    'unclassified_record_error':
                        lambda r,s,a,st:s['tests'][0].update(error=independent_error()),
                    'unexpected_spec_ok':
                        lambda r,s,a,st:s.update(ok=True),
                    'unexpected_reporter_annotation':
                        lambda r,s,a,st:a.update(annotations=[{'type':'fail'}]),
                    'unexpected_stderr':
                        lambda r,s,a,st:a.update(stderr=[{'text':'Unclassified failure'}]),
                }
                for name,mutation in cases.items():
                    rejected(name,mutation)
                # A clean product PASS with an extraneous hook failure must
                # also be blocked (not only the informational contrast case).
                altered=copy.deepcopy(report)
                clean=altered['suites'][0]['specs'][0]
                clean['tests'][0]['results'][0]['steps'].append({
                    'title':'After Hooks','error':independent_error()})
                with self.assertRaises(ValueError):
                    lab.verify_ci_acceptance(product,altered,p,
                        selected='all',lab_exit=2,expected=head)

    def test_ci_gate_command_rejects_missing_browser_report_and_untrusted_source(self):
        import os
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            p,head,result,report=self._build_ci_gate_fixture(root)
            env={'EXPECTED_SOURCE_SHA':head, 'GITHUB_RUN_ID':'ci-gate-test-run',
                 'GITHUB_RUN_ATTEMPT':'1'}
            with patch.object(lab,'ART',root),patch.dict(os.environ,env):
                with patch.object(lab,'require_exact_source',return_value=head), \
                     patch.object(lab,'validate_qualification_coverage',return_value={}):
                    before=(root/'result.json').read_bytes()
                    self.assertEqual(lab.ci_acceptance_command(p,'all',2,head),0)
                    self.assertEqual((root/'result.json').read_bytes(),before)
                    self.assertEqual(json.loads((root/'ci-acceptance.json').read_text())
                                     ['ci_acceptance'],'PASS')
                    (root/'playwright.json').unlink()
                    self.assertEqual(lab.ci_acceptance_command(p,'all',2,head),2)
                    self.assertEqual(json.loads((root/'ci-acceptance.json').read_text())
                                     ['ci_acceptance'],'FAIL')
                    (root/'playwright.json').write_text('{not json')
                    self.assertEqual(lab.ci_acceptance_command(p,'all',2,head),2)
                    (root/'playwright.json').write_text(json.dumps(report))
                with patch.object(lab,'require_exact_source',
                                  side_effect=RuntimeError('Dirty tracked source')):
                    self.assertEqual(lab.ci_acceptance_command(p,'all',2,head),2)
                with patch.object(lab,'require_exact_source',return_value=head), \
                     patch.object(lab,'validate_qualification_coverage',
                                  side_effect=ValueError('Invalid predicate AST')):
                    self.assertEqual(lab.ci_acceptance_command(p,'all',2,head),2)
                self.assertEqual((root/'result.json').read_bytes(),before)

    def test_ci_acceptance_can_admit_contrast_pass_without_a_full_catalog_pass(self):
        import os
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            p,head,result,report=self._build_ci_gate_fixture(root,contrast_fail=False)
            with patch.object(lab,'ART',root),patch.dict(os.environ,{
                'EXPECTED_SOURCE_SHA':head,'GITHUB_RUN_ID':'ci-gate-test-run',
                'GITHUB_RUN_ATTEMPT':'1'
            }):
                verdict=lab.verify_ci_acceptance(
                    result,report,p,selected='all',lab_exit=2,expected=head)
                self.assertEqual(verdict['ci_acceptance'],'PASS')
                self.assertEqual(result['execution'],'INCOMPLETE')

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
