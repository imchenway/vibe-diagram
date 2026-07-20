from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path, PurePosixPath
from typing import Dict
from unittest.mock import patch

import scripts.build_packages as builder
from scripts.build_packages import (
    CLIENTS,
    AdapterSpec,
    ValidationError,
    canonical_file_map,
    file_records,
    load_adapter,
    load_reference_contract,
    load_template_contract,
    parse_skill_frontmatter,
    read_json_unique,
    read_version,
    render_template,
    safe_relative_path,
    sha256_file,
    template_structure_signature,
    tree_record,
    validate_repository_root,
)
from tests.template_contract import template_structure_signature as frozen_structure_signature


ROOT = Path(__file__).resolve().parents[1]
LICENSE_SHA256 = "c71d239df91726fc519c6eb72d318ec65820627232b2f796219e87dcf35d0ab4"


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def _copy_valid_repository(destination: Path) -> None:
    shutil.copy2(ROOT / "LICENSE", destination / "LICENSE")
    shutil.copy2(ROOT / "VERSION", destination / "VERSION")
    shutil.copytree(ROOT / "contracts", destination / "contracts")
    shutil.copytree(ROOT / "adapters", destination / "adapters")
    shutil.copytree(ROOT / "skills", destination / "skills")
    (destination / "scripts").mkdir()
    shutil.copy2(ROOT / "scripts" / "__init__.py", destination / "scripts" / "__init__.py")
    shutil.copy2(
        ROOT / "scripts" / "build_packages.py",
        destination / "scripts" / "build_packages.py",
    )


