#!/usr/bin/env python3
"""Verify the EV4 Qualification Service repository foundation contract."""

from __future__ import annotations

import ast
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ".github/workflows/repository-contract.yml"
CANONICAL_VERIFY_COMMAND = "python3 scripts/verify_repo.py"

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
    WORKFLOW_PATH,
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
        "The candidate is input data",
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
    ".gitattributes": ("* text=auto",),
    ".gitignore": ("__pycache__/", ".env", "artifacts/"),
}

ALLOWED_VERIFIER_IMPORTS = {"__future__", "ast", "pathlib", "sys"}


class WorkflowConfigError(ValueError):
    """Raised when the supported workflow subset is malformed or ambiguous."""


def read_text(root: Path, relative_path: str) -> str:
    return (root / relative_path).read_text(encoding="utf-8")


def verifier_imports(source: str) -> set[str]:
    tree = ast.parse(source, filename="scripts/verify_repo.py")
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name.split(".", 1)[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".", 1)[0])
    return imports


def _strip_yaml_comment(raw: str) -> str:
    single = False
    double = False
    escaped = False
    for index, char in enumerate(raw):
        if double and char == "\\" and not escaped:
            escaped = True
            continue
        if char == "'" and not double:
            single = not single
        elif char == '"' and not single and not escaped:
            double = not double
        elif char == "#" and not single and not double:
            if index == 0 or raw[index - 1].isspace():
                return raw[:index]
        escaped = False
    if single or double:
        raise WorkflowConfigError("unterminated quoted scalar")
    return raw


def _tokenize_yaml_subset(source: str) -> list[tuple[int, int, str]]:
    tokens: list[tuple[int, int, str]] = []
    for line_number, raw_line in enumerate(source.splitlines(), 1):
        if "\t" in raw_line[: len(raw_line) - len(raw_line.lstrip())]:
            raise WorkflowConfigError(
                f"line {line_number}: tab indentation is unsupported"
            )
        without_comment = _strip_yaml_comment(raw_line).rstrip()
        if not without_comment.strip():
            continue
        indent = len(without_comment) - len(without_comment.lstrip(" "))
        content = without_comment[indent:]
        if content in {"---", "..."}:
            raise WorkflowConfigError(
                f"line {line_number}: YAML document markers are unsupported"
            )
        tokens.append((line_number, indent, content))
    return tokens


def _split_mapping_entry(content: str, line_number: int) -> tuple[str, str]:
    single = False
    double = False
    escaped = False
    colon_index = None
    for index, char in enumerate(content):
        if double and char == "\\" and not escaped:
            escaped = True
            continue
        if char == "'" and not double:
            single = not single
        elif char == '"' and not single and not escaped:
            double = not double
        elif char == ":" and not single and not double:
            colon_index = index
            break
        escaped = False
    if colon_index is None:
        raise WorkflowConfigError(f"line {line_number}: expected mapping entry")
    key = content[:colon_index].strip()
    value = content[colon_index + 1 :].strip()
    if (
        not key
        or key[0] in "'\""
        or any(not (char.isalnum() or char in "_.-") for char in key)
    ):
        raise WorkflowConfigError(
            f"line {line_number}: unsupported mapping key {key!r}"
        )
    return key, value


def _parse_scalar(value: str, line_number: int) -> str:
    if not value:
        return ""
    if value[0] in "[{>|&*!":
        raise WorkflowConfigError(
            f"line {line_number}: unsupported or ambiguous YAML scalar syntax"
        )
    if value[0] in "'\"":
        if len(value) < 2 or value[-1] != value[0]:
            raise WorkflowConfigError(
                f"line {line_number}: malformed quoted scalar"
            )
        return value[1:-1]
    return value


