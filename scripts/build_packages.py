#!/usr/bin/env python3
"""Build deterministic Vibe Diagram client packages from the canonical Skill."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


SCRIPT_PATH = Path(__file__).absolute()
ROOT = SCRIPT_PATH.parents[1]
CANONICAL_RELATIVE = PurePosixPath("skills/vibe-diagram")
PUBLICATION_RELATIVE = PurePosixPath("plugins/vibe-diagram")
VERSION_RE = re.compile(r"(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)")
ID_RE = re.compile(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*")
VERSION_PLACEHOLDER = "${VERSION}"
ADAPTER_KEYS = {
    "schema_version", "client", "documentation", "manifest_template", "manifest_output",
    "skills_output", "extra_files",
}
EXTRA_KEYS = {"source", "output"}
UPDATE_KEYS = {"schema_version", "channel", "version", "ref", "tree_sha256"}
CLIENTS = ("claude", "codex", "copilot", "gemini")
REQUIRED_CANONICAL = {
    "SKILL.md",
    "VERSION",
    "update.json",
    "assets/shell/v1.css",
    "assets/shell/v1.js",
    "contracts/artifact-manifest.schema.json",
    "contracts/family-outcomes.json",
    "references/runtime-workflow.md",
    "references/artifact-authoring.md",
    "scripts/update_skill.py",
    "scripts/vibe_diagram_lint.py",
    "scripts/vibe_diagram_scaffold.py",
}
FORBIDDEN_CANONICAL = {
    "contracts/diagram-document.schema.json",
    "contracts/template-routing.json",
    "scripts/vibe_diagram_render.py",
    "scripts/vibe_diagram_spec.py",
}
ARCHETYPE_NAMES = {
    "async-retry-sequence.md",
    "basic-flow.md",
    "business-architecture.md",
    "code-review.md",
    "code-sequence.md",
    "comparison-matrix.md",
    "er-data-flow.md",
    "fault-causal-chain.md",
    "state-machine.md",
    "swimlane-exception-flow.md",
    "system-architecture.md",
    "technical-design-page-prototype.md",
}
FAMILY_NAMES = {
    "business-architecture", "business-flow", "code-sequence", "system-architecture",
    "fault-debugging", "state-machine", "data-model", "comparison-matrix", "code-review",
    "technical-design", "page-prototype",
}


class BuildError(RuntimeError):
    pass


class ValidationError(BuildError):
    pass


class DeterminismError(ValidationError):
    pass


@dataclass(frozen=True)
class ExtraFile:
    source: PurePosixPath
    output: PurePosixPath


@dataclass(frozen=True)
class AdapterSpec:
    client: str
    documentation: PurePosixPath
    manifest_template: PurePosixPath
    manifest_output: PurePosixPath
    skills_output: PurePosixPath
    extra_files: Tuple[ExtraFile, ...]


@dataclass(frozen=True)
class FileRecord:
    path: str
    size: int
    sha256: str


@dataclass(frozen=True)
class TreeRecord:
    file_count: int
    tree_sha256: str
    files: Tuple[FileRecord, ...]


def _fail(message: str) -> ValidationError:
    return ValidationError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json_unique(path: Path) -> Dict[str, Any]:
    def unique(pairs: List[Tuple[str, Any]]) -> Dict[str, Any]:
        result: Dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise _fail(f"duplicate JSON key in {path}: {key}")
            result[key] = value
        return result

    def reject_constant(value: str) -> Any:
        raise _fail(f"non-finite JSON value in {path}: {value}")

    try:
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique, parse_constant=reject_constant)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise _fail(f"could not read JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise _fail(f"JSON root must be an object: {path}")
    return value


def safe_relative_path(value: str) -> PurePosixPath:
    if not isinstance(value, str) or not value or "\\" in value or value.startswith("/"):
        raise _fail(f"unsafe relative path: {value!r}")
    path = PurePosixPath(value)
    if any(part in {"", ".", ".."} for part in path.parts):
        raise _fail(f"unsafe relative path: {value!r}")
    return path


def _real_file(root: Path, relative: PurePosixPath) -> Path:
    path = root.joinpath(*relative.parts)
    if path.is_symlink() or not path.is_file():
        raise _fail(f"required file must be regular and non-symlink: {relative}")
    return path


def read_version(root: Path) -> str:
    path = _real_file(root, PurePosixPath("VERSION"))
    try:
        text = path.read_text(encoding="ascii")
    except (OSError, UnicodeError) as exc:
        raise _fail(f"could not read VERSION: {exc}") from exc
    if not text.endswith("\n") or text.count("\n") != 1:
        raise _fail("VERSION must contain one newline-terminated line")
    value = text[:-1]
    if VERSION_RE.fullmatch(value) is None:
        raise _fail("VERSION must use strict major.minor.patch")
    return value


def validate_repository_root(root: Path) -> None:
    if root.is_symlink() or not root.is_dir():
        raise _fail(f"repository root must be a real directory: {root}")
    for relative in ("LICENSE", "VERSION", "skills/vibe-diagram/SKILL.md"):
        _real_file(root, safe_relative_path(relative))
    if read_version(root) != (root / "skills" / "vibe-diagram" / "VERSION").read_text(encoding="ascii").strip():
        raise _fail("repository and canonical Skill versions must match")


def parse_skill_frontmatter(text: str) -> Dict[str, str]:
    if not text.startswith("---\n"):
        raise _fail("SKILL.md requires YAML frontmatter")
    end = text.find("\n---\n", 4)
    if end < 0:
        raise _fail("SKILL.md frontmatter is not closed")
    result: Dict[str, str] = {}
    for line in text[4:end].splitlines():
        if not line.strip():
            continue
        if ":" not in line:
            raise _fail(f"unsupported SKILL.md frontmatter line: {line}")
        key, value = line.split(":", 1)
        key, value = key.strip(), value.strip().strip('"\'')
        if key in result:
            raise _fail(f"duplicate SKILL.md frontmatter key: {key}")
        result[key] = value
    if result.get("name") != "vibe-diagram" or not result.get("description"):
        raise _fail("SKILL.md frontmatter identity is invalid")
    return result


def render_template(value: Any, version: str) -> Any:
    if isinstance(value, str):
        return value.replace(VERSION_PLACEHOLDER, version)
    if isinstance(value, list):
        return [render_template(item, version) for item in value]
    if isinstance(value, dict):
        return {key: render_template(item, version) for key, item in value.items()}
    return value


def load_adapter(root: Path, client: str) -> AdapterSpec:
    if client not in CLIENTS:
        raise _fail(f"unsupported client: {client}")
    adapter_root = root / "adapters" / client
    value = read_json_unique(adapter_root / "adapter.json")
    if set(value) != ADAPTER_KEYS or value.get("schema_version") != 1 or value.get("client") != client:
        raise _fail(f"adapter contract is invalid: {client}")
    extras_value = value.get("extra_files")
    if not isinstance(extras_value, list):
        raise _fail(f"adapter extra_files must be an array: {client}")
    extras: List[ExtraFile] = []
    for item in extras_value:
        if not isinstance(item, dict) or set(item) != EXTRA_KEYS:
            raise _fail(f"adapter extra file is invalid: {client}")
        extras.append(ExtraFile(safe_relative_path(item["source"]), safe_relative_path(item["output"])))
    spec = AdapterSpec(
        client=client,
        documentation=safe_relative_path(value["documentation"]),
        manifest_template=safe_relative_path(value["manifest_template"]),
        manifest_output=safe_relative_path(value["manifest_output"]),
        skills_output=safe_relative_path(value["skills_output"]),
        extra_files=tuple(extras),
    )
    _real_file(adapter_root, spec.documentation)
    _real_file(adapter_root, spec.manifest_template)
    for extra in spec.extra_files:
        _real_file(adapter_root, extra.source)
    return spec


def validate_manifest(client: str, manifest: Mapping[str, Any], version: str) -> None:
    if manifest.get("name") != "vibe-diagram" or manifest.get("version") != version:
        raise _fail(f"rendered manifest identity is invalid: {client}")
    if not isinstance(manifest.get("description"), str) or not manifest["description"].strip():
        raise _fail(f"rendered manifest description is invalid: {client}")
    if VERSION_PLACEHOLDER in json.dumps(manifest):
        raise _fail(f"rendered manifest retains a version placeholder: {client}")
    if client == "codex":
        if manifest.get("skills") != "./skills/" or not isinstance(manifest.get("interface"), dict):
            raise _fail("Codex manifest must expose the skills directory and interface")


def _iter_files(root: Path) -> Iterable[Tuple[str, Path]]:
    if root.is_symlink() or not root.is_dir():
        raise _fail(f"tree root must be a real directory: {root}")
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix().encode("utf-8")):
        relative = path.relative_to(root).as_posix()
        if "__pycache__" in path.parts or path.name in {".DS_Store"} or path.suffix == ".pyc":
            continue
        if path.is_symlink():
            raise _fail(f"symlink is forbidden in a package tree: {relative}")
        if path.is_dir():
            continue
        if not path.is_file():
            raise _fail(f"non-regular package entry: {relative}")
        yield relative, path


def file_records(root: Path) -> Tuple[FileRecord, ...]:
    return tuple(FileRecord(path, file.stat().st_size, sha256_file(file)) for path, file in _iter_files(root))


def tree_record(root: Path) -> TreeRecord:
    files = file_records(root)
    digest = hashlib.sha256()
    for record in files:
        digest.update(record.path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(record.size.to_bytes(8, "big"))
        digest.update(bytes.fromhex(record.sha256))
    return TreeRecord(len(files), digest.hexdigest(), files)


def update_tree_sha256(skill_root: Path) -> str:
    digest = hashlib.sha256()
    for relative, path in _iter_files(skill_root):
        if relative == "update.json":
            continue
        payload = path.read_bytes()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(len(payload).to_bytes(8, "big"))
        digest.update(hashlib.sha256(payload).digest())
    return digest.hexdigest()


def canonical_file_map(root: Path) -> Dict[PurePosixPath, Path]:
    skill_root = root / "skills" / "vibe-diagram"
    result = {PurePosixPath(relative): path for relative, path in _iter_files(skill_root)}
    names = {path.as_posix() for path in result}
    missing = sorted(REQUIRED_CANONICAL - names)
    if missing:
        raise _fail(f"canonical Skill is missing required files: {', '.join(missing)}")
    forbidden = sorted(FORBIDDEN_CANONICAL.intersection(names))
    if forbidden or any(name.startswith("assets/templates/") for name in names):
        raise _fail(f"canonical Skill contains retired production files: {', '.join(forbidden or ['assets/templates/'])}")
    return result


def validate_canonical(root: Path) -> TreeRecord:
    files = canonical_file_map(root)
    skill_root = root / "skills" / "vibe-diagram"
    skill_text = files[PurePosixPath("SKILL.md")].read_text(encoding="utf-8")
    parse_skill_frontmatter(skill_text)
    if len(skill_text.splitlines()) > 120:
        raise _fail("SKILL.md must remain concise and use progressive disclosure")
    if "model owns fact selection" not in skill_text.lower() or "at most two" not in skill_text.lower():
        raise _fail("SKILL.md does not establish model-owned authoring and bounded archetype loading")

    archetypes = {
        path.name for path in files
        if path.parent == PurePosixPath("references/archetypes") and path.suffix == ".md"
    }
    if archetypes != ARCHETYPE_NAMES:
        raise _fail("canonical archetype inventory must match the approved twelve references")
    for match in re.findall(r"\]\((references/[^)]+)\)", skill_text):
        if PurePosixPath(match) not in files:
            raise _fail(f"SKILL.md references a missing resource: {match}")

    outcomes = read_json_unique(files[PurePosixPath("contracts/family-outcomes.json")])
    if outcomes.get("schema_version") != 1 or not isinstance(outcomes.get("families"), dict):
        raise _fail("family outcome contract is invalid")
    if set(outcomes["families"]) != FAMILY_NAMES:
        raise _fail("family outcome contract does not match the approved family set")
    schema = read_json_unique(files[PurePosixPath("contracts/artifact-manifest.schema.json")])
    if schema.get("$id") != "vibe-diagram/artifact-manifest@1" or "nodes" in schema.get("properties", {}):
        raise _fail("ArtifactManifest must be open to model-authored DOM and contain no node inventory")

    scaffold = files[PurePosixPath("scripts/vibe_diagram_scaffold.py")].read_text(encoding="utf-8")
    linter = files[PurePosixPath("scripts/vibe_diagram_lint.py")].read_text(encoding="utf-8")
    shell_js = files[PurePosixPath("assets/shell/v1.js")].read_text(encoding="utf-8")
    for marker in ("--output", "--title", "--lang", "data-vd-author-style"):
        if marker not in scaffold:
            raise _fail(f"blank scaffold is missing marker: {marker}")
    for marker in ("ArtifactManifest", "data-vd-critical", "family-outcomes.json"):
        if marker not in linter:
            raise _fail(f"outcome linter is missing marker: {marker}")
    for marker in ("edge-through-node", "edge-label-collision", "critical-target-not-primary-visible", "auditAll"):
        if marker not in shell_js:
            raise _fail(f"browser outcome audit is missing marker: {marker}")

    version = read_version(root)
    skill_version = files[PurePosixPath("VERSION")].read_text(encoding="ascii")
    if skill_version != f"{version}\n":
        raise _fail("canonical VERSION must match repository VERSION")
    update = read_json_unique(files[PurePosixPath("update.json")])
    if set(update) != UPDATE_KEYS or update.get("schema_version") != 1 or update.get("channel") != "stable":
        raise _fail("canonical update manifest is invalid")
    if update.get("version") != version or update.get("ref") != f"v{version}":
        raise _fail("canonical update manifest version is invalid")
    if update.get("tree_sha256") != update_tree_sha256(skill_root):
        raise _fail("canonical update manifest tree digest is stale")
    return tree_record(skill_root)


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=True, allow_nan=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _copy_file(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    os.chmod(target, 0o755 if os.access(source, os.X_OK) else 0o644)


def assemble_client_package(root: Path, target: Path, spec: AdapterSpec, version: str) -> None:
    if target.exists() or target.is_symlink():
        raise _fail(f"package output already exists: {target}")
    target.mkdir(parents=True)
    adapter_root = root / "adapters" / spec.client
    manifest = render_template(read_json_unique(adapter_root / spec.manifest_template), version)
    validate_manifest(spec.client, manifest, version)
    manifest_target = target.joinpath(*spec.manifest_output.parts)
    manifest_target.parent.mkdir(parents=True, exist_ok=True)
    manifest_target.write_bytes(_json_bytes(manifest))
    _copy_file(root / "LICENSE", target / "LICENSE")

    skill_target = target.joinpath(*spec.skills_output.parts)
    skill_target.mkdir(parents=True)
    for relative, source in canonical_file_map(root).items():
        _copy_file(source, skill_target.joinpath(*relative.parts))
    for extra in spec.extra_files:
        _copy_file(adapter_root.joinpath(*extra.source.parts), target.joinpath(*extra.output.parts))


def _record_dict(record: FileRecord) -> Dict[str, Any]:
    return {"path": record.path, "sha256": record.sha256, "size": record.size}


def _tree_dict(record: TreeRecord) -> Dict[str, Any]:
    return {
        "file_count": record.file_count,
        "tree_sha256": record.tree_sha256,
        "files": [_record_dict(file) for file in record.files],
    }


def build_workspace(root: Path, output: Path) -> Dict[str, Any]:
    if output.exists() or output.is_symlink():
        raise _fail(f"build output already exists: {output}")
    canonical = validate_canonical(root)
    version = read_version(root)
    output.mkdir(parents=True)
    packages: Dict[str, Any] = {}
    for client in CLIENTS:
        target = output / client
        assemble_client_package(root, target, load_adapter(root, client), version)
        packages[client] = _tree_dict(tree_record(target))
    report = {
        "schema_version": 2,
        "version": version,
        "static_validation": "passed",
        "browser_layout_validation": "not-verified",
        "runtime_validation": "unverified",
        "canonical": _tree_dict(canonical),
        "packages": packages,
    }
    (output / "build-report.json").write_bytes(_json_bytes(report))
    return report


def _tree_bytes(root: Path) -> Dict[str, bytes]:
    return {relative: path.read_bytes() for relative, path in _iter_files(root)}


def _replace_generated(target: Path, candidate: Path) -> None:
    staging = candidate.parent
    previous = staging / "previous"
    had_target = target.exists()
    if target.is_symlink():
        raise _fail(f"generated target must not be a symlink: {target}")
    if had_target:
        os.replace(target, previous)
    try:
        os.replace(candidate, target)
    except BaseException:
        if had_target:
            os.replace(previous, target)
        raise
    if previous.exists():
        shutil.rmtree(previous)


def sync_publication(root: Path) -> Dict[str, Any]:
    validate_canonical(root)
    version = read_version(root)
    target = root.joinpath(*PUBLICATION_RELATIVE.parts)
    with tempfile.TemporaryDirectory(prefix=".publication.staging-", dir=root) as temporary:
        staging = Path(temporary)
        candidate = staging / "candidate"
        assemble_client_package(root, candidate, load_adapter(root, "codex"), version)
        record = tree_record(candidate)
        _replace_generated(target, candidate)
    return {"publication": str(target), "status": "package-static-valid", "tree_sha256": record.tree_sha256}


def publish_build(root: Path) -> Dict[str, Any]:
    target = root / "build"
    with tempfile.TemporaryDirectory(prefix=".build.staging-", dir=root) as temporary:
        staging = Path(temporary)
        candidate = staging / "candidate"
        report = build_workspace(root, candidate)
        _replace_generated(target, candidate)
    return report


def _validate_archive(skill_root: Path) -> str:
    with tempfile.TemporaryDirectory() as temporary:
        archive = Path(temporary) / "canonical.zip"
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_STORED) as output:
            for relative, source in _iter_files(skill_root):
                info = zipfile.ZipInfo(relative, date_time=(1980, 1, 1, 0, 0, 0))
                info.create_system = 3
                info.external_attr = (0o755 if os.access(source, os.X_OK) else 0o644) << 16
                output.writestr(info, source.read_bytes())
        with zipfile.ZipFile(archive) as source:
            names = source.namelist()
            expected = [relative for relative, _path in _iter_files(skill_root)]
            if names != expected:
                raise _fail("canonical archive inventory is not deterministic")
            for name, path in _iter_files(skill_root):
                if source.read(name) != path.read_bytes():
                    raise _fail(f"canonical archive payload drifted: {name}")
        return sha256_file(archive)


def check(root: Path) -> Dict[str, Any]:
    canonical = validate_canonical(root)
    with tempfile.TemporaryDirectory() as first_temp, tempfile.TemporaryDirectory() as second_temp:
        first = Path(first_temp) / "build"
        second = Path(second_temp) / "build"
        first_report = build_workspace(root, first)
        build_workspace(root, second)
        if _tree_bytes(first) != _tree_bytes(second):
            raise DeterminismError("two clean package builds are not byte-identical")
        publication = root.joinpath(*PUBLICATION_RELATIVE.parts)
        if not publication.is_dir() or _tree_bytes(publication) != _tree_bytes(first / "codex"):
            raise _fail("tracked Codex publication projection does not match the deterministic package")
    result = subprocess.run(
        ["git", "diff", "--check"], cwd=root, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False
    )
    if result.returncode != 0:
        raise _fail(f"git diff --check failed:\n{result.stdout.strip()}")
    archive_sha = _validate_archive(root / "skills" / "vibe-diagram")
    return {
        "status": "static-valid",
        "version": read_version(root),
        "canonical_tree_sha256": canonical.tree_sha256,
        "canonical_archive_sha256": archive_sha,
        "browser_layout_validation": "not-verified",
        "runtime_validation": "unverified",
        "build": first_report["static_validation"],
    }


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true", help="validate two deterministic builds and projections")
    group.add_argument("--output", choices=["build"], help="replace the generated local build directory")
    group.add_argument("--sync-publication", action="store_true", help="replace the tracked Codex projection")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    try:
        validate_repository_root(ROOT)
        if args.check:
            result = check(ROOT)
        elif args.sync_publication:
            result = sync_publication(ROOT)
        else:
            result = publish_build(ROOT)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except BuildError as exc:
        print(f"build failed: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"build failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
