from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
UPDATER_PATH = ROOT / "skills" / "vibe-diagram" / "scripts" / "update_skill.py"


def load_updater():
    spec = importlib.util.spec_from_file_location("vibe_diagram_test_updater", UPDATER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load canonical updater")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ActivationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.updater = load_updater()
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.skill_root = self.root / "skills" / "vibe-diagram"
        self.skill_root.mkdir(parents=True)
        (self.skill_root / "VERSION").write_text("0.1.7\n", encoding="ascii")
        self.staging = self.root / "skills" / ".vibe-diagram-update-test"
        self.candidate = self.staging / "candidate"
        self.candidate.mkdir(parents=True)
        (self.candidate / "VERSION").write_text("0.1.8\n", encoding="ascii")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_successful_activation_removes_previous_tree(self) -> None:
        self.updater._activate_candidate(
            self.skill_root,
            self.candidate,
            self.staging,
        )

        self.assertEqual(
            (self.skill_root / "VERSION").read_text(encoding="ascii"),
            "0.1.8\n",
        )
        self.assertFalse((self.staging / "previous").exists())
        self.assertFalse((self.root / "backups").exists())

    def test_failed_promotion_restores_previous_tree_without_backup(self) -> None:
        real_replace = self.updater.os.replace
        calls = 0

        def fail_candidate_promotion(source: Path, target: Path) -> None:
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("promotion fixture")
            real_replace(source, target)

        with mock.patch.object(
            self.updater.os,
            "replace",
            side_effect=fail_candidate_promotion,
        ):
            with self.assertRaisesRegex(OSError, "promotion fixture"):
                self.updater._activate_candidate(
                    self.skill_root,
                    self.candidate,
                    self.staging,
                )

        self.assertEqual(
            (self.skill_root / "VERSION").read_text(encoding="ascii"),
            "0.1.7\n",
        )
        self.assertFalse((self.staging / "previous").exists())
        self.assertFalse((self.root / "backups").exists())

    def test_rollback_cli_is_not_available(self) -> None:
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as raised:
                self.updater.main(["--rollback"])

        self.assertEqual(raised.exception.code, 2)

    def test_result_payload_keeps_null_backup_compatibility_field(self) -> None:
        result = self.updater.UpdateResult("updated", "0.1.7", "0.1.8")

        self.assertIsNone(self.updater._result_payload(result)["backup_path"])

    def _legacy_backup(self, name: str) -> Path:
        backup = self.root / "backups" / "skills" / name
        backup.mkdir(parents=True)
        (backup / "VERSION").write_text("0.1.7\n", encoding="ascii")
        (backup / "payload.txt").write_text("verified\n", encoding="utf-8")
        manifest = {
            "channel": "stable",
            "ref": "v0.1.7",
            "schema_version": 1,
            "tree_sha256": self.updater.tree_sha256(backup),
            "version": "0.1.7",
        }
        (backup / "update.json").write_text(
            json.dumps(manifest, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return backup

    def test_cleanup_removes_only_verified_legacy_updater_backup(self) -> None:
        backup = self._legacy_backup("vibe-diagram-0.1.7-20260724010101")
        manual = backup.parent / "vibe-diagram-manual"
        manual.mkdir()

        removed = self.updater._cleanup_verified_legacy_backups(
            self.skill_root,
            "0.1.8",
        )

        self.assertEqual(removed, 1)
        self.assertFalse(backup.exists())
        self.assertTrue(manual.is_dir())

    def test_cleanup_preserves_tampered_legacy_backup(self) -> None:
        backup = self._legacy_backup("vibe-diagram-0.1.7-20260724010102")
        (backup / "payload.txt").write_text("tampered\n", encoding="utf-8")

        removed = self.updater._cleanup_verified_legacy_backups(
            self.skill_root,
            "0.1.8",
        )

        self.assertEqual(removed, 0)
        self.assertTrue(backup.is_dir())

    def test_cleanup_without_legacy_name_keeps_current_check_read_only(self) -> None:
        manual = self.root / "backups" / "skills" / "vibe-diagram-manual"
        manual.mkdir(parents=True)

        removed = self.updater._cleanup_verified_legacy_backups(
            self.skill_root,
            "0.1.8",
        )

        self.assertEqual(removed, 0)
        self.assertFalse(
            (self.skill_root.parent / ".vibe-diagram-update.lock").exists()
        )

    def test_current_gate_cleans_verified_legacy_backup(self) -> None:
        (self.skill_root / "VERSION").write_text("0.1.8\n", encoding="ascii")
        backup = self._legacy_backup("vibe-diagram-0.1.7-20260724010103")
        manifest = {
            "channel": "stable",
            "ref": "v0.1.8",
            "schema_version": 1,
            "tree_sha256": "0" * 64,
            "version": "0.1.8",
        }

        result = self.updater.check_and_update(
            self.skill_root,
            fetch_manifest=lambda: manifest,
            fetch_archive=lambda _ref, _target: self.fail(
                "current gate must not request an archive"
            ),
        )

        self.assertEqual(result.status, "current")
        self.assertFalse(backup.exists())
        self.assertEqual(
            result.message,
            "removed 1 verified legacy updater backup(s)",
        )


if __name__ == "__main__":
    unittest.main()
