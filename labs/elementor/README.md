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
    python3 bin/lab.py run --profile profiles/core-4.3.5.json --capability all

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

The catalog enumerates all areas A through O. Browser scripts include narrow real scenarios for A, B, C, D, I, K, L, M, N and O. They have NOT yet been proven to pass in an installed WordPress environment merely because their test files exist.

E (design-system classes/variables), F (components), G (positioning), H (media), J (dynamic content), the original native partial-color Heading question and other unimplemented scenarios remain NOT_EXECUTED. Pro loops require a lawful private Pro package and credentials. The current runner deliberately refuses additional arbitrary/unlicensed plugins. Generic sanitized target-profile configuration is not implemented and no TARGET_PROFILE_VERIFIED claim is made.

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