def _parse_mapping(
    tokens: list[tuple[int, int, str]], pos: int, indent: int
) -> tuple[dict[str, object], int]:
    result: dict[str, object] = {}
    while pos < len(tokens):
        line_number, current_indent, content = tokens[pos]
        if current_indent < indent:
            break
        if current_indent > indent:
            raise WorkflowConfigError(
                f"line {line_number}: ambiguous indentation in mapping"
            )
        if content.startswith("-"):
            break
        key, value = _split_mapping_entry(content, line_number)
        if key in result:
            raise WorkflowConfigError(
                f"line {line_number}: duplicate key {key!r}"
            )
        pos += 1
        if value:
            result[key] = _parse_scalar(value, line_number)
            if pos < len(tokens) and tokens[pos][1] > indent:
                raise WorkflowConfigError(
                    f"line {tokens[pos][0]}: scalar mapping entry has nested content"
                )
        elif pos < len(tokens) and tokens[pos][1] > indent:
            child_indent = tokens[pos][1]
            if tokens[pos][2].startswith("-"):
                child, pos = _parse_list(tokens, pos, child_indent)
            else:
                child, pos = _parse_mapping(tokens, pos, child_indent)
            result[key] = child
        else:
            result[key] = None
    return result, pos


def _parse_list(
    tokens: list[tuple[int, int, str]], pos: int, indent: int
) -> tuple[list[object], int]:
    result: list[object] = []
    while pos < len(tokens):
        line_number, current_indent, content = tokens[pos]
        if current_indent < indent:
            break
        if current_indent > indent:
            raise WorkflowConfigError(
                f"line {line_number}: ambiguous indentation in list"
            )
        if not content.startswith("-"):
            break
        item_content = content[1:].strip()
        pos += 1

        if not item_content:
            if pos >= len(tokens) or tokens[pos][1] <= indent:
                raise WorkflowConfigError(
                    f"line {line_number}: empty list item"
                )
            child_indent = tokens[pos][1]
            if tokens[pos][2].startswith("-"):
                child, pos = _parse_list(tokens, pos, child_indent)
            else:
                child, pos = _parse_mapping(tokens, pos, child_indent)
            result.append(child)
            continue

        if ":" in item_content:
            key, value = _split_mapping_entry(item_content, line_number)
            item: dict[str, object] = {
                key: _parse_scalar(value, line_number) if value else None
            }
            if pos < len(tokens) and tokens[pos][1] > indent:
                child_indent = tokens[pos][1]
                continuation, pos = _parse_mapping(
                    tokens, pos, child_indent
                )
                overlap = set(item).intersection(continuation)
                if overlap:
                    duplicate = sorted(overlap)[0]
                    raise WorkflowConfigError(
                        f"line {line_number}: duplicate list-item key {duplicate!r}"
                    )
                item.update(continuation)
            result.append(item)
        else:
            result.append(_parse_scalar(item_content, line_number))
            if pos < len(tokens) and tokens[pos][1] > indent:
                raise WorkflowConfigError(
                    f"line {tokens[pos][0]}: scalar list item has nested content"
                )
    return result, pos


def parse_workflow_subset(source: str) -> dict[str, object]:
    tokens = _tokenize_yaml_subset(source)
    if not tokens:
        raise WorkflowConfigError("workflow is empty")
    if tokens[0][1] != 0 or tokens[0][2].startswith("-"):
        raise WorkflowConfigError("workflow root must be a mapping")
    parsed, pos = _parse_mapping(tokens, 0, 0)
    if pos != len(tokens):
        raise WorkflowConfigError(
            f"line {tokens[pos][0]}: unsupported workflow structure"
        )
    return parsed


