#!/usr/bin/env python3
"""Verify the EV4 Qualification Service repository foundation contract.

This verifier intentionally uses only the Python standard library so the same
underlying contract can run locally and in GitHub Actions without dependency
installation.
"""

from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES = (
    "README.md",
    "AGENTS.md",
    ".gitattributes",
    ".gitignore",
    ".editorconfig",
    "docs/ARCHITECTURE.md",
    "docs/DEVELOPMENT.md",
    "docs/VALIDATION_CONTRACT.md",
    "scripts/verify_repo.py",
    ".github/workflows/repository-contract.yml",
)

TEXT_REQUIREMENTS = {
    "README.md": (
        "EV4 Qualification Service",
        "python3 scripts/verify_repo.py",
        "Foundation status",
        "SELF-EXPLAINING + SELF-VALIDATING",
    ),
    "AGENTS.md": (
        "docs/VALIDATION_CONTRACT.md",
        "docs/ARCHITECTURE.md",
        "python3 scripts/verify_repo.py",
        "VALIDATOR_FAIL",
        "EXECUTION_UNAVAILABLE",
    ),
    "docs/ARCHITECTURE.md": (
        "Candidate is input data",
        "VALIDATOR_FAIL",
        "EXECUTION_UNAVAILABLE",
        "trusted external executable validation with exact-target evidence",
    ),
    "docs/VALIDATION_CONTRACT.md": (
        "VALIDATOR_PASS",
        "VALIDATOR_FAIL",
        "EXECUTION_UNAVAILABLE",
        "NOT_EXECUTED",
        "NOT_PROVEN",
        "EXTERNAL_VALIDATION_NOT_EXECUTED",
        "Exact-target binding",
        "Trusted-validator boundary",
    ),
    "docs/DEVELOPMENT.md": (
        "python3 scripts/verify_repo.py",
        "no third-party Python packages",
        "NOT_APPLICABLE",
    ),
    ".gitattributes": (
        "* text=auto",
    ),
    ".gitignore": (
        "__pycache__/",
        ".env",
        "artifacts/",
    ),
    ".github/workflows/repository-contract.yml": (
        "pull_request:",
        "push:",
        "workflow_dispatch:",
        "permissions:",
        "contents: read",
        "python3 scripts/verify_repo.py",
    ),
}


def read_text(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def main() -> int:
    failures: list[str] = []

    for relative_path in REQUIRED_FILES:
        path = ROOT / relative_path
        if not path.is_file():
            failures.append(f"missing required file: {relative_path}")

    for relative_path, markers in TEXT_REQUIREMENTS.items():
        path = ROOT / relative_path
        if not path.is_file():
            continue
        text = read_text(relative_path)
        for marker in markers:
            if marker not in text:
                failures.append(
                    f"{relative_path}: missing required contract marker: {marker!r}"
                )

    # The canonical verifier should remain dependency-free at foundation stage.
    source = read_text("scripts/verify_repo.py")
    forbidden_imports = ("import yaml", "from yaml", "import requests", "from requests")
    for marker in forbidden_imports:
        if marker in source:
            failures.append(
                "scripts/verify_repo.py: third-party dependency introduced "
                f"without updating the foundation contract: {marker!r}"
            )

    if failures:
        print("REPOSITORY_CONTRACT: FAIL")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("REPOSITORY_CONTRACT: PASS")
    print(f"checked_files={len(REQUIRED_FILES)}")
    print("scope=foundation_structure_and_contract_alignment")
    print("ev4_package_validation=NOT_IMPLEMENTED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
