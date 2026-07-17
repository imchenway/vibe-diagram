from __future__ import annotations

import json
import re
import shutil
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path, PurePosixPath

from scripts.build_packages import (
    CLIENTS,
    ExtraFile,
    ValidationError,
    assemble_client_package,
    build_client,
    canonical_file_map,
    load_adapter,
    read_json_unique,
    read_version,
    render_template,
    tree_record,
    validate_canonical,
    validate_manifest,
    validate_package,
)
from tests.template_contract import (
    file_sha256,
    template_slots_macros_and_pairs,
    template_structure_signature,
)


ROOT = Path(__file__).resolve().parents[1]
CANONICAL_ROOT = ROOT / "skills" / "vibe-diagram"
TEMPLATE_ROOT = CANONICAL_ROOT / "assets" / "templates"
CONTRACT_RELATIVE = Path("contracts/template_migration_baseline.json")
VERSION = (ROOT / "VERSION").read_text(encoding="ascii").strip()


def _copy_repository(destination: Path) -> None:
    for name in ("LICENSE", "VERSION"):
        shutil.copy2(ROOT / name, destination / name)
    for name in ("contracts", "adapters", "skills", "scripts"):
        shutil.copytree(ROOT / name, destination / name)


def _snapshot(path: Path) -> dict:
    html = path.read_text(encoding="utf-8")
    slots, macros, pairs = template_slots_macros_and_pairs(html)
    return {
        "file_sha256": file_sha256(path),
        "structure_sha256": template_structure_signature(html),
        "data_slots": slots,
        "macros": macros,
        "slot_macro_pairs": pairs,
    }


def _refresh_template_contract(root: Path, relative: str, *, source: bool) -> None:
    contract_path = root / CONTRACT_RELATIVE
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    snapshot = _snapshot(root / "skills" / "vibe-diagram" / "assets" / "templates" / relative)
    contract["templates"][relative]["canonical"] = snapshot
    if source:
        contract["templates"][relative]["source"] = snapshot
    contract_path.write_text(json.dumps(contract, indent=2) + "\n", encoding="utf-8")


def _inject_before_body(path: Path, fragment: str) -> None:
    html = path.read_text(encoding="utf-8")
    if "</body>" not in html:
        raise AssertionError(path)
    path.write_text(html.replace("</body>", fragment + "\n</body>", 1), encoding="utf-8")


def _rendered_manifest(root: Path, client: str) -> dict:
    spec = load_adapter(root, client)
    template = read_json_unique(root / "adapters" / client / spec.manifest_template)
    return render_template(template, read_version(root))


