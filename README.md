# EV4 Qualification Service

External execution and qualification service for EV4 packages. Its purpose is to let LLM-driven EV4 workflows use canonical executable validators even when the model itself cannot run Python or other local tooling.

> **Agent entrypoint:** read [`AGENTS.md`](AGENTS.md) first.  
> **Foundation status:** repository contract and self-check CI remain implemented; the first real CE validator now has a dedicated Actions runner (see [CE validation](docs/CE_VALIDATION.md)).

## Why this repository exists

EV4 workflows may need executable validation that an LLM runtime cannot perform locally. This repository provides a trusted external execution surface so the model can submit an exact candidate, observe CI evidence, and retrieve results without pretending that an unavailable script was executed.

The intended operating principle is:

```text
candidate
  -> executable validation required?
  -> prefer trusted external CI
  -> exact validator result

PASS        -> validated result may be used
FAIL        -> do not bypass the failure with model-only fallback
UNAVAILABLE -> model may continue best-effort, but must preserve the evidence limit
```

GitHub/CI is an execution mechanism, not the owner of EV4 architecture, product, styling, or package decisions.

## Core contracts

- [Architecture](docs/ARCHITECTURE.md) — components, trust boundaries, execution path, and low-friction degradation model.
- [Validation Contract](docs/VALIDATION_CONTRACT.md) — result semantics, exact-target identity, failure/unavailability rules, and artifact claims.
- [Development](docs/DEVELOPMENT.md) — setup and the canonical repository verification command.

## Repository map

```text
AGENTS.md
README.md
docs/
  ARCHITECTURE.md
  DEVELOPMENT.md
  VALIDATION_CONTRACT.md
scripts/
  verify_repo.py
.github/
  workflows/
    repository-contract.yml
```

The first real validator uses the unchanged EV4 CE code; future validators are out of scope. Actual acceptance requires an observed, matching GitHub Actions run and result artifact.

## Canonical repository verification

Prerequisite: Python 3.11+ with only the standard library.

```bash
python3 scripts/verify_repo.py
```

The same underlying command is used by GitHub Actions.

Current stages:

- setup: no dependency installation required;
- build: `NOT_APPLICABLE` at foundation stage;
- lint/static analysis: `NOT_APPLICABLE` at foundation stage;
- tests: repository-contract verification only;
- full verification: `python3 scripts/verify_repo.py`;
- CI: `.github/workflows/repository-contract.yml`.

A workflow file is not evidence that CI passed. Current CI state must be observed on the exact target commit/PR when that claim matters.

## Low-friction policy

This is a personal project. The external validation path should reduce manual work, not become a new source of ceremony.

Accordingly:

- external CI validation is the preferred path when executable validation is needed;
- the service should automate candidate submission, execution, result lookup, and artifact retrieval as far as available integrations allow;
- infrastructure unavailability must not silently become `PASS`;
- infrastructure unavailability may permit model-only continuation when Owner policy allows it, but the output must state that external executable validation was not performed;
- an actual validator `FAIL` is materially different from CI being unavailable and must not be bypassed by fallback.

See [`docs/VALIDATION_CONTRACT.md`](docs/VALIDATION_CONTRACT.md).

## Foundation decisions

Applied now because they solve current repository needs:

- clear README entrypoint;
- concise cross-agent instructions;
- explicit architecture and validation contracts;
- `.gitignore`, `.gitattributes`, and `.editorconfig`;
- one stdlib-only repository verification command;
- CI that reuses the same verification command with read-only repository permissions.

Intentionally not added yet:

- branch protection / required checks — no hard merge gate until it provides more value than friction for this single-owner personal repository;
- CODEOWNERS — single-owner topology makes it unnecessary;
- issue/PR templates — no repeated intake failure exists yet;
- dependency automation — there are no managed runtime dependencies yet;
- release automation — no distributable service release exists yet;
- license — licensing intent has not been supplied by the Owner;
- additional EV4 validators — must be introduced with their actual contracts, not as placeholders.

## Foundation provenance

This repository foundation was adapted from the Repository Foundation domain in `rezahh107/Personal-Preference-Decision-Model`, inspected at:

`main@baad152c841713c703f0f56ae60eeff120c6ef50`

The applied principle is outcome-oriented rather than template-copying:

`Inspect -> Applicability -> Smallest Sufficient Delta -> Validate`

North Star:

`SELF-EXPLAINING + SELF-VALIDATING`

## First operational CE validator

Submit a PR containing `submissions/<id>/architect-handoff.json` and `submissions/<id>/ce-candidate.json` only as data. After the trusted service is installed on `main`, `CE Canonical Validation` runs the original `qualify_ce_handoff.py` via the read-only `pull_request_target` job, with trusted base code isolated from PR data. A result artifact includes the input HEAD and raw SHA-256 identities, trusted service SHA and run identity. Only an actual `VALIDATOR_PASS` produces `official-ce-handoff.json`; `VALIDATOR_FAIL` includes canonical error codes; no execution cannot be reported as success. See [instructions](docs/CE_VALIDATION.md).
