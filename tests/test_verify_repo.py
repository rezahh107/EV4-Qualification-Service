from __future__ import annotations

from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import verify_repo  # noqa: E402


class RepositoryContractTests(unittest.TestCase):
    def make_fixture(self) -> tuple[tempfile.TemporaryDirectory, Path]:
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        for relative_path in verify_repo.REQUIRED_FILES:
            source = ROOT / relative_path
            target = root / relative_path
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        return temp, root

    def mutate_workflow(self, root: Path, old: str, new: str) -> None:
        path = root / verify_repo.WORKFLOW_PATH
        source = path.read_text(encoding="utf-8")
        self.assertIn(old, source)
        path.write_text(source.replace(old, new, 1), encoding="utf-8")

    def assert_failure_contains(self, root: Path, text: str) -> None:
        failures = verify_repo.verify_repository(root)
        self.assertTrue(
            any(text in failure for failure in failures),
            msg=f"expected {text!r} in failures: {failures}",
        )

    def test_unmodified_repository_passes(self) -> None:
        self.assertEqual(verify_repo.verify_repository(ROOT), [])

    def test_push_target_other_than_main_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            self.mutate_workflow(root, "      - main", "      - feature")
            self.assert_failure_contains(root, "push trigger must target main")

    def test_commented_pr_marker_does_not_count_as_trigger(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            self.mutate_workflow(
                root,
                "  pull_request:",
                "  # pull_request: retained as inactive text",
            )
            self.assert_failure_contains(
                root, "active pull_request trigger is required"
            )

    def test_inert_command_mention_does_not_count_as_execution(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            self.mutate_workflow(
                root,
                "run: python3 scripts/verify_repo.py",
                'run: echo "python3 scripts/verify_repo.py"',
            )
            self.assert_failure_contains(
                root, "an executable step must run exactly"
            )

    def test_write_permission_with_read_comment_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            self.mutate_workflow(
                root,
                "  contents: read",
                "  contents: write # contents: read",
            )
            self.assert_failure_contains(
                root, "workflow permissions.contents must be read"
            )

    def test_missing_workflow_dispatch_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            self.mutate_workflow(
                root,
                "  workflow_dispatch:",
                "  # workflow_dispatch: removed",
            )
            self.assert_failure_contains(
                root, "active workflow_dispatch trigger is required"
            )

    def test_job_level_write_override_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            self.mutate_workflow(
                root,
                "    steps:\n",
                "    permissions:\n"
                "      contents: write\n\n"
                "    steps:\n",
            )
            self.assert_failure_contains(
                root,
                "canonical verifier job must have effective contents: read permission",
            )

    def test_duplicate_trigger_key_fails_closed(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            self.mutate_workflow(
                root,
                "  workflow_dispatch:\n",
                "  push:\n"
                "    branches:\n"
                "      - main\n"
                "  workflow_dispatch:\n",
            )
            self.assert_failure_contains(
                root, "unsupported/ambiguous workflow configuration"
            )

    def test_unsupported_flow_style_branches_fails_closed(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            self.mutate_workflow(
                root,
                "    branches:\n      - main",
                "    branches: [main]",
            )
            self.assert_failure_contains(
                root, "unsupported/ambiguous workflow configuration"
            )

    def test_required_file_check_still_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            (root / "AGENTS.md").unlink()
            self.assert_failure_contains(
                root, "missing required file: AGENTS.md"
            )

    def test_supported_text_contract_check_still_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / "README.md"
            source = path.read_text(encoding="utf-8")
            self.assertIn("Foundation status", source)
            path.write_text(
                source.replace("Foundation status", "Foundation state", 1),
                encoding="utf-8",
            )
            self.assert_failure_contains(
                root, "missing required contract marker: 'Foundation status'"
            )

    def test_verifier_third_party_import_still_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / "scripts/verify_repo.py"
            source = path.read_text(encoding="utf-8")
            path.write_text(source + "\nimport requests\n", encoding="utf-8")
            self.assert_failure_contains(
                root, "non-foundation dependency/import introduced"
            )


if __name__ == "__main__":
    unittest.main()
