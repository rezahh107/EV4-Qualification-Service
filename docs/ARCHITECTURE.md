# Architecture

## Mission

EV4 Qualification Service is an external execution boundary for canonical EV4 validators.

The service exists because an LLM may be able to create/review package artifacts while lacking local Python or another executable runtime. Instead of deleting the executable validation step or pretending the model executed it, the service provides a trusted CI path.

## System model

```text
LLM / EV4 role
    |
    | exact candidate + requested validator
    v
Submission transport
    |
    v
Trusted qualification service revision
    |
    +--> canonical validator
    |        |
    |        +--> PASS
    |        +--> FAIL
    |
    +--> execution infrastructure unavailable
             |
             +--> bounded fallback policy outside the validator result
```

### Components

**LLM / EV4 role**
- produces or receives a candidate;
- determines that executable validation is needed;
- submits the exact candidate when external execution is available;
- consumes evidence without upgrading it beyond what ran.

**Submission transport**
- carries candidate data and validation request into the service;
- may initially be a branch/PR-based GitHub flow because it is compatible with available integrations;
- is not the permanent architectural contract. A future direct dispatch/API transport may replace it without changing validation semantics.

**Qualification service**
- owns the executable validation environment and canonical validator selection;
- binds the result to candidate identity and service/validator identity;
- exposes machine-readable/human-readable evidence and, where appropriate, a validated artifact.

**Canonical validator**
- service-owned executable logic for a defined EV4 role/package contract;
- must not be replaced by code supplied inside the candidate being qualified.

## Trust boundary

The most important boundary is:

> The candidate is input data. It must not become the authority that chooses or rewrites the validator used to validate itself.

A future candidate-triggered workflow therefore needs a trusted-validator execution model. For example, it may read validator logic from an accepted service revision while reading the candidate from the submission revision/artifact.

A PR workflow that simply executes arbitrary validator code from an untrusted candidate branch is not sufficient for a strong independent-validation claim.

The current `repository-contract.yml` is different: it validates changes to this service repository itself. It is not yet the EV4 package qualification workflow.

## Low-friction degradation model

The Owner has explicitly prioritized keeping this personal workflow practical.

Therefore external CI is the **preferred executable validation path**, not a universal condition that must freeze all work whenever infrastructure is unavailable.

The distinction is:

```text
validator executed and FAILed
    !=
validator could not execute
```

- `VALIDATOR_FAIL`: the candidate violated an executed contract. Model-only fallback cannot erase this result.
- `EXECUTION_UNAVAILABLE`: the external environment/connector/CI path could not produce a result. If Owner policy permits, the LLM may continue with bounded model-level review and deliver an artifact, but it must not claim independent executable validation.
- `NOT_EXECUTED`: a runnable path existed or was expected but no execution evidence was obtained.
- `NOT_PROVEN`: evidence is insufficient for the stronger claim.

The goal is graceful degradation without false evidence.

## Evidence identity

A decision-relevant validation result should eventually identify at least:

- candidate identity (for example SHA-256 and/or repository blob/commit identity);
- requested validator/contract identity;
- trusted service revision;
- workflow run/job identity;
- result state;
- produced artifact identity when applicable.

Exact schema belongs to the validator/result contract once the first real EV4 validator is introduced.

## Responsibility boundary

This repository owns:

- external executable qualification infrastructure;
- canonical validator execution;
- traceable result/artifact evidence;
- failure versus infrastructure-unavailability distinction.

It does **not** own:

- EV4 product/role intent;
- architecture or UI decisions made by Architect/CE/Builder/Responsive;
- approval of business requirements;
- automatic conversion of missing evidence into success.

## Evolution principle

Prefer capability-level contracts over transport-specific rules.

The stable capability is:

`trusted external executable validation with exact-target evidence`

Today that may be GitHub Actions triggered by a PR. Tomorrow it may be a direct dispatch/API route. Transport changes should not require redefining what PASS, FAIL, or unavailable evidence means.