def workflow_contract_failures(source: str) -> list[str]:
    failures: list[str] = []
    try:
        workflow = parse_workflow_subset(source)
    except WorkflowConfigError as exc:
        return [
            f"{WORKFLOW_PATH}: unsupported/ambiguous workflow configuration: {exc}"
        ]

    triggers = workflow.get("on")
    if not isinstance(triggers, dict):
        return [f"{WORKFLOW_PATH}: active 'on' trigger mapping is required"]

    if "pull_request" not in triggers:
        failures.append(
            f"{WORKFLOW_PATH}: active pull_request trigger is required"
        )
    if "workflow_dispatch" not in triggers:
        failures.append(
            f"{WORKFLOW_PATH}: active workflow_dispatch trigger is required"
        )

    push = triggers.get("push")
    if not isinstance(push, dict):
        failures.append(
            f"{WORKFLOW_PATH}: active push trigger with branches is required"
        )
    else:
        branches = push.get("branches")
        if not isinstance(branches, list) or "main" not in branches:
            failures.append(
                f"{WORKFLOW_PATH}: push trigger must target main"
            )

    permissions = workflow.get("permissions")
    if (
        not isinstance(permissions, dict)
        or permissions.get("contents") != "read"
    ):
        failures.append(
            f"{WORKFLOW_PATH}: workflow permissions.contents must be read"
        )

    jobs = workflow.get("jobs")
    if not isinstance(jobs, dict) or not jobs:
        failures.append(f"{WORKFLOW_PATH}: at least one job is required")
        return failures

    verifier_step_found = False
    for job_name, job in jobs.items():
        if not isinstance(job, dict):
            failures.append(
                f"{WORKFLOW_PATH}: job {job_name!r} must be a mapping"
            )
            continue

        effective_permissions = permissions
        if "permissions" in job:
            job_permissions = job.get("permissions")
            if not isinstance(job_permissions, dict):
                failures.append(
                    f"{WORKFLOW_PATH}: job {job_name!r} permissions must be a mapping"
                )
                continue
            effective_permissions = job_permissions

        steps = job.get("steps")
        if not isinstance(steps, list):
            continue

        for step in steps:
            if not isinstance(step, dict):
                continue
            if step.get("run") == CANONICAL_VERIFY_COMMAND:
                verifier_step_found = True
                if (
                    not isinstance(effective_permissions, dict)
                    or effective_permissions.get("contents") != "read"
                ):
                    failures.append(
                        f"{WORKFLOW_PATH}: canonical verifier job must have "
                        "effective contents: read permission"
                    )

    if not verifier_step_found:
        failures.append(
            f"{WORKFLOW_PATH}: an executable step must run exactly "
            f"{CANONICAL_VERIFY_COMMAND!r}"
        )

    return failures


def verify_repository(root: Path) -> list[str]:
    failures: list[str] = []

    for relative_path in REQUIRED_FILES:
        path = root / relative_path
        if not path.is_file():
            failures.append(f"missing required file: {relative_path}")

    for relative_path, markers in TEXT_REQUIREMENTS.items():
        path = root / relative_path
        if not path.is_file():
            continue
        text = read_text(root, relative_path)
        for marker in markers:
            if marker not in text:
                failures.append(
                    f"{relative_path}: missing required contract marker: {marker!r}"
                )

    workflow_path = root / WORKFLOW_PATH
    if workflow_path.is_file():
        failures.extend(
            workflow_contract_failures(read_text(root, WORKFLOW_PATH))
        )

    verifier_path = root / "scripts/verify_repo.py"
    if verifier_path.is_file():
        source = read_text(root, "scripts/verify_repo.py")
        unexpected_imports = (
            verifier_imports(source) - ALLOWED_VERIFIER_IMPORTS
        )
        if unexpected_imports:
            failures.append(
                "scripts/verify_repo.py: non-foundation dependency/import "
                "introduced without updating the contract: "
                + ", ".join(sorted(unexpected_imports))
            )

    return failures


def main() -> int:
    failures = verify_repository(ROOT)
    if failures:
        print("REPOSITORY_CONTRACT: FAIL")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("REPOSITORY_CONTRACT: PASS")
    print(f"checked_files={len(REQUIRED_FILES)}")
    print("scope=foundation_structure_and_active_workflow_contract")
    print("ev4_package_validation=NOT_IMPLEMENTED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