class PackageAssemblyTests(unittest.TestCase):
    def test_validate_canonical_accepts_the_frozen_71_file_core(self) -> None:
        self.assertIsNone(validate_canonical(ROOT))
        self.assertEqual(71, len(canonical_file_map(ROOT)))
        self.assertEqual(71, tree_record(CANONICAL_ROOT).file_count)

    def test_four_clients_build_exact_self_contained_packages(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            staging = Path(temporary) / "build"
            staging.mkdir()
            reports = {}
            for client in CLIENTS:
                spec = load_adapter(ROOT, client)
                reports[client] = build_client(ROOT, staging, spec, VERSION)

            canonical = canonical_file_map(ROOT)
            canonical_hash = tree_record(CANONICAL_ROOT).tree_sha256
            manifests = {load_adapter(ROOT, client).manifest_output.as_posix() for client in CLIENTS}
            for client in CLIENTS:
                with self.subTest(client=client):
                    spec = load_adapter(ROOT, client)
                    package = staging / client
                    report = reports[client]
                    package_record = tree_record(package)
                    self.assertEqual(
                        {"manifest_path", "manifest_sha256", "canonical_sha256", "package"},
                        set(report),
                    )
                    self.assertEqual(
                        {"file_count", "tree_sha256", "files"},
                        set(report["package"]),
                    )
                    self.assertEqual(spec.manifest_output.as_posix(), report["manifest_path"])
                    self.assertEqual(
                        file_sha256(package / spec.manifest_output),
                        report["manifest_sha256"],
                    )
                    self.assertEqual(canonical_hash, report["canonical_sha256"])
                    self.assertEqual(74 if client == "codex" else 73, report["package"]["file_count"])
                    self.assertEqual((ROOT / "LICENSE").read_bytes(), (package / "LICENSE").read_bytes())
                    self.assertEqual(
                        package_record.tree_sha256,
                        report["package"]["tree_sha256"],
                    )
                    expected_files = [
                        {"path": record.path, "size": record.size, "sha256": record.sha256}
                        for record in package_record.files
                    ]
                    self.assertEqual(expected_files, report["package"]["files"])
                    self.assertTrue(
                        all(
                            set(record) == {"path", "size", "sha256"}
                            for record in report["package"]["files"]
                        )
                    )
                    for relative, source in canonical.items():
                        target = package / spec.skills_output / relative
                        self.assertEqual(source.read_bytes(), target.read_bytes(), relative.as_posix())
                    package_paths = {record.path for record in tree_record(package).files}
                    self.assertIn(spec.manifest_output.as_posix(), package_paths)
                    self.assertTrue(
                        (manifests - {spec.manifest_output.as_posix()}).isdisjoint(package_paths)
                    )
                    agents = package / spec.skills_output / "agents"
                    self.assertEqual(client == "codex", agents.is_dir())

    def test_direct_package_assembler_matches_build_client_byte_for_byte(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            legacy_root = base / "legacy"
            direct_parent = base / "direct"
            legacy_root.mkdir()
            direct_parent.mkdir()
            spec = load_adapter(ROOT, "codex")

            legacy_report = build_client(ROOT, legacy_root, spec, VERSION)
            direct_package = direct_parent / "vibe-diagram"
            direct_report = assemble_client_package(ROOT, direct_package, spec, VERSION)

            self.assertEqual(legacy_report, direct_report)
            self.assertEqual(tree_record(legacy_root / "codex"), tree_record(direct_package))
            for record in tree_record(direct_package).files:
                self.assertEqual(
                    (legacy_root / "codex" / record.path).read_bytes(),
                    (direct_package / record.path).read_bytes(),
                    record.path,
                )

    def test_validate_package_rejects_license_content_file_set_and_symlink_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            staging = Path(temporary) / "build"
            staging.mkdir()
            spec = load_adapter(ROOT, "codex")
            build_client(ROOT, staging, spec, VERSION)
            package = staging / "codex"

            (package / "LICENSE").write_text("changed\n", encoding="utf-8")
            with self.assertRaises(ValidationError):
                validate_package(ROOT, package, spec, VERSION)
            shutil.copy2(ROOT / "LICENSE", package / "LICENSE")

            skill_path = package / spec.skills_output / "SKILL.md"
            skill_bytes = skill_path.read_bytes()
            skill_path.unlink()
            with self.assertRaises(ValidationError):
                validate_package(ROOT, package, spec, VERSION)
            skill_path.write_bytes(skill_bytes)

            extra = package / "not-allowlisted.txt"
            extra.write_text("extra\n", encoding="utf-8")
            with self.assertRaises(ValidationError):
                validate_package(ROOT, package, spec, VERSION)
            extra.unlink()

            manifest_path = package / spec.manifest_output
            manifest_bytes = manifest_path.read_bytes()
            manifest_path.write_text(
                json.dumps(json.loads(manifest_bytes.decode("utf-8"))), encoding="utf-8"
            )
            with self.assertRaises(ValidationError):
                validate_package(ROOT, package, spec, VERSION)
            manifest_path.write_bytes(manifest_bytes)

            skill_path.unlink()
            skill_path.symlink_to(ROOT / "skills" / "vibe-diagram" / "SKILL.md")
            with self.assertRaises(ValidationError):
                validate_package(ROOT, package, spec, VERSION)

    def test_build_client_rejects_noncanonical_specs_before_writing(self) -> None:
        base = load_adapter(ROOT, "codex")
        variants = (
            replace(
                base,
                extra_files=(
                    ExtraFile(
                        source=PurePosixPath("README.md"),
                        output=PurePosixPath("skills/vibe-diagram/SKILL.md"),
                    ),
                ),
            ),
            replace(
                base,
                extra_files=(
                    ExtraFile(
                        source=PurePosixPath("missing.yaml"),
                        output=PurePosixPath("extra.yaml"),
                    ),
                ),
            ),
            replace(base, manifest_output=PurePosixPath("../plugin.json")),
            replace(base, manifest_output=PurePosixPath("/plugin.json")),
        )
        with tempfile.TemporaryDirectory() as temporary:
            for index, spec in enumerate(variants):
                with self.subTest(index=index):
                    staging = Path(temporary) / f"build-{index}"
                    staging.mkdir()
                    with self.assertRaises(ValidationError):
                        build_client(ROOT, staging, spec, VERSION)
                    self.assertEqual([], list(staging.iterdir()))

    def test_manifest_validation_rejects_cross_client_schema_and_value_drift(self) -> None:
        for client in CLIENTS:
            manifest = _rendered_manifest(ROOT, client)
            self.assertIsNone(validate_manifest(client, manifest, VERSION))
            for key, value in (
                ("name", "other"),
                ("version", "9.9.9"),
                ("description", ""),
                ("description", 7),
            ):
                with self.subTest(client=client, key=key, value=value):
                    changed = dict(manifest)
                    changed[key] = value
                    with self.assertRaises(ValidationError):
                        validate_manifest(client, changed, VERSION)

        codex = _rendered_manifest(ROOT, "codex")
        for skills in ("skills/", "../skills/", "/skills/", 7):
            changed = dict(codex)
            changed["skills"] = skills
            with self.subTest(codex_skills=skills), self.assertRaises(ValidationError):
                validate_manifest("codex", changed, VERSION)
        changed = dict(codex)
        changed["interface"] = {"displayName": "Incomplete"}
        with self.assertRaises(ValidationError):
            validate_manifest("codex", changed, VERSION)

        for client in ("codex", "claude", "copilot"):
            manifest = _rendered_manifest(ROOT, client)
            for key, value in (("author", {"name": "other"}), ("license", "MIT")):
                changed = dict(manifest)
                changed[key] = value
                with self.subTest(client=client, key=key), self.assertRaises(ValidationError):
                    validate_manifest(client, changed, VERSION)

        gemini = _rendered_manifest(ROOT, "gemini")
        for key, value in (
            ("author", {"name": "imchenway"}),
            ("license", "Apache-2.0"),
            ("skills", "./skills/"),
            ("unexpected", True),
        ):
            changed = dict(gemini)
            changed[key] = value
            with self.subTest(gemini_key=key), self.assertRaises(ValidationError):
                validate_manifest("gemini", changed, VERSION)

        copilot = _rendered_manifest(ROOT, "copilot")
        copilot["description"] = "x" * 1025
        with self.assertRaises(ValidationError):
            validate_manifest("copilot", copilot, VERSION)

    def test_canonical_rejects_reference_template_and_inventory_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            for case in ("reference", "template", "missing-skill", "missing-template"):
                with self.subTest(case=case):
                    root = base / case
                    root.mkdir()
                    _copy_repository(root)
                    if case == "reference":
                        path = root / "skills" / "vibe-diagram" / "references" / "business-flow.md"
                        path.write_text(path.read_text(encoding="utf-8") + "\nDrift.\n", encoding="utf-8")
                    elif case == "template":
                        path = root / "skills" / "vibe-diagram" / "assets" / "templates" / "business-flow" / "stage-track.html"
                        path.write_text(path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
                    elif case == "missing-skill":
                        (root / "skills" / "vibe-diagram" / "SKILL.md").unlink()
                    else:
                        (root / "skills" / "vibe-diagram" / "assets" / "templates" / "business-flow" / "stage-track.html").unlink()
                    with self.assertRaises(ValidationError):
                        validate_canonical(root)

    def test_canonical_rejects_host_terms_and_han_in_skill_core(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            for case, fragment in (
                ("host", "\nClaude\n"),
                ("host-lower", "\ncodex\n"),
                ("han", "\n中文\n"),
                ("han-extension", "\n\U00020000\n"),
                ("han-ideographic-zero", "\n\u3007\n"),
                ("han-compatibility-supplement", "\n\U0002F800\n"),
                ("linter-host", "\n# Codex\n"),
            ):
                with self.subTest(case=case):
                    root = base / case
                    root.mkdir()
                    _copy_repository(root)
                    target = (
                        root / "skills" / "vibe-diagram" / "scripts" / "vibe_diagram_lint.py"
                        if case == "linter-host"
                        else root / "skills" / "vibe-diagram" / "SKILL.md"
                    )
                    target.write_text(target.read_text(encoding="utf-8") + fragment, encoding="utf-8")
                    with self.assertRaises(ValidationError):
                        validate_canonical(root)

    def test_canonical_resource_scanner_rejects_network_and_allows_embedded_refs(self) -> None:
        relative = "code-sequence/participant-timeline.html"
        invalid = (
            '<img src="relative.png" alt="x">',
            '<img src="/root.png" alt="x">',
            '<img src="//cdn.example/x.png" alt="x">',
            '<style>.x{background:url("https://example.com/x.png")}</style>',
            '<iframe src="data:text/html,x"></iframe>',
            '<script>fetch("https://example.com")</script>',
            '<script>globalThis["fetch"]("./payload.json")</script>',
            '<script>new Image().src="//evil.example/pixel"</script>',
            '<script>new Image().src="./pixel.png"</script>',
            '<script>const node={};node.src="./pixel.png"</script>',
            '<script>const node={};node["src"]="./pixel.png"</script>',
            '<script>window.location="./next.html"</script>',
            '<script>window["location"]="./next.html"</script>',
            '<script>document.location="./next.html"</script>',
            '<script>location.assign("./next.html")</script>',
            '<script>location.replace("./next.html")</script>',
            '<script>window.open("./next.html")</script>',
            '<script>globalThis["open"]("./next.html")</script>',
            '<meta http-equiv="refresh" content="0;url=./next.html">',
            '<a href="#ok" ping="./audit">Local</a>',
        )
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            for index, fragment in enumerate(invalid):
                with self.subTest(index=index):
                    root = base / f"invalid-{index}"
                    root.mkdir()
                    _copy_repository(root)
                    path = root / "skills" / "vibe-diagram" / "assets" / "templates" / relative
                    _inject_before_body(path, fragment)
                    _refresh_template_contract(root, relative, source=False)
                    with self.assertRaises(ValidationError):
                        validate_canonical(root)

            allowed = base / "allowed"
            allowed.mkdir()
            _copy_repository(allowed)
            path = allowed / "skills" / "vibe-diagram" / "assets" / "templates" / relative
            _inject_before_body(
                path,
                '<a id="local" href="#local">Local</a>'
                '<img src="data:image/gif;base64,AAAA" alt="x">'
                '<script>globalThis["theme"]="dark"</script>',
            )
            _refresh_template_contract(allowed, relative, source=False)
            self.assertIsNone(validate_canonical(allowed))

    def test_canonical_rejects_duplicate_family_structure_even_with_matching_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy_repository(root)
            source = root / "skills" / "vibe-diagram" / "assets" / "templates" / "code-sequence" / "participant-timeline.html"
            target = root / "skills" / "vibe-diagram" / "assets" / "templates" / "code-sequence" / "async-callback-sequence.html"
            html = source.read_text(encoding="utf-8")
            html = html.replace(
                'data-template-id="participant-timeline"',
                'data-template-id="async-callback-sequence"',
                1,
            ).replace(
                'data-template-layout="participant-timeline"',
                'data-template-layout="async-callback-sequence"',
                1,
            )
            target.write_text(html, encoding="utf-8")
            _refresh_template_contract(
                root, "code-sequence/async-callback-sequence.html", source=False
            )
            with self.assertRaises(ValidationError):
                validate_canonical(root)

    def test_canonical_rejects_sequence_kernel_endpoint_complexity_and_fixed_layout_drift(self) -> None:
        relative = "code-sequence/participant-timeline.html"
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)

            kernel = base / "kernel"
            kernel.mkdir()
            _copy_repository(kernel)
            path = kernel / "skills" / "vibe-diagram" / "assets" / "templates" / relative
            html = path.read_text(encoding="utf-8").replace(
                '<style data-sequence-kernel="1">',
                '<style data-sequence-kernel="1">\n/* drift */',
                1,
            )
            path.write_text(html, encoding="utf-8")
            _refresh_template_contract(kernel, relative, source=False)
            with self.assertRaises(ValidationError):
                validate_canonical(kernel)

            endpoint = base / "endpoint"
            endpoint.mkdir()
            _copy_repository(endpoint)
            path = endpoint / "skills" / "vibe-diagram" / "assets" / "templates" / relative
            path.write_text(
                path.read_text(encoding="utf-8").replace(
                    'data-to="coordinator"', 'data-to="missing-participant"', 1
                ),
                encoding="utf-8",
            )
            _refresh_template_contract(endpoint, relative, source=False)
            with self.assertRaises(ValidationError):
                validate_canonical(endpoint)

            complexity = base / "complexity"
            complexity.mkdir()
            _copy_repository(complexity)
            path = complexity / "skills" / "vibe-diagram" / "assets" / "templates" / relative
            participants = "".join(
                f'<div data-participant-id="extra-{index}"><strong>X</strong><span>X</span></div>'
                for index in range(9)
            )
            path.write_text(
                path.read_text(encoding="utf-8").replace(
                    '<header class="sequence-participants" data-sequence-participants>',
                    '<header class="sequence-participants" data-sequence-participants>' + participants,
                    1,
                ),
                encoding="utf-8",
            )
            _refresh_template_contract(complexity, relative, source=False)
            with self.assertRaises(ValidationError):
                validate_canonical(complexity)

            fixed = base / "fixed"
            fixed.mkdir()
            _copy_repository(fixed)
            path = fixed / "skills" / "vibe-diagram" / "assets" / "templates" / relative
            _inject_before_body(path, "<style>.bad{width:2040px;grid-template-columns:repeat(12,1fr)}</style>")
            _refresh_template_contract(fixed, relative, source=False)
            with self.assertRaises(ValidationError):
                validate_canonical(fixed)

    def test_canonical_sequence_requires_canvas_participants_and_messages(self) -> None:
        relative = "code-sequence/participant-timeline.html"
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            for case in ("no-canvas", "one-participant", "no-messages"):
                with self.subTest(case=case):
                    root = base / case
                    root.mkdir()
                    _copy_repository(root)
                    path = (
                        root
                        / "skills"
                        / "vibe-diagram"
                        / "assets"
                        / "templates"
                        / relative
                    )
                    html = path.read_text(encoding="utf-8")
                    if case == "no-canvas":
                        html = html.replace(
                            " data-sequence-canvas data-sequence-contract=",
                            " data-sequence-contract=",
                            1,
                        )
                    elif case == "one-participant":
                        seen = [0]

                        def remove_after_first(match: re.Match[str]) -> str:
                            seen[0] += 1
                            return match.group(0) if seen[0] == 1 else ""

                        html = re.sub(
                            r'\sdata-participant-id="[^"]+"', remove_after_first, html
                        )
                        html = re.sub(r"\sdata-sequence-message(?=[\s>])", "", html)
                    else:
                        html = re.sub(r"\sdata-sequence-message(?=[\s>])", "", html)
                    path.write_text(html, encoding="utf-8")
                    _refresh_template_contract(root, relative, source=False)
                    with self.assertRaises(ValidationError):
                        validate_canonical(root)


if __name__ == "__main__":
    unittest.main()
