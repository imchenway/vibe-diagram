from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import stat
import sys
import tempfile
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple


SCRIPT_PATH = Path(__file__).absolute()
ROOT = SCRIPT_PATH.parents[1]


CLIENTS: Tuple[str, ...] = ("codex", "claude", "gemini", "copilot")
PUBLICATION_PLUGIN = PurePosixPath("plugins/vibe-diagram")
MARKETPLACE_CATALOG = PurePosixPath(".agents/plugins/marketplace.json")
PUBLICATION_BACKUP_NAME = ".publication.backup"
PUBLICATION_STAGING_PREFIX = ".publication.staging-"
PUBLICATION_JOURNAL = PurePosixPath("transaction.json")
PUBLICATION_PHASES = {
    "backup-created",
    "plugin-backed-up",
    "catalog-backed-up",
    "plugin-promoted",
    "catalog-promoted",
    "validated",
    "cleanup-pending",
}
SEMVER_RE = re.compile(
    r"^(0|[1-9]\d*)\."
    r"(0|[1-9]\d*)\."
    r"(0|[1-9]\d*)"
    r"(?:-((?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*))*))?"
    r"(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
)
HEX_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
VERSION_PLACEHOLDER = "${VERSION}"
LICENSE_SIZE = 11357
LICENSE_SHA256 = "c71d239df91726fc519c6eb72d318ec65820627232b2f796219e87dcf35d0ab4"
SOURCE_TEMPLATE_CONTRACT_SHA256 = "cab7874937427e6092defb67b2e28f280d9d31022788c9c6382bbfe334f93959"
SOURCE_TEMPLATE_SNAPSHOTS_SHA256 = "cfc532f1abd6ccf7de33c25eba107739da351ce466cd27bc4c871d099c816bd1"
SOURCE_SKILL_CONTENT_SHA256 = "6d123fce6a33df73e04f8f953d9429c24cc833897291ca30dad62ecf611dfb48"
ADAPTER_KEYS = {
    "schema_version",
    "client",
    "documentation",
    "manifest_template",
    "manifest_output",
    "skills_output",
    "extra_files",
}
EXTRA_FILE_KEYS = {"source", "output"}
TEMPLATE_CONTRACT_KEYS = {
    "schema_version",
    "signature_algorithm",
    "source_contract_sha256",
    "sequence_redesign_allowlist",
    "interaction_migration_batches",
    "templates",
}
TEMPLATE_ENTRY_KEYS = {"source", "canonical", "change_reason"}
TEMPLATE_SNAPSHOT_KEYS = {
    "file_sha256",
    "structure_sha256",
    "data_slots",
    "macros",
    "slot_macro_pairs",
}
SEQUENCE_REDESIGN_PATHS = (
    "code-sequence/async-callback-sequence.html",
    "code-sequence/participant-timeline.html",
    "code-sequence/retry-exception-sequence.html",
    "code-sequence/transaction-boundary-sequence.html",
    "fault-debugging/debugging-sequence.html",
    "feature-iteration/current-target-sequence.html",
)
TEMPLATE_PATHS: Tuple[str, ...] = (
    "business-architecture/capability-domain-map.html",
    "business-architecture/participant-boundary.html",
    "business-architecture/rule-constraint-heatmap.html",
    "business-architecture/value-chain-map.html",
    "business-flow/bpmn-light-flow.html",
    "business-flow/exception-branch-flow.html",
    "business-flow/stage-track.html",
    "business-flow/swimlane-flow.html",
    "code-sequence/async-callback-sequence.html",
    "code-sequence/participant-timeline.html",
    "code-sequence/retry-exception-sequence.html",
    "code-sequence/transaction-boundary-sequence.html",
    "decision-communication/decision-tree.html",
    "decision-communication/option-matrix-path.html",
    "decision-communication/recommended-path.html",
    "decision-communication/tradeoff-quadrant.html",
    "delivery-acceptance/acceptance-ledger.html",
    "delivery-acceptance/delivery-timeline.html",
    "delivery-acceptance/evidence-swimlane.html",
    "delivery-acceptance/risk-action-board.html",
    "fault-debugging/before-after-flow.html",
    "fault-debugging/bpmn-debug-flow.html",
    "fault-debugging/causal-chain.html",
    "fault-debugging/debugging-sequence.html",
    "fault-debugging/state-data-breakpoint.html",
    "feature-iteration/current-target-flow.html",
    "feature-iteration/current-target-sequence.html",
    "feature-iteration/diff-heatmap.html",
    "feature-iteration/release-rollback-track.html",
    "page-mockup/artboard-filmstrip.html",
    "page-mockup/artboard-wireframe.html",
    "page-mockup/primary-path-page-flow.html",
    "page-mockup/responsive-state-board.html",
    "state-data-model/data-flow-model.html",
    "state-data-model/er-lite.html",
    "state-data-model/lifecycle-track.html",
    "state-data-model/state-event-matrix.html",
    "state-data-model/state-machine.html",
    "system-architecture/api-integration.html",
    "system-architecture/component-breakdown.html",
    "system-architecture/data-architecture.html",
    "system-architecture/data-flow.html",
    "system-architecture/delivery-pipeline.html",
    "system-architecture/deployment-topology.html",
    "system-architecture/event-driven.html",
    "system-architecture/identity-access.html",
    "system-architecture/logical-layering.html",
    "system-architecture/network-topology.html",
    "system-architecture/observability-view.html",
    "system-architecture/resilience-view.html",
    "system-architecture/router-v6.html",
    "system-architecture/security-view.html",
    "system-architecture/system-context.html",
    "system-architecture/workload-overview.html",
    "technical-design/api-contract-swimlane.html",
    "technical-design/data-consistency-boundary.html",
    "technical-design/module-contract-data-topology.html",
    "technical-design/release-switch-track.html",
)
REFERENCE_PATHS: Tuple[str, ...] = (
    "business-architecture.md",
    "business-flow.md",
    "code-sequence.md",
    "decision-communication.md",
    "delivery-acceptance.md",
    "fault-debugging.md",
    "feature-iteration.md",
    "page-mockup.md",
    "state-data-model.md",
    "system-architecture.md",
    "technical-design.md",
)
RUNTIME_WORKFLOW_PATH = "runtime-workflow.md"
ADAPTIVE_REFERENCE_PATH = "adaptive-readability.md"
CONTRACT_ASSET_PATHS: Tuple[str, ...] = (
    "assets/contracts/adaptive-viewport/v1.css",
    "assets/contracts/adaptive-viewport/v1.js",
    "assets/contracts/progressive-disclosure/v1.css",
    "assets/contracts/progressive-disclosure/v1.js",
    "assets/contracts/semantic-relations/v1.css",
    "contracts/family-policies.json",
)
UPDATE_MANIFEST_KEYS = {"schema_version", "channel", "version", "ref", "tree_sha256"}
CANONICAL_FILE_COUNT = 82
ADAPTER_IDENTITIES = {
    "codex": (
        "README.md",
        "manifest.template.json",
        ".codex-plugin/plugin.json",
        "skills/vibe-diagram",
        (("files/agents/openai.yaml", "skills/vibe-diagram/agents/openai.yaml"),),
    ),
    "claude": (
        "README.md",
        "manifest.template.json",
        ".claude-plugin/plugin.json",
        "skills/vibe-diagram",
        (),
    ),
    "gemini": (
        "README.md",
        "manifest.template.json",
        "gemini-extension.json",
        "skills/vibe-diagram",
        (),
    ),
    "copilot": (
        "README.md",
        "manifest.template.json",
        "plugin.json",
        "skills/vibe-diagram",
        (),
    ),
}
FORBIDDEN_HOST_TERMS = (
    "Codex",
    "Claude",
    "Gemini",
    "Copilot",
    "Telegram",
    "Vibego",
    "Hypha",
    "LicenseRef-Proprietary",
    "file://",
    "~" + "/.codex",
    "~" + "/.claude",
    "~" + "/.gemini",
)
HAN_RANGES = (
    (0x3007, 0x3007),
    (0x3400, 0x4DBF),
    (0x4E00, 0x9FFF),
    (0xF900, 0xFAFF),
    (0x20000, 0x2A6DF),
    (0x2A700, 0x2B73F),
    (0x2B740, 0x2B81F),
    (0x2B820, 0x2CEAF),
    (0x2CEB0, 0x2EBEF),
    (0x2F800, 0x2FA1F),
    (0x30000, 0x3134F),
    (0x31350, 0x323AF),
)
MACRO_RE = re.compile(r"\{\{\s*([^{}\s]+?)\s*\}\}")
CSS_URL_RE = re.compile(r"url\(\s*(['\"]?)(.*?)\1\s*\)", re.IGNORECASE | re.DOTALL)
CSS_ESCAPE_RE = re.compile(r"\\(?:([0-9a-fA-F]{1,6})\s?|([^\r\n\f]))")
JAVASCRIPT_ESCAPE_RE = re.compile(
    r"\\u\{([0-9a-fA-F]{1,6})\}|\\u([0-9a-fA-F]{4})|\\x([0-9a-fA-F]{2})"
)
NETWORK_SCRIPT_PATTERNS = (
    re.compile(r"\bfetch\b"),
    re.compile(r"\bXMLHttpRequest\b"),
    re.compile(r"\bWebSocket\b"),
    re.compile(r"\bEventSource\b"),
    re.compile(r"\bsendBeacon\b"),
    re.compile(r"\bimportScripts\b"),
    re.compile(r"\bimport\s*\("),
    re.compile(r"\bWorker\b"),
    re.compile(r"\b(?:eval|Function)\b"),
    re.compile(r"\bnew\s+Image\s*\(", re.IGNORECASE),
    re.compile(
        r"(?:\.\s*(?:src|srcset|href|poster|action|formaction)"
        r"|\[\s*['\"](?:src|srcset|href|poster|action|formaction)['\"]\s*\])\s*=",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:window|document|self|globalThis)\s*"
        r"(?:\.\s*(?:location|open)|\[\s*['\"](?:location|open)['\"]\s*\])",
        re.IGNORECASE,
    ),
    re.compile(r"\blocation\s*\.\s*(?:assign|replace)\s*\(", re.IGNORECASE),
    re.compile(r"https?:|(?<!:)//", re.IGNORECASE),
)
RESOURCE_ATTRIBUTES = {"src", "srcset", "poster", "action", "formaction"}
LINK_ATTRIBUTES = {"href", "xlink:href"}
SEQUENCE_CONTRACT_VERSION = "1"
SEQUENCE_MESSAGE_KINDS = frozenset({"sync", "return", "async", "self", "error"})
SEQUENCE_FRAGMENT_KINDS = frozenset({"tx", "opt", "loop", "alt", "group"})
SEQUENCE_OUTCOMES = frozenset({"success", "failure", "partial", "empty"})
SEQUENCE_ROLES = frozenset({"standalone", "overview", "detail"})
SEQUENCE_WIDTH_MODES = frozenset({"auto", "contained", "wide"})
SEQUENCE_HEIGHT_MODES = frozenset({"auto", "flow", "scroll"})
SEQUENCE_PARTICIPANT_LIMIT = 12
SEQUENCE_MESSAGE_LIMIT = 40
SEQUENCE_PHASE_LIMIT = 4
GENERIC_CONTRACT_VERSION = "1"
GENERIC_PROFILES = frozenset({"graph", "matrix", "timeline", "artboard", "ledger"})
GENERIC_WIDTH_MODES = frozenset({"contained", "auto", "wide"})
GENERIC_HEIGHT_MODES = frozenset({"flow", "auto", "scroll"})
GENERIC_MOBILE_MODES = frozenset({"stack", "scroll", "summary"})
GENERIC_LIMIT_KEYS = frozenset({"nodes", "relations", "groups", "details"})
FAMILY_POLICY_KEYS = frozenset(
    {
        "schema_version",
        "contract_version",
        "sequence_exclusions",
        "migration_batches",
        "families",
    }
)
FAMILY_POLICY_FAMILY_KEYS = frozenset({"limits", "templates"})
FAMILY_POLICY_TEMPLATE_KEYS = frozenset({"profile", "limits"})
REFERENCE_CONTRACT_KEYS = {"schema_version", "source_skill_content_sha256", "references"}
CONTENT_ATTRIBUTES = {
    "aria-label",
    "aria-description",
    "title",
    "alt",
    "data-slot",
    "data-body",
    "data-label",
    "data-description",
    "data-content",
    "data-details",
}


def marketplace_document() -> Dict[str, Any]:
    return {
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


VOID_ELEMENTS = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "param",
    "source",
    "track",
    "wbr",
}


class BuildError(RuntimeError):
    """Base class for expected build failures."""


class ValidationError(BuildError):
    """Repository, adapter, manifest, or package validation failed."""


class DeterminismError(ValidationError):
    """Two check builds differed byte-for-byte."""


class PublishError(BuildError):
    """Pre-commit promotion or rollback did not complete cleanly."""


@dataclass(frozen=True)
class ExtraFile:
    source: PurePosixPath
    output: PurePosixPath


@dataclass(frozen=True)
class AdapterSpec:
    schema_version: int
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


@dataclass(frozen=True)
class PublicationFileState:
    sha256: str
    git_mode: int


def _fail(message: str) -> ValidationError:
    return ValidationError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise _fail(f"could not hash {path}: {exc}") from exc
    return digest.hexdigest()


def read_json_unique(path: Path) -> Dict[str, Any]:
    def reject_duplicates(pairs: List[Tuple[str, Any]]) -> Dict[str, Any]:
        result: Dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise _fail(f"duplicate JSON key in {path}: {key}")
            result[key] = value
        return result

    def reject_constant(value: str) -> Any:
        raise _fail(f"non-finite JSON number in {path}: {value}")

    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=reject_duplicates,
            parse_constant=reject_constant,
        )
    except ValidationError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise _fail(f"invalid JSON file {path}: {exc}") from exc

    def reject_non_finite_numbers(item: Any) -> None:
        if isinstance(item, float) and not math.isfinite(item):
            raise _fail(f"non-finite JSON number in {path}")
        if isinstance(item, dict):
            for nested in item.values():
                reject_non_finite_numbers(nested)
        elif isinstance(item, list):
            for nested in item:
                reject_non_finite_numbers(nested)

    reject_non_finite_numbers(value)
    if not isinstance(value, dict):
        raise _fail(f"JSON root must be an object: {path}")
    return value


