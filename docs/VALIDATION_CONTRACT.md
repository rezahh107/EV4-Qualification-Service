# Validation Contract

## Purpose

This document defines the result semantics for EV4 Qualification Service.

It separates:

- a validator's actual finding about a candidate;
- the availability of the execution infrastructure;
- model-level fallback review;
- the claim that may be made about a delivered artifact.

These states must not be collapsed.

## Canonical result states

### `VALIDATOR_PASS`

Use only when:

- the intended canonical validator actually executed;
- it executed against the exact candidate claimed;
- the validator/service identity is known at the required boundary;
- the executed predicates all passed.

A PASS proves only the predicates actually executed.

### `VALIDATOR_FAIL`

Use when the canonical validator executed and one or more required predicates failed.

A known `VALIDATOR_FAIL` must not be bypassed by saying CI was unavailable, by switching to model-only validation, or by delivering the same candidate as independently validated.

Repair/requalification may produce a new candidate and new result.

### `EXECUTION_UNAVAILABLE`

Use when external executable validation could not complete because the required execution environment or integration was unavailable, inaccessible, or operationally unable to produce the required result.

Examples can include connector/access failure, CI platform failure, unavailable runner, or an equivalent infrastructure boundary.

This is **not** evidence that the candidate failed.

Owner policy for this personal project permits bounded continuation when appropriate, but the delivered result must preserve the claim ceiling.

### `NOT_EXECUTED`

Use when an executable path exists or is expected but there is no evidence that it actually ran for the claimed target.

Workflow presence, instructions, or a configured trigger are not execution evidence.

### `NOT_PROVEN`

Use when available evidence is insufficient for the stronger claim being considered.

## Model-only fallback state

When external executable validation is unavailable and Owner policy permits continuation, use the explicit evidence label:

`EXTERNAL_VALIDATION_NOT_EXECUTED`

The LLM may perform the strongest reasonable model-level/static review available and may still deliver the artifact when the task permits it.

It must not describe that artifact as:

- CI validated;
- executable-validator passed;
- independently validated;
- officially accepted by this service;

unless those claims have separate executed evidence.

## Exact-target binding

Decision-relevant external validation must bind to the exact candidate.

At minimum, the implementation must provide a stable candidate identity appropriate to the artifact type, such as:

- SHA-256 for a package/archive;
- Git commit/blob identity for repository-native input;
- another deterministic content identity qualified by the validator contract.

When the validator identity materially controls admission, record the trusted service revision and validator identity as well.

Historical evidence for a different candidate must not be silently reused as current PASS evidence.

## Trusted-validator boundary

For independent qualification, validator authority must come from the trusted service, not from candidate-controlled input.

The candidate may contain scripts as data, but those scripts must not silently replace the canonical validator used to decide that candidate's result.

When a PR or branch is used as submission transport, qualification workflow design must prevent candidate-controlled changes from redefining the qualification predicate being applied.

## Artifact claims

A future validated-artifact output should carry enough evidence to correlate:

- candidate identity;
- validation state;
- validator/service revision;
- workflow execution identity;
- output artifact identity.

A validated artifact is not implied merely because an artifact file was uploaded by CI.

## Low-friction continuation policy

The preferred order is:

```text
1. Attempt trusted external executable validation.
2. If it executes:
   PASS -> continue with PASS-bounded claims.
   FAIL -> stop that candidate's independent-validation path; repair or requalify.
3. If execution is unavailable:
   preserve EXECUTION_UNAVAILABLE / EXTERNAL_VALIDATION_NOT_EXECUTED;
   perform model-level fallback if Owner policy permits;
   continue without claiming external PASS.
```

Do not add repeated retries, mandatory human intervention, or blocking integration controls unless they materially improve this personal workflow enough to justify the friction.

## Claim ceiling examples

| Evidence | Allowed claim |
|---|---|
| Workflow file exists | external validation path is configured |
| Workflow ran but validator step did not execute | `NOT_EXECUTED` / bounded infrastructure evidence |
| Canonical validator executed and passed exact target | `VALIDATOR_PASS` for its executed predicates |
| Canonical validator executed and failed | `VALIDATOR_FAIL` |
| GitHub/connector unavailable | `EXECUTION_UNAVAILABLE` |
| Model reviewed candidate after external path failed to execute | model-level review completed + `EXTERNAL_VALIDATION_NOT_EXECUTED` |

## Current implementation boundary

At foundation v1:

- repository self-verification exists;
- repository-contract CI exists;
- EV4 package/role validators do not yet exist;
- no production validated-artifact contract is claimed.

Do not upgrade those absent capabilities based on this document alone.
