from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import scripts.build_packages as build_packages
from scripts.build_packages import (
    BuildError,
    CLIENTS,
    DeterminismError,
    PUBLICATION_JOURNAL,
    PUBLICATION_PHASES,
    PublishError,
    assemble_build_tree,
    assemble_publication_tree,
    build_all,
    main,
    parse_args,
    replace_build_transactionally,
    sync_publication,
    tree_record,
    update_tree_sha256,
    validate_publication_tree,
)


ROOT = Path(__file__).resolve().parents[1]


def _copy_repository(destination: Path, *, seed_publication: bool = True) -> None:
    destination.mkdir()
    for name in ("LICENSE", "VERSION"):
        shutil.copy2(ROOT / name, destination / name)
    for name in ("contracts", "adapters", "skills", "scripts"):
        shutil.copytree(
            ROOT / name,
            destination / name,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
    if seed_publication:
        with tempfile.TemporaryDirectory(dir=destination.parent) as temporary:
            expected = Path(temporary) / "publication"
            expected.mkdir()
            assemble_publication_tree(destination, expected)
            shutil.copytree(expected / "plugins", destination / "plugins")
            shutil.copytree(expected / ".agents", destination / ".agents")


def _set_repository_version(repository: Path, version: str) -> None:
    """Keep the repository and canonical Skill version contract in sync."""
    (repository / "VERSION").write_text(f"{version}\n", encoding="ascii")
    skill_root = repository / "skills" / "vibe-diagram"
    (skill_root / "VERSION").write_text(f"{version}\n", encoding="ascii")
    manifest_path = skill_root / "update.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["version"] = version
    manifest["ref"] = f"v{version}"
    manifest["tree_sha256"] = update_tree_sha256(repository)
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _file_bytes(root: Path) -> dict[str, bytes]:
    if not root.exists():
        return {}
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file() and not path.is_symlink()
    }


def _run_cli(root: Path, *arguments: str, home: Path | None = None) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    if home is not None:
        environment["HOME"] = str(home)
    return subprocess.run(
        [sys.executable, str(root / "scripts" / "build_packages.py"), *arguments],
        cwd=root,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )


