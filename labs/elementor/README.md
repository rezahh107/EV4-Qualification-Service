# EV4 Elementor Compatibility Lab

Independent, opt-in test environment using actual released WordPress, Elementor and Chromium. The lab does not modify or certify the trusted CE Validator or CE handoff.

## Reproducible profile

The default profile pins WordPress 7.1.3, Elementor Core 4.3.5 and Hello Elementor 3.5.1. It selects PHP 8.3, MariaDB 11.4, wp-env 11.17.0, Playwright 1.58.2 and Node 22. The runner verifies actual installed versions. wp-env does not pin PHP/MariaDB patch releases. This branch does not yet provide a transitive npm lockfile or immutable Docker image digest: full bit-for-bit reproducibility is therefore NOT_PROVEN.

Atomic Editor is a released 4.x capability and should be enabled on clean installs, but the runtime is not treated as verified until the editor actually creates and reopens a native Atomic Heading. No hidden experiments are enabled.

## Run locally

Requires Docker, Node 22, Python 3.11+, network access for the public pinned ZIP files, and Chromium installation.

From labs/elementor execute:

    npm install --ignore-scripts --no-audit --no-fund
    npx playwright install chromium
    python3 -m unittest discover -s bin -p 'test_*.py' -v
    python3 bin/lab.py catalog
    EXPECTED_SOURCE_SHA="$(git rev-parse HEAD)" python3 bin/lab.py run --profile profiles/core-4.3.5.json --capability all

Replace all with a single domain letter A through O for targeted validation. M is a necessary precondition for frontend scenarios and is also exercised in a targeted frontend run.

Artifacts live in artifacts/: result.json (primary), summary.md, Playwright JSON/HTML, failure traces, console log and optional responsive geometry. The runner starts and cleans up isolated wp-env resources. Cleanup failures are independently reported.

## What each result means

- VERIFIED_PASS: the named real assertion executed and passed.
- VERIFIED_FAIL: an observed matching assertion failed.
- NOT_PROVEN: insufficient or broken browser harness evidence.
- NOT_EXECUTED: capability has no verified execution.
- ENVIRONMENT_UNAVAILABLE: the requested runtime failed provisioning.
- PRO_OR_LICENSE_UNAVAILABLE: a Pro-only scenario cannot run.
- INCOMPLETE: summary, not proof of domain-level acceptance.

A source-level fixture generated through the real running Elementor editor commands still needs editor reloading, published DOM observation, and actual WordPress post-meta validation. These are separate checks. A successful screenshot or generic HTML is never mistaken for native Elementor behavior.

## Current coverage boundary

