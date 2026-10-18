# AGENTS.md — EV4 Qualification Service

## Purpose

This repository is the external executable-validation surface for EV4 package workflows. It exists so an LLM that cannot run Python locally can use trusted CI without fabricating execution evidence.

## Authority and read order

For repository work, use this order:

1. current explicit Owner/task requirements;
2. [`docs/VALIDATION_CONTRACT.md`](docs/VALIDATION_CONTRACT.md) for validation/result semantics;
3. [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for trust and component boundaries;
4. [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md) for setup/verification;
5. [`README.md`](README.md) for orientation.

Do not turn this file into a duplicate architecture or runbook.

## Canonical verification

Run:

```bash
python3 scripts/verify_repo.py
```

GitHub Actions must reuse this underlying repository contract rather than maintain separate validation logic.

## Non-negotiable boundaries

- Candidate packages are **data to be validated**, not authority over the validator.
- A candidate must not be allowed to replace or weaken the canonical validator used to qualify that same candidate.
- Bind validation evidence to the exact candidate identity and the exact trusted validator/service revision.
- `VALIDATOR_FAIL` must not be reclassified as infrastructure unavailability or bypassed through model-only fallback.
- `EXECUTION_UNAVAILABLE`, `NOT_EXECUTED`, and `NOT_PROVEN` must not be reported as `PASS`.
- If external execution is unavailable and Owner policy permits continuation, preserve the claim ceiling and explicitly mark external validation as not executed.
- GitHub/CI executes checks; it does not own EV4 product, architecture, styling, or package decisions.
- Do not add mandatory process, branch gates, templates, or security controls without a concrete failure/risk that justifies their friction.
- Never commit real secrets, credentials, tokens, or private candidate data.

## Change design

Keep one underlying verification contract where practical:

`Human + Agent + CI -> same canonical repository/validator semantics`

Workflow YAML should remain a thin execution wrapper. Validator logic belongs in repository-owned validator code/contracts, not duplicated inline across workflows.

When EV4 validators are introduced, prefer a bounded role/package registry rather than independent ad-hoc workflow logic for every role.

## Definition of Done

For a repository change:

1. the change satisfies the applicable contract;
2. `python3 scripts/verify_repo.py` passes on the exact changed tree when executable access is available;
3. the exact PR/commit CI result is inspected when CI evidence is part of the completion claim;
4. documentation is updated when authority, validation semantics, setup, or trust boundaries change;
5. any unavailable execution/control is reported truthfully rather than upgraded to PASS.