class BuildPackagesUnitTests(unittest.TestCase):
    def test_clients_and_adapter_dataclass_contract(self) -> None:
        self.assertEqual(("codex", "claude", "gemini", "copilot"), CLIENTS)
        adapter = load_adapter(ROOT, "codex")
        self.assertIsInstance(adapter, AdapterSpec)
        self.assertEqual(PurePosixPath(".codex-plugin/plugin.json"), adapter.manifest_output)
        self.assertEqual(PurePosixPath("skills/vibe-diagram"), adapter.skills_output)
        self.assertEqual(1, len(adapter.extra_files))

    def test_read_version_accepts_strict_semver_2(self) -> None:
        valid = (
            "0.0.0",
            "1.2.3",
            "1.2.3-alpha.1+build.5",
            "10.20.30-rc-1",
        )
        invalid = (
            "v1.2.3",
            "1.2",
            "01.2.3",
            "1.02.3",
            "1.2.03",
            "1.2.3-01",
            "1.2.3-alpha.01",
            "1.2.3\nextra",
            "1.2.3",
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for value in valid:
                with self.subTest(valid=value):
                    (root / "VERSION").write_text(value + "\n", encoding="ascii")
                    self.assertEqual(value, read_version(root))
            for index, value in enumerate(invalid):
                with self.subTest(invalid=value, index=index):
                    raw = value if index == len(invalid) - 1 else value + "\n"
                    (root / "VERSION").write_text(raw, encoding="ascii")
                    with self.assertRaises(ValidationError):
                        read_version(root)

    def test_read_json_unique_rejects_duplicates_constants_and_non_object_roots(self) -> None:
        invalid = {
            "duplicate": '{"outer":{"key":1,"key":2}}',
            "nan": '{"value":NaN}',
            "infinity": '{"value":Infinity}',
            "negative-infinity": '{"value":-Infinity}',
            "overflow-infinity": '{"value":1e999}',
            "overflow-negative-infinity": '{"value":{"nested":-1e999}}',
            "array-root": "[]",
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            valid_path = root / "valid.json"
            valid_path.write_text('{"outer":{"key":1}}', encoding="utf-8")
            self.assertEqual({"outer": {"key": 1}}, read_json_unique(valid_path))
            for name, text in invalid.items():
                with self.subTest(name=name):
                    path = root / f"{name}.json"
                    path.write_text(text, encoding="utf-8")
                    with self.assertRaises(ValidationError):
                        read_json_unique(path)

    def test_parse_skill_frontmatter_accepts_only_name_and_description_strings(self) -> None:
        current = parse_skill_frontmatter(
            (ROOT / "skills" / "vibe-diagram" / "SKILL.md").read_text(encoding="utf-8")
        )
        self.assertEqual({"name", "description"}, set(current))
        self.assertEqual("vibe-diagram", current["name"])
        valid = "---\nname: sample-skill\ndescription: One line.\n---\n# Body\n"
        self.assertEqual(
            {"name": "sample-skill", "description": "One line."},
            parse_skill_frontmatter(valid),
        )
        invalid = (
            "name: sample\ndescription: Missing fences.\n",
            "---\nname: a\nname: b\ndescription: d\n---\n",
            "---\nname: a\ndescription:\n  nested: value\n---\n",
            "---\nname: a\ndescription: [one, two]\n---\n",
            "---\nname: a\ndescription: |\n  multiple lines\n---\n",
            "---\nname: a\ndescription: d\nextra: value\n---\n",
            "---\nname: a\n---\n",
        )
        for index, text in enumerate(invalid):
            with self.subTest(index=index):
                with self.assertRaises(ValidationError):
                    parse_skill_frontmatter(text)

    def test_safe_relative_path_rejects_escape_and_ambiguous_forms(self) -> None:
        for valid in ("skills/vibe-diagram", ".codex-plugin/plugin.json", "README.md"):
            with self.subTest(valid=valid):
                self.assertEqual(PurePosixPath(valid), safe_relative_path(valid))
        invalid = (
            "",
            ".",
            "..",
            "../escape",
            "folder/../escape",
            "/absolute",
            "folder//file",
            "folder\\file",
            "folder/./file",
            "nul\x00file",
        )
        for value in invalid:
            with self.subTest(invalid=value):
                with self.assertRaises(ValidationError):
                    safe_relative_path(value)

    def test_render_template_requires_one_exact_version_placeholder(self) -> None:
        source = {"name": "vibe", "nested": ["keep", {"version": "${VERSION}"}]}
        rendered = render_template(source, "1.2.3")
        self.assertEqual(
            {"name": "vibe", "nested": ["keep", {"version": "1.2.3"}]},
            rendered,
        )
        self.assertEqual("${VERSION}", source["nested"][1]["version"])
        for invalid in (
            {"name": "vibe"},
            {"one": "${VERSION}", "two": "${VERSION}"},
            {"version": "release-${VERSION}"},
        ):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValidationError):
                    render_template(invalid, "1.2.3")

    def test_validate_repository_root_accepts_current_repository(self) -> None:
        self.assertIsNone(validate_repository_root(ROOT))
        self.assertEqual(11357, (ROOT / "LICENSE").stat().st_size)
        self.assertEqual(LICENSE_SHA256, sha256_file(ROOT / "LICENSE"))

    def test_validate_repository_root_rejects_symlinks_non_files_and_license_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)

            real_root = base / "real-root"
            real_root.mkdir()
            _copy_valid_repository(real_root)
            linked_root = base / "linked-root"
            linked_root.symlink_to(real_root, target_is_directory=True)
            with self.assertRaises(ValidationError):
                validate_repository_root(linked_root)

            for case in ("version-symlink", "license-directory", "contracts-symlink", "contract-symlink"):
                with self.subTest(case=case):
                    root = base / case
                    root.mkdir()
                    _copy_valid_repository(root)
                    if case == "version-symlink":
                        (root / "VERSION").unlink()
                        (root / "VERSION").symlink_to(real_root / "VERSION")
                    elif case == "license-directory":
                        (root / "LICENSE").unlink()
                        (root / "LICENSE").mkdir()
                    elif case == "contracts-symlink":
                        shutil.rmtree(root / "contracts")
                        (root / "contracts").symlink_to(
                            real_root / "contracts", target_is_directory=True
                        )
                    else:
                        contract = root / "contracts" / "template_migration_baseline.json"
                        contract.unlink()
                        contract.symlink_to(
                            real_root / "contracts" / "template_migration_baseline.json"
                        )
                    with self.assertRaises(ValidationError):
                        validate_repository_root(root)

            drifted = base / "license-drift"
            drifted.mkdir()
            _copy_valid_repository(drifted)
            (drifted / "LICENSE").write_bytes((ROOT / "LICENSE").read_bytes() + b"\n")
            with self.assertRaises(ValidationError):
                validate_repository_root(drifted)

            missing_url = base / "license-url"
            missing_url.mkdir()
            _copy_valid_repository(missing_url)
            license_path = missing_url / "LICENSE"
            raw = license_path.read_bytes().replace(
                b"http://www.apache.org/licenses/", b"x" * len(b"http://www.apache.org/licenses/")
            )
            license_path.write_bytes(raw)
            with patch.object(builder, "LICENSE_SIZE", len(raw)), patch.object(
                builder, "LICENSE_SHA256", hashlib.sha256(raw).hexdigest()
            ):
                with self.assertRaises(ValidationError):
                    validate_repository_root(missing_url)

    def test_every_required_file_and_repository_ancestor_rejects_symlinks_or_non_files(self) -> None:
        required_files = (
            "VERSION",
            "LICENSE",
            "scripts/build_packages.py",
            "contracts/template_migration_baseline.json",
            "contracts/reference_migration_baseline.json",
            "contracts/interaction_contract_baseline.json",
        )
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            source = base / "source"
            source.mkdir()
            _copy_valid_repository(source)

            for index, relative in enumerate(required_files):
                with self.subTest(kind="symlink", relative=relative):
                    root = base / f"file-link-{index}"
                    root.mkdir()
                    _copy_valid_repository(root)
                    target = root / relative
                    target.unlink()
                    target.symlink_to(source / relative)
                    with self.assertRaises(ValidationError):
                        validate_repository_root(root)

                with self.subTest(kind="non-file", relative=relative):
                    root = base / f"file-directory-{index}"
                    root.mkdir()
                    _copy_valid_repository(root)
                    target = root / relative
                    target.unlink()
                    target.mkdir()
                    with self.assertRaises(ValidationError):
                        validate_repository_root(root)

            for index, relative in enumerate(("scripts", "contracts")):
                with self.subTest(kind="ancestor-symlink", relative=relative):
                    root = base / f"ancestor-link-{index}"
                    root.mkdir()
                    _copy_valid_repository(root)
                    shutil.rmtree(root / relative)
                    (root / relative).symlink_to(source / relative, target_is_directory=True)
                    with self.assertRaises(ValidationError):
                        validate_repository_root(root)

    def test_load_adapters_validates_client_keys_paths_outputs_and_documentation(self) -> None:
        for client in CLIENTS:
            with self.subTest(client=client):
                self.assertEqual(client, load_adapter(ROOT, client).client)
        with self.assertRaises(ValidationError):
            load_adapter(ROOT, "unknown")

        mutations: Dict[str, object] = {
            "unknown-key": ("unexpected", True),
            "client-mismatch": ("client", "other"),
            "escape-output": ("manifest_output", "../plugin.json"),
        }
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            for case, (key, value) in mutations.items():
                with self.subTest(case=case):
                    root = base / case
                    root.mkdir()
                    _copy_valid_repository(root)
                    path = root / "adapters" / "codex" / "adapter.json"
                    adapter = json.loads(path.read_text(encoding="utf-8"))
                    adapter[key] = value
                    _write_json(path, adapter)
                    with self.assertRaises(ValidationError):
                        load_adapter(root, "codex")

            duplicate_output = base / "duplicate-output"
            duplicate_output.mkdir()
            _copy_valid_repository(duplicate_output)
            path = duplicate_output / "adapters" / "codex" / "adapter.json"
            adapter = json.loads(path.read_text(encoding="utf-8"))
            adapter["extra_files"][0]["output"] = adapter["manifest_output"]
            _write_json(path, adapter)
            with self.assertRaises(ValidationError):
                load_adapter(duplicate_output, "codex")

            missing_boundary = base / "missing-boundary"
            missing_boundary.mkdir()
            _copy_valid_repository(missing_boundary)
            (missing_boundary / "adapters" / "codex" / "README.md").write_text(
                "No verification boundary.\n", encoding="utf-8"
            )
            with self.assertRaises(ValidationError):
                load_adapter(missing_boundary, "codex")

            alternate_documentation = base / "alternate-documentation"
            alternate_documentation.mkdir()
            _copy_valid_repository(alternate_documentation)
            adapter_dir = alternate_documentation / "adapters" / "codex"
            (adapter_dir / "ALT.md").write_text("Status: Unverified.\n", encoding="utf-8")
            path = adapter_dir / "adapter.json"
            adapter = json.loads(path.read_text(encoding="utf-8"))
            adapter["documentation"] = "ALT.md"
            _write_json(path, adapter)
            with self.assertRaises(ValidationError):
                load_adapter(alternate_documentation, "codex")

    def test_contract_loaders_validate_current_frozen_contracts(self) -> None:
        template = load_template_contract(ROOT)
        reference = load_reference_contract(ROOT)
        self.assertEqual(3, template["schema_version"])
        self.assertEqual(58, len(template["templates"]))
        changed = [
            path
            for path, entry in template["templates"].items()
            if entry["source"] != entry["canonical"]
        ]
        migrated = {
            path
            for paths in template["interaction_migration_batches"].values()
            for path in paths
        }
        self.assertEqual(
            set(template["sequence_redesign_allowlist"]) | migrated,
            set(changed),
        )
        self.assertEqual(1, reference["schema_version"])
        self.assertEqual(11, len(reference["references"]))

    def test_contract_loaders_fail_closed_on_schema_or_change_reason_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)

            extra_key = base / "extra-key"
            extra_key.mkdir()
            _copy_valid_repository(extra_key)
            path = extra_key / "contracts" / "template_migration_baseline.json"
            contract = json.loads(path.read_text(encoding="utf-8"))
            contract["unexpected"] = True
            _write_json(path, contract)
            with self.assertRaises(ValidationError):
                load_template_contract(extra_key)

            bad_change = base / "bad-change"
            bad_change.mkdir()
            _copy_valid_repository(bad_change)
            path = bad_change / "contracts" / "template_migration_baseline.json"
            contract = json.loads(path.read_text(encoding="utf-8"))
            migrated_path = contract["interaction_migration_batches"]["B01"][0]
            contract["templates"][migrated_path]["change_reason"] = None
            _write_json(path, contract)
            with self.assertRaises(ValidationError):
                load_template_contract(bad_change)

            bad_reference = base / "bad-reference"
            bad_reference.mkdir()
            _copy_valid_repository(bad_reference)
            path = bad_reference / "contracts" / "reference_migration_baseline.json"
            contract = json.loads(path.read_text(encoding="utf-8"))
            contract["references"]["extra.md"] = "0" * 64
            _write_json(path, contract)
            with self.assertRaises(ValidationError):
                load_reference_contract(bad_reference)

            digest_drift = base / "digest-drift"
            digest_drift.mkdir()
            _copy_valid_repository(digest_drift)
            template_path = digest_drift / "contracts" / "template_migration_baseline.json"
            template_contract = json.loads(template_path.read_text(encoding="utf-8"))
            template_contract["source_contract_sha256"] = "0" * 64
            _write_json(template_path, template_contract)
            reference_path = digest_drift / "contracts" / "reference_migration_baseline.json"
            reference_contract = json.loads(reference_path.read_text(encoding="utf-8"))
            reference_contract["source_skill_content_sha256"] = "0" * 64
            _write_json(reference_path, reference_contract)
            with self.assertRaises(ValidationError):
                load_template_contract(digest_drift)
            with self.assertRaises(ValidationError):
                load_reference_contract(digest_drift)

            template_rename = base / "template-rename"
            template_rename.mkdir()
            _copy_valid_repository(template_rename)
            contract_path = template_rename / "contracts" / "template_migration_baseline.json"
            contract = json.loads(contract_path.read_text(encoding="utf-8"))
            old_name = next(iter(contract["templates"]))
            new_name = "business-architecture/renamed-template.html"
            contract["templates"][new_name] = contract["templates"].pop(old_name)
            _write_json(contract_path, contract)
            canonical = template_rename / "skills" / "vibe-diagram" / "assets" / "templates"
            (canonical / old_name).rename(canonical / new_name)
            with self.assertRaises(ValidationError):
                load_template_contract(template_rename)

            reference_rename = base / "reference-rename"
            reference_rename.mkdir()
            _copy_valid_repository(reference_rename)
            contract_path = reference_rename / "contracts" / "reference_migration_baseline.json"
            contract = json.loads(contract_path.read_text(encoding="utf-8"))
            old_name = next(iter(contract["references"]))
            new_name = "renamed-reference.md"
            contract["references"][new_name] = contract["references"].pop(old_name)
            _write_json(contract_path, contract)
            canonical = reference_rename / "skills" / "vibe-diagram" / "references"
            (canonical / old_name).rename(canonical / new_name)
            with self.assertRaises(ValidationError):
                load_reference_contract(reference_rename)

            source_snapshot_drift = base / "source-snapshot-drift"
            source_snapshot_drift.mkdir()
            _copy_valid_repository(source_snapshot_drift)
            contract_path = (
                source_snapshot_drift / "contracts" / "template_migration_baseline.json"
            )
            contract = json.loads(contract_path.read_text(encoding="utf-8"))
            relative = next(iter(contract["templates"]))
            contract["templates"][relative]["source"]["file_sha256"] = "0" * 64
            _write_json(contract_path, contract)
            with self.assertRaises(ValidationError):
                load_template_contract(source_snapshot_drift)

    def test_canonical_file_map_is_relative_complete_and_rejects_symlinks(self) -> None:
        files = canonical_file_map(ROOT)
        self.assertEqual(81, len(files))
        self.assertIn(PurePosixPath("SKILL.md"), files)
        self.assertIn(PurePosixPath("VERSION"), files)
        self.assertIn(PurePosixPath("update.json"), files)
        self.assertIn(PurePosixPath("scripts/update_skill.py"), files)
        self.assertIn(PurePosixPath("references/runtime-workflow.md"), files)
        self.assertIn(PurePosixPath("references/adaptive-readability.md"), files)
        self.assertIn(PurePosixPath("contracts/family-policies.json"), files)
        self.assertIn(
            PurePosixPath("assets/templates/code-sequence/participant-timeline.html"), files
        )
        self.assertNotIn(PurePosixPath("skills/vibe-diagram/SKILL.md"), files)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            shutil.copytree(ROOT / "skills", root / "skills")
            (root / "skills" / "vibe-diagram" / "linked.md").symlink_to(
                ROOT / "skills" / "vibe-diagram" / "SKILL.md"
            )
            with self.assertRaises(ValidationError):
                canonical_file_map(root)

    def test_structure_signature_matches_frozen_htmlparser_contract(self) -> None:
        path = (
            ROOT
            / "skills"
            / "vibe-diagram"
            / "assets"
            / "templates"
            / "code-sequence"
            / "participant-timeline.html"
        )
        html = path.read_text(encoding="utf-8")
        self.assertEqual(frozen_structure_signature(html), template_structure_signature(html))

    def test_file_and_tree_records_are_sorted_and_use_binary_framing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "nested").mkdir()
            (root / "z.txt").write_bytes(b"z")
            (root / "nested" / "a.bin").write_bytes(b"alpha\x00beta")
            records = file_records(root)
            self.assertEqual(["nested/a.bin", "z.txt"], [record.path for record in records])
            self.assertEqual([10, 1], [record.size for record in records])

            payload = bytearray(b"vibe-diagram-tree-v1\0")
            for record in records:
                path_bytes = record.path.encode("utf-8")
                payload.extend(len(path_bytes).to_bytes(4, "big"))
                payload.extend(path_bytes)
                payload.extend(bytes.fromhex(record.sha256))
            expected = hashlib.sha256(bytes(payload)).hexdigest()
            first = tree_record(root)
            self.assertEqual(2, first.file_count)
            self.assertEqual(expected, first.tree_sha256)
            self.assertEqual(records, first.files)

            os.utime(root / "z.txt", (1, 1))
            self.assertEqual(first, tree_record(root))


if __name__ == "__main__":
    unittest.main()