def safe_relative_path(value: str) -> PurePosixPath:
    if not isinstance(value, str) or not value:
        raise _fail("path must be a non-empty string")
    if "\x00" in value or "\\" in value or "//" in value:
        raise _fail(f"path is not canonical POSIX syntax: {value!r}")
    if value.startswith("/") or re.match(r"^[A-Za-z]:/", value):
        raise _fail(f"absolute path is forbidden: {value!r}")
    parts = value.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise _fail(f"path traversal or ambiguous segment is forbidden: {value!r}")
    path = PurePosixPath(value)
    if path.is_absolute() or path.as_posix() != value:
        raise _fail(f"path is not canonical: {value!r}")
    return path


def _ensure_root_directory(root: Path) -> None:
    if root.is_symlink() or not root.is_dir():
        raise _fail(f"repository root must be a real directory: {root}")


def _ensure_path(root: Path, relative: PurePosixPath, final: str) -> Path:
    _ensure_root_directory(root)
    current = root
    for index, component in enumerate(relative.parts):
        current = current / component
        if current.is_symlink():
            raise _fail(f"symlink is forbidden: {current}")
        is_final = index == len(relative.parts) - 1
        if is_final:
            if final == "file" and not current.is_file():
                raise _fail(f"required regular file is missing: {current}")
            if final == "directory" and not current.is_dir():
                raise _fail(f"required directory is missing: {current}")
        elif not current.is_dir():
            raise _fail(f"path ancestor must be a real directory: {current}")
    return current


def read_version(root: Path) -> str:
    path = _ensure_path(root, PurePosixPath("VERSION"), "file")
    try:
        raw = path.read_bytes()
        text = raw.decode("ascii")
    except (OSError, UnicodeError) as exc:
        raise _fail(f"VERSION must be ASCII: {exc}") from exc
    if not text.endswith("\n") or text.count("\n") != 1:
        raise _fail("VERSION must contain exactly one newline-terminated line")
    version = text[:-1]
    if SEMVER_RE.fullmatch(version) is None:
        raise _fail(f"VERSION is not strict SemVer 2.0: {version!r}")
    return version


def validate_repository_root(root: Path) -> None:
    _ensure_root_directory(root)
    required = (
        PurePosixPath("scripts/build_packages.py"),
        PurePosixPath("VERSION"),
        PurePosixPath("LICENSE"),
        PurePosixPath("contracts/template_migration_baseline.json"),
        PurePosixPath("contracts/reference_migration_baseline.json"),
        PurePosixPath("contracts/interaction_contract_baseline.json"),
    )
    for relative in required:
        _ensure_path(root, relative, "file")
    read_version(root)
    license_path = root / "LICENSE"
    try:
        size = license_path.stat().st_size
        text = license_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise _fail(f"could not read LICENSE: {exc}") from exc
    if size != LICENSE_SIZE or sha256_file(license_path) != LICENSE_SHA256:
        raise _fail("LICENSE does not match the frozen Apache-2.0 text")
    if (
        "Apache License" not in text
        or "Version 2.0, January 2004" not in text
        or "http://www.apache.org/licenses/" not in text
    ):
        raise _fail("LICENSE is missing the Apache-2.0 heading")
    for section in range(1, 10):
        if re.search(rf"(?m)^\s*{section}\. ", text) is None:
            raise _fail(f"LICENSE is missing Apache-2.0 section {section}")


def parse_skill_frontmatter(text: str) -> Dict[str, str]:
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        raise _fail("SKILL.md must begin with YAML frontmatter")
    try:
        closing = lines.index("---", 1)
    except ValueError as exc:
        raise _fail("SKILL.md frontmatter is not closed") from exc
    values: Dict[str, str] = {}
    for line in lines[1:closing]:
        if not line or line[:1].isspace() or ":" not in line:
            raise _fail("frontmatter must contain flat single-line key/value pairs")
        key, value = line.split(":", 1)
        value = value.strip()
        if key in values:
            raise _fail(f"duplicate frontmatter key: {key}")
        if key not in {"name", "description"}:
            raise _fail(f"unsupported frontmatter key: {key}")
        if not value or value[0] in "[{|>&*!" or value.startswith("- "):
            raise _fail(f"frontmatter {key} must be a single-line string")
        if value.lower() in {"null", "true", "false", "~"} or re.fullmatch(
            r"[-+]?\d+(?:\.\d+)?", value
        ):
            raise _fail(f"frontmatter {key} must be a string")
        values[key] = value
    if set(values) != {"name", "description"}:
        raise _fail("frontmatter must contain exactly name and description")
    return values


def _render_value(value: Any, version: str, counter: List[int]) -> Any:
    if isinstance(value, dict):
        rendered: Dict[str, Any] = {}
        for key, nested in value.items():
            if VERSION_PLACEHOLDER in key:
                raise _fail("version placeholder is forbidden in JSON object keys")
            rendered[key] = _render_value(nested, version, counter)
        return rendered
    if isinstance(value, list):
        return [_render_value(nested, version, counter) for nested in value]
    if isinstance(value, str):
        if value == VERSION_PLACEHOLDER:
            counter[0] += 1
            return version
        if VERSION_PLACEHOLDER in value:
            raise _fail("version placeholder must occupy an entire string value")
    return value


def render_template(value: Any, version: str) -> Any:
    if SEMVER_RE.fullmatch(version) is None:
        raise _fail(f"render version is not strict SemVer 2.0: {version!r}")
    counter = [0]
    rendered = _render_value(value, version, counter)
    if counter[0] != 1:
        raise _fail(f"manifest template must contain exactly one {VERSION_PLACEHOLDER}")
    return rendered


def load_adapter(root: Path, client: str) -> AdapterSpec:
    if client not in CLIENTS:
        raise _fail(f"unknown client: {client}")
    adapter_dir = PurePosixPath("adapters") / client
    _ensure_path(root, adapter_dir, "directory")
    definition_path = _ensure_path(root, adapter_dir / "adapter.json", "file")
    definition = read_json_unique(definition_path)
    if set(definition) != ADAPTER_KEYS:
        raise _fail(f"adapter {client} has an invalid key set")
    if type(definition["schema_version"]) is not int or definition["schema_version"] != 1:
        raise _fail(f"adapter {client} schema_version must be integer 1")
    if definition["client"] != client:
        raise _fail(f"adapter client does not match directory: {client}")
    expected_identity = ADAPTER_IDENTITIES[client]
    expected_definition = {
        "schema_version": 1,
        "client": client,
        "documentation": expected_identity[0],
        "manifest_template": expected_identity[1],
        "manifest_output": expected_identity[2],
        "skills_output": expected_identity[3],
        "extra_files": [
            {"source": source, "output": output}
            for source, output in expected_identity[4]
        ],
    }
    if definition != expected_definition:
        raise _fail(f"adapter {client} does not match its frozen identity")
    string_keys = (
        "documentation",
        "manifest_template",
        "manifest_output",
        "skills_output",
    )
    if any(not isinstance(definition[key], str) for key in string_keys):
        raise _fail(f"adapter {client} paths must be strings")
    documentation = safe_relative_path(definition["documentation"])
    manifest_template = safe_relative_path(definition["manifest_template"])
    manifest_output = safe_relative_path(definition["manifest_output"])
    skills_output = safe_relative_path(definition["skills_output"])
    documentation_path = _ensure_path(root, adapter_dir / documentation, "file")
    template_path = _ensure_path(root, adapter_dir / manifest_template, "file")
    try:
        documentation_text = documentation_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise _fail(f"could not read adapter documentation: {exc}") from exc
    if "Unverified" not in documentation_text:
        raise _fail(f"adapter {client} documentation must preserve the Unverified boundary")
    render_template(read_json_unique(template_path), "0.0.0")
    raw_extra = definition["extra_files"]
    if not isinstance(raw_extra, list):
        raise _fail(f"adapter {client} extra_files must be an array")
    extras: List[ExtraFile] = []
    outputs = {manifest_output}
    for index, item in enumerate(raw_extra):
        if not isinstance(item, dict) or set(item) != EXTRA_FILE_KEYS:
            raise _fail(f"adapter {client} extra_files[{index}] has invalid keys")
        if not isinstance(item["source"], str) or not isinstance(item["output"], str):
            raise _fail(f"adapter {client} extra file paths must be strings")
        source = safe_relative_path(item["source"])
        output = safe_relative_path(item["output"])
        _ensure_path(root, adapter_dir / source, "file")
        if output in outputs:
            raise _fail(f"adapter {client} has duplicate derived output: {output}")
        outputs.add(output)
        extras.append(ExtraFile(source=source, output=output))
    return AdapterSpec(
        schema_version=1,
        client=client,
        documentation=documentation,
        manifest_template=manifest_template,
        manifest_output=manifest_output,
        skills_output=skills_output,
        extra_files=tuple(extras),
    )


def _validate_sha256(value: Any, label: str) -> None:
    if not isinstance(value, str) or HEX_SHA256_RE.fullmatch(value) is None:
        raise _fail(f"{label} must be a lowercase SHA-256 digest")


def _validate_string_list(value: Any, label: str) -> None:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise _fail(f"{label} must be an array of strings")


def _validate_template_snapshot(snapshot: Any, label: str) -> None:
    if not isinstance(snapshot, dict) or set(snapshot) != TEMPLATE_SNAPSHOT_KEYS:
        raise _fail(f"{label} has an invalid snapshot schema")
    _validate_sha256(snapshot["file_sha256"], f"{label}.file_sha256")
    _validate_sha256(snapshot["structure_sha256"], f"{label}.structure_sha256")
    _validate_string_list(snapshot["data_slots"], f"{label}.data_slots")
    _validate_string_list(snapshot["macros"], f"{label}.macros")
    pairs = snapshot["slot_macro_pairs"]
    if not isinstance(pairs, list):
        raise _fail(f"{label}.slot_macro_pairs must be an array")
    for index, pair in enumerate(pairs):
        if (
            not isinstance(pair, dict)
            or set(pair) != {"macro", "slot"}
            or not isinstance(pair["macro"], str)
            or not isinstance(pair["slot"], str)
        ):
            raise _fail(f"{label}.slot_macro_pairs[{index}] is invalid")


def canonical_file_map(root: Path) -> Dict[PurePosixPath, Path]:
    canonical_relative = PurePosixPath("skills/vibe-diagram")
    canonical_root = _ensure_path(root, canonical_relative, "directory")
    files: Dict[PurePosixPath, Path] = {}
    for path in canonical_root.rglob("*"):
        if path.is_symlink():
            raise _fail(f"symlink is forbidden in canonical skill tree: {path}")
        if path.is_dir():
            continue
        if not path.is_file():
            raise _fail(f"non-regular object is forbidden in canonical skill tree: {path}")
        relative = PurePosixPath(path.relative_to(canonical_root).as_posix())
        files[relative] = path
    return dict(sorted(files.items(), key=lambda item: item[0].as_posix().encode("utf-8")))


