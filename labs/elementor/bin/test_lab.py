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
                self.assertEqual(len(lab.validate_qualification_coverage()), 15)

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
            with patch.object(lab,'ROOT',root):
                for before,after in changes:
                    self.assertIn(before,original)
                    (root/'tests/native.spec.mjs').write_text(original.replace(before,after,1))
                    with self.subTest(before=before):
                        with self.assertRaisesRegex(ValueError,'Structural source qualification failed'):
                            lab.validate_qualification_coverage()
                (root/'tests/native.spec.mjs').write_text(original)
                self.assertEqual(len(lab.validate_qualification_coverage()),15)
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
                self.assertEqual(len(lab.validate_qualification_coverage()), 15)
                helper = root / 'tests/helpers.mjs'
                helper.write_text(helper.read_text().replace(
                    'return {root,ids};',
                    'return {root,ids:{...ids,atomic:"fake123"}};'
                ))
                with self.assertRaisesRegex(
                    ValueError, 'Structural source qualification failed'
                ):
                    lab.validate_qualification_coverage()

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
            with patch.object(lab, 'ROOT', root):
                path.write_text(original)
                self.assertEqual(len(lab.validate_qualification_coverage()), 15)
                path.write_text(harmless)
                self.assertEqual(len(lab.validate_qualification_coverage()), 15)
                for name, mutation in mutations.items():
                    with self.subTest(name=name):
                        path.write_text(mutation)
                        with self.assertRaisesRegex(
                            ValueError, 'Structural source qualification failed'
                        ):
                            lab.validate_qualification_coverage()

    def test_native_atomic_container_topology_is_unique_and_direct(self):
        """Exercise production parser; browser and storage states are separate."""
        ids = {'atomic': '2eb52f4', 'container': '5509617'}
        expected_title = {'$type': 'escaped-html', 'value': 'EV4 Atomic Heading'}
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
                    '$type': 'html', 'value': 'EV4 Atomic Heading'}}}])], 'UNSUPPORTED'),
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
