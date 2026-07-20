from __future__ import annotations

import importlib.util
import json
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skills" / "vibe-diagram"
UPDATE_SCRIPT = SKILL_ROOT / "scripts" / "update_skill.py"

SPEC = importlib.util.spec_from_file_location("vibe_diagram_update", UPDATE_SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise AssertionError("could not load update_skill.py")
UPDATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(UPDATE)


def _write_skill(root: Path, version: str, runtime: str) -> None:
    (root / "references").mkdir(parents=True, exist_ok=True)
    (root / "scripts").mkdir(parents=True, exist_ok=True)
    (root / "SKILL.md").write_text(
        "---\nname: vibe-diagram\ndescription: Use when a diagram is needed.\n---\n",
        encoding="utf-8",
    )
    (root / "VERSION").write_text(version + "\n", encoding="ascii")
    (root / "update.json").write_text("{}\n", encoding="utf-8")
    (root / "references" / "runtime-workflow.md").write_text(runtime, encoding="utf-8")
    shutil.copy2(UPDATE_SCRIPT, root / "scripts" / "update_skill.py")
    shutil.copy2(
        SKILL_ROOT / "scripts" / "vibe_diagram_lint.py",
        root / "scripts" / "vibe_diagram_lint.py",
    )


def _manifest_for(skill: Path, version: str) -> dict:
    return {
        "schema_version": 1,
        "channel": "stable",
        "version": version,
        "ref": f"v{version}",
        "tree_sha256": UPDATE.tree_sha256(skill),
    }


def _seal_manifest(skill: Path, version: str) -> dict:
    manifest = _manifest_for(skill, version)
    (skill / "update.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def _write_archive(path: Path, skill: Path, version: str) -> None:
    prefix = f"vibe-diagram-{version}/skills/vibe-diagram"
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for source in sorted(item for item in skill.rglob("*") if item.is_file()):
            relative = source.relative_to(skill).as_posix()
            archive.write(source, f"{prefix}/{relative}")


class SkillUpdateTests(unittest.TestCase):
    def test_repository_and_installed_versions_are_v011(self) -> None:
        self.assertEqual("0.1.1", (ROOT / "VERSION").read_text(encoding="ascii").strip())
        self.assertEqual("0.1.1", (SKILL_ROOT / "VERSION").read_text(encoding="ascii").strip())
        manifest = json.loads((SKILL_ROOT / "update.json").read_text(encoding="utf-8"))
        self.assertEqual(_manifest_for(SKILL_ROOT, "0.1.1"), manifest)

    def test_strict_version_comparison(self) -> None:
        self.assertLess(UPDATE.parse_version("0.1.1"), UPDATE.parse_version("0.1.2"))
        self.assertLess(UPDATE.parse_version("0.9.9"), UPDATE.parse_version("0.10.0"))
        for invalid in ("v0.1.1", "0.1", "01.1.1", "0.1.1-rc.1"):
            with self.subTest(invalid=invalid), self.assertRaises(UPDATE.UpdateError):
                UPDATE.parse_version(invalid)

    def test_tree_digest_excludes_only_the_release_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            skill = Path(temporary) / "vibe-diagram"
            _write_skill(skill, "0.1.1", "runtime one\n")
            (skill / "update.json").write_text("{}\n", encoding="utf-8")
            first = UPDATE.tree_sha256(skill)
            (skill / "update.json").write_text('{"changed": true}\n', encoding="utf-8")
            self.assertEqual(first, UPDATE.tree_sha256(skill))
            (skill / "references" / "runtime-workflow.md").write_text(
                "runtime two\n", encoding="utf-8"
            )
            self.assertNotEqual(first, UPDATE.tree_sha256(skill))

    def test_every_direct_invocation_fetches_the_stable_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            skill = Path(temporary) / "skills" / "vibe-diagram"
            _write_skill(skill, "0.1.1", "runtime\n")
            manifest = _manifest_for(skill, "0.1.1")
            calls = []

            def fetch_manifest() -> dict:
                calls.append("manifest")
                return manifest

            for _ in range(2):
                result = UPDATE.check_and_update(
                    skill,
                    fetch_manifest=fetch_manifest,
                    fetch_archive=lambda _ref, _target: self.fail("archive must not be fetched"),
                )
                self.assertEqual("current", result.status)
            self.assertEqual(["manifest", "manifest"], calls)

    def test_managed_package_skips_network_update(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            package = Path(temporary) / "package"
            skill = package / "skills" / "vibe-diagram"
            _write_skill(skill, "0.1.1", "runtime\n")
            (package / "VERSION").write_text("0.1.1\n", encoding="ascii")
            (package / "LICENSE").write_text("license\n", encoding="utf-8")
            result = UPDATE.check_and_update(
                skill,
                fetch_manifest=lambda: self.fail("managed packages must not fetch"),
                fetch_archive=lambda _ref, _target: self.fail("managed packages must not fetch"),
            )
            self.assertEqual("managed", result.status)

    def test_generated_package_manifest_skips_network_without_root_version(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            package = Path(temporary) / "package"
            skill = package / "skills" / "vibe-diagram"
            _write_skill(skill, "0.1.1", "runtime\n")
            (package / "LICENSE").write_text("license\n", encoding="utf-8")
            manifest = package / ".bundle" / "plugin.json"
            manifest.parent.mkdir(parents=True)
            manifest.write_text(
                json.dumps({"name": "vibe-diagram", "version": "0.1.1"}) + "\n",
                encoding="utf-8",
            )
            result = UPDATE.check_and_update(
                skill,
                fetch_manifest=lambda: self.fail("generated packages must not fetch"),
                fetch_archive=lambda _ref, _target: self.fail("generated packages must not fetch"),
            )
            self.assertEqual("managed", result.status)

    def test_offline_check_keeps_the_installed_version(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            skill = Path(temporary) / "skills" / "vibe-diagram"
            _write_skill(skill, "0.1.1", "runtime\n")

            def offline() -> dict:
                raise OSError("offline")

            result = UPDATE.check_and_update(
                skill,
                fetch_manifest=offline,
                fetch_archive=lambda _ref, _target: self.fail("archive must not be fetched"),
            )
            self.assertEqual("offline", result.status)
            self.assertEqual("0.1.1", (skill / "VERSION").read_text(encoding="ascii").strip())

    def test_newer_release_is_verified_backed_up_and_activated(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            skill = base / "skills" / "vibe-diagram"
            candidate = base / "candidate"
            archive = base / "candidate.zip"
            _write_skill(skill, "0.1.1", "old runtime\n")
            _write_skill(candidate, "0.1.2", "new runtime\n")
            manifest = _seal_manifest(candidate, "0.1.2")
            _write_archive(archive, candidate, "0.1.2")

            def fetch_archive(_ref: str, target: Path) -> None:
                shutil.copy2(archive, target)

            result = UPDATE.check_and_update(
                skill,
                fetch_manifest=lambda: manifest,
                fetch_archive=fetch_archive,
            )
            self.assertEqual("updated", result.status, result.message)
            self.assertEqual("0.1.2", (skill / "VERSION").read_text(encoding="ascii").strip())
            self.assertEqual(
                "new runtime\n",
                (skill / "references" / "runtime-workflow.md").read_text(encoding="utf-8"),
            )
            self.assertIsNotNone(result.backup_path)
            self.assertEqual(
                "0.1.1",
                (Path(result.backup_path) / "VERSION").read_text(encoding="ascii").strip(),
            )

    def test_invalid_release_keeps_current_tree(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            skill = base / "skills" / "vibe-diagram"
            candidate = base / "candidate"
            archive = base / "candidate.zip"
            _write_skill(skill, "0.1.1", "old runtime\n")
            _write_skill(candidate, "0.1.2", "tampered runtime\n")
            manifest = _seal_manifest(candidate, "0.1.2")
            manifest["tree_sha256"] = "0" * 64
            _write_archive(archive, candidate, "0.1.2")

            result = UPDATE.check_and_update(
                skill,
                fetch_manifest=lambda: manifest,
                fetch_archive=lambda _ref, target: shutil.copy2(archive, target),
            )
            self.assertEqual("failed", result.status)
            self.assertEqual("0.1.1", (skill / "VERSION").read_text(encoding="ascii").strip())
            self.assertEqual(
                "old runtime\n",
                (skill / "references" / "runtime-workflow.md").read_text(encoding="utf-8"),
            )

    def test_rollback_restores_the_newest_recoverable_backup(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            skill = base / "skills" / "vibe-diagram"
            backup = base / "backups" / "skills" / "vibe-diagram-0.1.1-20260720000000"
            _write_skill(skill, "0.1.2", "current runtime\n")
            _write_skill(backup, "0.1.1", "restored runtime\n")

            result = UPDATE.rollback(skill)

            self.assertEqual("rolled_back", result.status)
            self.assertEqual("0.1.1", (skill / "VERSION").read_text(encoding="ascii").strip())
            self.assertEqual(
                "restored runtime\n",
                (skill / "references" / "runtime-workflow.md").read_text(encoding="utf-8"),
            )
            self.assertIsNotNone(result.backup_path)
            self.assertEqual(
                "0.1.2",
                (Path(result.backup_path) / "VERSION").read_text(encoding="ascii").strip(),
            )

    def test_archive_path_traversal_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            archive_path = base / "unsafe.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr(
                    "vibe-diagram-0.1.2/skills/vibe-diagram/VERSION",
                    "0.1.2\n",
                )
                archive.writestr(
                    "vibe-diagram-0.1.2/skills/vibe-diagram/../escaped.txt",
                    "unsafe\n",
                )
            with self.assertRaises(UPDATE.UpdateError):
                UPDATE.stage_archive(archive_path, base / "staging")
            self.assertFalse((base / "escaped.txt").exists())

    def test_readme_exposes_fixed_install_and_manual_update_commands(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn(
            "https://github.com/imchenway/vibe-diagram/tree/stable/skills/vibe-diagram",
            readme,
        )
        self.assertIn("update_skill.py", readme)
        self.assertIn("--force-check", readme)


if __name__ == "__main__":
    unittest.main()