The catalog explicitly accounts for all domains A through O; it does **not** claim exhaustive testing. On the exact observed [GitHub Actions run #39411240686](https://github.com/rezahh107/EV4-Qualification-Service/actions/runs/39411240686) for commit `6ab081d`, 14 real browser scenarios are `VERIFIED_PASS`, one real accessibility assertion is `VERIFIED_FAIL`, twelve catalog scenarios remain `NOT_EXECUTED` and one Pro-only scenario is `PRO_OR_LICENSE_UNAVAILABLE`.

Narrow verified cases exist for **A, B, C, D, E, I, K, L, M, N and O**. The E result proves native V4 Global Class attachment and persistence in the published frontend, **not** Variables or style precedence. F (Components), G (Positioning), H (Media) and J (Dynamic Content) have no executed assertions. The original single Atomic Heading with differently colored inline text remains `NOT_EXECUTED`, as do many subfeatures within the tested domains.

No supplied lawful Elementor Pro license/package is available. No sanitized target-like profile has been executed and no `TARGET_PROFILE_VERIFIED` claim is made. The full GitHub job is intentionally failing because the default button fixture did not meet its text-contrast expectation; this observed product/environment finding must not be relabeled as a test-harness outage.

## GitHub Actions / LLM consumer

The dedicated elementor-lab.yml workflow accepts workflow_dispatch inputs capability and profile after it exists on the default branch. PR runs on laboratory changes use the candidate workflow only; they are not evidence that the default-branch manual trigger works.

An EV4 consumer with the GitHub connector can read catalog.json, request a supported manual workflow through the GitHub Actions interface (or an authorized dispatch connector), inspect the matching run and download its artifact. Match exact source commit, run ID, attempt, profile, runtime version, test identity and fingerprint before using a result. If dispatch is not available, declare NOT_EXECUTED instead of creating a fake PASS or requiring local Python from the consumer.

For a local maintainer to assess prior artifact identity only:

    python3 bin/lab.py reuse --profile profiles/core-4.3.5.json --evidence artifacts/result.json

A matching historical result is REVIEW_REQUIRED, never automatic production-site verification.

## References

- https://elementor.com/help/get-started-with-the-elementor-editor-v4/
- https://developer.wordpress.org/block-editor/reference-guides/packages/packages-env/
- https://developer.wordpress.org/news/2026/05/getting-started-writing-wordpress-e2e-tests-with-playwright/
- https://github.com/elementor/elementor/blob/main/tests/test-environment-setup.md

The official Elementor development test setup uses source builds and hidden experiments. This lab instead points at released Elementor ZIPs.

## Recorded baseline accessibility finding (2026-10-20)

The released Core + Hello Elementor fixture renders the native legacy button with foreground rgb(255,255,255) and background rgb(97,206,112), approximately 1.99:1 contrast. This is a deliberately retained **VERIFIED_FAIL** against WCAG AA 4.5:1 normal-text contrast in this exact profile, not a harness failure or a domain-wide Elementor conclusion. Keyboard Tab reachability is a separate positive scenario so its PASS is not hidden by the contrast failure. Source execution: https://github.com/rezahh107/EV4-Qualification-Service/actions/runs/39410361085. Do not change the contrast threshold or fixture design merely to turn this observation green.

## Evidence-integrity controls (PR #7 repair)

1. **Exact Head execution.** Pull-request checkout uses `github.event.pull_request.head.sha` directly, and manual dispatch uses `github.sha`. A preliminary verification command plus the runner's own gate compare `git rev-parse --verify HEAD^{commit}` to the expected immutable SHA before qualification. Evidence includes the prior `source_commit` and `checkout_commit` fields, plus `expected_source_commit`, `actual_checkout_commit`, and `provenance_verified`. Absent or mismatched source identity results in `NOT_PROVEN`. A matching tree with a different commit is rejected.

2. **Finalized fixture evidence.** The canonical M fixture must pass its Playwright scenario **and** exact WordPress `_elementor_data` and published post-status probes before dependent A/B/C/D/E/I/K/L/N claims remain qualified. An executed mismatched persistence probe marks M `VERIFIED_FAIL`; a transport or execution failure marks M `NOT_PROVEN`. All dependent conclusions are reconciled afterward, retaining original browser observations as lower-strength evidence, not independent persistence proof. Independently verified O remains separate.

3. **Structured assertion origin.** Browser qualification assertions use `productAssertion(id, callback)` wrapping Playwright `test.step('EV4_PRODUCT_ASSERTION:' + id)`. Only a failed step with this exact ID and category establishes `VERIFIED_FAIL`. A failed setup assertion—even if its text contains `expect()`—is `NOT_PROVEN`. A passing test requires its qualifying step to run. The runner rejects catalog-backed test cases missing this wrapper; regression tests exercise harness spoofing and qualified product failure. The native button's computed contrast still uses **4.5:1** and its measured failure is retained.

These repairs **do not broaden A–O coverage**, accept missing Pro credentials, merge the independent CE validator workflow, or make an unsuccessful product assertion into PASS. A fully executed laboratory run can legitimately have a failing workflow and trustworthy individual scenario PASS/FAIL evidence. The standalone default-branch `workflow_dispatch` invocation is separate from a PR CI run and remains not proven until executed there.

## PRI-FND-004 — structural assertion authority

Catalog-backed browser test declarations and `productAssertion()` calls are parsed as JavaScript AST using **Acorn 8.18.0** (exact dependency pin), before running and again when classifying evidence. The source checker rejects comments/strings as non-executable markers; mismatched, duplicated, shadowed or unawaited qualification calls; computed or aliased Playwright step construction; reserved titles in executable test/helper source outside `qualification.mjs`; dynamic code loading; and missing, duplicated or unauthorized catalog cases. The dedicated qualification helper is structurally constrained to one native step with the canonical title.

In the Playwright JSON report, exactly one matching reserved step must appear for a scenario and its structurally authorized test implementation must be present. Duplicate, foreign, missing or ambiguous reserved steps are `NOT_PROVEN` (not `VERIFIED_FAIL`). This maintains the existing scenario names, result states and `EXPLICIT_PLAYWRIGHT_STEP` evidence label. A product assertion that actually fails inside the authorized helper remains `VERIFIED_FAIL`, including the default-button WCAG AA **4.5:1** contrast check. A subsequent harness failure after a successful product assertion remains `NOT_PROVEN`.

This is a deliberately narrow source contract for the present test harness, not a general JavaScript static-security sandbox. A new test authoring pattern requires an explicit reviewed extension of the source checker and relevant falsification tests. `bin/validate-source.mjs` participates in the test evidence hash so validator changes cannot silently reuse an earlier test identity.

## PRI-FND-005 — observable geometry before the product assertion

The responsive `K:ten-viewport-geometry` test first collects all ten real
viewport measurements (viewport size, navigation and browser DOM measurements)
**outside** the reserved `productAssertion()` step. It then performs the
unchanged geometry comparisons, plus an observation-count check, inside exactly
one reserved Step. The recorded responsive geometry artifact and the original
320/360/375/390/412/414/768/1024/1440/1920 widths are retained.

The Acorn-backed structural source contract now rejects known setup,
navigation and measurement browser methods inside **any catalog-backed
qualification callback**, including nested/computed member access. Tests
falsify mutations to K and unrelated C/E/L scenario callbacks. If browser
navigation or measurement fails before the Step, the classifier cannot claim a
qualified responsive failure and returns `NOT_PROVEN`. A completed measurement
that violates a geometry assertion remains `VERIFIED_FAIL`. This is a bounded
authoring-side control, not a general JavaScript effect system.

RC-1 exact-Head gating, RC-2 fixture persistence reconciliation, the
reserved-Step origin contract, Pro availability and the default-button
**4.5:1** WCAG contrast threshold remain unchanged.

## Full evidence-boundary repair (F-01 / F-02 / F-03)

The authorized step for each of the 15 implemented catalog scenarios now consumes a
JSON-safe **completed observation snapshot**, produced outside the step through
`observe(identity, acquisition)`. Acquisitions and native-editor operations are
not product proof. Acquisition receipts record `COMPLETE` and a SHA-256 of the
snapshot only after successful serialization, or `UNAVAILABLE` on failure.

A `productAssertion(identity, observation, snapshot => { ... })` has precisely
one bounded native Playwright step. The callback is restricted by Acorn **8.18.0**
to synchronous Playwright **value** matchers reading only `snapshot` and
immutable loop variables; nested/browser calls, arbitrary helpers, async
predicates, assignments, dynamic member access and unknown representations
fail source qualification. Native Playwright's matcher error carries a
structured `matcherResult.pass === false` discriminator: the qualified helper
records `PRODUCT_FAIL` only then. Generic exceptions record `UNPROVEN`.
The final runner requires both the unique reserved Step and matching
observation/product receipts before admitting PASS/FAIL. This is deliberately
not a universal JavaScript side-effect sandbox.

The measurement/acquisition phase retains bounded Playwright auto-wait where
needed (notably the native editor and duplicate/delete counts), then
re-acquires the actual completed DOM observation. An observed negative count
is product evidence; a failed browser transport is not. Completed C width and
height, O HTTP and form visibility, A count transitions, K's exact ten widths
and layout bounds, live native link/heading/class compatibility expectations,
and measured 4.5:1 normal-text contrast remain explicitly asserted.

### Structural native Elementor fixture storage

A real Core **4.3.5** lab run established the saved Atomic Heading representation:
`widgetType = e-heading`, `elType = widget`, and
`settings.title = {"$$type":"escaped-html","value":"EV4 Atomic Heading"}`.
The actual generated widget ID and its parent container ID are read back from
the same run's `element-ids.json`; a unique matching node must have the
correct type, parent, title and published post status. Malformed JSON, foreign
IDs, unrelated string occurrences and wrong titles cannot qualify. Unknown
title representations are `UNSUPPORTED` and prevent M from becoming
`VERIFIED_PASS` rather than being guessed at. The only generated data
included in the storage sample is a synthetic lab fixture, never customer data.

Unknown/unavailable browser or WordPress provenance retains `NOT_PROVEN`;
failed prerequisites do not upgrade dependent A/B/C/D/E/I/K/L/N statuses.
Previously validated RC-1 exact commit provenance, independent CE workflows,
scenario IDs and public result states are preserved. Result evidence adds
structured `observation_state`, `product_assertion_state` and SHA-256 per
executed scenario, while keeping the existing `assertion_origin` indicator.
A lab CI failure may still truthfully represent the measured product contrast
violation and is not necessarily a test-harness outage.

### Predicate and receipt-authority identity

The reviewed predicate AST signatures for all 15 executable scenarios are
pinned in `predicate-contract.json` and verified by `validate-source.mjs`.
Any deleted, weakened or added predicate must be admitted through a reviewed
manifest successor; whitespace/comment-only edits do not change the signature.
The `qualification.mjs` and `observation.mjs` helper Git Blob identities are
also exact-bound in the same source contract so a test cannot redefine evidence
receipt production. The predicate manifest, helpers and isolated real-Playwright
origin-falsification tests contribute to the result's test fingerprint.

The isolated `bin/origin-contract.spec.mjs` suite uses actual native Playwright
value matchers and intentionally expected failing steps to exercise complete
negative snapshots, unavailable observations, unexpected callback exceptions,
negated matcher outcomes and successful data-only predicates. These test
fixtures are unit evidence, not WordPress product evidence.

### Additional source-integrity closure: observation acquisition

The predicate manifest (schema version **2**) also pins the canonical Acorn
AST body of each of the 15 executable scenario functions in
`scenario_source`. This closes a separate source-authority gap: a future
change that replaces actual browser observation with fabricated, prevalidated
snapshot values must no longer pass merely because the pure-data product
predicates are unchanged. The native fixture-creation helper
`tests/helpers.mjs` is also bound to its reviewed Git Blob identity.
Altered acquisition, precondition, fixture setup, or assertion code requires
a new reviewed manifest/identity before its evidence can qualify. Comments
and formatting do not change AST signatures.

Regression mutations substitute fabricated C, O, A and K observations while
preserving the existing predicates, and alter the fixture helper's emitted
element identity. All must fail closed at source qualification. This contract
is source-integrity control for the accepted Core 4.3.5 scenario
implementations—not a general proof that every browser observation is correct.

### F-04 / F-05 — approved module acquisition authority and container topology

The approved scenario AST manifest also requires a canonical, unaliased
`observe` and `settledCount` import from `./observation.mjs`. For this
bounded Core 4.3.5 lab, `native.spec.mjs` permits only the five reviewed
module imports, three reviewed constant initializers, and the existing
catalog-bound top-level test declarations. Unreviewed module wrappers,
shadowing, aliases, reassignment, computed dynamic top-level code or new
module declarations fail closed. AST comparison accepts harmless comment and
formatting edits; new legitimate module bindings require explicit source
contract review. This is an authoring gate, not a universal JavaScript sandbox
or a separately non-bypassable validator trust authority.

Native WordPress `_elementor_data` qualification now requires the uniquely
identified Atomic Heading to be the direct child (by node identity) of exactly
one generated native Container (`elType=container`) in the inspected tree.
The existing Elementor 4.3.5 escaped-html title encoding, heading type,
post publication, transport handling and unsupported-format classification
remain unchanged. Mismatched document topology yields `MISMATCH`; storage
transport yields `UNAVAILABLE`; unqualified title encodings yield
`UNSUPPORTED`. Existing finalized M prerequisite reconciliation preserves
browser-only observations without elevating unqualified storage.

## Executable test discovery and source-authority gate — PRI-FND-001

Playwright's reviewed `testDir: './tests'` and recursive `testMatch: '**/*.spec.mjs'` define the executable browser-test set. `bin/validate-source.mjs` now verifies the entire Playwright config using its canonical Acorn AST (comment/format changes remain admissible), recursively enumerates the `tests/` tree, and rejects any unreviewed path, nested runnable spec, symbolic link, special file or unsupported representation **before browser execution**. The current approved set is `native.spec.mjs`, `helpers.mjs`, `qualification.mjs` and `observation.mjs`. Adding a legitimate spec or changing discovery configuration requires a reviewed source-contract/catalog successor; never silently skip the new executable source.

Exact-source evidence fingerprints also include recursively nested test files, preventing a new nested test from reusing unchanged historical test identity. Regression tests use real Playwright `--list` to demonstrate nested spec discoverability, while the source gate rejects it before executing a test body. The existing reviewed 15 scenario/predicate AST fingerprints, native fixture storage, public result states, Acorn 8.18.0 authority and normal-text WCAG contrast threshold 4.5:1 are unchanged.

## EC-FND-001 — Exact-source working-tree integrity

Matching Git HEAD alone does not establish that the executed local source
bytes are those stored in that commit. Both `verify-checkout` and lab
pre-provisioning admission now invoke `require_exact_source()`.

The guard compares every tracked regular file's **actual bytes** against
the corresponding Git HEAD blob object (SHA-1/SHA-256 as appropriate),
independent of Git index/staged/unstaged and assume-unchanged flags.
Unsupported tracked objects, missing/nonregular tracked files and new
nonignored untracked paths fail closed. Legitimate generated output
ignored by the repository (`artifacts/`, `.lab-state/`, `node_modules/`,
`.wp-env.json`, `package-lock.json`) does not invalidate provenance.

The existing Acorn recursive source validator now also runs before
WordPress provisioning. Public evidence/status fields, the reviewed
predicate/source manifests, fixture storage contracts, version scope,
and the 4.5:1 contrast threshold remain unchanged. This is a local
admission snapshot, not a separate immutable external trust system
or protection against a hostile concurrent post-admission mutation.