def update_tree_sha256(root: Path) -> str:
    digest = hashlib.sha256()
    for relative, path in canonical_file_map(root).items():
        if relative == PurePosixPath("update.json"):
            continue
        payload = path.read_bytes()
        digest.update(relative.as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(len(payload).to_bytes(8, "big"))
        digest.update(hashlib.sha256(payload).digest())
    return digest.hexdigest()


def load_template_contract(root: Path) -> Dict[str, Any]:
    path = _ensure_path(
        root, PurePosixPath("contracts/template_migration_baseline.json"), "file"
    )
    contract = read_json_unique(path)
    if set(contract) != TEMPLATE_CONTRACT_KEYS:
        raise _fail("template contract has an invalid root schema")
    if type(contract["schema_version"]) is not int or contract["schema_version"] != 3:
        raise _fail("template contract schema_version must be integer 3")
    if contract["signature_algorithm"] != "htmlparser-events-v1":
        raise _fail("template contract signature_algorithm is invalid")
    _validate_sha256(contract["source_contract_sha256"], "source_contract_sha256")
    if contract["source_contract_sha256"] != SOURCE_TEMPLATE_CONTRACT_SHA256:
        raise _fail("template contract source digest does not match the frozen migration input")
    allowlist = contract["sequence_redesign_allowlist"]
    if allowlist != list(SEQUENCE_REDESIGN_PATHS):
        raise _fail("template contract sequence redesign allowlist is invalid")
    migration_batches = contract["interaction_migration_batches"]
    policy_path = _ensure_path(
        root,
        PurePosixPath("skills/vibe-diagram/contracts/family-policies.json"),
        "file",
    )
    policy = load_family_policies(policy_path)
    if migration_batches != policy["migration_batches"]:
        raise _fail("template contract migration batches differ from the family policy")
    templates = contract["templates"]
    if not isinstance(templates, dict):
        raise _fail("template contract templates must be an object")
    canonical_templates = {
        relative.as_posix()[len("assets/templates/") :]
        for relative in canonical_file_map(root)
        if relative.as_posix().startswith("assets/templates/")
        and relative.as_posix().endswith(".html")
    }
    if set(templates) != set(TEMPLATE_PATHS) or canonical_templates != set(TEMPLATE_PATHS):
        raise _fail("template contract must contain the exact 58 canonical template paths")
    changed = set()
    for relative, entry in templates.items():
        safe_relative_path(relative)
        if not isinstance(entry, dict) or set(entry) != TEMPLATE_ENTRY_KEYS:
            raise _fail(f"template contract entry is invalid: {relative}")
        _validate_template_snapshot(entry["source"], f"{relative}.source")
        _validate_template_snapshot(entry["canonical"], f"{relative}.canonical")
        if entry["source"] != entry["canonical"]:
            changed.add(relative)
            if not isinstance(entry["change_reason"], str) or not entry["change_reason"].strip():
                raise _fail(f"changed template requires a reason: {relative}")
        elif entry["change_reason"] is not None:
            raise _fail(f"unchanged template reason must be null: {relative}")
    source_payload = json.dumps(
        {relative: templates[relative]["source"] for relative in TEMPLATE_PATHS},
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    if hashlib.sha256(source_payload).hexdigest() != SOURCE_TEMPLATE_SNAPSHOTS_SHA256:
        raise _fail("template contract frozen source snapshots have drifted")
    completed = {
        relative
        for entries in migration_batches.values()
        for relative in entries
    }
    if changed != set(SEQUENCE_REDESIGN_PATHS) | completed:
        raise _fail("changed templates differ from the approved sequence and interaction migrations")
    return contract


def load_reference_contract(root: Path) -> Dict[str, Any]:
    path = _ensure_path(
        root, PurePosixPath("contracts/reference_migration_baseline.json"), "file"
    )
    contract = read_json_unique(path)
    if set(contract) != REFERENCE_CONTRACT_KEYS:
        raise _fail("reference contract has an invalid root schema")
    if type(contract["schema_version"]) is not int or contract["schema_version"] != 1:
        raise _fail("reference contract schema_version must be integer 1")
    _validate_sha256(contract["source_skill_content_sha256"], "source_skill_content_sha256")
    if contract["source_skill_content_sha256"] != SOURCE_SKILL_CONTENT_SHA256:
        raise _fail("reference contract source digest does not match the frozen skill input")
    references = contract["references"]
    if not isinstance(references, dict):
        raise _fail("reference contract references must be an object")
    expected = {
        relative.name
        for relative in canonical_file_map(root)
        if relative.parent == PurePosixPath("references")
        and relative.suffix == ".md"
        and relative.name not in {RUNTIME_WORKFLOW_PATH, ADAPTIVE_REFERENCE_PATH}
    }
    if set(references) != set(REFERENCE_PATHS) or expected != set(REFERENCE_PATHS):
        raise _fail("reference contract must contain the exact 11 canonical references")
    for relative, digest in references.items():
        safe_relative_path(relative)
        _validate_sha256(digest, f"references.{relative}")
    return contract


def load_interaction_contract(root: Path) -> Dict[str, Any]:
    path = _ensure_path(
        root, PurePosixPath("contracts/interaction_contract_baseline.json"), "file"
    )
    contract = read_json_unique(path)
    if set(contract) != {"schema_version", "contracts", "scope", "evidence"}:
        raise _fail("interaction contract has an invalid root schema")
    if type(contract["schema_version"]) is not int or contract["schema_version"] != 1:
        raise _fail("interaction contract schema_version must be integer 1")
    if contract["contracts"] != {
        "adaptive_viewport": "1",
        "semantic_relations": "1",
        "progressive_disclosure": "1",
    }:
        raise _fail("interaction contract versions are invalid")
    scope = contract["scope"]
    if not isinstance(scope, dict) or set(scope) != {
        "generic_template_count",
        "sequence_template_count",
        "completed_batches",
        "completed_templates",
    }:
        raise _fail("interaction contract scope is invalid")
    if type(scope["generic_template_count"]) is not int or scope["generic_template_count"] != 52:
        raise _fail("interaction contract generic template count is invalid")
    if type(scope["sequence_template_count"]) is not int or scope["sequence_template_count"] != 6:
        raise _fail("interaction contract sequence template count is invalid")
    completed_batches = scope["completed_batches"]
    if (
        not isinstance(completed_batches, list)
        or not completed_batches
        or completed_batches[0] != "B00"
        or len(completed_batches) != len(set(completed_batches))
        or any(re.fullmatch(r"B(?:0[0-9]|1[0-5])", batch) is None for batch in completed_batches)
    ):
        raise _fail("interaction contract completed batches are invalid")
    completed_templates = scope["completed_templates"]
    generic_templates = set(TEMPLATE_PATHS) - set(SEQUENCE_REDESIGN_PATHS)
    if (
        not isinstance(completed_templates, list)
        or completed_templates != sorted(completed_templates)
        or len(completed_templates) != len(set(completed_templates))
        or not set(completed_templates) <= generic_templates
    ):
        raise _fail("interaction contract completed templates are invalid")
    evidence = contract["evidence"]
    if not isinstance(evidence, dict) or set(evidence) != {
        "synthetic_contracts",
        "canonical_templates",
        "browser_runtime",
        "client_runtime",
    }:
        raise _fail("interaction contract evidence scope is invalid")
    return contract


class _TemplateLayoutParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.events: List[Sequence[object]] = []
        self.root_count = 0
        self._stack: List[str] = []

    @staticmethod
    def _is_root(tag: str, attrs: Sequence[Tuple[str, Optional[str]]]) -> bool:
        if tag != "section":
            return False
        class_value = next((value or "" for name, value in attrs if name == "class"), "")
        return "template-layout" in class_value.split()

    @staticmethod
    def _attrs(attrs: Sequence[Tuple[str, Optional[str]]]) -> Tuple[Tuple[str, str], ...]:
        normalized = []
        for name, value in attrs:
            normalized_value = "_" if name in CONTENT_ATTRIBUTES or name.startswith("aria-") else value or ""
            normalized.append((name, normalized_value))
        return tuple(sorted(normalized))

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        tag = tag.lower()
        if self._is_root(tag, attrs):
            self.root_count += 1
            if self._stack:
                raise _fail("template-layout roots must not be nested")
            self._stack.append(tag)
            return
        if not self._stack:
            return
        self.events.append(("start", tag, self._attrs(attrs)))
        if tag not in VOID_ELEMENTS:
            self._stack.append(tag)

    def handle_startendtag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        tag = tag.lower()
        if self._is_root(tag, attrs):
            self.root_count += 1
            raise _fail("template-layout root must not be self-closing")
        if self._stack:
            self.events.append(("empty", tag, self._attrs(attrs)))

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if not self._stack:
            return
        if self._stack[-1] != tag:
            raise _fail(f"mismatched closing tag: expected {self._stack[-1]}, got {tag}")
        if len(self._stack) > 1:
            self.events.append(("end", tag))
        self._stack.pop()

    def finish(self) -> None:
        if self.root_count != 1:
            raise _fail(f"expected exactly one template-layout root, found {self.root_count}")
        if self._stack:
            raise _fail("template-layout root is not closed")


def template_structure_signature(html: str) -> str:
    parser = _TemplateLayoutParser()
    try:
        parser.feed(html)
        parser.close()
        parser.finish()
    except ValidationError:
        raise
    except Exception as exc:
        raise _fail(f"could not parse template structure: {exc}") from exc
    payload = json.dumps(parser.events, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def file_records(root: Path) -> Tuple[FileRecord, ...]:
    _ensure_root_directory(root)
    records: List[FileRecord] = []
    for path in root.rglob("*"):
        if path.is_symlink():
            raise _fail(f"symlink is forbidden in package tree: {path}")
        if path.is_dir():
            continue
        if not path.is_file():
            raise _fail(f"non-regular object is forbidden in package tree: {path}")
        relative = path.relative_to(root).as_posix()
        try:
            size = path.stat().st_size
        except OSError as exc:
            raise _fail(f"could not stat package file {path}: {exc}") from exc
        records.append(FileRecord(path=relative, size=size, sha256=sha256_file(path)))
    return tuple(sorted(records, key=lambda record: record.path.encode("utf-8")))


def tree_record(root: Path) -> TreeRecord:
    records = file_records(root)
    framed = bytearray(b"vibe-diagram-tree-v1\0")
    for record in records:
        path_bytes = record.path.encode("utf-8")
        framed.extend(len(path_bytes).to_bytes(4, "big"))
        framed.extend(path_bytes)
        framed.extend(bytes.fromhex(record.sha256))
    return TreeRecord(
        file_count=len(records),
        tree_sha256=hashlib.sha256(bytes(framed)).hexdigest(),
        files=records,
    )


def _file_record_dict(record: FileRecord) -> Dict[str, Any]:
    return {"path": record.path, "size": record.size, "sha256": record.sha256}


def _tree_record_dict(record: TreeRecord) -> Dict[str, Any]:
    return {
        "file_count": record.file_count,
        "tree_sha256": record.tree_sha256,
        "files": [_file_record_dict(item) for item in record.files],
    }


def _duplicates(attrs: Sequence[Tuple[str, Optional[str]]]) -> List[str]:
    names = [name.lower() for name, _ in attrs]
    return sorted({name for name in names if names.count(name) > 1})


def _validated_limits(value: Any, label: str, *, partial: bool) -> Dict[str, int]:
    if not isinstance(value, dict):
        raise _fail(f"{label} must be an object")
    keys = set(value)
    if (not partial and keys != GENERIC_LIMIT_KEYS) or (partial and not keys <= GENERIC_LIMIT_KEYS):
        raise _fail(f"{label} has an invalid key set")
    result: Dict[str, int] = {}
    for key, limit in value.items():
        if type(limit) is not int or limit < 1:
            raise _fail(f"{label}.{key} must be a positive integer")
        result[key] = limit
    return result


def _validated_migration_batches(value: Any) -> Dict[str, List[str]]:
    if not isinstance(value, dict) or list(value) != sorted(value):
        raise _fail("family policy migration batches must be an ordered object")
    generic_templates = set(TEMPLATE_PATHS) - set(SEQUENCE_REDESIGN_PATHS)
    seen = set()
    result: Dict[str, List[str]] = {}
    for batch, paths in value.items():
        if re.fullmatch(r"B(?:0[1-9]|1[0-3])", batch) is None:
            raise _fail(f"family policy migration batch id is invalid: {batch}")
        if (
            not isinstance(paths, list)
            or not paths
            or paths != sorted(paths)
            or len(paths) != len(set(paths))
            or not set(paths) <= generic_templates
            or seen & set(paths)
        ):
            raise _fail(f"family policy migration batch paths are invalid: {batch}")
        seen.update(paths)
        result[batch] = paths
    return result


def load_family_policies(path: Path) -> Dict[str, Any]:
    policy = read_json_unique(path)
    if set(policy) != FAMILY_POLICY_KEYS:
        raise _fail("family policy has an invalid root schema")
    if type(policy["schema_version"]) is not int or policy["schema_version"] != 1:
        raise _fail("family policy schema_version must be integer 1")
    if policy["contract_version"] != GENERIC_CONTRACT_VERSION:
        raise _fail("family policy contract_version is invalid")
    exclusions = policy["sequence_exclusions"]
    if exclusions != sorted(SEQUENCE_REDESIGN_PATHS):
        raise _fail("family policy sequence exclusions are invalid")
    _validated_migration_batches(policy["migration_batches"])
    families = policy["families"]
    if not isinstance(families, dict) or len(families) != 10:
        raise _fail("family policy must define exactly ten generic families")
    covered = set()
    for family, definition in families.items():
        if not isinstance(definition, dict) or set(definition) != FAMILY_POLICY_FAMILY_KEYS:
            raise _fail(f"family policy definition is invalid: {family}")
        family_limits = _validated_limits(
            definition["limits"], f"families.{family}.limits", partial=False
        )
        templates = definition["templates"]
        if not isinstance(templates, dict) or not templates:
            raise _fail(f"family policy templates must be a non-empty object: {family}")
        for template_id, template in templates.items():
            if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", template_id):
                raise _fail(f"family policy template id is invalid: {family}/{template_id}")
            if not isinstance(template, dict) or set(template) != FAMILY_POLICY_TEMPLATE_KEYS:
                raise _fail(f"family policy template definition is invalid: {family}/{template_id}")
            if template["profile"] not in GENERIC_PROFILES:
                raise _fail(f"family policy profile is invalid: {family}/{template_id}")
            overrides = _validated_limits(
                template["limits"],
                f"families.{family}.templates.{template_id}.limits",
                partial=True,
            )
            if any(limit > family_limits[key] for key, limit in overrides.items()):
                raise _fail(f"family policy template limit widens its family: {family}/{template_id}")
            covered.add(f"{family}/{template_id}.html")
    expected = set(TEMPLATE_PATHS) - set(SEQUENCE_REDESIGN_PATHS)
    if covered != expected:
        raise _fail("family policy must cover the exact 52 non-sequence templates")
    return policy


@dataclass
class _GenericCanvasRecord:
    attrs: Dict[str, str]
    node_ids: List[str]
    group_ids: List[str]
    relations: List[Tuple[str, str, str, str, str]]
    row_ids: List[str]
    col_ids: List[str]
    cells: List[Tuple[str, str]]
    detail_ids: List[str]
    visible_relation_ids: List[str]


class _GenericContractParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.canvases: List[_GenericCanvasRecord] = []
        self.fallback_ids: List[str] = []
        self.errors: List[str] = []
        self._canvas: Optional[_GenericCanvasRecord] = None
        self._stack: List[Tuple[str, bool]] = []

    def handle_starttag(
        self, tag: str, attrs: List[Tuple[str, Optional[str]]]
    ) -> None:
        normalized = [(name.lower(), value or "") for name, value in attrs]
        values = dict(normalized)
        starts_canvas = "data-diagram-canvas" in values
        if starts_canvas:
            if self._canvas is not None:
                self.errors.append("Diagram canvases must not be nested.")
            else:
                self._canvas = _GenericCanvasRecord(values, [], [], [], [], [], [], [], [])
                self.canvases.append(self._canvas)
        if "data-fallback-for" in values:
            self.fallback_ids.append(values["data-fallback-for"].strip())
        if self._canvas is not None:
            semantic = any(
                key in values
                for key in (
                    "data-diagram-node-id",
                    "data-diagram-group-id",
                    "data-diagram-relation-id",
                    "data-matrix-row-id",
                    "data-matrix-col-id",
                    "data-diagram-detail-id",
                    "data-diagram-visible-relation-id",
                )
            )
            duplicates = _duplicates(attrs) if semantic or starts_canvas else []
            if duplicates:
                self.errors.append(
                    "Duplicate generic contract attributes: " + ", ".join(duplicates) + "."
                )
            if "data-diagram-node-id" in values:
                self._canvas.node_ids.append(values["data-diagram-node-id"].strip())
                if not values.get("data-semantic-role", "").strip():
                    self.errors.append("Every diagram node must declare data-semantic-role.")
            if "data-diagram-group-id" in values:
                self._canvas.group_ids.append(values["data-diagram-group-id"].strip())
                if not values.get("data-semantic-role", "").strip():
                    self.errors.append("Every diagram group must declare data-semantic-role.")
            if "data-diagram-relation-id" in values:
                self._canvas.relations.append(
                    (
                        values["data-diagram-relation-id"].strip(),
                        values.get("data-from", "").strip(),
                        values.get("data-to", "").strip(),
                        values.get("data-relation-kind", "").strip(),
                        values.get("data-semantic", "").strip(),
                    )
                )
            if "data-matrix-row-id" in values:
                self._canvas.row_ids.append(values["data-matrix-row-id"].strip())
            if "data-matrix-col-id" in values:
                self._canvas.col_ids.append(values["data-matrix-col-id"].strip())
            if "data-matrix-row" in values or "data-matrix-col" in values:
                self._canvas.cells.append(
                    (
                        values.get("data-matrix-row", "").strip(),
                        values.get("data-matrix-col", "").strip(),
                    )
                )
            if "data-diagram-detail-id" in values:
                self._canvas.detail_ids.append(values["data-diagram-detail-id"].strip())
            if "data-diagram-visible-relation-id" in values:
                is_svg_edge = tag in {"line", "path", "polygon", "polyline"}
                is_html_edge = values.get("data-visible-relation-kind") == "edge"
                if not (is_svg_edge or is_html_edge):
                    self.errors.append(
                        "Visible relation bindings must use an SVG edge or an explicit HTML edge carrier."
                    )
                self._canvas.visible_relation_ids.append(
                    values["data-diagram-visible-relation-id"].strip()
                )
        if tag not in VOID_ELEMENTS:
            self._stack.append((tag, starts_canvas))

    def handle_startendtag(
        self, tag: str, attrs: List[Tuple[str, Optional[str]]]
    ) -> None:
        self.handle_starttag(tag, attrs)
        if tag not in VOID_ELEMENTS:
            self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        if not self._stack:
            return
        _open_tag, closes_canvas = self._stack.pop()
        if closes_canvas:
            self._canvas = None


def generic_contract_errors(
    html: str,
    family: str,
    template_id: str,
    policy: Mapping[str, Any],
) -> List[str]:
    relative = f"{family}/{template_id}.html"
    if relative in set(policy["sequence_exclusions"]):
        return []
    definition = policy["families"].get(family, {}).get("templates", {}).get(template_id)
    if definition is None:
        return [f"No generic contract policy exists for {family}/{template_id}."]
    parser = _GenericContractParser()
    try:
        parser.feed(html)
        parser.close()
    except Exception as exc:
        return [f"Could not parse generic diagram contract: {exc}."]
    errors = list(parser.errors)
    if not parser.canvases:
        errors.append("Generic diagram contract requires at least one canvas.")
        return errors
    family_limits = policy["families"][family]["limits"]
    limits = {**family_limits, **definition["limits"]}
    canvas_ids = [canvas.attrs.get("data-diagram-id", "").strip() for canvas in parser.canvases]
    if "" in canvas_ids:
        errors.append("Every diagram canvas requires a non-empty data-diagram-id.")
    if len(canvas_ids) != len(set(canvas_ids)):
        errors.append("Diagram canvas ids must be unique.")
    for canvas in parser.canvases:
        attrs = canvas.attrs
        canvas_id = attrs.get("data-diagram-id", "").strip()
        if attrs.get("data-diagram-contract") != GENERIC_CONTRACT_VERSION:
            errors.append("Diagram canvas contract must be version 1.")
        if attrs.get("data-diagram-profile") != definition["profile"]:
            errors.append("Diagram canvas profile must match its trusted family policy.")
        if attrs.get("data-diagram-width") not in GENERIC_WIDTH_MODES:
            errors.append("Diagram canvas width mode is invalid.")
        if attrs.get("data-diagram-height") not in GENERIC_HEIGHT_MODES:
            errors.append("Diagram canvas height mode is invalid.")
        if attrs.get("data-diagram-mobile") not in GENERIC_MOBILE_MODES:
            errors.append("Diagram canvas mobile fallback mode is invalid.")
        semantic_ids = canvas.node_ids + canvas.group_ids
        if any(not value for value in semantic_ids):
            errors.append("Diagram node and group ids must be non-empty.")
        if len(semantic_ids) != len(set(semantic_ids)):
            errors.append("Diagram node and group ids must be unique within a canvas.")
        endpoints = set(semantic_ids)
        relation_ids = []
        for relation_id, source, target, kind, semantic in canvas.relations:
            relation_ids.append(relation_id)
            if not all((relation_id, source, target, kind, semantic)):
                errors.append("Every diagram relation requires id, endpoints, kind, and semantic.")
            elif source not in endpoints or target not in endpoints:
                errors.append("Diagram relation endpoints must reference authored nodes or groups.")
        if len(relation_ids) != len(set(relation_ids)):
            errors.append("Diagram relation ids must be unique within a canvas.")
        visible_relation_ids = canvas.visible_relation_ids
        if any(not relation_id for relation_id in visible_relation_ids):
            errors.append("Visible relation bindings must use non-empty relation ids.")
        if len(visible_relation_ids) != len(set(visible_relation_ids)):
            errors.append("Visible relation bindings must be unique within a canvas.")
        missing_visible = sorted(set(relation_ids) - set(visible_relation_ids))
        extra_visible = sorted(set(visible_relation_ids) - set(relation_ids))
        if missing_visible:
            errors.append(
                "Every diagram relation requires one visible edge binding: "
                + ", ".join(missing_visible)
                + "."
            )
        if extra_visible:
            errors.append(
                "Visible edge bindings must reference authored diagram relations: "
                + ", ".join(extra_visible)
                + "."
            )
        if definition["profile"] == "matrix":
            rows, columns = set(canvas.row_ids), set(canvas.col_ids)
            if not rows or not columns or not canvas.cells:
                errors.append("Matrix profile requires authored row axes, column axes, and cells.")
            for row, column in canvas.cells:
                if row not in rows or column not in columns:
                    errors.append("Matrix cells must reference authored row and column axes.")
        counts = {
            "nodes": len(canvas.node_ids),
            "relations": len(canvas.relations),
            "groups": len(canvas.group_ids),
            "details": len(canvas.detail_ids),
        }
        for key, count in counts.items():
            if count > limits[key]:
                errors.append(f"Diagram canvas exceeds the {key} complexity budget.")
        if canvas_id and canvas_id not in parser.fallback_ids:
            errors.append("Every diagram canvas requires a matching data-fallback-for baseline.")
    return list(dict.fromkeys(errors))


def adaptive_kernel_errors(html: str, css: str, script: str) -> List[str]:
    errors = []
    for tag, expected in (("style", css), ("script", script)):
        matches = re.findall(
            rf'<{tag} data-adaptive-viewport-kernel="1">\n(.*?)\n</{tag}>',
            html,
            flags=re.DOTALL,
        )
        if len(matches) != 1:
            errors.append(f"Migrated generic template requires exactly one adaptive {tag} kernel.")
        elif matches[0] != expected.rstrip("\n"):
            errors.append(f"Migrated generic template adaptive {tag} kernel has drifted.")
    return errors


def _allowed_embedded_reference(value: str) -> bool:
    value = value.strip()
    return not value or value.startswith("#") or value.startswith("data:")


def _contains_han(text: str) -> bool:
    return any(start <= ord(character) <= end for character in text for start, end in HAN_RANGES)


def _decode_css_escapes(value: str) -> str:
    def replace(match: re.Match) -> str:
        if match.group(1):
            codepoint = int(match.group(1), 16)
            return chr(codepoint) if codepoint and codepoint <= 0x10FFFF else "\ufffd"
        return match.group(2) or "\ufffd"

    return CSS_ESCAPE_RE.sub(replace, value)


def _decode_javascript_escapes(value: str) -> str:
    def replace(match: re.Match) -> str:
        codepoint = int(next(group for group in match.groups() if group is not None), 16)
        return chr(codepoint) if codepoint <= 0x10FFFF else "\ufffd"

    return JAVASCRIPT_ESCAPE_RE.sub(replace, value)


class _CanonicalHtmlParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.has_doctype = False
        self.has_html_en = False
        self.has_viewport = False
        self.has_main = False
        self.has_h1 = False
        self.main_attrs: List[Dict[str, str]] = []
        self.styles: List[str] = []
        self.scripts: List[str] = []
        self.errors: List[str] = []
        self._style_depth = 0
        self._script_depth = 0

    def handle_decl(self, decl: str) -> None:
        if decl.strip().lower() == "doctype html":
            self.has_doctype = True

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        tag = tag.lower()
        duplicates = _duplicates(attrs)
        if duplicates:
            self.errors.append(f"duplicate attributes on {tag}: {', '.join(duplicates)}")
        attrs_map = {name.lower(): value or "" for name, value in attrs}
        if tag == "html" and attrs_map.get("lang") == "en":
            self.has_html_en = True
        if tag == "meta" and attrs_map.get("name", "").lower() == "viewport":
            self.has_viewport = True
        if tag == "meta" and attrs_map.get("http-equiv", "").strip().casefold() == "refresh":
            self.errors.append("meta refresh navigation is forbidden")
        if tag == "main":
            self.has_main = True
            self.main_attrs.append(attrs_map)
        if tag == "h1":
            self.has_h1 = True
        if tag in {"iframe", "object", "embed"}:
            self.errors.append(f"embedded container is forbidden: {tag}")
        for name, value in attrs_map.items():
            if name == "ping" and value.strip():
                self.errors.append("ping navigation is forbidden")
            elif name == "srcset" and value.strip():
                self.errors.append("srcset is forbidden")
            elif name in RESOURCE_ATTRIBUTES and not _allowed_embedded_reference(value):
                self.errors.append(f"external or relative resource is forbidden: {name}={value}")
            elif name in LINK_ATTRIBUTES and not _allowed_embedded_reference(value):
                self.errors.append(f"external or relative link is forbidden: {name}={value}")
            if name == "style":
                self.styles.append(value)
        if tag == "style":
            self._style_depth += 1
        if tag == "script":
            if attrs_map.get("type", "").strip().lower() == "module":
                self.errors.append("JavaScript module loading is forbidden")
            self._script_depth += 1

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "style":
            self._style_depth = max(0, self._style_depth - 1)
        if tag == "script":
            self._script_depth = max(0, self._script_depth - 1)

    def handle_data(self, data: str) -> None:
        if self._style_depth:
            self.styles.append(data)
        if self._script_depth:
            self.scripts.append(data)

    def finish(self) -> None:
        for css in self.styles:
            normalized = _decode_css_escapes(css)
            if re.search(r"@import\b", normalized, re.IGNORECASE):
                self.errors.append("CSS @import is forbidden")
            if re.search(r"(?:-webkit-)?image-set\s*\(", normalized, re.IGNORECASE):
                self.errors.append("CSS image-set is forbidden")
            for match in CSS_URL_RE.finditer(normalized):
                if not _allowed_embedded_reference(match.group(2)):
                    self.errors.append(f"external or relative CSS url is forbidden: {match.group(2)}")
        script = _decode_javascript_escapes("\n".join(self.scripts))
        for pattern in NETWORK_SCRIPT_PATTERNS:
            if pattern.search(script):
                self.errors.append(f"runtime network or dynamic-code API is forbidden: {pattern.pattern}")


class _SlotMacroParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.data_slots: List[str] = []
        self.macros: List[str] = []
        self.pairs: List[Dict[str, str]] = []
        self._stack: List[Tuple[str, str]] = []

    def _record(self, value: str, slot: str) -> None:
        for match in MACRO_RE.finditer(value):
            macro = match.group(1)
            self.macros.append(macro)
            self.pairs.append({"macro": macro, "slot": slot})

    def _start(
        self, tag: str, attrs: Sequence[Tuple[str, Optional[str]]], push: bool
    ) -> None:
        parent_slot = self._stack[-1][1] if self._stack else ""
        own_slot = next((value or "" for name, value in attrs if name == "data-slot"), "")
        current_slot = own_slot or parent_slot
        if own_slot:
            self.data_slots.append(own_slot)
        for _, value in attrs:
            if value:
                self._record(value, current_slot)
        if push and tag not in VOID_ELEMENTS:
            self._stack.append((tag, current_slot))

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        self._start(tag.lower(), attrs, True)

    def handle_startendtag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        self._start(tag.lower(), attrs, False)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in VOID_ELEMENTS:
            return
        if not self._stack or self._stack[-1][0] != tag:
            raise _fail(f"malformed template while reading slots: {tag}")
        self._stack.pop()

    def handle_data(self, data: str) -> None:
        self._record(data, self._stack[-1][1] if self._stack else "")

    def finish(self) -> None:
        if self._stack:
            raise _fail(f"unclosed template tag: {self._stack[-1][0]}")


def _slots_macros_pairs(html: str) -> Tuple[List[str], List[str], List[Dict[str, str]]]:
    parser = _SlotMacroParser()
    parser.feed(html)
    parser.close()
    parser.finish()
    macros = [match.group(1) for match in MACRO_RE.finditer(html)]
    return parser.data_slots, macros, parser.pairs


@dataclass(frozen=True)
class _SequenceCanvas:
    canvas_id: str
    role: str
    detail_for: str
    contract: str
    width: str
    height: str
    participants: Tuple[str, ...]
    messages: Tuple[Tuple[str, str, str, str], ...]
    phases: Tuple[str, ...]


@dataclass
class _SequenceRecord:
    attrs: Dict[str, str]
    participants: List[str]
    messages: List[Tuple[str, str, str, str]]
    phases: List[str]
    participant_group_ids: List[str]
    message_steps: List[str]
    fragments: List[Tuple[str, str]]
    outcomes: List[str]
    risk_ids: List[str]
    evidence_links: List[str]


class _SequenceParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.records: List[_SequenceRecord] = []
        self.errors: List[str] = []
        self.document_evidence_ids: List[str] = []
        self._active: List[_SequenceRecord] = []
        self._stack: List[Tuple[str, bool]] = []

    def _start(
        self, tag: str, attrs: List[Tuple[str, Optional[str]]], push: bool
    ) -> None:
        tag = tag.lower()
        duplicates = _duplicates(attrs)
        attrs_map = {name.lower(): value or "" for name, value in attrs}
        if "data-sequence-evidence-id" in attrs_map:
            evidence_id = attrs_map["data-sequence-evidence-id"].strip()
            self.document_evidence_ids.append(evidence_id)
            if tag != "details":
                self.errors.append("sequence evidence ids must use native details elements")
        is_canvas = "data-sequence-canvas" in attrs_map
        endpoint_attrs = {
            "data-from",
            "data-to",
            "data-message-kind",
            "data-semantic",
            "data-participant-id",
            "data-participant-group-id",
        }
        if duplicates and any(
            name.startswith("data-sequence") or name in endpoint_attrs for name in duplicates
        ):
            self.errors.append(f"duplicate sequence attributes on {tag}")
        if is_canvas:
            if self._active:
                self.errors.append("sequence canvases must not be nested")
            record = _SequenceRecord(attrs_map, [], [], [], [], [], [], [], [], [])
            self.records.append(record)
            self._active.append(record)
        if self._active:
            record = self._active[-1]
            if "data-participant-id" in attrs_map:
                record.participants.append(attrs_map["data-participant-id"].strip())
            if "data-participant-group-id" in attrs_map:
                record.participant_group_ids.append(
                    attrs_map["data-participant-group-id"].strip()
                )
            if "data-sequence-message" in attrs_map:
                record.messages.append(
                    (
                        attrs_map.get("data-from", "").strip(),
                        attrs_map.get("data-to", "").strip(),
                        attrs_map.get("data-message-kind", "").strip(),
                        attrs_map.get("data-semantic", "").strip(),
                    )
                )
                record.message_steps.append(
                    attrs_map.get("data-sequence-step-index", "").strip()
                )
            if "data-sequence-phase-id" in attrs_map:
                record.phases.append(attrs_map["data-sequence-phase-id"].strip())
            if (
                "data-sequence-fragment-id" in attrs_map
                or "data-sequence-fragment-kind" in attrs_map
            ):
                record.fragments.append(
                    (
                        attrs_map.get("data-sequence-fragment-id", "").strip(),
                        attrs_map.get("data-sequence-fragment-kind", "").strip(),
                    )
                )
            if "data-sequence-outcome" in attrs_map:
                record.outcomes.append(attrs_map["data-sequence-outcome"].strip())
            if "data-sequence-risk-id" in attrs_map:
                record.risk_ids.append(attrs_map["data-sequence-risk-id"].strip())
            if "data-sequence-evidence-for" in attrs_map:
                record.evidence_links.append(
                    attrs_map["data-sequence-evidence-for"].strip()
                )
        if push and tag not in VOID_ELEMENTS:
            self._stack.append((tag, is_canvas))
        elif is_canvas:
            self.errors.append("sequence canvas must not be self-closing")
            self._active.pop()

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        self._start(tag, attrs, True)

    def handle_startendtag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        self._start(tag, attrs, False)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if not self._stack:
            return
        open_tag, closes_canvas = self._stack.pop()
        if open_tag != tag:
            self.errors.append(f"malformed sequence markup: {open_tag}/{tag}")
        if closes_canvas and self._active:
            self._active.pop()

    def finish(self) -> None:
        if self._active:
            self.errors.append("sequence canvas is not closed")


def _sequence_canvases(html: str) -> Tuple[Tuple[_SequenceCanvas, ...], _SequenceParser]:
    parser = _SequenceParser()
    parser.feed(html)
    parser.close()
    parser.finish()
    canvases = tuple(
        _SequenceCanvas(
            canvas_id=record.attrs.get("data-sequence-id", "").strip(),
            role=record.attrs.get("data-sequence-role", "").strip(),
            detail_for=record.attrs.get("data-sequence-detail-for", "").strip(),
            contract=record.attrs.get("data-sequence-contract", "").strip(),
            width=record.attrs.get("data-sequence-width", "").strip(),
            height=record.attrs.get("data-sequence-height", "").strip(),
            participants=tuple(record.participants),
            messages=tuple(record.messages),
            phases=tuple(record.phases),
        )
        for record in parser.records
    )
    return canvases, parser


def _sequence_errors(html: str) -> List[str]:
    canvases, parser = _sequence_canvases(html)
    errors = list(parser.errors)
    if not canvases:
        errors.append("sequence template must contain at least one canvas")
    evidence_ids = parser.document_evidence_ids
    if any(not evidence_id for evidence_id in evidence_ids):
        errors.append("sequence evidence ids must be non-empty")
    if len(evidence_ids) != len(set(evidence_ids)):
        errors.append("sequence evidence ids must be unique within a document")
    evidence_targets = set(evidence_ids)
    ids = [canvas.canvas_id for canvas in canvases]
    for index, (record, canvas) in enumerate(zip(parser.records, canvases), start=1):
        label = canvas.canvas_id or f"canvas-{index}"
        if not canvas.canvas_id or ids.count(canvas.canvas_id) != 1:
            errors.append(f"invalid sequence canvas id: {label}")
        if canvas.contract != SEQUENCE_CONTRACT_VERSION:
            errors.append(f"invalid sequence contract: {label}")
        if canvas.role not in SEQUENCE_ROLES:
            errors.append(f"invalid sequence role: {label}")
        if canvas.width not in SEQUENCE_WIDTH_MODES or canvas.height not in SEQUENCE_HEIGHT_MODES:
            errors.append(f"invalid sequence sizing mode: {label}")
        if canvas.role == "detail" and not canvas.detail_for:
            errors.append(f"detail sequence lacks overview link: {label}")
        if canvas.role != "detail" and canvas.detail_for:
            errors.append(f"non-detail sequence has detail link: {label}")
        if any(not value for value in canvas.participants) or len(set(canvas.participants)) != len(
            canvas.participants
        ):
            errors.append(f"invalid sequence participants: {label}")
        if len(canvas.participants) < 2:
            errors.append(f"sequence requires at least two participants: {label}")
        if not canvas.messages:
            errors.append(f"sequence requires at least one message: {label}")
        if any(not value for value in canvas.phases) or len(set(canvas.phases)) != len(canvas.phases):
            errors.append(f"invalid sequence phases: {label}")
        participant_group_ids = record.participant_group_ids
        if any(not group_id for group_id in participant_group_ids):
            errors.append(f"invalid sequence participant group ids: {label}")
        if len(participant_group_ids) != len(set(participant_group_ids)):
            errors.append(f"duplicate sequence participant group ids: {label}")
        if any(record.message_steps):
            if any(not step for step in record.message_steps):
                errors.append(f"partial sequence message step indices: {label}")
            non_empty_steps = [step for step in record.message_steps if step]
            if len(non_empty_steps) != len(set(non_empty_steps)):
                errors.append(f"duplicate sequence message step indices: {label}")
            if any(re.fullmatch(r"\d{1,3}", step) is None for step in non_empty_steps):
                errors.append(f"invalid sequence message step indices: {label}")
        fragment_ids = [fragment_id for fragment_id, _kind in record.fragments]
        for fragment_id, kind in record.fragments:
            if not fragment_id or not kind:
                errors.append(f"incomplete sequence fragment: {label}")
            elif kind not in SEQUENCE_FRAGMENT_KINDS:
                errors.append(f"invalid sequence fragment kind: {label}")
        if len(fragment_ids) != len(set(fragment_ids)):
            errors.append(f"duplicate sequence fragment ids: {label}")
        if any(outcome not in SEQUENCE_OUTCOMES for outcome in record.outcomes):
            errors.append(f"invalid sequence outcome: {label}")
        if any(not risk_id for risk_id in record.risk_ids):
            errors.append(f"invalid sequence risk ids: {label}")
        if len(record.risk_ids) != len(set(record.risk_ids)):
            errors.append(f"duplicate sequence risk ids: {label}")
        if any(
            not evidence_for or evidence_for not in evidence_targets
            for evidence_for in record.evidence_links
        ):
            errors.append(f"invalid sequence evidence link: {label}")
        participants = set(canvas.participants)
        for source, target, kind, semantic in canvas.messages:
            if not source or not target or source not in participants or target not in participants:
                errors.append(f"invalid sequence endpoint: {label}")
            if kind not in SEQUENCE_MESSAGE_KINDS or not semantic:
                errors.append(f"invalid sequence message contract: {label}")
            if (kind == "self") != (source == target):
                errors.append(f"invalid sequence self-call semantics: {label}")
        participant_over = len(canvas.participants) > SEQUENCE_PARTICIPANT_LIMIT
        message_over = len(canvas.messages) > SEQUENCE_MESSAGE_LIMIT
        phase_over = len(canvas.phases) > SEQUENCE_PHASE_LIMIT
        if canvas.role in {"standalone", "detail"} and (
            participant_over or message_over or phase_over
        ):
            errors.append(f"sequence exceeds complexity budget: {label}")
        if canvas.role == "overview" and (participant_over or message_over):
            errors.append(f"overview exceeds complexity budget: {label}")
    standalones = [canvas for canvas in canvases if canvas.role == "standalone"]
    overviews = [canvas for canvas in canvases if canvas.role == "overview"]
    details = [canvas for canvas in canvases if canvas.role == "detail"]
    if standalones and (overviews or details):
        errors.append("standalone and split sequences cannot be mixed")
    if details and len(overviews) != 1:
        errors.append("details require exactly one overview")
    if len(overviews) > 1:
        errors.append("only one overview is allowed")
    if overviews:
        overview = overviews[0]
        linked = [detail.detail_for for detail in details]
        if not details:
            errors.append("overview requires linked details")
        for detail in details:
            if detail.detail_for not in set(overview.phases):
                errors.append("detail references an unknown overview phase")
        for phase in overview.phases:
            if phase not in linked:
                errors.append("overview phase lacks a linked detail")
        detail_participants = {
            participant for detail in details for participant in detail.participants
        }
        detail_messages = sum(len(detail.messages) for detail in details)
        split_needed = (
            len(detail_participants) > SEQUENCE_PARTICIPANT_LIMIT
            or detail_messages > SEQUENCE_MESSAGE_LIMIT
            or len(overview.phases) > SEQUENCE_PHASE_LIMIT
        )
        if details and not split_needed:
            errors.append("overview/detail split is unnecessary")
    return errors


def _sequence_kernel_body(html: str, tag: str) -> str:
    pattern = re.compile(
        rf"<{tag}\b(?P<attrs>[^>]*)>(?P<body>.*?)</{tag}\s*>",
        re.IGNORECASE | re.DOTALL,
    )
    blocks = []
    for match in pattern.finditer(html):
        attrs = match.group("attrs")
        if re.search(r"\bdata-sequence-kernel\b", attrs, re.IGNORECASE):
            version = re.search(
                r"\bdata-sequence-kernel\s*=\s*([\"'])(?P<version>.*?)\1",
                attrs,
                re.IGNORECASE | re.DOTALL,
            )
            blocks.append((version.group("version") if version else "", match.group("body")))
    if len(blocks) != 1 or blocks[0][0] != SEQUENCE_CONTRACT_VERSION:
        raise _fail(f"expected one version-1 sequence kernel {tag} block")
    return blocks[0][1]


def _sequence_kernel_digest(html: str) -> str:
    style = _sequence_kernel_body(html, "style").encode("utf-8")
    script = _sequence_kernel_body(html, "script").encode("utf-8")
    return hashlib.sha256(b"sequence-kernel-v1\0" + style + b"\0" + script).hexdigest()


def _canonical_snapshot(path: Path, html: str) -> Dict[str, Any]:
    slots, macros, pairs = _slots_macros_pairs(html)
    return {
        "file_sha256": sha256_file(path),
        "structure_sha256": template_structure_signature(html),
        "data_slots": slots,
        "macros": macros,
        "slot_macro_pairs": pairs,
    }


def _validate_template_html(relative: str, html: str) -> Dict[str, str]:
    parser = _CanonicalHtmlParser()
    try:
        parser.feed(html)
        parser.close()
        parser.finish()
    except Exception as exc:
        raise _fail(f"invalid HTML template {relative}: {exc}") from exc
    if parser.errors:
        raise _fail(f"template {relative} is not self-contained: {'; '.join(parser.errors)}")
    if not all(
        (parser.has_doctype, parser.has_html_en, parser.has_viewport, parser.has_main, parser.has_h1)
    ):
        raise _fail(f"template {relative} is missing required document structure")
    if _contains_han(html):
        raise _fail(f"canonical template contains Han text: {relative}")
    if "http://" in html.lower() or "https://" in html.lower() or "//cdn" in html.lower():
        raise _fail(f"canonical template contains a remote reference: {relative}")
    if len(parser.main_attrs) != 1:
        raise _fail(f"template must contain exactly one main element: {relative}")
    identity = parser.main_attrs[0]
    expected_family, filename = relative.split("/", 1)
    expected_id = Path(filename).stem
    if (
        identity.get("data-template-family") != expected_family
        or identity.get("data-template-id") != expected_id
        or not identity.get("data-template-layout")
        or not identity.get("data-diagram-type")
    ):
        raise _fail(f"template identity does not match path: {relative}")
    return identity


def validate_canonical(root: Path) -> None:
    validate_repository_root(root)
    files = canonical_file_map(root)
    expected = {
        PurePosixPath("SKILL.md"),
        PurePosixPath("VERSION"),
        PurePosixPath("update.json"),
        PurePosixPath("scripts/update_skill.py"),
        PurePosixPath("scripts/vibe_diagram_lint.py"),
        PurePosixPath("references") / RUNTIME_WORKFLOW_PATH,
        PurePosixPath("references") / ADAPTIVE_REFERENCE_PATH,
        *(PurePosixPath("references") / name for name in REFERENCE_PATHS),
        *(PurePosixPath(name) for name in CONTRACT_ASSET_PATHS),
        *(PurePosixPath("assets/templates") / name for name in TEMPLATE_PATHS),
    }
    if set(files) != expected or len(files) != CANONICAL_FILE_COUNT:
        raise _fail(
            f"canonical skill tree must contain the exact {CANONICAL_FILE_COUNT}-file inventory"
        )
    canonical_text = "\n".join(
        path.read_text(encoding="utf-8")
        for relative, path in files.items()
        if relative.suffix in {".md", ".html", ".py"}
    )
    if _contains_han(canonical_text):
        raise _fail("canonical skill tree must remain English")
    canonical_casefold = canonical_text.casefold()
    for term in FORBIDDEN_HOST_TERMS:
        if term.casefold() in canonical_casefold:
            raise _fail(f"canonical skill tree contains a host-specific term: {term}")

    skill_path = files[PurePosixPath("SKILL.md")]
    skill_text = skill_path.read_text(encoding="utf-8")
    frontmatter = parse_skill_frontmatter(skill_text)
    if frontmatter["name"] != "vibe-diagram" or not frontmatter["description"].startswith(
        "Use when"
    ):
        raise _fail("canonical skill frontmatter identity is invalid")
    if len(frontmatter["name"]) > 64 or len(frontmatter["description"]) > 1024:
        raise _fail("canonical skill frontmatter exceeds its size limit")
    if len(skill_text.splitlines()) > 500:
        raise _fail("canonical SKILL.md exceeds 500 lines")
    if (
        "On every invocation" not in skill_text
        or "scripts/update_skill.py --check-and-update --json" not in skill_text
        or f"references/{RUNTIME_WORKFLOW_PATH}" not in skill_text
    ):
        raise _fail("canonical SKILL.md is missing the update bootstrap contract")

    version = read_version(root)
    if files[PurePosixPath("VERSION")].read_bytes() != f"{version}\n".encode("ascii"):
        raise _fail("canonical skill VERSION does not match repository VERSION")
    update_manifest = read_json_unique(files[PurePosixPath("update.json")])
    if set(update_manifest) != UPDATE_MANIFEST_KEYS:
        raise _fail("canonical update manifest has an invalid key set")
    if (
        type(update_manifest["schema_version"]) is not int
        or update_manifest["schema_version"] != 1
        or update_manifest["channel"] != "stable"
        or update_manifest["version"] != version
        or update_manifest["ref"] != f"v{version}"
    ):
        raise _fail("canonical update manifest identity is invalid")
    _validate_sha256(update_manifest["tree_sha256"], "update manifest tree_sha256")
    if update_manifest["tree_sha256"] != update_tree_sha256(root):
        raise _fail("canonical update manifest tree digest drifted")

    policy = load_family_policies(files[PurePosixPath("contracts/family-policies.json")])
    interaction_contract = load_interaction_contract(root)
    completed_templates = set(interaction_contract["scope"]["completed_templates"])
    migration_batches = policy["migration_batches"]
    policy_completed = {
        relative for paths in migration_batches.values() for relative in paths
    }
    if completed_templates != policy_completed or interaction_contract["scope"][
        "completed_batches"
    ] != ["B00", *migration_batches]:
        raise _fail("interaction baseline differs from the trusted migration batches")

    asset_requirements = {
        "assets/contracts/adaptive-viewport/v1.css": ("data-diagram-canvas", "--diagram-scale"),
        "assets/contracts/adaptive-viewport/v1.js": ("VibeDiagramViewport", "0.75", "reset"),
        "assets/contracts/progressive-disclosure/v1.css": ("data-diagram-detail", "@media print"),
        "assets/contracts/progressive-disclosure/v1.js": ("VibeDiagramDisclosure", "reset"),
        "assets/contracts/semantic-relations/v1.css": (
            "data-diagram-visible-relation-id",
            "vector-effect",
        ),
    }
    for relative, required_tokens in asset_requirements.items():
        text = files[PurePosixPath(relative)].read_text(encoding="utf-8")
        if any(token not in text for token in required_tokens):
            raise _fail(f"canonical interaction asset is incomplete: {relative}")

    reference_contract = load_reference_contract(root)
    reference_texts = []
    for name in REFERENCE_PATHS:
        relative = PurePosixPath("references") / name
        path = files[relative]
        if sha256_file(path) != reference_contract["references"][name]:
            raise _fail(f"canonical reference hash drifted: {name}")
        reference_texts.append(path.read_text(encoding="utf-8"))
    adaptive_reference = files[
        PurePosixPath("references") / ADAPTIVE_REFERENCE_PATH
    ].read_text(encoding="utf-8")
    runtime_workflow = files[
        PurePosixPath("references") / RUNTIME_WORKFLOW_PATH
    ].read_text(encoding="utf-8")
    canonical_prose = "\n".join(
        [skill_text, runtime_workflow, adaptive_reference] + reference_texts
    )
    referenced_templates = set(
        re.findall(r"\.\./assets/templates/([a-z0-9-]+/[a-z0-9-]+\.html)", canonical_prose)
    )
    if referenced_templates != set(TEMPLATE_PATHS):
        raise _fail("reference template links must cover the exact template inventory")

    template_contract = load_template_contract(root)
    family_signatures: Dict[str, Dict[str, str]] = {}
    sequence_digests = set()
    for relative in TEMPLATE_PATHS:
        path = files[PurePosixPath("assets/templates") / relative]
        html = path.read_text(encoding="utf-8")
        _validate_template_html(relative, html)
        snapshot = _canonical_snapshot(path, html)
        if snapshot != template_contract["templates"][relative]["canonical"]:
            raise _fail(f"canonical template snapshot drifted: {relative}")
        family = relative.split("/", 1)[0]
        signature = snapshot["structure_sha256"]
        seen = family_signatures.setdefault(family, {})
        if signature in seen:
            raise _fail(
                f"template structures are duplicated within {family}: {seen[signature]}, {relative}"
            )
        seen[signature] = relative
        if relative in SEQUENCE_REDESIGN_PATHS:
            sequence_errors = _sequence_errors(html)
            if sequence_errors:
                raise _fail(f"invalid sequence template {relative}: {'; '.join(sequence_errors)}")
            sequence_digests.add(_sequence_kernel_digest(html))
            if re.search(r"2040px|repeat\(\s*12\b", html, re.IGNORECASE):
                raise _fail(f"sequence template contains a fixed oversized layout: {relative}")
            if re.search(
                r"match\(.+→|seq-route.+match|route.+match", html, re.IGNORECASE | re.DOTALL
            ):
                raise _fail(f"sequence template parses visible route text: {relative}")
        elif relative in completed_templates:
            generic_errors = generic_contract_errors(
                html, family, Path(relative).stem, policy
            )
            generic_errors.extend(
                adaptive_kernel_errors(
                    html,
                    files[
                        PurePosixPath("assets/contracts/adaptive-viewport/v1.css")
                    ].read_text(encoding="utf-8"),
                    files[
                        PurePosixPath("assets/contracts/adaptive-viewport/v1.js")
                    ].read_text(encoding="utf-8"),
                )
            )
            if generic_errors:
                raise _fail(
                    f"invalid generic template {relative}: {'; '.join(generic_errors)}"
                )
    if len(sequence_digests) != 1:
        raise _fail("the six sequence templates must embed one identical interaction kernel")


def validate_manifest(client: str, manifest: Mapping[str, Any], version: str) -> None:
    if client not in CLIENTS:
        raise _fail(f"unknown manifest client: {client}")
    if SEMVER_RE.fullmatch(version) is None:
        raise _fail("manifest version contract requires strict SemVer 2.0")
    if not isinstance(manifest, Mapping):
        raise _fail("manifest must be an object")
    expected_keys = {
        "codex": {"name", "version", "description", "author", "license", "skills", "interface"},
        "claude": {"name", "version", "description", "author", "license"},
        "gemini": {"name", "version", "description"},
        "copilot": {"name", "version", "description", "author", "license"},
    }[client]
    if set(manifest) != expected_keys:
        raise _fail(f"{client} manifest has an invalid field set")
    if manifest.get("name") != "vibe-diagram":
        raise _fail(f"{client} manifest name must be vibe-diagram")
    if manifest.get("version") != version:
        raise _fail(f"{client} manifest version does not match VERSION")
    description = manifest.get("description")
    if not isinstance(description, str) or not description.strip():
        raise _fail(f"{client} manifest description must be a non-empty string")
    if client == "copilot" and len(description) > 1024:
        raise _fail("Copilot manifest description exceeds 1024 characters")
    if client in {"codex", "claude", "copilot"}:
        if manifest.get("author") != {"name": "imchenway"}:
            raise _fail(f"{client} manifest author is invalid")
        if manifest.get("license") != "Apache-2.0":
            raise _fail(f"{client} manifest license is invalid")
    if client == "codex":
        if manifest.get("skills") != "./skills/":
            raise _fail("Codex manifest skills must be exactly ./skills/")
        expected_interface = {
            "displayName": "Vibe Diagram",
            "shortDescription": "Self-contained HTML diagrams for complex ideas",
            "longDescription": (
                "Turn architecture, workflows, sequences, state, debugging, design, decisions, "
                "and delivery acceptance into self-contained HTML diagrams."
            ),
            "developerName": "imchenway",
            "category": "Developer Tools",
            "capabilities": ["Read", "Write"],
            "defaultPrompt": [
                "Use Vibe Diagram to create a self-contained HTML diagram for this request."
            ],
            "brandColor": "#1F6FB2",
        }
        if manifest.get("interface") != expected_interface:
            raise _fail("Codex manifest interface does not match the frozen contract")


def _expected_package_paths(spec: AdapterSpec) -> set:
    paths = {PurePosixPath("LICENSE"), spec.manifest_output}
    paths.update(spec.skills_output / relative for relative in _canonical_relative_paths())
    paths.update(extra.output for extra in spec.extra_files)
    return paths


def _canonical_relative_paths() -> Tuple[PurePosixPath, ...]:
    return (
        PurePosixPath("SKILL.md"),
        PurePosixPath("VERSION"),
        PurePosixPath("update.json"),
        PurePosixPath("scripts/update_skill.py"),
        PurePosixPath("scripts/vibe_diagram_lint.py"),
        PurePosixPath("references") / RUNTIME_WORKFLOW_PATH,
        PurePosixPath("references") / ADAPTIVE_REFERENCE_PATH,
        *(PurePosixPath("references") / name for name in REFERENCE_PATHS),
        *(PurePosixPath(name) for name in CONTRACT_ASSET_PATHS),
        *(PurePosixPath("assets/templates") / name for name in TEMPLATE_PATHS),
    )


def validate_package(
    root: Path,
    package_root: Path,
    spec: AdapterSpec,
    version: str,
) -> TreeRecord:
    validate_canonical(root)
    if version != read_version(root):
        raise _fail("package version does not match repository VERSION")
    canonical_spec = load_adapter(root, spec.client)
    if spec != canonical_spec:
        raise _fail(f"package spec does not match frozen adapter: {spec.client}")
    records = file_records(package_root)
    actual = {PurePosixPath(record.path) for record in records}
    expected = _expected_package_paths(spec)
    if actual != expected:
        raise _fail(f"package {spec.client} file inventory does not match its whitelist")
    if (package_root / "LICENSE").read_bytes() != (root / "LICENSE").read_bytes():
        raise _fail(f"package {spec.client} LICENSE differs from repository LICENSE")
    manifest = read_json_unique(package_root / spec.manifest_output)
    validate_manifest(spec.client, manifest, version)
    expected_manifest = render_template(
        read_json_unique(root / "adapters" / spec.client / spec.manifest_template), version
    )
    expected_manifest_bytes = (
        json.dumps(
            expected_manifest,
            ensure_ascii=True,
            allow_nan=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")
    if (package_root / spec.manifest_output).read_bytes() != expected_manifest_bytes:
        raise _fail(f"package {spec.client} manifest bytes are not canonical")
    canonical = canonical_file_map(root)
    for relative, source in canonical.items():
        target = package_root / spec.skills_output / relative
        if target.read_bytes() != source.read_bytes():
            raise _fail(f"package {spec.client} canonical file drifted: {relative}")
    adapter_root = root / "adapters" / spec.client
    for extra in spec.extra_files:
        source = adapter_root / extra.source
        target = package_root / extra.output
        if target.read_bytes() != source.read_bytes():
            raise _fail(f"package {spec.client} extra file drifted: {extra.output}")
    return tree_record(package_root)


def _deterministic_json_bytes(value: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(value, ensure_ascii=True, allow_nan=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _git_file_mode(path: Path) -> int:
    try:
        mode = path.stat().st_mode
    except OSError as exc:
        raise _fail(f"could not stat publication file {path}: {exc}") from exc
    return 0o100755 if mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH) else 0o100644


def _publication_file_inspection(
    publication_root: Path,
) -> Tuple[Dict[str, PublicationFileState], Dict[str, str]]:
    _ensure_root_directory(publication_root)
    states: Dict[str, PublicationFileState] = {}
    errors: Dict[str, str] = {}

    catalog_relative = MARKETPLACE_CATALOG.as_posix()
    try:
        catalog_path = _ensure_path(publication_root, MARKETPLACE_CATALOG, "file")
    except ValidationError as exc:
        errors[catalog_relative] = f"{catalog_relative}: {exc}"
    else:
        try:
            states[catalog_relative] = PublicationFileState(
                sha256=sha256_file(catalog_path),
                git_mode=_git_file_mode(catalog_path),
            )
        except ValidationError as exc:
            errors[catalog_relative] = f"{catalog_relative}: {exc}"

    plugin_relative = PUBLICATION_PLUGIN.as_posix()
    try:
        plugin_root = _ensure_path(publication_root, PUBLICATION_PLUGIN, "directory")
    except ValidationError as exc:
        errors[plugin_relative] = f"{plugin_relative}: {exc}"
        return states, errors

    try:
        plugin_paths = sorted(
            plugin_root.rglob("*"),
            key=lambda path: path.relative_to(plugin_root).as_posix().encode("utf-8"),
        )
    except OSError as exc:
        errors[plugin_relative] = f"could not inspect publication plugin {plugin_relative}: {exc}"
        return states, errors

    regular_files: List[Tuple[str, Path]] = []
    plugin_has_invalid_objects = False
    for path in plugin_paths:
        relative = (
            PUBLICATION_PLUGIN / PurePosixPath(path.relative_to(plugin_root).as_posix())
        ).as_posix()
        if path.is_symlink():
            errors[relative] = f"symlink is forbidden in package tree: {path}"
            plugin_has_invalid_objects = True
        elif path.is_dir():
            continue
        elif not path.is_file():
            errors[relative] = f"non-regular object is forbidden in package tree: {path}"
            plugin_has_invalid_objects = True
        else:
            regular_files.append((relative, path))

    if plugin_has_invalid_objects:
        for relative, path in regular_files:
            try:
                states[relative] = PublicationFileState(
                    sha256=sha256_file(path),
                    git_mode=_git_file_mode(path),
                )
            except ValidationError as exc:
                errors[relative] = f"{relative}: {exc}"
        return states, errors

    try:
        records = file_records(plugin_root)
    except ValidationError as exc:
        errors[plugin_relative] = f"{plugin_relative}: {exc}"
        return states, errors
    for record in records:
        relative = (PUBLICATION_PLUGIN / PurePosixPath(record.path)).as_posix()
        try:
            states[relative] = PublicationFileState(
                sha256=record.sha256,
                git_mode=_git_file_mode(plugin_root / record.path),
            )
        except ValidationError as exc:
            errors[relative] = f"{relative}: {exc}"
    return states, errors


def _publication_file_state(publication_root: Path) -> Dict[str, PublicationFileState]:
    states, errors = _publication_file_inspection(publication_root)
    if errors:
        relative = min(errors, key=lambda value: value.encode("utf-8"))
        raise _fail(errors[relative])
    return states


def first_publication_drift(expected_root: Path, actual_root: Path) -> Optional[str]:
    expected = _publication_file_state(expected_root)
    try:
        actual, actual_errors = _publication_file_inspection(actual_root)
    except ValidationError as exc:
        return f"publication validation drift: {exc}"

    expected_paths = set(expected)
    actual_paths = set(actual)
    candidates: List[Tuple[str, int, str]] = [
        (relative, 0, f"publication validation drift: {message}")
        for relative, message in actual_errors.items()
    ]
    candidates.extend(
        (relative, 1, f"publication file missing: {relative}")
        for relative in expected_paths - actual_paths
    )
    candidates.extend(
        (relative, 2, f"publication file extra: {relative}")
        for relative in actual_paths - expected_paths
    )
    for relative in expected_paths & actual_paths:
        expected_file = expected[relative]
        actual_file = actual[relative]
        if expected_file.git_mode != actual_file.git_mode:
            candidates.append(
                (
                    relative,
                    3,
                    f"publication file mode drift: {relative}; "
                    f"expected {expected_file.git_mode:o}, found {actual_file.git_mode:o}",
                )
            )
        if expected_file.sha256 != actual_file.sha256:
            candidates.append(
                (relative, 4, f"publication file bytes drift: {relative}")
            )
    if not candidates:
        return None
    return min(candidates, key=lambda item: (item[0].encode("utf-8"), item[1]))[2]


def _expected_publication_paths(spec: AdapterSpec) -> set:
    paths = {PUBLICATION_PLUGIN / relative for relative in _expected_package_paths(spec)}
    paths.add(MARKETPLACE_CATALOG)
    return paths


def validate_publication_tree(root: Path, publication_root: Path) -> Dict[str, Any]:
    validate_repository_root(root)
    _ensure_root_directory(publication_root)
    version = read_version(root)
    spec = load_adapter(root, "codex")
    plugin_root = _ensure_path(publication_root, PUBLICATION_PLUGIN, "directory")
    catalog_path = _ensure_path(publication_root, MARKETPLACE_CATALOG, "file")

    plugin_records = file_records(plugin_root)
    actual_paths = {
        PUBLICATION_PLUGIN / PurePosixPath(record.path) for record in plugin_records
    }
    actual_paths.add(MARKETPLACE_CATALOG)
    if actual_paths != _expected_publication_paths(spec):
        raise _fail("publication file inventory does not match the Codex package whitelist")

    package_record = validate_package(root, plugin_root, spec, version)
    expected_catalog = marketplace_document()
    catalog = read_json_unique(catalog_path)
    if catalog != expected_catalog:
        raise _fail(f"marketplace catalog does not match the frozen contract: {catalog_path}")
    if catalog_path.read_bytes() != _deterministic_json_bytes(expected_catalog):
        raise _fail(f"marketplace catalog bytes are not canonical: {catalog_path}")
    return {
        "package_version": version,
        "plugin_manifest_sha256": sha256_file(plugin_root / spec.manifest_output),
        "plugin_tree_sha256": package_record.tree_sha256,
        "marketplace_sha256": sha256_file(catalog_path),
        "runtime_validation": "unverified",
    }


def assemble_publication_tree(root: Path, destination: Path) -> Dict[str, Any]:
    validate_repository_root(root)
    if destination.is_symlink() or not destination.is_dir():
        raise _fail(f"publication destination must be a real directory: {destination}")
    try:
        if any(destination.iterdir()):
            raise _fail(f"publication destination must be empty: {destination}")
    except OSError as exc:
        raise _fail(f"could not inspect publication destination {destination}: {exc}") from exc

    version = read_version(root)
    spec = load_adapter(root, "codex")
    plugin_root = destination / PUBLICATION_PLUGIN
    catalog_path = destination / MARKETPLACE_CATALOG
    action = f"create publication plugin parent {plugin_root.parent}"
    try:
        plugin_root.parent.mkdir(parents=True)
        action = f"assemble Codex publication plugin {plugin_root}"
        package_report = assemble_client_package(root, plugin_root, spec, version)
        action = f"create marketplace catalog parent {catalog_path.parent}"
        catalog_path.parent.mkdir(parents=True)
        action = f"write marketplace catalog {catalog_path}"
        catalog_path.write_bytes(_deterministic_json_bytes(marketplace_document()))

        action = f"validate publication tree {destination}"
        publication_record = validate_publication_tree(root, destination)
        if (
            publication_record["plugin_manifest_sha256"]
            != package_report["manifest_sha256"]
            or publication_record["plugin_tree_sha256"]
            != package_report["package"]["tree_sha256"]
        ):
            raise DeterminismError(
                "publication plugin hashes diverged from the assembled Codex package"
            )
    except Exception as original:
        cleanup_failures: List[str] = []
        for created_root in (destination / "plugins", destination / ".agents"):
            try:
                if created_root.is_symlink():
                    created_root.unlink()
                elif created_root.is_dir():
                    shutil.rmtree(created_root)
                elif created_root.exists():
                    created_root.unlink()
            except Exception as cleanup:
                cleanup_failures.append(f"{created_root}: {cleanup}")
        try:
            leftovers = tuple(destination.iterdir())
        except Exception as cleanup:
            cleanup_failures.append(f"could not inspect {destination}: {cleanup}")
        else:
            if leftovers:
                cleanup_failures.append(
                    "destination is not empty: "
                    + ", ".join(str(path) for path in leftovers)
                )

        if cleanup_failures:
            raise BuildError(
                f"publication assembly failed during {action}: "
                f"{type(original).__name__}: {original}; cleanup failed: "
                + "; ".join(cleanup_failures)
            ) from original
        if isinstance(original, BuildError):
            raise
        if isinstance(original, OSError):
            raise BuildError(f"could not {action}: {original}") from original
        raise
    return publication_record


def assemble_client_package(
    root: Path,
    package_root: Path,
    spec: AdapterSpec,
    version: str,
) -> Dict[str, Any]:
    validate_canonical(root)
    if version != read_version(root):
        raise _fail("build version does not match repository VERSION")
    canonical_spec = load_adapter(root, spec.client)
    if spec != canonical_spec:
        raise _fail(f"build spec does not match frozen adapter: {spec.client}")
    _ensure_root_directory(package_root.parent)
    if package_root.exists() or package_root.is_symlink():
        raise _fail(f"package staging output already exists: {package_root}")
    expected_outputs = _expected_package_paths(spec)
    expected_count = CANONICAL_FILE_COUNT + (3 if spec.client == "codex" else 2)
    if len(expected_outputs) != expected_count:
        raise _fail(f"client output whitelist has an invalid size: {spec.client}")
    for output in expected_outputs:
        safe_relative_path(output.as_posix())
    adapter_root = root / "adapters" / spec.client
    for extra in spec.extra_files:
        _ensure_path(root, PurePosixPath("adapters") / spec.client / extra.source, "file")
    template = read_json_unique(adapter_root / spec.manifest_template)
    manifest = render_template(template, version)
    validate_manifest(spec.client, manifest, version)

    package_root.mkdir()
    try:
        shutil.copyfile(root / "LICENSE", package_root / "LICENSE")
        for relative, source in canonical_file_map(root).items():
            target = package_root / spec.skills_output / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
        manifest_target = package_root / spec.manifest_output
        manifest_target.parent.mkdir(parents=True, exist_ok=True)
        manifest_target.write_bytes(_deterministic_json_bytes(manifest))
        for extra in spec.extra_files:
            target = package_root / extra.output
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(adapter_root / extra.source, target)
        package_record = validate_package(root, package_root, spec, version)
    except Exception:
        shutil.rmtree(package_root, ignore_errors=True)
        raise
    canonical_record = tree_record(root / "skills" / "vibe-diagram")
    return {
        "manifest_path": spec.manifest_output.as_posix(),
        "manifest_sha256": sha256_file(package_root / spec.manifest_output),
        "canonical_sha256": canonical_record.tree_sha256,
        "package": _tree_record_dict(package_record),
    }


def build_client(
    root: Path,
    staging_build: Path,
    spec: AdapterSpec,
    version: str,
) -> Dict[str, Any]:
    _ensure_root_directory(staging_build)
    client_root = staging_build / spec.client
    if client_root.exists() or client_root.is_symlink():
        raise _fail(f"client staging output already exists: {spec.client}")
    return assemble_client_package(root, client_root, spec, version)


def assemble_build_tree(root: Path, destination: Path) -> Dict[str, Any]:
    validate_repository_root(root)
    if destination.is_symlink() or not destination.is_dir():
        raise _fail(f"build destination must be a real directory: {destination}")
    try:
        if any(destination.iterdir()):
            raise _fail(f"build destination must be empty: {destination}")
    except OSError as exc:
        raise _fail(f"could not inspect build destination {destination}: {exc}") from exc

    version = read_version(root)
    validate_canonical(root)
    canonical_sources = canonical_file_map(root)
    frozen_canonical = {
        relative: source.read_bytes() for relative, source in canonical_sources.items()
    }
    canonical_record = tree_record(root / "skills" / "vibe-diagram")
    frozen_records = {record.path: record for record in canonical_record.files}
    for relative, payload in frozen_canonical.items():
        record = frozen_records.get(relative.as_posix())
        if (
            record is None
            or record.size != len(payload)
            or record.sha256 != hashlib.sha256(payload).hexdigest()
        ):
            raise DeterminismError("canonical input changed while the build snapshot was frozen")

    def assert_frozen_canonical(client: Optional[str] = None) -> None:
        current = canonical_file_map(root)
        if set(current) != set(frozen_canonical):
            raise DeterminismError("canonical file inventory changed during the four-client build")
        for relative, expected in frozen_canonical.items():
            if current[relative].read_bytes() != expected:
                raise DeterminismError(
                    f"canonical source changed during the four-client build: {relative}"
                )
            if client is not None:
                spec = load_adapter(root, client)
                packaged = destination / client / spec.skills_output / relative
                try:
                    actual = packaged.read_bytes()
                except OSError as exc:
                    raise DeterminismError(
                        f"could not verify frozen canonical in {client}: {relative}: {exc}"
                    ) from exc
                if actual != expected:
                    raise DeterminismError(
                        f"client package diverged from the frozen canonical: {client}: {relative}"
                    )

    clients: Dict[str, Any] = {}
    for client in CLIENTS:
        clients[client] = build_client(root, destination, load_adapter(root, client), version)
        if clients[client]["canonical_sha256"] != canonical_record.tree_sha256:
            raise DeterminismError(
                f"client report diverged from the frozen canonical: {client}"
            )
        assert_frozen_canonical(client)
    assert_frozen_canonical()
    report: Dict[str, Any] = {
        "schema_version": 1,
        "package_version": version,
        "static_validation": "passed",
        "runtime_validation": "unverified",
        "canonical": _tree_record_dict(canonical_record),
        "clients": clients,
    }
    try:
        (destination / "build-report.json").write_bytes(_deterministic_json_bytes(report))
    except OSError as exc:
        raise BuildError(f"could not write deterministic build report: {exc}") from exc
    return report


def replace_build_transactionally(
    staged_build: Path,
    output: Path,
    *,
    rename: Callable[[Path, Path], None] = os.replace,
) -> bool:
    if staged_build.parent != output.parent:
        raise PublishError("staged build and output must be siblings on one filesystem")
    if staged_build.is_symlink() or not staged_build.is_dir():
        raise PublishError(f"staged build must be a real directory: {staged_build}")
    if output.name != "build":
        raise PublishError(f"output must be the repository build directory: {output}")
    if output.is_symlink() or (output.exists() and not output.is_dir()):
        raise PublishError(f"existing output must be a real directory: {output}")

    backup = output.with_name(".build.backup")
    if backup.exists() or backup.is_symlink():
        raise PublishError(f"residual backup must be resolved before publishing: {backup}")

    had_output = output.exists()
    if had_output:
        try:
            rename(output, backup)
        except OSError as exc:
            raise PublishError(f"could not move old build to backup {backup}: {exc}") from exc
    try:
        rename(staged_build, output)
    except OSError as promotion_error:
        if had_output:
            try:
                rename(backup, output)
            except OSError as rollback_error:
                raise PublishError(
                    "build promotion and rollback both failed; preserve evidence at "
                    f"{staged_build} and {backup}; promotion={promotion_error}; "
                    f"rollback={rollback_error}"
                ) from rollback_error
        raise PublishError(f"build promotion failed: {promotion_error}") from promotion_error

    if had_output:
        try:
            shutil.rmtree(backup)
        except OSError:
            return True
    return False


def _remove_staging(path: Path) -> None:
    if not path.exists() and not path.is_symlink():
        return
    try:
        if path.is_symlink() or not path.is_dir():
            path.unlink()
        else:
            shutil.rmtree(path)
    except OSError as exc:
        raise BuildError(f"could not remove staging directory {path}: {exc}") from exc


def _new_staging(root: Path, label: str) -> Path:
    try:
        return Path(tempfile.mkdtemp(prefix=f".build.staging-{label}-", dir=str(root)))
    except OSError as exc:
        raise BuildError(f"could not create build staging directory under {root}: {exc}") from exc


def _new_publication_staging(root: Path, label: str) -> Path:
    try:
        return Path(
            tempfile.mkdtemp(
                prefix=f"{PUBLICATION_STAGING_PREFIX}{label}-",
                dir=str(root),
            )
        )
    except OSError as exc:
        raise BuildError(
            f"could not create publication staging directory under {root}: {exc}"
        ) from exc


def _publication_target_existence(root: Path) -> Tuple[bool, bool]:
    plugin = root / PUBLICATION_PLUGIN
    catalog = root / MARKETPLACE_CATALOG
    for relative in (
        PurePosixPath("plugins"),
        PurePosixPath(".agents"),
        PurePosixPath(".agents/plugins"),
    ):
        path = root / relative
        if path.is_symlink() or (path.exists() and not path.is_dir()):
            raise PublishError(f"publication path ancestor must be a real directory: {path}")
    if plugin.is_symlink() or (plugin.exists() and not plugin.is_dir()):
        raise PublishError(f"publication plugin must be a real directory: {plugin}")
    if catalog.is_symlink() or (catalog.exists() and not catalog.is_file()):
        raise PublishError(f"publication catalog must be a regular file: {catalog}")
    plugin_exists = plugin.exists()
    catalog_exists = catalog.exists()
    if plugin_exists != catalog_exists:
        raise PublishError(
            "publication plugin and catalog must either both exist or both be absent"
        )
    return plugin_exists, catalog_exists


def _write_publication_journal(
    backup: Path,
    journal: Mapping[str, Any],
    rename: Callable[[Path, Path], None],
) -> None:
    temporary = backup / ".transaction.json.tmp"
    target = backup / PUBLICATION_JOURNAL
    try:
        temporary.write_bytes(_deterministic_json_bytes(journal))
        rename(temporary, target)
    except OSError as exc:
        raise PublishError(f"could not update publication transaction journal: {exc}") from exc


def _remove_tree_and_require_absent(
    path: Path,
    remove_tree: Callable[[Path], None],
) -> None:
    remove_tree(path)
    if path.exists() or path.is_symlink():
        raise OSError(f"publication cleanup returned but path remains: {path}")


def _remove_publication_path(
    path: Path,
    remove_tree: Callable[[Path], None],
) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.is_dir():
        _remove_tree_and_require_absent(path, remove_tree)


def _remove_created_publication_parents(
    root: Path,
    created_parent_paths: Sequence[str],
) -> None:
    for relative in reversed(created_parent_paths):
        path = root / PurePosixPath(relative)
        if not path.exists() and not path.is_symlink():
            continue
        if path.is_symlink() or not path.is_dir():
            raise PublishError(
                f"transaction-owned publication parent changed during rollback: {path}"
            )
        try:
            path.rmdir()
        except OSError:
            try:
                if any(path.iterdir()):
                    continue
            except OSError:
                pass
            raise


def _ensure_publication_cleanup_marker(
    backup: Path,
    journal: Dict[str, Any],
    rename: Callable[[Path, Path], None],
) -> None:
    journal["phase"] = "cleanup-pending"
    target = backup / PUBLICATION_JOURNAL
    expected = _deterministic_json_bytes(journal)
    try:
        if backup.is_symlink() or (backup.exists() and not backup.is_dir()):
            raise PublishError(
                f"publication cleanup marker parent must be a real directory: {backup}"
            )
        if not backup.exists():
            backup.mkdir()
        _write_publication_journal(backup, journal, rename)
        if target.is_symlink() or not target.is_file():
            raise PublishError(
                f"publication cleanup marker journal is not a regular file: {target}"
            )
        if target.read_bytes() != expected:
            raise PublishError(
                f"publication cleanup marker journal verification failed: {target}"
            )
    except (OSError, PublishError) as exc:
        raise PublishError(
            "could not establish fail-closed publication cleanup marker journal at "
            f"{target}: {exc}"
        ) from exc


def _ensure_publication_recovery_staging(staged: Path) -> bool:
    if staged.is_symlink() or (staged.exists() and not staged.is_dir()):
        raise PublishError(
            f"publication recovery staging must be a real directory: {staged}"
        )
    if staged.exists():
        return False
    staged.mkdir()
    return True


def replace_publication_transactionally(
    root: Path,
    staged: Path,
    *,
    rename: Callable[[Path, Path], None] = os.replace,
    remove_tree: Callable[[Path], None] = shutil.rmtree,
) -> bool:
    validate_repository_root(root)
    if staged.parent != root:
        raise PublishError("staged publication must be a repository-root sibling")
    if staged.is_symlink() or not staged.is_dir():
        raise PublishError(f"staged publication must be a real directory: {staged}")
    staged_record = validate_publication_tree(root, staged)
    plugin_existed, catalog_existed = _publication_target_existence(root)

    backup = root / PUBLICATION_BACKUP_NAME
    if backup.exists() or backup.is_symlink():
        raise PublishError(
            f"residual publication backup must be resolved before publishing: {backup}"
        )
    try:
        backup.mkdir()
    except OSError as exc:
        raise PublishError(f"could not create publication backup {backup}: {exc}") from exc

    journal: Dict[str, Any] = {
        "schema_version": 1,
        "package_version": staged_record["package_version"],
        "plugin_existed": plugin_existed,
        "catalog_existed": catalog_existed,
        "created_parent_paths": [],
        "phase": "backup-created",
    }
    created_parent_paths: List[str] = []
    staged_plugin = staged / PUBLICATION_PLUGIN
    staged_catalog = staged / MARKETPLACE_CATALOG
    plugin = root / PUBLICATION_PLUGIN
    catalog = root / MARKETPLACE_CATALOG
    backup_plugin = backup / PUBLICATION_PLUGIN
    backup_catalog = backup / MARKETPLACE_CATALOG
    plugin_backed_up = False
    catalog_backed_up = False
    plugin_promoted = False
    catalog_promoted = False

    try:
        _write_publication_journal(backup, journal, rename)
        for relative in (
            PurePosixPath(".agents"),
            PurePosixPath(".agents/plugins"),
            PurePosixPath("plugins"),
        ):
            path = root / relative
            if not path.exists():
                path.mkdir()
                created_parent_paths.append(relative.as_posix())
                journal["created_parent_paths"] = list(created_parent_paths)
                _write_publication_journal(backup, journal, rename)
        if plugin_existed and catalog_existed:
            backup_plugin.parent.mkdir(parents=True)
            backup_catalog.parent.mkdir(parents=True)
            rename(plugin, backup_plugin)
            plugin_backed_up = True
            journal["phase"] = "plugin-backed-up"
            _write_publication_journal(backup, journal, rename)
            rename(catalog, backup_catalog)
            catalog_backed_up = True
            journal["phase"] = "catalog-backed-up"
            _write_publication_journal(backup, journal, rename)
        rename(staged_plugin, plugin)
        plugin_promoted = True
        journal["phase"] = "plugin-promoted"
        _write_publication_journal(backup, journal, rename)
        rename(staged_catalog, catalog)
        catalog_promoted = True
        journal["phase"] = "catalog-promoted"
        _write_publication_journal(backup, journal, rename)
        actual_record = validate_publication_tree(root, root)
        if actual_record != staged_record:
            raise DeterminismError(
                "validated publication record differs from the staged publication record"
            )
        journal["phase"] = "validated"
        _write_publication_journal(backup, journal, rename)
    except BaseException as original_error:
        try:
            if catalog_promoted:
                _remove_publication_path(catalog, remove_tree)
            if plugin_promoted:
                _remove_publication_path(plugin, remove_tree)
            if catalog_backed_up:
                rename(backup_catalog, catalog)
            if plugin_backed_up:
                rename(backup_plugin, plugin)
        except BaseException as rollback_error:
            raise PublishError(
                "publication transaction and rollback both failed; preserve recovery "
                f"evidence; original={type(original_error).__name__}: {original_error}; "
                f"rollback={type(rollback_error).__name__}: {rollback_error}; "
                f"staged={staged}; backup={backup}"
            ) from rollback_error
        try:
            _remove_created_publication_parents(root, created_parent_paths)
            _remove_tree_and_require_absent(staged, remove_tree)
            _remove_tree_and_require_absent(backup, remove_tree)
        except BaseException as cleanup_error:
            evidence_notes: List[str] = []
            marker_error: Optional[BaseException] = None
            try:
                if _ensure_publication_recovery_staging(staged):
                    evidence_notes.append(
                        "staging recovery path was removed and recreated empty"
                    )
            except BaseException as exc:
                evidence_notes.append(f"staging recovery failed: {exc}")
            try:
                _ensure_publication_cleanup_marker(backup, journal, rename)
            except BaseException as exc:
                marker_error = exc
                evidence_notes.append(f"cleanup marker failed: {exc}")
            evidence = "; ".join(evidence_notes) or "recovery paths remained present"
            if marker_error is not None:
                raise PublishError(
                    "publication targets were rolled back, but recovery cleanup failed "
                    "and the fail-closed marker could not be established; "
                    f"original={type(original_error).__name__}: {original_error}; "
                    f"cleanup={type(cleanup_error).__name__}: {cleanup_error}; "
                    f"evidence={evidence}; staged={staged}; backup={backup}"
                ) from marker_error
            raise PublishError(
                "publication targets were rolled back, but recovery cleanup failed; "
                f"original={type(original_error).__name__}: {original_error}; "
                f"cleanup={type(cleanup_error).__name__}: {cleanup_error}; "
                f"evidence={evidence}; staged={staged}; backup={backup}"
            ) from cleanup_error
        if isinstance(original_error, Exception):
            raise PublishError(
                "publication transaction failed and was rolled back: "
                f"{type(original_error).__name__}: {original_error}"
            ) from original_error
        raise

    expected_backup_payload: Optional[Dict[str, PublicationFileState]] = None
    backup_payload_baseline_error: Optional[BuildError] = None
    if plugin_existed and catalog_existed:
        try:
            expected_backup_payload = _publication_file_state(backup)
        except BuildError as exc:
            backup_payload_baseline_error = exc

    try:
        _remove_tree_and_require_absent(staged, remove_tree)
    except OSError as cleanup_error:
        try:
            _ensure_publication_cleanup_marker(backup, journal, rename)
        except PublishError as marker_error:
            raise PublishError(
                "publication committed, but staging cleanup failed and the fail-closed "
                "marker journal could not be established; "
                f"cleanup={cleanup_error}; marker={marker_error}; "
                f"staged={staged}; backup={backup}"
            ) from marker_error
        return True
    try:
        _remove_tree_and_require_absent(backup, remove_tree)
    except OSError as cleanup_error:
        evidence_losses: List[str] = []
        if backup_payload_baseline_error is not None:
            evidence_losses.append(
                "old backup payload integrity was unverifiable before cleanup: "
                f"{backup_payload_baseline_error}"
            )
        if backup.is_symlink() or not backup.is_dir():
            evidence_losses.append("backup directory was removed")
        else:
            journal_path = backup / PUBLICATION_JOURNAL
            if journal_path.is_symlink() or not journal_path.is_file():
                evidence_losses.append("transaction journal was removed")
            if expected_backup_payload is not None:
                try:
                    actual_backup_payload = _publication_file_state(backup)
                except BuildError as exc:
                    evidence_losses.append(f"old backup payload was removed or invalid: {exc}")
                else:
                    if actual_backup_payload != expected_backup_payload:
                        evidence_losses.append("old backup payload was partially removed")
        try:
            _ensure_publication_cleanup_marker(backup, journal, rename)
        except PublishError as marker_error:
            raise PublishError(
                "publication committed, but backup cleanup failed and the fail-closed "
                "marker journal could not be established; "
                f"cleanup={cleanup_error}; marker={marker_error}; "
                f"staged={staged}; backup={backup}"
            ) from marker_error
        if evidence_losses:
            raise PublishError(
                "publication committed, but backup cleanup removed recovery evidence "
                "before reporting failure; a fail-closed marker was recreated; "
                f"cleanup={cleanup_error}; evidence={'; '.join(evidence_losses)}; "
                f"staged={staged}; backup={backup}"
            ) from cleanup_error
        return True
    return False


def sync_publication(
    root: Path,
    *,
    rename: Callable[[Path, Path], None] = os.replace,
    remove_tree: Callable[[Path], None] = shutil.rmtree,
) -> Tuple[Dict[str, Any], bool, bool]:
    validate_repository_root(root)
    backup = root / PUBLICATION_BACKUP_NAME
    if backup.exists() or backup.is_symlink():
        raise PublishError(
            f"residual publication backup must be resolved before syncing: {backup}"
        )
    plugin_exists, catalog_exists = _publication_target_existence(root)

    staged = _new_publication_staging(root, "sync")
    try:
        record = assemble_publication_tree(root, staged)
        if plugin_exists and catalog_exists and first_publication_drift(staged, root) is None:
            _remove_staging(staged)
            return record, False, False
        cleanup_pending = replace_publication_transactionally(
            root,
            staged,
            rename=rename,
            remove_tree=remove_tree,
        )
        return record, True, cleanup_pending
    except BaseException as original_error:
        if staged.exists() and not (root / PUBLICATION_BACKUP_NAME).exists():
            try:
                _remove_staging(staged)
            except BaseException as cleanup_error:
                if isinstance(original_error, Exception):
                    raise BuildError(
                        "publication sync failed and staging cleanup also failed; "
                        f"original={type(original_error).__name__}: {original_error}; "
                        f"cleanup={type(cleanup_error).__name__}: {cleanup_error}; "
                        f"staged={staged}"
                    ) from cleanup_error
                raise original_error from cleanup_error
        raise


def check_publication(root: Path) -> Dict[str, Any]:
    validate_repository_root(root)
    backup = root / PUBLICATION_BACKUP_NAME
    if backup.exists() or backup.is_symlink():
        raise PublishError(
            f"residual publication backup must be resolved before checking: {backup}"
        )

    staged = _new_publication_staging(root, "check")
    try:
        staged_record = assemble_publication_tree(root, staged)
        drift = first_publication_drift(staged, root)
        if drift is not None:
            raise _fail(drift)
        actual_record = validate_publication_tree(root, root)
        if actual_record != staged_record:
            raise DeterminismError(
                "validated publication record differs from the staged publication record"
            )
    except Exception as original:
        try:
            _remove_staging(staged)
        except Exception as cleanup:
            raise BuildError(
                "publication check failed: "
                f"{type(original).__name__}: {original}; staging cleanup failed: "
                f"{type(cleanup).__name__}: {cleanup}"
            ) from cleanup
        raise
    else:
        _remove_staging(staged)
        return actual_record


def build_all(
    root: Path,
    output: Optional[Path] = None,
    check: bool = False,
) -> Tuple[Dict[str, Any], bool]:
    validate_repository_root(root)
    backup = root / ".build.backup"
    if backup.exists() or backup.is_symlink():
        raise PublishError(f"residual backup must be resolved before building: {backup}")
    if check:
        if output is not None:
            raise BuildError("check-only mode does not accept an output path")
        publication_backup = root / PUBLICATION_BACKUP_NAME
        if publication_backup.exists() or publication_backup.is_symlink():
            raise PublishError(
                "residual publication backup must be resolved before checking: "
                f"{publication_backup}"
            )
        first = _new_staging(root, "check-one")
        second: Optional[Path] = None
        try:
            first_report = assemble_build_tree(root, first)
            second = _new_staging(root, "check-two")
            second_report = assemble_build_tree(root, second)
            if first_report != second_report or tree_record(first) != tree_record(second):
                raise DeterminismError("two check builds were not byte-for-byte deterministic")
            check_publication(root)
            return first_report, False
        finally:
            _remove_staging(first)
            if second is not None:
                _remove_staging(second)

    expected_output = root / "build"
    if output is None or output != expected_output:
        raise BuildError(f"output must be exactly the repository build directory: {expected_output}")

    staged = _new_staging(root, "publish")
    preserve_evidence = False
    try:
        report = assemble_build_tree(root, staged)
        cleanup_pending = replace_build_transactionally(staged, output)
        return report, cleanup_pending
    except PublishError:
        preserve_evidence = staged.exists() and backup.exists() and not output.exists()
        raise
    finally:
        if not preserve_evidence:
            _remove_staging(staged)


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build deterministic vibe-diagram client packages.",
        allow_abbrev=False,
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="validate two clean builds without publishing")
    mode.add_argument("--output", choices=("build",), help="publish all clients to ./build")
    mode.add_argument(
        "--sync-publication",
        action="store_true",
        help="synchronize the tracked Codex publication projection",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    arguments = parse_args(argv)
    try:
        if arguments.sync_publication:
            report, changed, cleanup_pending = sync_publication(ROOT)
            summary = {
                "backup_cleanup_pending": cleanup_pending,
                "changed": changed,
                "mode": "sync-publication",
                "output": [
                    PUBLICATION_PLUGIN.as_posix(),
                    MARKETPLACE_CATALOG.as_posix(),
                ],
                "runtime_validation": report["runtime_validation"],
                "static_validation": "passed",
            }
        elif arguments.check:
            report, cleanup_pending = build_all(ROOT, check=True)
            mode = "check"
            output_value: Optional[str] = None
        else:
            report, cleanup_pending = build_all(ROOT, output=ROOT / "build")
            mode = "build"
            output_value = "build"
    except BuildError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if arguments.sync_publication:
        print(json.dumps(summary, ensure_ascii=True, allow_nan=False, sort_keys=True))
        if cleanup_pending:
            print(
                "warning: new publication is active; inspect and manually remove "
                "residual backup before continuing: "
                f"{ROOT / PUBLICATION_BACKUP_NAME}",
                file=sys.stderr,
            )
            return 1
        return 0

    summary = {
        "backup_cleanup_pending": cleanup_pending,
        "mode": mode,
        "output": output_value,
        "runtime_validation": report["runtime_validation"],
        "static_validation": report["static_validation"],
    }
    print(json.dumps(summary, ensure_ascii=True, allow_nan=False, sort_keys=True))
    if cleanup_pending:
        print(
            f"warning: new build is active; remove residual backup after inspection: {ROOT / '.build.backup'}",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
