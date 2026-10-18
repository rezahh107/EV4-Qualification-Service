# Canonical CE Validation (first executable service)

The **trusted service revision** owns the original EV4 `validators/qualify_ce_handoff.py` and its unchanged Python dependencies. This is the CE-specific validator from `EV4_ROLE_SUPPORT_SOURCE_AND_COMPILER_BUNDLE_v1.5.0.zip` (nested unchanged inside coordinated v2.8.18). For connector transport only, the minimal dependency/source/fixture subset is losslessly stored in `trusted/ce-source-v1.5.0.tar.xz.b85`, with per-file SHA-256 values in its sibling JSON manifest. `scripts/restore_ce_source.py` restores and verifies the **original file bytes**, without changing their contents.

## Submit (no Python or CLI on the LLM side)

1. Through the GitHub connector, create a branch from **main**, such as `submission/ce-20261018-01`.
2. Add **exactly one** `submissions/<id>/` directory containing two UTF-8 JSON files:
   - `architect-handoff.json` — upstream Architect handoff (the original `fixtures/chain/ARCHITECT_HANDOFF.json` illustrates the format).
   - `ce-candidate.json` — the pending CE candidate (the original `fixtures/chain/CE_CANDIDATE_HANDOFF.json` illustrates the format).
3. Open a PR **into main** from this submission branch. No need for `workflow_dispatch`. The GitHub Actions `CE Canonical Validation` workflow handles the submission after the service PR has been merged into `main` (not before).
4. Find the `pull_request_target` run for that PR/head SHA under **Actions → CE Canonical Validation**, and download its `ce-validation-pr-…-head-…-attempt-…` artifact. Match the SHA, PR number, run ID/attempt and `trusted_service_commit` in `result.json` before relying on it.

Profile and project-style contract are **not supplied by the candidate**. The pinned source files are deliberately loaded from the trusted bundle, byte-for-byte. The canonical validator also reads the pinned Architect coverage adapter and style precedence registry. Changing those requires a separately reviewed trusted-service PR.

## Result and artifacts

The upload includes `result.json`, `canonical-result.json` when emitted, and `validator-stderr.txt` when available. `result.json` records raw SHA-256 for the submitted Architect/CE inputs and the trusted validator/profile/contract, the head commit, service base commit and Actions run identity.

- `VALIDATOR_PASS`: canonical script exited 0, said `OFFICIAL_ACCEPTED`, and wrote `official-ce-handoff.json`. Only this case includes an **official CE handoff**.
- `VALIDATOR_FAIL`: canonical script exited 1, said `REJECTED`, included its error codes, and wrote no official handoff. Workflow job intentionally fails while artifact upload still executes.
- `NOT_EXECUTED`: missing/malformed data or no evidence that the canonical validator produced a usable result.
- `EXECUTION_UNAVAILABLE`: required trusted sources or execution are unavailable, or runner/validator output disagrees. This must not become a PASS.

GitHub Actions run-level failures before artifact upload have **no validator PASS evidence**. CI/repository outages are not classified as validator FAIL. A PASS covers **only this original CE validator's predicates**, not architectural correctness, upstream truth, runtime product behavior, or EV4 package-side successor acceptance.

## Trust and test boundaries

The `pull_request_target` job checks out trusted **base SHA** as executable service code, and checks out the **exact submission head SHA** into a separate `incoming/` data-only directory. The candidate branch's workflow/validator files are **never executed** as qualification authority. The job has `contents: read`, checkout does not persist credentials, and untrusted files have bounded size.

The service implementation PR itself is tested with a separate `pull_request`-only regression job; that developmental test exercises the canonical PASS fixture and a deliberately invalid candidate, but **is not independent submission qualification** until the trusted workflow is installed on `main`. Existing repository-contract CI is retained.

Locally, for repository maintainers only:

```bash
python3 scripts/restore_ce_source.py
python3 -m unittest discover -s tests -p 'test_*.py'
python3 scripts/verify_repo.py
```

Do not run the validator directly against an untrusted repository checkout as trusted service logic. Never add a result-changing bypass on FAIL.