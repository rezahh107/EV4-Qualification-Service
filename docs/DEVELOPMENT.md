# Development

## Supported foundation environment

Foundation verification requires:

- Git;
- Python 3.11 or newer;
- no third-party Python packages.

The repository currently has no application dependency installation step.

## Setup

Clone the repository and enter it:

```bash
git clone https://github.com/rezahh107/EV4-Qualification-Service.git
cd EV4-Qualification-Service
```

No `pip install` step is required for the current foundation verifier.

## Canonical verification

Run:

```bash
python3 scripts/verify_repo.py
```

This is the canonical full repository-contract verification command at foundation stage.

It verifies the repository-owned foundation surfaces and the active GitHub Actions workflow contract. It does **not** qualify EV4 packages.

Focused falsification/regression tests for the verifier are:

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
```

The focused tests mutate isolated fixture copies; they do not rewrite the working repository.

## CI

`.github/workflows/repository-contract.yml` invokes the same canonical verification command on:

- pull requests;
- pushes to `main`;
- manual workflow dispatch.

CI also runs the focused verifier falsification/regression tests before the canonical verifier.

The workflow uses read-only repository contents permission.

A configured workflow is not evidence of a successful execution. Inspect the exact run associated with the exact commit/PR when CI status is part of a qualification claim.

## Current stage applicability

| Stage | State | Reason |
|---|---|---|
| setup | applicable | Python runtime only |
| build | `NOT_APPLICABLE` | no build product yet |
| lint/static analysis | `NOT_APPLICABLE` | no application code/toolchain yet |
| unit/integration tests | `NOT_APPLICABLE` beyond foundation contract | EV4 validators are not implemented |
| repository verification | applicable | `python3 scripts/verify_repo.py` |
| CI | applicable | repository exists to provide repeatable external execution |
| release | `NOT_APPLICABLE` | no released service artifact yet |

Do not add fake stages merely to make the table look complete.

## Adding the first EV4 validator

Do not start by duplicating logic inside workflow YAML.

First define:

1. candidate type and exact identity;
2. validator authority/ownership;
3. accepted inputs;
4. executed predicates;
5. PASS/FAIL semantics;
6. trusted-validator boundary;
7. result/artifact evidence;
8. failure versus infrastructure-unavailable behavior;
9. local/CI invocation sharing where practical;
10. falsification cases.

Then implement repository-owned validator code and make CI a thin wrapper around it.

## Repository changes

Before claiming a repository change complete:

1. run the canonical verifier when executable access is available;
2. run focused verifier tests when verifier behavior changes;
3. inspect the exact CI run if CI evidence is part of the claim;
4. keep `README.md`, `AGENTS.md`, and docs synchronized when contracts change;
5. do not call unavailable execution `PASS`.
