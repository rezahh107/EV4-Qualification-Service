#!/usr/bin/env python3
"""Isolated released-Elementor qualification. Never convert unavailable to PASS."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import time
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / 'artifacts'
CAT = ROOT / 'catalog.json'
DOMAINS = 'ABCDEFGHIJKLMNO'
FIXTURE_DEPENDENTS = frozenset('ABCDEIKLN')
COMMIT_SHA = re.compile(r'[0-9a-f]{40}\Z')
QUALIFIED_STEP_PREFIX = 'EV4_PRODUCT_ASSERTION:'


def digest(obj):
    if isinstance(obj, bytes):
        data = obj
    else:
        data = json.dumps(obj, sort_keys=True, separators=(',', ':')).encode()
    return hashlib.sha256(data).hexdigest()



def actual_git_checkout(root=ROOT):
    """Read the checked-out Git commit, never a GitHub context or tree digest."""
    completed = subprocess.run(
        ['git', 'rev-parse', '--verify', 'HEAD^{commit}'],
        cwd=root, text=True, capture_output=True, check=False,
    )
    if completed.returncode or not COMMIT_SHA.fullmatch(completed.stdout.strip()):
        raise RuntimeError('Actual Git checkout identity unavailable')
    return completed.stdout.strip()


def require_exact_checkout(expected, observed):
    if not isinstance(expected, str) or not COMMIT_SHA.fullmatch(expected):
        raise RuntimeError('Expected immutable source Head is absent or invalid')
    if observed != expected:
        raise RuntimeError('Git checkout does not match expected exact Head: '
                           + str(observed) + ' != ' + expected)
    return observed


def require_clean_source_tree(root=ROOT):
    """Compare actual checkout bytes with HEAD blobs, independently of Git index."""
    root = Path(root).resolve()

    def git_bytes(*args):
        try:
            proc = subprocess.run(['git', *args], cwd=root, capture_output=True,
                                  check=False)
        except OSError as exc:
            raise RuntimeError('Git source-integrity inspection unavailable') from exc
        if proc.returncode:
            raise RuntimeError('Git source-integrity inspection failed: '
                               + proc.stderr.decode('utf-8', errors='replace')[-400:])
        return proc.stdout

    repo = Path(os.fsdecode(git_bytes('rev-parse', '--show-toplevel').strip())).resolve()
    if not root.is_relative_to(repo):
        raise RuntimeError('Qualification source is outside Git checkout')
    object_format = git_bytes('rev-parse', '--show-object-format').strip().decode('ascii')
    if object_format not in ('sha1', 'sha256'):
        raise RuntimeError('Unsupported Git object format: ' + object_format)
    entries = git_bytes('ls-tree', '-r', '-z', '--full-tree', 'HEAD').split(b'\0')
    checked = 0
    for entry in entries:
        if not entry:
            continue
        try:
            metadata, raw_name = entry.split(b'\t', 1)
            mode, object_type, expected_blob = metadata.split(b' ')
        except ValueError as exc:
            raise RuntimeError('Unrecognized tracked Git tree entry') from exc
        name = os.fsdecode(raw_name)
        source = repo / name
        if object_type != b'blob' or mode not in (b'100644', b'100755'):
            raise RuntimeError('Unsupported tracked source representation: ' + repr(name))
        try:
            current = source.lstat()
            if not stat.S_ISREG(current.st_mode):
                raise RuntimeError('Tracked source is not a regular file: ' + repr(name))
            payload = source.read_bytes()
        except OSError as exc:
            raise RuntimeError('Tracked source cannot be read: ' + repr(name)) from exc
        actual = hashlib.new(object_format, b'blob ' + str(len(payload)).encode('ascii')
                             + b'\0' + payload).hexdigest().encode('ascii')
        if actual != expected_blob:
            raise RuntimeError('Tracked working-tree source differs from HEAD: ' + repr(name))
        checked += 1
    if not checked:
        raise RuntimeError('No tracked source files qualified against HEAD')

    untracked = git_bytes('ls-files', '--others', '--exclude-standard', '-z', '--')
    if untracked:
        offender = os.fsdecode(untracked.split(b'\0', 1)[0])
        raise RuntimeError('Unreviewed untracked source in working tree: ' + repr(offender))


def require_exact_source(expected, root=ROOT):
    """Single authoritative checkout + actual-byte provenance admission."""
    observed = actual_git_checkout(root)
    require_exact_checkout(expected, observed)
    require_clean_source_tree(root)
    return observed


def profile(path):
    path = path.resolve()
    if not path.is_relative_to((ROOT / 'profiles').resolve()):
        raise ValueError('Only repository profiles/ files are allowed')
    p = json.loads(path.read_text())
    if set(p) != {'id', 'wordpress', 'php', 'mariadb', 'elementor', 'theme', 'plugins', 'features', 'breakpoints', 'scope'}:
        raise ValueError('Unexpected profile shape')
    for key in ('wordpress', 'php', 'mariadb', 'elementor'):
        if not re.fullmatch(r'\d+(?:\.\d+){1,3}', p[key]):
            raise ValueError('Unpinned version: ' + key)
    if p['theme']['slug'] != 'hello-elementor' or not re.fullmatch(r'\d+\.\d+\.\d+', p['theme']['version']):
        raise ValueError('Unknown theme build')
    if p['plugins'] or p['features'] != {'atomic_editor': 'released-default-not-assumed-verified'}:
        raise ValueError('No unverified plugin/experiment inputs in core profile')
    if not all(type(w) is int and 240 <= w <= 4000 for w in p['breakpoints']):
        raise ValueError('Invalid breakpoints')
    if p['scope'] != 'GENERAL_LAB_VERIFIED':
        raise ValueError('Invalid claim scope')
    return p


def catalog():
    c = json.loads(CAT.read_text())
    ds = c['domains']
    if c['schema_version'] != 1 or len(ds) != 15 or set(d['id'] for d in ds) != set(DOMAINS):
        raise ValueError('A-O coverage catalog invalid')
    ids = []
    for domain in ds:
        for scenario in domain['scenarios']:
            key = domain['id'] + ':' + scenario['id']
            if scenario['test'] not in (None, key):
                raise ValueError('Test identity mismatch: ' + key)
            ids.append(key)
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate scenario')
    return c


def wp_env_profile(p):
    return {'$schema': 'https://schemas.wp.org/trunk/wp-env.json',
            'core': 'https://wordpress.org/wordpress-' + p['wordpress'] + '.zip',
            'phpVersion': p['php'], 'mariadbVersion': p['mariadb'],
            'plugins': ['https://downloads.wordpress.org/plugin/elementor.' + p['elementor'] + '.zip'],
            'themes': ['https://downloads.wordpress.org/theme/hello-elementor.' + p['theme']['version'] + '.zip'],
            'config': {'WP_DEBUG': False, 'SCRIPT_DEBUG': False, 'WP_AUTO_UPDATE_CORE': False,
                       'AUTOMATIC_UPDATER_DISABLED': True}}


def test_hash():
    paths = [ROOT / 'bin/lab.py', ROOT / 'bin/validate-source.mjs',
             ROOT / 'bin/origin-contract.spec.mjs', ROOT / 'bin/origin-playwright.config.mjs',
             ROOT / 'predicate-contract.json', ROOT / 'playwright.config.mjs',
             ROOT / 'package.json', CAT,
             *sorted(p for p in (ROOT / 'tests').rglob('*') if p.is_file() or p.is_symlink())]
    if any(p.is_symlink() for p in paths):
        raise ValueError('Symlinked test source cannot be fingerprinted')
    return digest(b''.join(
        p.relative_to(ROOT).as_posix().encode() + b'\0' + p.read_bytes()
        for p in paths
    ))


def binary(name):
    path = ROOT / 'node_modules' / '.bin' / (name + ('.cmd' if os.name == 'nt' else ''))
    if not path.is_file():
        raise RuntimeError('Missing test tooling: ' + str(path))
    return str(path)


def command(argv, *, env=None, timeout=300, allow_fail=False):
    p = subprocess.run(argv, cwd=ROOT, env=env, capture_output=True, text=True, timeout=timeout)
    if p.returncode and not allow_fail:
        raise RuntimeError('Command exited ' + str(p.returncode) + ': ' + ' '.join(argv[:5]) + '\n' + p.stderr[-700:] + p.stdout[-300:])
    return p


def wp(*args):
    return command([binary('wp-env'), 'run', 'cli', 'wp', *args]).stdout


def single_version(text):
    values = [s.strip() for s in text.splitlines() if re.fullmatch(r'\d+\.\d+(?:\.\d+){0,2}(?:[-+][\w.-]+)?', s.strip())]
    if len(values) != 1:
        raise RuntimeError('Cannot prove exactly one installed software version')
    return values[0]


def runtime(p):
    wp('theme', 'activate', 'hello-elementor')
    actual = {'wordpress': single_version(wp('core', 'version')),
              'elementor': single_version(wp('plugin', 'get', 'elementor', '--field=version')),
              'theme': single_version(wp('theme', 'get', 'hello-elementor', '--field=version')),
              'php': single_version(wp('eval', 'echo PHP_VERSION;'))}
    db = wp('db', 'query', 'SELECT VERSION();', '--skip-column-names')
    match = re.search(r'\b(\d+\.\d+\.\d+)-MariaDB', db)
    if not match:
        raise RuntimeError('Cannot prove MariaDB runtime version')
    actual['mariadb'] = match.group(1)
    actual['atomic_editor_option'] = command([binary('wp-env'), 'run', 'cli', 'wp', 'option', 'get',
                                                'elementor_experiment-e_atomic_elements'], allow_fail=True).stdout.strip()[:100]
    for key, expected in (('wordpress', p['wordpress']), ('elementor', p['elementor']),
                          ('theme', p['theme']['version'])):
        if actual[key] != expected:
            raise RuntimeError('Wrong ' + key + ': ' + actual[key] + ' vs ' + expected)
    for key in ('php', 'mariadb'):
        if not actual[key].startswith(p[key] + '.'):
            raise RuntimeError('Wrong ' + key + ' family: ' + actual[key])
    return actual


def template(p, selected):
    scenarios = []
    for domain in catalog()['domains']:
        if selected not in ('all', domain['id']) and not (
            selected in FIXTURE_DEPENDENTS and domain['id'] == 'M'
        ):
            continue
        for s in domain['scenarios']:
            scenarios.append({'capability': domain['id'], 'scenario': s['id'],
                              'test_identity': s['test'],
                              'status': 'PRO_OR_LICENSE_UNAVAILABLE' if s.get('requires_pro') else 'NOT_EXECUTED',
                              'observed': None})
    return {'schema_version': 1, 'requested': p, 'profile_sha256': digest(p), 'test_sha256': test_hash(),
            'source_commit': os.getenv('EXPECTED_SOURCE_SHA') or os.getenv('SOURCE_SHA') or 'UNBOUND',
            'checkout_commit': None, 'actual_checkout_commit': None,
            'expected_source_commit': os.getenv('EXPECTED_SOURCE_SHA'),
            'provenance_verified': False,
            'github_run': os.getenv('GITHUB_RUN_ID'),
            'github_attempt': os.getenv('GITHUB_RUN_ATTEMPT'), 'scope': p['scope'],
            'installed': None, 'environment_fingerprint': None, 'execution': 'NOT_EXECUTED',
            'setup_error': None, 'teardown': 'NOT_EXECUTED', 'scenarios': scenarios}




def validate_qualification_coverage():
    """Use pinned executable-AST source contract, never raw marker substrings."""
    expected = sorted(x['test'] for domain in catalog()['domains']
                      for x in domain['scenarios'] if x['test'])
    script = Path(__file__).resolve().parent / 'validate-source.mjs'
    try:
        run = subprocess.run(
            ['node', str(script), str(ROOT), json.dumps(expected)],
            cwd=ROOT, capture_output=True, text=True, check=False,
        )
    except OSError as exc:
        raise ValueError('Structural source parser unavailable') from exc
    if run.returncode:
        raise ValueError('Structural source qualification failed: ' + run.stderr[-1500:])
    try:
        accepted = json.loads(run.stdout)['qualified']
    except (ValueError, KeyError, TypeError) as exc:
        raise ValueError('Structural qualification output invalid') from exc
    if accepted != expected:
        raise ValueError('Parser-qualified declarations differ from catalog')
    # Temporary qualification instrumentation: bind the accepted predicate AST
    # representation before locking the reviewed manifest at the next Head.
    if 'predicate_fingerprints' in json.loads(run.stdout):
        ART.mkdir(parents=True, exist_ok=True)
        (ART / 'predicate-fingerprints-observed.json').write_text(
            json.dumps(json.loads(run.stdout)['predicate_fingerprints'],
                       sort_keys=True, indent=2) + '\n')
    return {item: True for item in accepted}


def qualified_steps(steps):
    """Collect every reserved step, including duplicates and mismatched identities."""
    matched = []
    for step in steps:
        if not isinstance(step, dict):
            continue
        title = step.get('title')
        if isinstance(title, str) and title.startswith(QUALIFIED_STEP_PREFIX):
            matched.append(step)
        matched.extend(qualified_steps(step.get('steps', [])))
    return matched


def read_qualification_receipts(identity):
    """Independent structured proof from the same authorized acquisition/step."""
    name = identity.replace(':', '__')
    directory = ART / 'observation-provenance'
    try:
        observation = json.loads((directory / (name + '.observation.json')).read_text())
        assertion = json.loads((directory / (name + '.assertion.json')).read_text())
    except (OSError, ValueError, TypeError):
        return {'observation_state': 'NOT_PROVEN', 'assertion_state': 'NOT_PROVEN'}
    try:
        serialized = json.dumps(observation['value'], separators=(',', ':'), ensure_ascii=False)
        # JS JSON.stringify uses insertion-order keys and compact separators.
        sha = hashlib.sha256(serialized.encode()).hexdigest()
        valid = (observation.get('state') == 'COMPLETE' and
                 observation.get('identity') == identity and
                 re.fullmatch(r'[0-9a-f]{64}', observation['sha256']) and
                 sha == observation['sha256'] and
                 assertion.get('identity') == identity and
                 assertion.get('observation_sha256') == sha)
        return {'observation_state': 'COMPLETE' if valid else 'NOT_PROVEN',
                'assertion_state': assertion.get('state') if valid else 'NOT_PROVEN',
                'observation_sha256': sha if valid else None}
    except (KeyError, TypeError, ValueError):
        return {'observation_state': 'NOT_PROVEN', 'assertion_state': 'NOT_PROVEN'}


def classify_playwright(report, result):
    """Require validated executable origin plus a single matching runtime step."""
    try:
        authorized = validate_qualification_coverage()
    except (ValueError, OSError) as exc:
        result['source_contract_error'] = str(exc)[:1500]
        for scenario in result['scenarios']:
            if scenario['test_identity']:
                scenario['status'] = 'NOT_PROVEN'
        return 0
    observed = {}
    def visit(suite):
        for spec in suite.get('specs', []):
            match = re.match(r'^\[([A-O]):([a-z0-9-]+)\]', spec.get('title', ''))
            if not match:
                continue
            identity = match.group(1) + ':' + match.group(2)
            if identity in observed:
                raise ValueError('Duplicate Playwright scenario result: ' + identity)
            test_records = spec.get('tests', [])
            if len(test_records) != 1:
                raise ValueError('Ambiguous Playwright result cardinality: ' + identity)
            attempts = test_records[0].get('results', [])
            final = attempts[-1] if attempts else {}
            browser_state = final.get('status', 'skipped')
            reserved = qualified_steps(final.get('steps', []))
            matches = (len(reserved) == 1
                       and reserved[0].get('title') == QUALIFIED_STEP_PREFIX + identity
                       and identity in authorized)
            marker = reserved[0] if matches else None
            marker_failure = bool(marker and marker.get('error'))
            proof = read_qualification_receipts(identity)
            proof_complete = proof['observation_state'] == 'COMPLETE'
            if (browser_state == 'passed' and matches and not marker_failure and
                    proof_complete and proof['assertion_state'] == 'PRODUCT_PASS'):
                status = 'VERIFIED_PASS'
            elif (browser_state in ('failed', 'timedOut') and matches and marker_failure and
                  proof_complete and proof['assertion_state'] == 'PRODUCT_FAIL'):
                status = 'VERIFIED_FAIL'
            elif browser_state == 'skipped' and not reserved:
                status = 'NOT_EXECUTED'
            else:
                status = 'NOT_PROVEN'
            observed[identity] = (status, {
                'assertion_origin': 'EXPLICIT_PLAYWRIGHT_STEP' if matches else 'UNCLASSIFIED',
                'qualified_step_count': len(reserved),
                'qualified_step_failed': marker_failure,
                'browser_state': browser_state,
                'observation_state': proof['observation_state'],
                'product_assertion_state': proof['assertion_state'],
                'observation_sha256': proof.get('observation_sha256'),
                'errors': [str(e.get('message',''))[:900] for e in final.get('errors', [])
                           if isinstance(e, dict)][:2]})
        for child in suite.get('suites', []):
            visit(child)
    try:
        for suite in report.get('suites', []):
            visit(suite)
    except (ValueError, TypeError) as exc:
        result['assertion_origin_error'] = str(exc)[:1500]
        for item in result['scenarios']:
            if item['test_identity']:
                item['status'] = 'NOT_PROVEN'
        return 0
    for item in result['scenarios']:
        if item['test_identity'] in observed:
            status, evidence = observed[item['test_identity']]
            item.update(status=status, observed=evidence)
    return len(observed)


def _inspect_atomic_document(raw, fixture_ids):
    """Pinned Elementor 4.3.5 native V4 title format observed on installed lab."""
    try:
        document = json.loads(raw)
    except (TypeError, ValueError):
        return {'state': 'MISMATCH', 'reason': 'Malformed JSON persisted'}
    if not isinstance(document, list):
        return {'state': 'MISMATCH', 'reason': 'Elementor document must be a node list'}
    atomic_id = fixture_ids.get('atomic')
    container_id = fixture_ids.get('container')
    if not all(isinstance(x, str) and re.fullmatch(r'[a-zA-Z0-9]{7,12}', x)
               for x in (atomic_id, container_id)):
        return {'state': 'UNSUPPORTED', 'reason': 'Generated element identity is unavailable'}
    matching = []
    containers = []
    def visit(nodes, parent=None):
        for node in nodes:
            if not isinstance(node, dict) or not isinstance(node.get('id'), str):
                raise ValueError('Malformed Elementor document node')
            if node['id'] == atomic_id:
                matching.append((node, parent))
            if node['id'] == container_id:
                containers.append(node)
            children = node.get('elements', [])
            if not isinstance(children, list):
                raise ValueError('Malformed Elementor children')
            visit(children, node)
    try:
        visit(document)
    except (ValueError, RecursionError):
        return {'state': 'MISMATCH', 'reason': 'Malformed nested Elementor element structure'}
    if len(matching) != 1:
        return {'state': 'MISMATCH', 'reason': 'Missing or ambiguous generated Atomic Heading ID'}
    if len(containers) != 1:
        return {'state': 'MISMATCH', 'reason': 'Generated container ID missing or duplicated'}
    container = containers[0]
    node, parent = matching[0]
    if (container.get('elType') != 'container' or parent is not container or
            node.get('elType') != 'widget' or
            node.get('widgetType') != 'e-heading'):
        return {'state': 'MISMATCH', 'reason': 'Incorrect native heading type or parent'}
    settings = node.get('settings')
    if not isinstance(settings, dict):
        return {'state': 'MISMATCH', 'reason': 'Native heading settings unavailable'}
    title = settings.get('title')
    # Exact actual observed Elementor Core 4.3.5 representation:
    # {"$$type":"escaped-html","value":"EV4 Atomic Heading"}
    if not isinstance(title, dict) or title.get('$$type') != 'escaped-html':
        return {'state': 'UNSUPPORTED', 'reason': 'Unqualified title storage representation'}
    if not isinstance(title.get('value'), str):
        return {'state': 'MISMATCH', 'reason': 'Malformed native title value'}
    if title['value'] != 'EV4 Atomic Heading':
        return {'state': 'MISMATCH', 'reason': 'Native title content differs'}
    return {'state': 'VERIFIED', 'atomic_data': True,
            'generated_atomic_id': atomic_id, 'generated_container_id': container_id,
            'title_type': 'escaped-html'}


def probe_wordpress_persistence(post_id, fetch=wp):
    """Transport, representation and persisted mismatch are distinct outcomes."""
    try:
        ids_path = ART / 'element-ids.json'
        ids = json.loads(ids_path.read_text())
        if not isinstance(ids, dict):
            raise ValueError('Missing native element identity')
    except (OSError, ValueError, TypeError) as exc:
        return {'state': 'UNAVAILABLE', 'reason': 'Generated fixture identity not available',
                'error': str(exc)[:400]}
    try:
        meta = fetch('post', 'meta', 'get', post_id, '_elementor_data')
        published = fetch('post', 'get', post_id, '--field=post_status')
    except (RuntimeError, OSError, subprocess.TimeoutExpired) as exc:
        return {'state': 'UNAVAILABLE', 'error': str(exc)[:800]}
    ART.mkdir(parents=True, exist_ok=True)
    (ART / 'native-storage-sample.json').write_text(json.dumps({
        'fixture_post_id': post_id, 'generated_element_ids': ids,
        'raw_elementor_data': meta.strip(), 'post_status': published.strip(),
    }, ensure_ascii=False, indent=2) + '\n')
    proof = _inspect_atomic_document(meta.strip(), ids)
    proof['published'] = published.strip() == 'publish'
    if proof['state'] == 'VERIFIED' and not proof['published']:
        proof.update(state='MISMATCH', reason='Post is not published')
    return proof


def finalize_fixture_evidence(result, storage):
    """Authoritative final prerequisite state, then reconcile all dependents."""
    fixture = next((s for s in result['scenarios']
                    if s['test_identity'] == 'M:native-editor-create-reopen'), None)
    if fixture is None:
        return
    browser_state = fixture['status']
    if browser_state == 'VERIFIED_PASS':
        state = storage.get('state', 'UNAVAILABLE')
        if state == 'VERIFIED':
            result['elementor_storage'] = 'Verified native _elementor_data and publication'
            if result['installed'] is not None:
                result['installed']['atomic_editor_observed'] = True
        else:
            fixture['status'] = 'VERIFIED_FAIL' if state == 'MISMATCH' else 'NOT_PROVEN'
            fixture['observed'] = {
                'browser_observation': fixture['observed'],
                'browser_status': browser_state,
                'storage_probe': storage,
            }
    if fixture['status'] != 'VERIFIED_PASS':
        result.pop('elementor_storage', None)
        if result['installed'] is not None:
            result['installed'].pop('atomic_editor_observed', None)
        for item in result['scenarios']:
            if item['capability'] not in FIXTURE_DEPENDENTS:
                continue
            if item['status'] in ('VERIFIED_PASS', 'VERIFIED_FAIL'):
                item['observed'] = {
                    'precondition': 'Finalized native Elementor fixture is not VERIFIED_PASS',
                    'fixture_status': fixture['status'],
                    'browser_status': item['status'],
                    'browser_observation': item['observed'],
                }
                item['status'] = 'NOT_PROVEN'
                item.pop('expected', None)


def finish(result):
    statuses = [s['status'] for s in result['scenarios']]
    if result.get('source_contract_error') or result.get('assertion_origin_error'):
        result['execution'] = 'NOT_PROVEN'
    elif not result['provenance_verified']:
        result['execution'] = 'NOT_PROVEN'
    elif result['installed'] is None:
        result['execution'] = 'ENVIRONMENT_UNAVAILABLE'
    elif 'ENVIRONMENT_UNAVAILABLE' in statuses:
        result['execution'] = 'ENVIRONMENT_UNAVAILABLE'
    elif 'VERIFIED_FAIL' in statuses:
        result['execution'] = 'VERIFIED_FAIL'
    elif result['teardown'] != 'VERIFIED' or result['setup_error'] or any(s != 'VERIFIED_PASS' for s in statuses):
        result['execution'] = 'INCOMPLETE'
    else:
        result['execution'] = 'VERIFIED_PASS'
    ART.mkdir(parents=True, exist_ok=True)
    (ART / 'result.json').write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
    md = ['# Elementor Lab Evidence', '', 'Execution: ' + result['execution'],
          'Environment fingerprint: ' + str(result['environment_fingerprint']), '',
          '| Domain | Scenario | State |', '|---|---|---|']
    md += ['| ' + s['capability'] + ' | ' + s['scenario'] + ' | ' + s['status'] + ' |'
           for s in result['scenarios']]
    md += ['', 'Scenario PASS does not establish full-domain, site, or WCAG qualification.']
    (ART / 'summary.md').write_text('\n'.join(md) + '\n')
    print('LAB_EXECUTION: ' + result['execution'])
    if result['setup_error']:
        print('LAB_ERROR: ' + result['setup_error'])
    for item in result['scenarios']:
        print(item['capability'] + ':' + item['scenario'] + ' = ' + item['status'])


def execute(p, selected):
    r = template(p, selected)
    # A previous run's Playwright JSON must NEVER qualify a new execution.
    if ART.is_symlink():
        raise ValueError('Refusing symlinked artifact directory')
    if ART.exists():
        shutil.rmtree(ART)
    ART.mkdir(parents=True, exist_ok=True)
    try:
        observed_head = actual_git_checkout()
        r['checkout_commit'] = observed_head
        r['actual_checkout_commit'] = observed_head
        require_exact_checkout(os.getenv('EXPECTED_SOURCE_SHA'), observed_head)
        require_exact_source(os.getenv('EXPECTED_SOURCE_SHA'))
        validate_qualification_coverage()
        r['provenance_verified'] = True
    except (RuntimeError, OSError) as exc:
        r['setup_error'] = str(exc)
        r['provenance_error'] = str(exc)
        for item in r['scenarios']:
            if item['test_identity']:
                item['status'] = 'NOT_PROVEN'
        r['teardown'] = 'NOT_STARTED'
        finish(r)
        return 2
    (ROOT / '.wp-env.json').write_text(json.dumps(wp_env_profile(p), indent=2) + '\n')
    env = os.environ.copy()
    env.update(WP_ENV_HOME=str((ROOT / '.lab-state' / 'wp-env').resolve()), WP_ENV_PORT='8888',
               LAB_BASE_URL='http://localhost:8888', LAB_BREAKPOINTS=json.dumps(p['breakpoints']))
    started = False
    stage = 'provisioning'
    try:
        command([binary('wp-env'), 'start'], env=env, timeout=900)
        started = True
        os.environ.update({k: env[k] for k in ('WP_ENV_HOME', 'WP_ENV_PORT')})
        stage = 'provisioning'
        r['installed'] = runtime(p)
        for attempt in range(40):
            try:
                with urlopen('http://localhost:8888/wp-login.php', timeout=3) as response:
                    if response.status == 200:
                        break
            except Exception:
                time.sleep(2)
        else:
            raise RuntimeError('WordPress HTTP readiness not verified')
        created = wp('post', 'create', '--post_type=page', '--post_status=draft',
                     '--post_title=EV4 Lab Fixture', '--porcelain')
        ids = [s.strip() for s in created.splitlines() if s.strip().isdigit()]
        if len(ids) != 1:
            raise RuntimeError('Cannot prove fixture post identity')
        r['fixture_post_id'] = ids[0]
        env['LAB_PAGE_ID'] = ids[0]
        r['environment_fingerprint'] = digest({'requested': p, 'installed': r['installed'],
                                               'test_sha256': r['test_sha256'], 'catalog_sha256': digest(CAT.read_bytes())})
        cmd = [binary('playwright'), 'test', '--config=playwright.config.mjs']
        if selected != 'all':
            selector = '(?:M|' + selected + ')' if selected in FIXTURE_DEPENDENTS else selected
            cmd.extend(['--grep', r'^\[' + selector + ':'])
        stage = 'browser'
        test = command(cmd, env=env, timeout=1200, allow_fail=True)
        (ART / 'playwright-console.log').write_text((test.stdout + '\n' + test.stderr)[-40000:])
        report = ART / 'playwright.json'
        if not report.is_file() or not classify_playwright(json.loads(report.read_text()), r):
            r['setup_error'] = 'No recognizable executed Playwright scenario evidence'
        browser = ART / 'browser.json'
        if browser.is_file():
            r['installed']['browser'] = json.loads(browser.read_text())
        geometry = ART / 'responsive-geometry.json'
        if geometry.is_file():
            for item in r['scenarios']:
                if item['test_identity'] == 'K:ten-viewport-geometry' and item['status'] == 'VERIFIED_PASS':
                    item['observed']['geometry'] = json.loads(geometry.read_text())
                    item['expected'] = {'no_page_horizontal_overflow': True, 'visible_atomic_heading': True}
        contrast_evidence = ART / 'accessibility-contrast.json'
        if contrast_evidence.is_file():
            measured = json.loads(contrast_evidence.read_text())
            for item in r['scenarios']:
                if item['test_identity'] == 'L:contrast-aa-default-button':
                    observed = item['observed'] or {}
                    observed['measured_css'] = measured
                    item['observed'] = observed
                    item['expected'] = {'minimum_normal_text_contrast_ratio': 4.5}
        r['environment_fingerprint'] = digest({
            'requested': p, 'installed': r['installed'],
            'test_sha256': r['test_sha256'],
            'catalog_sha256': digest(CAT.read_bytes())
        })
        fixture = next((s for s in r['scenarios']
                        if s['test_identity'] == 'M:native-editor-create-reopen'), None)
        storage = (probe_wordpress_persistence(ids[0])
                   if fixture is not None and fixture['status'] == 'VERIFIED_PASS'
                   else {'state': 'NOT_EXECUTED'})
        r['fixture_storage_probe'] = storage
        finalize_fixture_evidence(r, storage)
        if test.returncode and not any(s['status'] in ('VERIFIED_FAIL', 'NOT_PROVEN') for s in r['scenarios']):
            r['setup_error'] = 'Playwright returned failure without recognizable assertion'
    except (RuntimeError, OSError, ValueError, subprocess.TimeoutExpired) as e:
        r['setup_error'] = str(e)[:2000]
        if stage == 'source_validation':
            r['source_contract_error'] = str(e)[:1500]
            for item in r['scenarios']:
                if item['test_identity']:
                    item['status'] = 'NOT_PROVEN'
        elif stage == 'provisioning':
            for item in r['scenarios']:
                if item['test_identity']:
                    item['status'] = 'ENVIRONMENT_UNAVAILABLE'
    finally:
        try:
            if started:
                command([binary('wp-env'), 'cleanup', '--force'], env=env, timeout=300)
                r['teardown'] = 'VERIFIED'
            else:
                r['teardown'] = 'NOT_STARTED'
        except Exception as e:
            r['teardown'] = 'NOT_PROVEN: ' + str(e)[:200]
        finish(r)
    return 0 if r['execution'] == 'VERIFIED_PASS' and r['setup_error'] is None else 2


def main():
    cli = argparse.ArgumentParser()
    sub = cli.add_subparsers(dest='operation', required=True)
    run = sub.add_parser('run')
    run.add_argument('--profile', default='profiles/core-4.3.5.json')
    run.add_argument('--capability', default='all', choices=['all', *DOMAINS])
    sub.add_parser('catalog')
    verify = sub.add_parser('verify-checkout')
    verify.add_argument('--expected', required=True)
    reuse = sub.add_parser('reuse')
    reuse.add_argument('--profile', default='profiles/core-4.3.5.json')
    reuse.add_argument('--evidence', required=True)
    args = cli.parse_args()
    if args.operation == 'catalog':
        print(json.dumps(catalog(), indent=2))
        return 0
    if args.operation == 'verify-checkout':
        try:
            actual = require_exact_source(args.expected)
        except (RuntimeError, OSError) as exc:
            print('EXACT_HEAD: NOT_PROVEN: ' + str(exc))
            return 2
        print('EXACT_HEAD: VERIFIED ' + actual)
        return 0
    p = profile((ROOT / args.profile).resolve())
    if args.operation == 'run':
        return execute(p, args.capability)
    old = json.loads(Path(args.evidence).read_text())
    matching = old.get('profile_sha256') == digest(p) and old.get('test_sha256') == test_hash() and bool(old.get('environment_fingerprint'))
    print(json.dumps({'identity_match': matching,
                      'disposition': 'REVIEW_REQUIRED' if matching else 'NOT_PROVEN',
                      'note': 'Historical matching metadata never proves the current live site.'}, indent=2))
    return 0 if matching else 2


if __name__ == '__main__':
    sys.exit(main())