class BuildTransactionTests(unittest.TestCase):
    def test_sync_publication_initial_publish_is_valid_and_second_sync_is_noop(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary) / "repository"
            _copy_repository(repository, seed_publication=False)

            first_record, first_changed, first_cleanup_pending = sync_publication(repository)

            self.assertTrue(first_changed)
            self.assertFalse(first_cleanup_pending)
            self.assertEqual(first_record, validate_publication_tree(repository, repository))
            plugin_before = _file_bytes(repository / "plugins" / "vibe-diagram")
            catalog_before = (
                repository / ".agents" / "plugins" / "marketplace.json"
            ).read_bytes()
            no_op_renames: list[tuple[Path, Path]] = []

            def observe_no_op_rename(source: Path, destination: Path) -> None:
                no_op_renames.append((source, destination))
                os.replace(source, destination)

            second_record, second_changed, second_cleanup_pending = sync_publication(
                repository,
                rename=observe_no_op_rename,
            )

            self.assertEqual(first_record, second_record)
            self.assertFalse(second_changed)
            self.assertFalse(second_cleanup_pending)
            self.assertEqual(
                plugin_before,
                _file_bytes(repository / "plugins" / "vibe-diagram"),
            )
            self.assertEqual(
                catalog_before,
                (repository / ".agents" / "plugins" / "marketplace.json").read_bytes(),
            )
            self.assertFalse((repository / ".publication.backup").exists())
            self.assertEqual([], list(repository.glob(".publication.staging-*")))
            self.assertEqual([], no_op_renames)

    def test_publication_backup_and_split_pair_fail_before_staging(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            repository = base / "residual-backup"
            _copy_repository(repository)
            target_before = {
                "plugin": _file_bytes(repository / "plugins" / "vibe-diagram"),
                "catalog": (
                    repository / ".agents" / "plugins" / "marketplace.json"
                ).read_bytes(),
            }
            backup = repository / ".publication.backup"
            backup.mkdir()
            (backup / "sentinel.txt").write_bytes(b"preserve\n")

            with self.assertRaisesRegex(PublishError, "backup"):
                sync_publication(repository)
            with self.assertRaisesRegex(PublishError, "backup"):
                build_all(repository, check=True)

            self.assertEqual(
                target_before["plugin"],
                _file_bytes(repository / "plugins" / "vibe-diagram"),
            )
            self.assertEqual(
                target_before["catalog"],
                (repository / ".agents" / "plugins" / "marketplace.json").read_bytes(),
            )
            self.assertEqual(b"preserve\n", (backup / "sentinel.txt").read_bytes())
            self.assertEqual([], list(repository.glob(".publication.staging-*")))

            for retained in ("plugin", "catalog"):
                with self.subTest(retained=retained):
                    split = base / f"split-{retained}"
                    _copy_repository(split)
                    if retained == "plugin":
                        (split / ".agents" / "plugins" / "marketplace.json").unlink()
                    else:
                        shutil.rmtree(split / "plugins" / "vibe-diagram")
                    before = _file_bytes(split)

                    with self.assertRaisesRegex(PublishError, "both"):
                        sync_publication(split)

                    self.assertEqual(before, _file_bytes(split))
                    self.assertFalse((split / ".publication.backup").exists())
                    self.assertEqual([], list(split.glob(".publication.staging-*")))

    def test_sync_combines_pretransaction_error_with_staging_cleanup_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary) / "repository"
            _copy_repository(repository, seed_publication=False)
            original = BuildError("injected publication assembly failure")
            cleanup = BuildError("injected secondary staging cleanup failure")

            with patch(
                "scripts.build_packages.assemble_publication_tree",
                side_effect=original,
            ), patch(
                "scripts.build_packages._remove_staging",
                side_effect=cleanup,
            ) as cleanup_call, self.assertRaises(BuildError) as raised:
                sync_publication(repository)

            message = str(raised.exception)
            self.assertIn("assembly failure", message)
            self.assertIn("secondary staging cleanup failure", message)
            cleanup_call.assert_called_once()
            self.assertFalse((repository / ".publication.backup").exists())
            self.assertEqual(1, len(list(repository.glob(".publication.staging-*"))))

    def test_sync_preserves_interrupt_type_and_chains_staging_cleanup_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary) / "repository"
            _copy_repository(repository, seed_publication=False)
            original = KeyboardInterrupt("injected pretransaction interrupt")
            cleanup = BuildError("injected interrupt staging cleanup failure")

            with patch(
                "scripts.build_packages.assemble_publication_tree",
                side_effect=original,
            ), patch(
                "scripts.build_packages._remove_staging",
                side_effect=cleanup,
            ) as cleanup_call, self.assertRaises(KeyboardInterrupt) as raised:
                sync_publication(repository)

            self.assertIn("pretransaction interrupt", str(raised.exception))
            self.assertIs(cleanup, raised.exception.__cause__)
            cleanup_call.assert_called_once()
            self.assertFalse((repository / ".publication.backup").exists())
            self.assertEqual(1, len(list(repository.glob(".publication.staging-*"))))

    def test_publication_journal_is_deterministic_and_tracks_payload_phases(self) -> None:
        expected_fields = {
            "schema_version",
            "package_version",
            "plugin_existed",
            "catalog_existed",
            "created_parent_paths",
            "phase",
        }
        allowed_parents = {"plugins", ".agents", ".agents/plugins"}
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            for state in ("initial", "update"):
                with self.subTest(state=state):
                    repository = base / state
                    _copy_repository(repository, seed_publication=state == "update")
                    if state == "update":
                        _set_repository_version(repository, "1.2.3")
                    backup = repository / ".publication.backup"
                    journal_path = backup / PUBLICATION_JOURNAL
                    snapshots: list[tuple[dict[str, object], bytes]] = []
                    payload_phases: list[str] = []

                    def observing_rename(source: Path, destination: Path) -> None:
                        if destination == journal_path:
                            os.replace(source, destination)
                            raw = destination.read_bytes()
                            snapshots.append((json.loads(raw), raw))
                            return
                        payload_phases.append(
                            json.loads(journal_path.read_text(encoding="utf-8"))["phase"]
                        )
                        os.replace(source, destination)

                    _, changed, cleanup_pending = sync_publication(
                        repository,
                        rename=observing_rename,
                    )

                    self.assertTrue(changed)
                    self.assertFalse(cleanup_pending)
                    phases: list[str] = []
                    for payload, raw in snapshots:
                        self.assertEqual(expected_fields, set(payload))
                        self.assertIs(type(payload["schema_version"]), int)
                        self.assertEqual(1, payload["schema_version"])
                        self.assertIn(payload["phase"], PUBLICATION_PHASES)
                        parents = payload["created_parent_paths"]
                        self.assertIsInstance(parents, list)
                        self.assertEqual(sorted(set(parents)), parents)
                        self.assertLessEqual(set(parents), allowed_parents)
                        encoded = json.dumps(payload, sort_keys=True)
                        self.assertNotIn(str(repository), encoded)
                        self.assertNotIn("timestamp", encoded.lower())
                        self.assertNotIn(".publication.staging-", encoded)
                        self.assertEqual(
                            (
                                json.dumps(
                                    payload,
                                    ensure_ascii=True,
                                    allow_nan=False,
                                    indent=2,
                                    sort_keys=True,
                                )
                                + "\n"
                            ).encode("utf-8"),
                            raw,
                        )
                        phase = payload["phase"]
                        if not phases or phases[-1] != phase:
                            phases.append(phase)

                    if state == "initial":
                        self.assertEqual(
                            [
                                "backup-created",
                                "plugin-promoted",
                                "catalog-promoted",
                                "validated",
                            ],
                            phases,
                        )
                        self.assertEqual(
                            ["backup-created", "plugin-promoted"],
                            payload_phases,
                        )
                    else:
                        self.assertEqual(
                            [
                                "backup-created",
                                "plugin-backed-up",
                                "catalog-backed-up",
                                "plugin-promoted",
                                "catalog-promoted",
                                "validated",
                            ],
                            phases,
                        )
                        self.assertEqual(
                            [
                                "backup-created",
                                "plugin-backed-up",
                                "catalog-backed-up",
                                "plugin-promoted",
                            ],
                            payload_phases,
                        )

    def test_publication_failure_matrix_rolls_back_initial_and_update_pairs(self) -> None:
        failure_points = {
            "initial": ("plugin-promote", "catalog-promote", "final-validate"),
            "update": (
                "plugin-backup",
                "catalog-backup",
                "plugin-promote",
                "catalog-promote",
                "final-validate",
            ),
        }
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            for state, points in failure_points.items():
                for point in points:
                    with self.subTest(state=state, point=point):
                        repository = base / f"{state}-{point}"
                        _copy_repository(repository, seed_publication=state == "update")
                        plugin = repository / "plugins" / "vibe-diagram"
                        catalog = repository / ".agents" / "plugins" / "marketplace.json"
                        old_plugin = _file_bytes(plugin)
                        old_catalog = catalog.read_bytes() if catalog.is_file() else None
                        if state == "update":
                            _set_repository_version(repository, "1.2.3")
                        backup = repository / ".publication.backup"

                        def operation(source: Path, destination: Path) -> str | None:
                            if destination == backup / "plugins" / "vibe-diagram":
                                return "plugin-backup"
                            if destination == backup / ".agents" / "plugins" / "marketplace.json":
                                return "catalog-backup"
                            if destination == plugin:
                                return "plugin-promote"
                            if destination == catalog:
                                return "catalog-promote"
                            return None

                        failure_injected = False

                        def failing_rename(source: Path, destination: Path) -> None:
                            nonlocal failure_injected
                            if not failure_injected and operation(source, destination) == point:
                                failure_injected = True
                                raise OSError(f"injected {point} failure")
                            os.replace(source, destination)

                        real_validate = build_packages.validate_publication_tree

                        def failing_final_validate(root: Path, publication_root: Path) -> dict:
                            if point == "final-validate" and publication_root == repository:
                                raise build_packages.ValidationError(
                                    "injected final-validate failure"
                                )
                            return real_validate(root, publication_root)

                        with patch(
                            "scripts.build_packages.validate_publication_tree",
                            side_effect=failing_final_validate,
                        ), self.assertRaisesRegex(PublishError, f"injected {point}"):
                            sync_publication(repository, rename=failing_rename)

                        if state == "initial":
                            self.assertFalse(plugin.exists())
                            self.assertFalse(catalog.exists())
                        else:
                            self.assertEqual(old_plugin, _file_bytes(plugin))
                            self.assertEqual(old_catalog, catalog.read_bytes())
                        self.assertFalse(backup.exists())
                        self.assertEqual([], list(repository.glob(".publication.staging-*")))

    def test_publication_journal_rename_failure_matrix_rolls_back_cleanly(self) -> None:
        cases = {
            "initial": (
                ("initial-journal", 1, "backup-created", []),
                ("parent-agents", 2, "backup-created", [".agents"]),
                (
                    "parent-marketplace",
                    3,
                    "backup-created",
                    [".agents", ".agents/plugins"],
                ),
                (
                    "parent-plugins",
                    4,
                    "backup-created",
                    [".agents", ".agents/plugins", "plugins"],
                ),
                (
                    "plugin-promoted",
                    5,
                    "plugin-promoted",
                    [".agents", ".agents/plugins", "plugins"],
                ),
                (
                    "catalog-promoted",
                    6,
                    "catalog-promoted",
                    [".agents", ".agents/plugins", "plugins"],
                ),
                (
                    "validated",
                    7,
                    "validated",
                    [".agents", ".agents/plugins", "plugins"],
                ),
            ),
            "update": (
                ("initial-journal", 1, "backup-created", []),
                ("plugin-backed-up", 2, "plugin-backed-up", []),
                ("catalog-backed-up", 3, "catalog-backed-up", []),
                ("plugin-promoted", 4, "plugin-promoted", []),
                ("catalog-promoted", 5, "catalog-promoted", []),
                ("validated", 6, "validated", []),
            ),
        }
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            for state, state_cases in cases.items():
                for label, failing_write, expected_phase, expected_parents in state_cases:
                    with self.subTest(state=state, label=label):
                        repository = base / f"{state}-{label}"
                        _copy_repository(
                            repository,
                            seed_publication=state == "update",
                        )
                        plugin = repository / "plugins" / "vibe-diagram"
                        catalog = repository / ".agents" / "plugins" / "marketplace.json"
                        old_plugin = _file_bytes(plugin)
                        old_catalog = catalog.read_bytes() if catalog.is_file() else None
                        if state == "update":
                            _set_repository_version(repository, "1.2.3")
                        backup = repository / ".publication.backup"
                        journal_path = backup / PUBLICATION_JOURNAL
                        journal_writes = 0
                        failed_payload: dict[str, object] = {}

                        def fail_selected_journal_write(
                            source: Path,
                            destination: Path,
                        ) -> None:
                            nonlocal journal_writes
                            if destination == journal_path:
                                journal_writes += 1
                                payload = json.loads(source.read_text(encoding="utf-8"))
                                if journal_writes == failing_write:
                                    failed_payload.update(payload)
                                    raise OSError(
                                        f"injected journal rename failure {label}"
                                    )
                            os.replace(source, destination)

                        with self.assertRaises(PublishError) as raised:
                            sync_publication(
                                repository,
                                rename=fail_selected_journal_write,
                            )

                        self.assertIn(label, str(raised.exception))
                        self.assertEqual(expected_phase, failed_payload["phase"])
                        self.assertEqual(
                            expected_parents,
                            failed_payload["created_parent_paths"],
                        )
                        if state == "initial":
                            self.assertFalse(plugin.exists())
                            self.assertFalse(catalog.exists())
                        else:
                            self.assertEqual(old_plugin, _file_bytes(plugin))
                            self.assertEqual(old_catalog, catalog.read_bytes())
                        self.assertFalse(backup.exists())
                        self.assertEqual(
                            [],
                            list(repository.glob(".publication.staging-*")),
                        )

    def test_journal_failure_with_rollback_rename_failure_preserves_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary) / "repository"
            _copy_repository(repository)
            _set_repository_version(repository, "1.2.3")
            plugin = repository / "plugins" / "vibe-diagram"
            catalog = repository / ".agents" / "plugins" / "marketplace.json"
            backup = repository / ".publication.backup"
            journal = backup / PUBLICATION_JOURNAL
            backup_catalog = backup / ".agents" / "plugins" / "marketplace.json"

            def fail_journal_then_rollback(source: Path, destination: Path) -> None:
                if destination == journal:
                    payload = json.loads(source.read_text(encoding="utf-8"))
                    if payload["phase"] == "plugin-promoted":
                        raise OSError("injected plugin-promoted journal failure")
                if source == backup_catalog and destination == catalog:
                    raise OSError("injected rollback rename failure")
                os.replace(source, destination)

            with self.assertRaises(PublishError) as raised:
                sync_publication(repository, rename=fail_journal_then_rollback)

            message = str(raised.exception)
            self.assertIn("plugin-promoted journal", message)
            self.assertIn("rollback rename", message)
            self.assertIn(str(backup), message)
            self.assertTrue(backup.is_dir())
            self.assertTrue(journal.is_file())
            self.assertEqual(1, len(list(repository.glob(".publication.staging-*"))))
            self.assertFalse(plugin.exists())
            self.assertFalse(catalog.exists())

    def test_publication_rollback_failure_preserves_recovery_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary) / "repository"
            _copy_repository(repository)
            _set_repository_version(repository, "1.2.3")
            plugin = repository / "plugins" / "vibe-diagram"
            catalog = repository / ".agents" / "plugins" / "marketplace.json"
            backup = repository / ".publication.backup"
            rollback_source = backup / "plugins" / "vibe-diagram"
            original_injected = False

            def fail_promotion_and_rollback(source: Path, destination: Path) -> None:
                nonlocal original_injected
                if destination == catalog and not original_injected:
                    original_injected = True
                    raise OSError("injected catalog-promote failure")
                if source == rollback_source and destination == plugin:
                    raise OSError("injected rollback failure")
                os.replace(source, destination)

            with self.assertRaises(PublishError) as raised:
                sync_publication(repository, rename=fail_promotion_and_rollback)

            message = str(raised.exception)
            self.assertIn("catalog-promote", message)
            self.assertIn("rollback", message)
            self.assertIn("staged", message)
            self.assertIn(str(backup), message)
            self.assertTrue(backup.is_dir())
            self.assertTrue((backup / PUBLICATION_JOURNAL).is_file())
            staging = list(repository.glob(".publication.staging-*"))
            self.assertEqual(1, len(staging))
            self.assertTrue(staging[0].is_dir())

    def test_keyboard_interrupt_after_initial_mutation_rolls_back_then_reraises(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary) / "repository"
            _copy_repository(repository, seed_publication=False)
            backup = repository / ".publication.backup"
            journal = backup / PUBLICATION_JOURNAL

            def interrupt_plugin_promoted_journal(source: Path, destination: Path) -> None:
                if destination == journal:
                    payload = json.loads(source.read_text(encoding="utf-8"))
                    if payload["phase"] == "plugin-promoted":
                        raise KeyboardInterrupt("injected post-mutation interrupt")
                os.replace(source, destination)

            with self.assertRaises(KeyboardInterrupt) as raised:
                sync_publication(
                    repository,
                    rename=interrupt_plugin_promoted_journal,
                )

            self.assertIn("post-mutation", str(raised.exception))
            self.assertFalse((repository / "plugins" / "vibe-diagram").exists())
            self.assertFalse(
                (repository / ".agents" / "plugins" / "marketplace.json").exists()
            )
            self.assertFalse(backup.exists())
            self.assertEqual([], list(repository.glob(".publication.staging-*")))

    def test_system_exit_after_update_mutation_rolls_back_then_reraises(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary) / "repository"
            _copy_repository(repository)
            plugin = repository / "plugins" / "vibe-diagram"
            catalog = repository / ".agents" / "plugins" / "marketplace.json"
            old_plugin = _file_bytes(plugin)
            old_catalog = catalog.read_bytes()
            _set_repository_version(repository, "1.2.3")
            backup = repository / ".publication.backup"
            journal = backup / PUBLICATION_JOURNAL

            def interrupt_catalog_backed_up_journal(source: Path, destination: Path) -> None:
                if destination == journal:
                    payload = json.loads(source.read_text(encoding="utf-8"))
                    if payload["phase"] == "catalog-backed-up":
                        raise SystemExit("injected post-mutation exit")
                os.replace(source, destination)

            with self.assertRaises(SystemExit) as raised:
                sync_publication(
                    repository,
                    rename=interrupt_catalog_backed_up_journal,
                )

            self.assertIn("post-mutation", str(raised.exception))
            self.assertEqual(old_plugin, _file_bytes(plugin))
            self.assertEqual(old_catalog, catalog.read_bytes())
            self.assertFalse(backup.exists())
            self.assertEqual([], list(repository.glob(".publication.staging-*")))

    def test_interrupt_with_rollback_failure_preserves_diagnostic_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary) / "repository"
            _copy_repository(repository)
            _set_repository_version(repository, "1.2.3")
            plugin = repository / "plugins" / "vibe-diagram"
            catalog = repository / ".agents" / "plugins" / "marketplace.json"
            backup = repository / ".publication.backup"
            journal = backup / PUBLICATION_JOURNAL
            backup_catalog = backup / ".agents" / "plugins" / "marketplace.json"

            def interrupt_then_fail_rollback(source: Path, destination: Path) -> None:
                if destination == journal:
                    payload = json.loads(source.read_text(encoding="utf-8"))
                    if payload["phase"] == "plugin-promoted":
                        raise KeyboardInterrupt("injected post-mutation interrupt")
                if source == backup_catalog and destination == catalog:
                    raise OSError("injected rollback rename failure")
                os.replace(source, destination)

            with self.assertRaises(PublishError) as raised:
                sync_publication(
                    repository,
                    rename=interrupt_then_fail_rollback,
                )

            message = str(raised.exception)
            self.assertIn("KeyboardInterrupt", message)
            self.assertIn("post-mutation", message)
            self.assertIn("rollback", message)
            self.assertIn(str(backup), message)
            self.assertTrue(backup.is_dir())
            self.assertTrue((backup / PUBLICATION_JOURNAL).is_file())
            self.assertEqual(1, len(list(repository.glob(".publication.staging-*"))))
            self.assertFalse(plugin.exists())
            self.assertFalse(catalog.exists())

    def test_publication_staging_cleanup_failure_marks_cleanup_pending(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary) / "repository"
            _copy_repository(repository)
            _set_repository_version(repository, "1.2.3")
            backup = repository / ".publication.backup"

            def fail_staging_cleanup(path: Path) -> None:
                if path.name.startswith(".publication.staging-"):
                    raise OSError("injected staging cleanup failure")
                shutil.rmtree(path)

            record, changed, cleanup_pending = sync_publication(
                repository,
                remove_tree=fail_staging_cleanup,
            )

            self.assertTrue(changed)
            self.assertTrue(cleanup_pending)
            self.assertEqual(record, validate_publication_tree(repository, repository))
            self.assertTrue(backup.is_dir())
            self.assertEqual(
                "cleanup-pending",
                json.loads(
                    (backup / PUBLICATION_JOURNAL).read_text(encoding="utf-8")
                )["phase"],
            )
            self.assertEqual(1, len(list(repository.glob(".publication.staging-*"))))
            with self.assertRaisesRegex(PublishError, "backup"):
                sync_publication(repository)

    def test_publication_backup_cleanup_failure_marks_cleanup_pending(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary) / "repository"
            _copy_repository(repository)
            _set_repository_version(repository, "1.2.3")
            backup = repository / ".publication.backup"

            def fail_backup_cleanup(path: Path) -> None:
                if path == backup:
                    raise OSError("injected backup cleanup failure")
                shutil.rmtree(path)

            record, changed, cleanup_pending = sync_publication(
                repository,
                remove_tree=fail_backup_cleanup,
            )

            self.assertTrue(changed)
            self.assertTrue(cleanup_pending)
            self.assertEqual(record, validate_publication_tree(repository, repository))
            self.assertTrue(backup.is_dir())
            self.assertEqual(
                "cleanup-pending",
                json.loads(
                    (backup / PUBLICATION_JOURNAL).read_text(encoding="utf-8")
                )["phase"],
            )
            self.assertEqual([], list(repository.glob(".publication.staging-*")))
            with self.assertRaisesRegex(PublishError, "backup"):
                sync_publication(repository)

    def test_final_staging_cleanup_silent_noop_becomes_cleanup_pending(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary) / "repository"
            _copy_repository(repository)
            _set_repository_version(repository, "1.2.3")
            backup = repository / ".publication.backup"

            def leave_staging(path: Path) -> None:
                if path.name.startswith(".publication.staging-"):
                    return
                shutil.rmtree(path)

            record, changed, cleanup_pending = sync_publication(
                repository,
                remove_tree=leave_staging,
            )

            self.assertTrue(changed)
            self.assertTrue(cleanup_pending)
            self.assertEqual(record, validate_publication_tree(repository, repository))
            self.assertTrue(backup.is_dir())
            self.assertEqual(
                "cleanup-pending",
                json.loads(
                    (backup / PUBLICATION_JOURNAL).read_text(encoding="utf-8")
                )["phase"],
            )
            self.assertEqual(1, len(list(repository.glob(".publication.staging-*"))))
            with self.assertRaisesRegex(PublishError, "backup"):
                sync_publication(repository)
            with self.assertRaisesRegex(PublishError, "backup"):
                build_packages.check_publication(repository)

    def test_final_backup_cleanup_silent_noop_becomes_cleanup_pending(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary) / "repository"
            _copy_repository(repository)
            _set_repository_version(repository, "1.2.3")
            backup = repository / ".publication.backup"

            def leave_backup(path: Path) -> None:
                if path == backup:
                    return
                shutil.rmtree(path)

            record, changed, cleanup_pending = sync_publication(
                repository,
                remove_tree=leave_backup,
            )

            self.assertTrue(changed)
            self.assertTrue(cleanup_pending)
            self.assertEqual(record, validate_publication_tree(repository, repository))
            self.assertTrue(backup.is_dir())
            self.assertEqual(
                "cleanup-pending",
                json.loads(
                    (backup / PUBLICATION_JOURNAL).read_text(encoding="utf-8")
                )["phase"],
            )
            self.assertEqual([], list(repository.glob(".publication.staging-*")))
            with self.assertRaisesRegex(PublishError, "backup"):
                sync_publication(repository)
            with self.assertRaisesRegex(PublishError, "backup"):
                build_packages.check_publication(repository)

    def test_initial_rollback_staging_cleanup_silent_noop_preserves_blocker(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary) / "repository"
            _copy_repository(repository, seed_publication=False)
            backup = repository / ".publication.backup"
            real_validate = build_packages.validate_publication_tree

            def fail_final_validate(root: Path, publication_root: Path) -> dict:
                if publication_root == repository:
                    raise build_packages.ValidationError(
                        "injected final-validate failure"
                    )
                return real_validate(root, publication_root)

            def leave_staging(path: Path) -> None:
                if path.name.startswith(".publication.staging-"):
                    return
                shutil.rmtree(path)

            with patch(
                "scripts.build_packages.validate_publication_tree",
                side_effect=fail_final_validate,
            ), self.assertRaises(PublishError) as raised:
                sync_publication(repository, remove_tree=leave_staging)

            self.assertIn("recovery cleanup", str(raised.exception))
            self.assertFalse((repository / "plugins" / "vibe-diagram").exists())
            self.assertFalse(
                (repository / ".agents" / "plugins" / "marketplace.json").exists()
            )
            self.assertTrue(backup.is_dir())
            self.assertEqual(
                "cleanup-pending",
                json.loads(
                    (backup / PUBLICATION_JOURNAL).read_text(encoding="utf-8")
                )["phase"],
            )
            self.assertEqual(1, len(list(repository.glob(".publication.staging-*"))))
            with self.assertRaisesRegex(PublishError, "backup"):
                sync_publication(repository)
            with self.assertRaisesRegex(PublishError, "backup"):
                build_packages.check_publication(repository)

    def test_update_rollback_backup_cleanup_silent_noop_preserves_blocker(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary) / "repository"
            _copy_repository(repository)
            plugin = repository / "plugins" / "vibe-diagram"
            catalog = repository / ".agents" / "plugins" / "marketplace.json"
            old_plugin = _file_bytes(plugin)
            old_catalog = catalog.read_bytes()
            _set_repository_version(repository, "1.2.3")
            backup = repository / ".publication.backup"
            real_validate = build_packages.validate_publication_tree

            def fail_final_validate(root: Path, publication_root: Path) -> dict:
                if publication_root == repository:
                    raise build_packages.ValidationError(
                        "injected final-validate failure"
                    )
                return real_validate(root, publication_root)

            def leave_backup(path: Path) -> None:
                if path == backup:
                    return
                shutil.rmtree(path)

            with patch(
                "scripts.build_packages.validate_publication_tree",
                side_effect=fail_final_validate,
            ), self.assertRaises(PublishError) as raised:
                sync_publication(repository, remove_tree=leave_backup)

            self.assertIn("recovery cleanup", str(raised.exception))
            self.assertEqual(old_plugin, _file_bytes(plugin))
            self.assertEqual(old_catalog, catalog.read_bytes())
            self.assertTrue(backup.is_dir())
            self.assertEqual(
                "cleanup-pending",
                json.loads(
                    (backup / PUBLICATION_JOURNAL).read_text(encoding="utf-8")
                )["phase"],
            )
            self.assertEqual(1, len(list(repository.glob(".publication.staging-*"))))
            with self.assertRaisesRegex(PublishError, "backup"):
                sync_publication(repository)
            with self.assertRaisesRegex(PublishError, "backup"):
                build_packages.check_publication(repository)

    def test_publication_backup_cleanup_delete_then_raise_reestablishes_fail_closed_marker(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary) / "repository"
            _copy_repository(repository)
            _set_repository_version(repository, "1.2.3")
            backup = repository / ".publication.backup"

            def delete_backup_then_fail(path: Path) -> None:
                shutil.rmtree(path)
                if path == backup:
                    raise OSError("injected backup cleanup deleted evidence")

            with self.assertRaises(PublishError) as raised:
                sync_publication(repository, remove_tree=delete_backup_then_fail)

            message = str(raised.exception)
            self.assertIn("cleanup", message)
            self.assertIn("evidence", message)
            self.assertIn("removed", message)
            self.assertIn(str(backup), message)
            self.assertEqual(
                "1.2.3",
                validate_publication_tree(repository, repository)["package_version"],
            )
            self.assertTrue(backup.is_dir())
            journal = backup / PUBLICATION_JOURNAL
            self.assertTrue(journal.is_file())
            self.assertEqual(
                "cleanup-pending",
                json.loads(journal.read_text(encoding="utf-8"))["phase"],
            )
            with self.assertRaisesRegex(PublishError, "backup"):
                sync_publication(repository)
            with self.assertRaisesRegex(PublishError, "backup"):
                build_packages.check_publication(repository)

    def test_unverifiable_old_backup_cleanup_failure_is_never_reported_as_plain_pending(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary) / "repository"
            _copy_repository(repository)
            old_plugin = repository / "plugins" / "vibe-diagram"
            (old_plugin / "drift-link").symlink_to("LICENSE")
            _set_repository_version(repository, "1.2.3")
            backup = repository / ".publication.backup"
            backup_license = backup / "plugins" / "vibe-diagram" / "LICENSE"

            def partially_delete_unverifiable_backup(path: Path) -> None:
                if path == backup:
                    backup_license.unlink()
                    raise OSError(
                        "injected partial cleanup of unverifiable backup payload"
                    )
                shutil.rmtree(path)

            with self.assertRaises(PublishError) as raised:
                sync_publication(
                    repository,
                    remove_tree=partially_delete_unverifiable_backup,
                )

            message = str(raised.exception)
            self.assertIn("cleanup", message)
            self.assertIn("evidence", message)
            self.assertIn("unverifiable", message)
            self.assertEqual(
                "1.2.3",
                validate_publication_tree(repository, repository)["package_version"],
            )
            self.assertTrue(backup.is_dir())
            journal = backup / PUBLICATION_JOURNAL
            self.assertTrue(journal.is_file())
            self.assertEqual(
                "cleanup-pending",
                json.loads(journal.read_text(encoding="utf-8"))["phase"],
            )
            with self.assertRaisesRegex(PublishError, "backup"):
                sync_publication(repository)
            with self.assertRaisesRegex(PublishError, "backup"):
                build_packages.check_publication(repository)

    def test_initial_rollback_staging_cleanup_delete_then_raise_preserves_fail_closed_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary) / "repository"
            _copy_repository(repository, seed_publication=False)
            backup = repository / ".publication.backup"
            real_validate = build_packages.validate_publication_tree

            def fail_final_validate(root: Path, publication_root: Path) -> dict:
                if publication_root == repository:
                    raise build_packages.ValidationError(
                        "injected final-validate failure"
                    )
                return real_validate(root, publication_root)

            def delete_staging_then_fail(path: Path) -> None:
                shutil.rmtree(path)
                if path.name.startswith(".publication.staging-"):
                    raise OSError("injected rollback staging cleanup deleted evidence")

            with patch(
                "scripts.build_packages.validate_publication_tree",
                side_effect=fail_final_validate,
            ), self.assertRaises(PublishError) as raised:
                sync_publication(repository, remove_tree=delete_staging_then_fail)

            message = str(raised.exception)
            self.assertIn("final-validate", message)
            self.assertIn("recovery cleanup", message)
            self.assertIn("staging cleanup", message)
            self.assertIn(str(backup), message)
            self.assertFalse((repository / "plugins" / "vibe-diagram").exists())
            self.assertFalse(
                (repository / ".agents" / "plugins" / "marketplace.json").exists()
            )
            self.assertTrue(backup.is_dir())
            self.assertEqual(
                "cleanup-pending",
                json.loads(
                    (backup / PUBLICATION_JOURNAL).read_text(encoding="utf-8")
                )["phase"],
            )
            staging = list(repository.glob(".publication.staging-*"))
            self.assertEqual(1, len(staging))
            self.assertTrue(staging[0].is_dir())
            with self.assertRaisesRegex(PublishError, "backup"):
                sync_publication(repository)
            with self.assertRaisesRegex(PublishError, "backup"):
                build_packages.check_publication(repository)

    def test_update_rollback_backup_cleanup_delete_then_raise_preserves_fail_closed_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary) / "repository"
            _copy_repository(repository)
            plugin = repository / "plugins" / "vibe-diagram"
            catalog = repository / ".agents" / "plugins" / "marketplace.json"
            old_plugin = _file_bytes(plugin)
            old_catalog = catalog.read_bytes()
            _set_repository_version(repository, "1.2.3")
            backup = repository / ".publication.backup"
            real_validate = build_packages.validate_publication_tree

            def fail_final_validate(root: Path, publication_root: Path) -> dict:
                if publication_root == repository:
                    raise build_packages.ValidationError(
                        "injected final-validate failure"
                    )
                return real_validate(root, publication_root)

            def delete_backup_then_fail(path: Path) -> None:
                shutil.rmtree(path)
                if path == backup:
                    raise OSError("injected rollback backup cleanup deleted evidence")

            with patch(
                "scripts.build_packages.validate_publication_tree",
                side_effect=fail_final_validate,
            ), self.assertRaises(PublishError) as raised:
                sync_publication(repository, remove_tree=delete_backup_then_fail)

            message = str(raised.exception)
            self.assertIn("final-validate", message)
            self.assertIn("recovery cleanup", message)
            self.assertIn("backup cleanup", message)
            self.assertIn(str(backup), message)
            self.assertEqual(old_plugin, _file_bytes(plugin))
            self.assertEqual(old_catalog, catalog.read_bytes())
            self.assertTrue(backup.is_dir())
            self.assertEqual(
                "cleanup-pending",
                json.loads(
                    (backup / PUBLICATION_JOURNAL).read_text(encoding="utf-8")
                )["phase"],
            )
            staging = list(repository.glob(".publication.staging-*"))
            self.assertEqual(1, len(staging))
            self.assertTrue(staging[0].is_dir())
            with self.assertRaisesRegex(PublishError, "backup"):
                sync_publication(repository)
            with self.assertRaisesRegex(PublishError, "backup"):
                build_packages.check_publication(repository)

    def test_cleanup_pending_journal_rewrite_failure_remains_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary) / "repository"
            _copy_repository(repository)
            _set_repository_version(repository, "1.2.3")
            backup = repository / ".publication.backup"
            journal = backup / PUBLICATION_JOURNAL

            def fail_staging_cleanup(path: Path) -> None:
                if path.name.startswith(".publication.staging-"):
                    raise OSError("injected staging cleanup failure")
                shutil.rmtree(path)

            def fail_cleanup_pending_journal(source: Path, destination: Path) -> None:
                if destination == journal:
                    payload = json.loads(source.read_text(encoding="utf-8"))
                    if payload["phase"] == "cleanup-pending":
                        raise OSError("injected cleanup-pending journal rewrite failure")
                os.replace(source, destination)

            with self.assertRaises(PublishError) as raised:
                sync_publication(
                    repository,
                    rename=fail_cleanup_pending_journal,
                    remove_tree=fail_staging_cleanup,
                )

            message = str(raised.exception)
            self.assertIn("staging cleanup", message)
            self.assertIn("journal", message)
            self.assertIn("fail-closed", message)
            self.assertTrue(backup.is_dir())
            self.assertTrue(journal.is_file())
            self.assertNotEqual(
                "cleanup-pending",
                json.loads(journal.read_text(encoding="utf-8"))["phase"],
            )
            self.assertEqual(
                "1.2.3",
                validate_publication_tree(repository, repository)["package_version"],
            )
            with self.assertRaisesRegex(PublishError, "backup"):
                sync_publication(repository)
            with self.assertRaisesRegex(PublishError, "backup"):
                build_packages.check_publication(repository)

    def test_publication_rollback_preserves_preexisting_parents_and_unrelated_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            for state in ("initial", "update"):
                with self.subTest(state=state):
                    repository = base / state
                    _copy_repository(repository, seed_publication=state == "update")
                    plugins = repository / "plugins"
                    marketplace_parent = repository / ".agents" / "plugins"
                    plugins.mkdir(parents=True, exist_ok=True)
                    marketplace_parent.mkdir(parents=True, exist_ok=True)
                    (plugins / "unrelated.txt").write_bytes(b"plugin parent sentinel\n")
                    (marketplace_parent / "unrelated.json").write_bytes(
                        b'{"preserve": true}\n'
                    )
                    plugin = plugins / "vibe-diagram"
                    catalog = marketplace_parent / "marketplace.json"
                    old_plugin = _file_bytes(plugin)
                    old_catalog = catalog.read_bytes() if catalog.is_file() else None
                    if state == "update":
                        _set_repository_version(repository, "1.2.3")
                    failure_injected = False

                    def fail_catalog_promotion(source: Path, destination: Path) -> None:
                        nonlocal failure_injected
                        if destination == catalog and not failure_injected:
                            failure_injected = True
                            raise OSError("injected catalog-promote failure")
                        os.replace(source, destination)

                    with self.assertRaisesRegex(PublishError, "catalog-promote"):
                        sync_publication(repository, rename=fail_catalog_promotion)

                    self.assertEqual(
                        b"plugin parent sentinel\n",
                        (plugins / "unrelated.txt").read_bytes(),
                    )
                    self.assertEqual(
                        b'{"preserve": true}\n',
                        (marketplace_parent / "unrelated.json").read_bytes(),
                    )
                    if state == "initial":
                        self.assertFalse(plugin.exists())
                        self.assertFalse(catalog.exists())
                    else:
                        self.assertEqual(old_plugin, _file_bytes(plugin))
                        self.assertEqual(old_catalog, catalog.read_bytes())
                    self.assertFalse((repository / ".publication.backup").exists())
                    self.assertEqual([], list(repository.glob(".publication.staging-*")))

    def test_initial_publication_rollback_removes_transaction_owned_empty_parents(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary) / "repository"
            _copy_repository(repository, seed_publication=False)
            catalog = repository / ".agents" / "plugins" / "marketplace.json"
            failure_injected = False

            def fail_catalog_promotion(source: Path, destination: Path) -> None:
                nonlocal failure_injected
                if destination == catalog and not failure_injected:
                    failure_injected = True
                    raise OSError("injected catalog-promote failure")
                os.replace(source, destination)

            with self.assertRaisesRegex(PublishError, "catalog-promote"):
                sync_publication(repository, rename=fail_catalog_promotion)

            self.assertFalse((repository / "plugins").exists())
            self.assertFalse((repository / ".agents").exists())
            self.assertFalse((repository / ".publication.backup").exists())
            self.assertEqual([], list(repository.glob(".publication.staging-*")))

    def test_assemble_build_tree_is_exact_complete_and_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            first = base / "first"
            second = base / "second"
            first.mkdir()
            second.mkdir()

            first_report = assemble_build_tree(ROOT, first)
            second_report = assemble_build_tree(ROOT, second)

            self.assertEqual(first_report, second_report)
            self.assertEqual(
                {
                    "schema_version",
                    "package_version",
                    "static_validation",
                    "runtime_validation",
                    "canonical",
                    "clients",
                },
                set(first_report),
            )
            self.assertEqual(1, first_report["schema_version"])
            self.assertEqual((ROOT / "VERSION").read_text(encoding="ascii").strip(), first_report["package_version"])
            self.assertEqual("passed", first_report["static_validation"])
            self.assertEqual("unverified", first_report["runtime_validation"])
            self.assertEqual(set(CLIENTS), set(first_report["clients"]))
            self.assertEqual(81, first_report["canonical"]["file_count"])
            canonical_paths = [record["path"] for record in first_report["canonical"]["files"]]
            self.assertEqual(sorted(canonical_paths, key=lambda value: value.encode("utf-8")), canonical_paths)
            for client in CLIENTS:
                self.assertEqual(
                    first_report["canonical"]["tree_sha256"],
                    first_report["clients"][client]["canonical_sha256"],
                )

            first_bytes = (first / "build-report.json").read_bytes()
            second_bytes = (second / "build-report.json").read_bytes()
            self.assertEqual(first_bytes, second_bytes)
            self.assertEqual(_file_bytes(first), _file_bytes(second))
            self.assertTrue(first_bytes.endswith(b"\n"))
            for forbidden in (str(base).encode(), str(Path.home()).encode(), b"staging", b"timestamp"):
                self.assertNotIn(forbidden, first_bytes)

    def test_check_only_is_offline_home_clean_and_preserves_existing_build(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            repository = base / "repository"
            home = base / "home"
            _copy_repository(repository)
            home.mkdir()
            (home / "sentinel.txt").write_text("home\n", encoding="utf-8")
            output = repository / "build"
            output.mkdir()
            (output / "old-sentinel.txt").write_text("old\n", encoding="utf-8")
            output_before = _file_bytes(output)
            home_before = _file_bytes(home)

            with patch.dict(os.environ, {"HOME": str(home)}), patch(
                "subprocess.run", side_effect=AssertionError("subprocess forbidden")
            ), patch("socket.create_connection", side_effect=AssertionError("socket forbidden")), patch(
                "urllib.request.urlopen", side_effect=AssertionError("urlopen forbidden")
            ):
                report, cleanup_pending = build_all(repository, check=True)

            self.assertFalse(cleanup_pending)
            self.assertEqual("passed", report["static_validation"])
            self.assertEqual("unverified", report["runtime_validation"])
            self.assertEqual(output_before, _file_bytes(output))
            self.assertEqual(home_before, _file_bytes(home))
            self.assertEqual([], list(repository.glob(".build.staging-*")))

    def test_build_all_publishes_all_four_clients_and_report(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary) / "repository"
            _copy_repository(repository)
            output = repository / "build"

            report, cleanup_pending = build_all(repository, output=output)

            self.assertFalse(cleanup_pending)
            self.assertEqual(report, json.loads((output / "build-report.json").read_text(encoding="utf-8")))
            self.assertEqual(set(CLIENTS), {path.name for path in output.iterdir() if path.is_dir()})
            self.assertEqual([], list(repository.glob(".build.staging-*")))

    def test_client_failure_preserves_old_build_and_cleans_staging(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary) / "repository"
            _copy_repository(repository)
            output = repository / "build"
            output.mkdir()
            sentinel = output / "old-sentinel.txt"
            sentinel.write_text("old\n", encoding="utf-8")
            real_build_client = build_packages.build_client

            def fail_second(root: Path, staging: Path, spec: object, version: str) -> dict:
                if getattr(spec, "client") == "claude":
                    raise BuildError("injected client failure")
                return real_build_client(root, staging, spec, version)

            with patch("scripts.build_packages.build_client", side_effect=fail_second):
                with self.assertRaisesRegex(BuildError, "injected client failure"):
                    build_all(repository, output=output)

            self.assertEqual(b"old\n", sentinel.read_bytes())
            self.assertEqual([], list(repository.glob(".build.staging-*")))

    def test_canonical_mutation_between_clients_never_publishes_split_brain_packages(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary) / "repository"
            _copy_repository(repository)
            output = repository / "build"
            output.mkdir()
            sentinel = output / "old-sentinel.txt"
            sentinel.write_text("old\n", encoding="utf-8")
            real_build_client = build_packages.build_client

            def mutate_after_codex(root: Path, staging: Path, spec: object, version: str) -> dict:
                report = real_build_client(root, staging, spec, version)
                if getattr(spec, "client") == "codex":
                    skill = root / "skills" / "vibe-diagram" / "SKILL.md"
                    skill.write_text(skill.read_text(encoding="utf-8") + "\n", encoding="utf-8")
                return report

            with patch("scripts.build_packages.build_client", side_effect=mutate_after_codex):
                with self.assertRaises(DeterminismError):
                    build_all(repository, output=output)

            self.assertEqual(b"old\n", sentinel.read_bytes())
            self.assertEqual([], list(repository.glob(".build.staging-*")))

    def test_publish_failure_restores_old_build_and_no_old_build_leaves_no_output(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            output = base / "build"
            staged = base / ".build.staging-one"
            output.mkdir()
            staged.mkdir()
            (output / "old.txt").write_text("old", encoding="utf-8")
            (staged / "new.txt").write_text("new", encoding="utf-8")
            calls = 0

            def fail_promotion(source: Path, destination: Path) -> None:
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise OSError("promotion failed")
                os.replace(source, destination)

            with self.assertRaisesRegex(PublishError, "promotion failed"):
                replace_build_transactionally(staged, output, rename=fail_promotion)
            self.assertEqual(b"old", (output / "old.txt").read_bytes())
            self.assertFalse((base / ".build.backup").exists())

            staged = base / ".build.staging-two"
            staged.mkdir()
            (staged / "new.txt").write_text("new", encoding="utf-8")
            shutil.rmtree(output)
            with self.assertRaisesRegex(PublishError, "promotion failed"):
                replace_build_transactionally(
                    staged,
                    output,
                    rename=lambda source, destination: (_ for _ in ()).throw(OSError("promotion failed")),
                )
            self.assertFalse(output.exists())

    def test_residual_backup_fails_closed_and_rollback_failure_preserves_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            output = base / "build"
            staged = base / ".build.staging"
            backup = base / ".build.backup"
            output.mkdir()
            staged.mkdir()
            backup.mkdir()
            with self.assertRaisesRegex(PublishError, "backup"):
                replace_build_transactionally(staged, output)
            self.assertTrue(output.exists())
            self.assertTrue(staged.exists())

            shutil.rmtree(backup)
            calls = 0

            def fail_promotion_and_rollback(source: Path, destination: Path) -> None:
                nonlocal calls
                calls += 1
                if calls >= 2:
                    raise OSError(f"rename-{calls}")
                os.replace(source, destination)

            with self.assertRaisesRegex(PublishError, "rollback") as raised:
                replace_build_transactionally(staged, output, rename=fail_promotion_and_rollback)
            self.assertIn(str(staged), str(raised.exception))
            self.assertIn(str(backup), str(raised.exception))
            self.assertTrue(staged.exists())
            self.assertTrue(backup.exists())

    def test_residual_backup_blocks_check_core_and_cli_without_creating_staging(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary) / "repository"
            _copy_repository(repository)
            output = repository / "build"
            backup = repository / ".build.backup"
            output.mkdir()
            backup.mkdir()
            (output / "current.txt").write_text("current\n", encoding="utf-8")
            (backup / "old.txt").write_text("old\n", encoding="utf-8")
            output_before = _file_bytes(output)
            backup_before = _file_bytes(backup)

            with self.assertRaisesRegex(PublishError, "backup"):
                build_all(repository, check=True)
            result = _run_cli(repository, "--check")

            self.assertEqual(1, result.returncode, result.stderr)
            self.assertIn("backup", result.stderr.lower())
            self.assertEqual(output_before, _file_bytes(output))
            self.assertEqual(backup_before, _file_bytes(backup))
            self.assertEqual([], list(repository.glob(".build.staging-*")))

    def test_committed_build_survives_backup_cleanup_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            output = base / "build"
            staged = base / ".build.staging"
            backup = base / ".build.backup"
            output.mkdir()
            staged.mkdir()
            (output / "old.txt").write_text("old", encoding="utf-8")
            (staged / "new.txt").write_text("new", encoding="utf-8")

            with patch("scripts.build_packages.shutil.rmtree", side_effect=OSError("cleanup failed")):
                cleanup_pending = replace_build_transactionally(staged, output)

            self.assertTrue(cleanup_pending)
            self.assertEqual(b"new", (output / "new.txt").read_bytes())
            self.assertEqual(b"old", (backup / "old.txt").read_bytes())

    def test_parse_args_is_an_exact_required_mutually_exclusive_interface(self) -> None:
        self.assertTrue(parse_args(["--check"]).check)
        self.assertEqual("build", parse_args(["--output", "build"]).output)
        self.assertTrue(parse_args(["--sync-publication"]).sync_publication)
        for arguments in (
            [],
            ["--check", "--output", "build"],
            ["--check", "--sync-publication"],
            ["--output", "build", "--sync-publication"],
            ["--output", "elsewhere"],
            ["--out", "build"],
            ["--che"],
            ["--sync"],
            ["--sync-publicatio"],
        ):
            with self.subTest(arguments=arguments):
                with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
                    parse_args(arguments)
                self.assertEqual(2, raised.exception.code)

    def test_cli_sync_publication_has_exact_initial_and_noop_contracts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary) / "repository"
            _copy_repository(repository, seed_publication=False)
            expected_changed = {
                "backup_cleanup_pending": False,
                "changed": True,
                "mode": "sync-publication",
                "output": [
                    "plugins/vibe-diagram",
                    ".agents/plugins/marketplace.json",
                ],
                "runtime_validation": "unverified",
                "static_validation": "passed",
            }

            first = _run_cli(repository, "--sync-publication")

            self.assertEqual(0, first.returncode, first.stderr)
            self.assertEqual("", first.stderr)
            self.assertEqual(
                json.dumps(
                    expected_changed,
                    ensure_ascii=True,
                    allow_nan=False,
                    sort_keys=True,
                )
                + "\n",
                first.stdout,
            )
            validate_publication_tree(repository, repository)
            plugin_before = _file_bytes(repository / "plugins" / "vibe-diagram")
            catalog_before = (
                repository / ".agents" / "plugins" / "marketplace.json"
            ).read_bytes()

            second = _run_cli(repository, "--sync-publication")

            expected_noop = dict(expected_changed, changed=False)
            self.assertEqual(0, second.returncode, second.stderr)
            self.assertEqual("", second.stderr)
            self.assertEqual(
                json.dumps(
                    expected_noop,
                    ensure_ascii=True,
                    allow_nan=False,
                    sort_keys=True,
                )
                + "\n",
                second.stdout,
            )
            self.assertEqual(
                plugin_before,
                _file_bytes(repository / "plugins" / "vibe-diagram"),
            )
            self.assertEqual(
                catalog_before,
                (repository / ".agents" / "plugins" / "marketplace.json").read_bytes(),
            )
            self.assertFalse((repository / ".publication.backup").exists())
            self.assertEqual([], list(repository.glob(".publication.staging-*")))

    def test_cli_sync_publication_reports_business_errors_without_stdout_or_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary) / "repository"
            _copy_repository(repository, seed_publication=False)
            (repository / ".publication.backup").mkdir()

            result = _run_cli(repository, "--sync-publication")

            self.assertEqual(1, result.returncode)
            self.assertEqual("", result.stdout)
            self.assertTrue(result.stderr.startswith("error:"), result.stderr)
            self.assertNotIn("Traceback", result.stderr)
            self.assertIn(str(repository / ".publication.backup"), result.stderr)
            self.assertEqual([], list(repository.glob(".publication.staging-*")))

    def test_main_sync_publication_cleanup_pending_has_exact_summary_and_nonzero_exit(self) -> None:
        record = {"runtime_validation": "unverified"}
        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch(
            "scripts.build_packages.sync_publication",
            return_value=(record, True, True),
        ), contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            result = main(["--sync-publication"])

        expected = {
            "backup_cleanup_pending": True,
            "changed": True,
            "mode": "sync-publication",
            "output": [
                "plugins/vibe-diagram",
                ".agents/plugins/marketplace.json",
            ],
            "runtime_validation": "unverified",
            "static_validation": "passed",
        }
        self.assertEqual(1, result)
        self.assertEqual(
            json.dumps(expected, ensure_ascii=True, allow_nan=False, sort_keys=True)
            + "\n",
            stdout.getvalue(),
        )
        self.assertIn(str(ROOT / ".publication.backup"), stderr.getvalue())
        self.assertIn("manually", stderr.getvalue().lower())

    def test_main_sync_publication_is_offline_home_clean_and_does_not_build_clients(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            repository = base / "repository"
            home = base / "home"
            _copy_repository(repository, seed_publication=False)
            home.mkdir()
            (home / "sentinel.txt").write_text("home\n", encoding="utf-8")
            home_before = _file_bytes(home)
            stdout = io.StringIO()
            stderr = io.StringIO()

            with patch.object(build_packages, "ROOT", repository), patch.dict(
                os.environ,
                {"HOME": str(home)},
            ), patch(
                "subprocess.run",
                side_effect=AssertionError("subprocess forbidden"),
            ), patch(
                "socket.create_connection",
                side_effect=AssertionError("socket forbidden"),
            ), patch(
                "urllib.request.urlopen",
                side_effect=AssertionError("urlopen forbidden"),
            ), patch(
                "scripts.build_packages.build_client",
                side_effect=AssertionError("four-client build forbidden"),
            ), contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                result = main(["--sync-publication"])

            self.assertEqual(0, result, stderr.getvalue())
            self.assertEqual("", stderr.getvalue())
            self.assertEqual(home_before, _file_bytes(home))
            self.assertEqual("sync-publication", json.loads(stdout.getvalue())["mode"])
            validate_publication_tree(repository, repository)

    def test_main_build_keeps_publication_untouched_and_uses_no_publication_operation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary) / "repository"
            _copy_repository(repository)
            plugin_before = _file_bytes(repository / "plugins" / "vibe-diagram")
            catalog = repository / ".agents" / "plugins" / "marketplace.json"
            catalog_before = catalog.read_bytes()
            stdout = io.StringIO()
            stderr = io.StringIO()

            with patch.object(build_packages, "ROOT", repository), patch(
                "scripts.build_packages.sync_publication",
                side_effect=AssertionError("publication sync forbidden"),
            ), patch(
                "scripts.build_packages.check_publication",
                side_effect=AssertionError("publication check forbidden"),
            ), contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                result = main(["--output", "build"])

            self.assertEqual(0, result, stderr.getvalue())
            self.assertEqual("", stderr.getvalue())
            self.assertEqual("build", json.loads(stdout.getvalue())["mode"])
            self.assertEqual(
                plugin_before,
                _file_bytes(repository / "plugins" / "vibe-diagram"),
            )
            self.assertEqual(catalog_before, catalog.read_bytes())
            self.assertFalse((repository / ".publication.backup").exists())
            self.assertEqual([], list(repository.glob(".publication.staging-*")))

    def test_main_reports_success_build_error_and_cleanup_warning(self) -> None:
        report = {"static_validation": "passed", "runtime_validation": "unverified"}
        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch("scripts.build_packages.build_all", return_value=(report, True)), contextlib.redirect_stdout(
            stdout
        ), contextlib.redirect_stderr(stderr):
            self.assertEqual(0, main(["--output", "build"]))
        self.assertEqual(
            {
                "backup_cleanup_pending": True,
                "mode": "build",
                "output": "build",
                "runtime_validation": "unverified",
                "static_validation": "passed",
            },
            json.loads(stdout.getvalue()),
        )
        self.assertEqual(
            "warning: new build is active; remove residual backup after inspection: "
            f"{ROOT / '.build.backup'}\n",
            stderr.getvalue(),
        )

        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch("scripts.build_packages.build_all", side_effect=BuildError("actionable")), contextlib.redirect_stdout(
            stdout
        ), contextlib.redirect_stderr(stderr):
            self.assertEqual(1, main(["--check"]))
        self.assertEqual("", stdout.getvalue())
        self.assertIn("actionable", stderr.getvalue())

    def test_cli_check_and_build_have_exact_exit_and_summary_contracts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            repository = base / "repository"
            home = base / "home"
            _copy_repository(repository)
            home.mkdir()

            checked = _run_cli(repository, "--check", home=home)
            self.assertEqual(0, checked.returncode, checked.stderr)
            self.assertEqual("", checked.stderr)
            self.assertEqual(
                json.dumps(
                    {
                        "backup_cleanup_pending": False,
                        "mode": "check",
                        "output": None,
                        "runtime_validation": "unverified",
                        "static_validation": "passed",
                    },
                    ensure_ascii=True,
                    allow_nan=False,
                    sort_keys=True,
                )
                + "\n",
                checked.stdout,
            )
            built = _run_cli(repository, "--output", "build", home=home)
            self.assertEqual(0, built.returncode, built.stderr)
            self.assertEqual("", built.stderr)
            self.assertTrue((repository / "build" / "build-report.json").is_file())
            self.assertEqual(
                json.dumps(
                    {
                        "backup_cleanup_pending": False,
                        "mode": "build",
                        "output": "build",
                        "runtime_validation": "unverified",
                        "static_validation": "passed",
                    },
                    ensure_ascii=True,
                    allow_nan=False,
                    sort_keys=True,
                )
                + "\n",
                built.stdout,
            )
            for arguments in ((), ("--check", "--output", "build"), ("--output", "../build")):
                failed = _run_cli(repository, *arguments, home=home)
                self.assertEqual(2, failed.returncode, arguments)

    def test_cli_root_and_frozen_inputs_symlinks_or_license_drift_fail_before_staging(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            cases = ("root", "VERSION", "LICENSE", "contracts/template_migration_baseline.json")
            for case in cases:
                with self.subTest(case=case):
                    real_repository = base / f"real-{case.replace('/', '-')}"
                    _copy_repository(real_repository)
                    output = real_repository / "build"
                    output.mkdir()
                    (output / "old-sentinel.txt").write_text("old\n", encoding="utf-8")
                    invoked = real_repository
                    if case == "root":
                        invoked = base / "repository-link"
                        invoked.symlink_to(real_repository, target_is_directory=True)
                    else:
                        target = real_repository / case
                        preserved = target.with_name(target.name + ".real")
                        target.rename(preserved)
                        target.symlink_to(preserved)
                    result = _run_cli(invoked, "--check")
                    self.assertEqual(1, result.returncode, (case, result.stderr))
                    self.assertEqual(b"old\n", (output / "old-sentinel.txt").read_bytes())
                    self.assertEqual([], list(real_repository.glob(".build.staging-*")))
                    if case == "root":
                        invoked.unlink()

            drifted = base / "drifted-license"
            _copy_repository(drifted)
            (drifted / "LICENSE").write_text("not Apache\n", encoding="utf-8")
            result = _run_cli(drifted, "--check")
            self.assertEqual(1, result.returncode, result.stderr)
            self.assertEqual([], list(drifted.glob(".build.staging-*")))


if __name__ == "__main__":
    unittest.main()
