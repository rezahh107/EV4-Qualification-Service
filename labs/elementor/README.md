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
