from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.build_packages import (
    BuildError,
    ValidationError,
    assemble_build_tree,
    assemble_publication_tree,
    check_publication,
    first_publication_drift,
    read_json_unique,
    tree_record,
    validate_publication_tree,
)


ROOT = Path(__file__).resolve().parents[1]


def _file_bytes(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file() and not path.is_symlink()
    }


def _copy_repository_for_publication_check(source: Path, destination: Path) -> None:
    def ignore(directory: str, names: list[str]) -> set[str]:
        ignored = {
            name for name in names if name == "__pycache__" or name.endswith(".pyc")
        }
        if Path(directory) == source:
            ignored.update(
                name
                for name in names
                if name in {"build", "plugins", ".agents", ".publication.backup"}
                or name.startswith(".publication.staging-")
            )
        return ignored

    shutil.copytree(
        source,
        destination,
        ignore=ignore,
    )


class PublicationProjectionTests(unittest.TestCase):
    def test_first_publication_drift_reports_every_supported_drift_class(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            expected = base / "expected"
            expected.mkdir()
            assemble_publication_tree(ROOT, expected)
            relative_skill = Path("plugins/vibe-diagram/skills/vibe-diagram/SKILL.md")

            def remove_skill(actual: Path) -> None:
                (actual / relative_skill).unlink()

            def add_extra(actual: Path) -> None:
                (actual / "plugins" / "vibe-diagram" / "extra.txt").write_bytes(b"extra\n")

            def change_bytes(actual: Path) -> None:
                skill = actual / relative_skill
                skill.write_bytes(skill.read_bytes() + b"\n")

            def replace_with_symlink(actual: Path) -> None:
                skill = actual / relative_skill
                skill.unlink()
                skill.symlink_to(ROOT / "skills" / "vibe-diagram" / "SKILL.md")

            def add_executable_bit(actual: Path) -> None:
                skill = actual / relative_skill
                skill.chmod(skill.stat().st_mode | 0o100)

            cases = (
                ("missing", remove_skill),
                ("extra", add_extra),
                ("bytes", change_bytes),
                ("symlink", replace_with_symlink),
                ("mode", add_executable_bit),
            )
            for index, (keyword, mutate) in enumerate(cases):
                with self.subTest(drift=keyword):
                    actual = base / f"actual-{index}"
                    shutil.copytree(expected, actual)
                    mutate(actual)

                    drift = first_publication_drift(expected, actual)

                    self.assertIsInstance(drift, str)
                    self.assertIn(keyword, drift.lower())

    def test_first_publication_drift_orders_candidates_by_utf8_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            expected = base / "expected"
            expected.mkdir()
            assemble_publication_tree(ROOT, expected)

            mixed = base / "mixed"
            shutil.copytree(expected, mixed)
            catalog = mixed / ".agents" / "plugins" / "marketplace.json"
            catalog.write_bytes(catalog.read_bytes() + b"\n")
            skill = mixed / "plugins" / "vibe-diagram" / "skills" / "vibe-diagram" / "SKILL.md"
            skill.chmod(skill.stat().st_mode | 0o100)

            drift = first_publication_drift(expected, mixed)

            self.assertIsInstance(drift, str)
            self.assertIn(".agents/plugins/marketplace.json", drift)
            self.assertIn("bytes", drift.lower())

            missing = base / "missing"
            shutil.copytree(expected, missing)
            shutil.rmtree(missing / "plugins" / "vibe-diagram")
            (missing / ".agents" / "plugins" / "marketplace.json").unlink()

            drift = first_publication_drift(expected, missing)

            self.assertIsInstance(drift, str)
            self.assertIn(".agents/plugins/marketplace.json", drift)
            self.assertIn("missing", drift.lower())

    def test_first_publication_drift_sorts_invalid_objects_independent_of_creation_order(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            expected = base / "expected"
            expected.mkdir()
            assemble_publication_tree(ROOT, expected)
            references = Path("plugins/vibe-diagram/skills/vibe-diagram/references")
            earlier = references / "decision-communication.md"
            later = references / "system-architecture.md"
            target = ROOT / "skills" / "vibe-diagram" / "SKILL.md"

            for index, order in enumerate(((earlier, later), (later, earlier))):
                with self.subTest(order=tuple(path.name for path in order)):
                    actual = base / f"invalid-{index}"
                    shutil.copytree(expected, actual)
                    for relative in order:
                        path = actual / relative
                        path.unlink()
                        path.symlink_to(target)

                    drift = first_publication_drift(expected, actual)

                    self.assertIsInstance(drift, str)
                    self.assertIn(earlier.as_posix(), drift)
                    self.assertIn("symlink", drift.lower())

    def test_check_publication_is_read_only_and_accepts_an_exact_projection(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            repository = base / "repository"
            _copy_repository_for_publication_check(ROOT, repository)
            expected = base / "expected"
            expected.mkdir()
            assemble_publication_tree(repository, expected)
            shutil.copytree(expected / "plugins", repository / "plugins")
            shutil.copytree(expected / ".agents", repository / ".agents")

            def snapshot() -> dict[str, tuple[bytes, int]]:
                return {
                    path.relative_to(repository).as_posix(): (
                        path.read_bytes(),
                        path.stat().st_mode & 0o777,
                    )
                    for path in sorted(repository.rglob("*"))
                    if path.is_file() and not path.is_symlink()
                }

            before = snapshot()
            record = check_publication(repository)

            self.assertEqual("unverified", record["runtime_validation"])
            self.assertEqual(before, snapshot())
            self.assertEqual([], list(repository.glob(".publication.staging-*")))

    def test_publication_check_copy_excludes_preexisting_publication_state(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            source = base / "source"
            shutil.copytree(
                ROOT,
                source,
                ignore=shutil.ignore_patterns(
                    "build",
                    "plugins",
                    ".agents",
                    ".publication.backup",
                    ".publication.staging-*",
                    "__pycache__",
                    "*.pyc",
                ),
            )
            source_expected = base / "source-expected"
            source_expected.mkdir()
            assemble_publication_tree(source, source_expected)
            shutil.copytree(source_expected / "plugins", source / "plugins")
            shutil.copytree(source_expected / ".agents", source / ".agents")
            (source / "build").mkdir()
            (source / "build" / "sentinel.txt").write_bytes(b"build\n")
            (source / ".publication.backup").mkdir()
            (source / ".publication.backup" / "sentinel.txt").write_bytes(b"backup\n")
            (source / ".publication.staging-old").mkdir()
            (source / ".publication.staging-old" / "sentinel.txt").write_bytes(b"staging\n")
            (source / "tests" / "__pycache__").mkdir(exist_ok=True)
            (source / "tests" / "__pycache__" / "sentinel.pyc").write_bytes(b"cache\n")

            repository = base / "repository"
            _copy_repository_for_publication_check(source, repository)

            for relative in (
                "build",
                "plugins",
                ".agents",
                ".publication.backup",
                ".publication.staging-old",
                "tests/__pycache__",
            ):
                self.assertFalse((repository / relative).exists(), relative)

            expected = base / "expected"
            expected.mkdir()
            record = assemble_publication_tree(repository, expected)
            shutil.copytree(expected / "plugins", repository / "plugins")
            shutil.copytree(expected / ".agents", repository / ".agents")
            self.assertEqual(record, check_publication(repository))

    def test_check_publication_preserves_original_and_cleanup_failures(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            repository = base / "repository"
            _copy_repository_for_publication_check(ROOT, repository)
            expected = base / "expected"
            expected.mkdir()
            assemble_publication_tree(repository, expected)
            shutil.copytree(expected / "plugins", repository / "plugins")
            shutil.copytree(expected / ".agents", repository / ".agents")
            relative_skill = Path("plugins/vibe-diagram/skills/vibe-diagram/SKILL.md")
            skill = repository / relative_skill
            skill.write_bytes(skill.read_bytes() + b"\n")
            cleanup_error = BuildError("injected publication staging cleanup failure")

            with patch(
                "scripts.build_packages._remove_staging",
                side_effect=cleanup_error,
            ), self.assertRaises(BuildError) as context:
                check_publication(repository)

            message = str(context.exception).lower()
            self.assertIn("bytes", message)
            self.assertIn(relative_skill.as_posix().lower(), message)
            self.assertIn(str(cleanup_error).lower(), message)

            skill.write_bytes((expected / relative_skill).read_bytes())
            for staged in repository.glob(".publication.staging-*"):
                shutil.rmtree(staged)
            cleanup_only = BuildError("injected cleanup-only failure")
            with patch(
                "scripts.build_packages._remove_staging",
                side_effect=cleanup_only,
            ), self.assertRaises(BuildError) as context:
                check_publication(repository)
            self.assertIs(cleanup_only, context.exception)

    def test_publication_is_deterministic_and_matches_codex_package(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            first = base / "first-publication"
            second = base / "second-publication"
            build = base / "build"
            first.mkdir()
            second.mkdir()
            build.mkdir()

            first_record = assemble_publication_tree(ROOT, first)
            second_record = assemble_publication_tree(ROOT, second)
            build_report = assemble_build_tree(ROOT, build)

            self.assertEqual(first_record, second_record)
            self.assertEqual(_file_bytes(first), _file_bytes(second))
            self.assertEqual(
                {
                    "package_version",
                    "plugin_manifest_sha256",
                    "plugin_tree_sha256",
                    "marketplace_sha256",
                    "runtime_validation",
                },
                set(first_record),
            )
            self.assertEqual("unverified", first_record["runtime_validation"])

            codex_package = build / "codex"
            publication_plugin = first / "plugins" / "vibe-diagram"
            self.assertEqual(tree_record(codex_package), tree_record(publication_plugin))
            self.assertEqual(_file_bytes(codex_package), _file_bytes(publication_plugin))
            codex_modes = {
                relative: (codex_package / relative).stat().st_mode & 0o111
                for relative in _file_bytes(codex_package)
            }
            publication_modes = {
                relative: (publication_plugin / relative).stat().st_mode & 0o111
                for relative in _file_bytes(publication_plugin)
            }
            self.assertEqual(codex_modes, publication_modes)

            codex_report = build_report["clients"]["codex"]
            self.assertEqual(
                codex_report["manifest_sha256"],
                first_record["plugin_manifest_sha256"],
            )
            self.assertEqual(
                codex_report["package"]["tree_sha256"],
                first_record["plugin_tree_sha256"],
            )
            self.assertEqual(first_record, validate_publication_tree(ROOT, first))

    def test_marketplace_catalog_is_exact_and_deterministic(self) -> None:
        expected = {
            "name": "imchenway",
            "interface": {"displayName": "imchenway"},
            "plugins": [
                {
                    "name": "vibe-diagram",
                    "source": {
                        "source": "local",
                        "path": "./plugins/vibe-diagram",
                    },
                    "policy": {
                        "installation": "AVAILABLE",
                        "authentication": "ON_INSTALL",
                    },
                    "category": "Developer Tools",
                }
            ],
        }
        expected_bytes = (
            json.dumps(
                expected,
                ensure_ascii=True,
                allow_nan=False,
                indent=2,
                sort_keys=True,
            )
            + "\n"
        ).encode("utf-8")

        with tempfile.TemporaryDirectory() as temporary:
            publication = Path(temporary) / "publication"
            publication.mkdir()
            record = assemble_publication_tree(ROOT, publication)
            catalog = publication / ".agents" / "plugins" / "marketplace.json"

            self.assertEqual(expected, read_json_unique(catalog))
            self.assertEqual(expected_bytes, catalog.read_bytes())
            self.assertNotIn(b'"products"', catalog.read_bytes())
            marketplace_sha256 = record["marketplace_sha256"]
            self.assertEqual(64, len(marketplace_sha256))
            self.assertTrue(
                all(character in "0123456789abcdef" for character in marketplace_sha256)
            )

    def test_catalog_write_failure_is_cleaned_and_same_destination_can_retry(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            publication = Path(temporary) / "publication"
            publication.mkdir()
            catalog = publication / ".agents" / "plugins" / "marketplace.json"
            original_write_bytes = Path.write_bytes
            catalog_write_attempted = False

            def fail_catalog_write(path: Path, payload: bytes) -> int:
                nonlocal catalog_write_attempted
                if path == catalog:
                    catalog_write_attempted = True
                    raise OSError("injected catalog write failure")
                return original_write_bytes(path, payload)

            with patch.object(Path, "write_bytes", new=fail_catalog_write):
                with self.assertRaises(BuildError) as context:
                    assemble_publication_tree(ROOT, publication)

            self.assertTrue(catalog_write_attempted)
            self.assertIn(str(catalog), str(context.exception))
            self.assertIn("injected catalog write failure", str(context.exception))
            self.assertTrue(publication.is_dir())
            self.assertEqual([], list(publication.iterdir()))

            record = assemble_publication_tree(ROOT, publication)
            self.assertEqual(record, validate_publication_tree(ROOT, publication))

    def test_final_validation_failure_is_cleaned_and_same_destination_can_retry(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            publication = Path(temporary) / "publication"
            publication.mkdir()
            injected = ValidationError("injected final publication validation failure")

            with patch(
                "scripts.build_packages.validate_publication_tree",
                side_effect=injected,
            ):
                with self.assertRaises(BuildError) as context:
                    assemble_publication_tree(ROOT, publication)

            self.assertIs(type(context.exception), ValidationError)
            self.assertIs(context.exception, injected)
            self.assertTrue(publication.is_dir())
            self.assertEqual([], list(publication.iterdir()))

            record = assemble_publication_tree(ROOT, publication)
            self.assertEqual(record, validate_publication_tree(ROOT, publication))

    def test_cleanup_failure_reports_original_and_cleanup_errors(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            publication = Path(temporary) / "publication"
            publication.mkdir()
            original_message = "injected final publication validation failure"
            cleanup_message = "injected publication cleanup failure"

            with patch(
                "scripts.build_packages.validate_publication_tree",
                side_effect=ValidationError(original_message),
            ), patch(
                "scripts.build_packages.shutil.rmtree",
                side_effect=OSError(cleanup_message),
            ):
                with self.assertRaises(BuildError) as context:
                    assemble_publication_tree(ROOT, publication)

            message = str(context.exception)
            self.assertIn(original_message, message)
            self.assertIn(cleanup_message, message)
            self.assertTrue(any(publication.iterdir()))

    def test_validate_publication_tree_rejects_catalog_and_manifest_drift(self) -> None:
        expected = {
            "name": "imchenway",
            "interface": {"displayName": "imchenway"},
            "plugins": [
                {
                    "name": "vibe-diagram",
                    "source": {
                        "source": "local",
                        "path": "./plugins/vibe-diagram",
                    },
                    "policy": {
                        "installation": "AVAILABLE",
                        "authentication": "ON_INSTALL",
                    },
                    "category": "Developer Tools",
                }
            ],
        }

        def serialized(value: object) -> bytes:
            return (
                json.dumps(
                    value,
                    ensure_ascii=True,
                    allow_nan=False,
                    indent=2,
                    sort_keys=True,
                )
                + "\n"
            ).encode("utf-8")

        missing_root_field = json.loads(json.dumps(expected))
        del missing_root_field["interface"]
        extra_root_field = json.loads(json.dumps(expected))
        extra_root_field["unexpected"] = True
        wrong_source_path = json.loads(json.dumps(expected))
        wrong_source_path["plugins"][0]["source"]["path"] = "./plugins/other"
        wrong_policy = json.loads(json.dumps(expected))
        wrong_policy["plugins"][0]["policy"]["authentication"] = "NONE"
        wrong_category = json.loads(json.dumps(expected))
        wrong_category["plugins"][0]["category"] = "Other"
        two_plugins = json.loads(json.dumps(expected))
        two_plugins["plugins"].append(json.loads(json.dumps(expected["plugins"][0])))
        canonical_bytes = serialized(expected)
        duplicate_key = canonical_bytes.replace(
            b'  "name": "imchenway",',
            b'  "name": "imchenway",\n  "name": "imchenway",',
            1,
        )
        catalog_cases = (
            ("missing-root-field", serialized(missing_root_field)),
            ("extra-root-field", serialized(extra_root_field)),
            ("duplicate-json-key", duplicate_key),
            ("array-root", b"[]\n"),
            ("nan", b'{"name":NaN}\n'),
            ("wrong-source-path", serialized(wrong_source_path)),
            ("wrong-policy", serialized(wrong_policy)),
            ("wrong-category", serialized(wrong_category)),
            ("two-plugins", serialized(two_plugins)),
            (
                "non-canonical-whitespace",
                json.dumps(
                    expected,
                    ensure_ascii=True,
                    allow_nan=False,
                    sort_keys=True,
                ).encode("utf-8"),
            ),
        )

        for name, payload in catalog_cases:
            with self.subTest(catalog=name), tempfile.TemporaryDirectory() as temporary:
                publication = Path(temporary) / "publication"
                publication.mkdir()
                assemble_publication_tree(ROOT, publication)
                catalog = publication / ".agents" / "plugins" / "marketplace.json"
                catalog.write_bytes(payload)

                with self.assertRaises(ValidationError) as context:
                    validate_publication_tree(ROOT, publication)
                message = str(context.exception).lower()
                self.assertTrue(
                    "catalog" in message
                    or "marketplace.json" in message
                    or str(catalog).lower() in message,
                    message,
                )

        for field, value in (("name", "other-plugin"), ("version", "9.9.9")):
            with self.subTest(manifest=field), tempfile.TemporaryDirectory() as temporary:
                publication = Path(temporary) / "publication"
                publication.mkdir()
                assemble_publication_tree(ROOT, publication)
                manifest_path = (
                    publication
                    / "plugins"
                    / "vibe-diagram"
                    / ".codex-plugin"
                    / "plugin.json"
                )
                manifest = read_json_unique(manifest_path)
                manifest[field] = value
                manifest_path.write_bytes(serialized(manifest))

                with self.assertRaises(ValidationError) as context:
                    validate_publication_tree(ROOT, publication)
                message = str(context.exception).lower()
                self.assertTrue(
                    "manifest" in message or "version" in message or str(manifest_path) in message,
                    message,
                )


if __name__ == "__main__":
    unittest.main()
