#!/usr/bin/env python3
"""准备并验证失败关闭的 GitHub Skill 发行版。"""

from __future__ import annotations

import argparse
import concurrent.futures
import dataclasses
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Dict, List, Mapping, NamedTuple, Optional, Sequence, Tuple


SCRIPT_PATH = Path(__file__).absolute()
ROOT = SCRIPT_PATH.parents[1]
CONFIG_RELATIVE = Path("release/github-skill.json")
CONFIG_KEYS = {
    "schema_version",
    "repository",
    "main_branch",
    "stable_branch",
    "workflow_file",
    "version_file",
    "skill_root",
    "update_manifest",
    "publication_command",
    "build_command",
    "check_command",
}
MANIFEST_KEYS = {"schema_version", "channel", "version", "ref", "tree_sha256"}
STABLE_VERSION_RE = re.compile(
    r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
)
REPOSITORY_RE = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")
REF_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/-]*")
DIGEST_RE = re.compile(r"[0-9a-f]{64}")
SHA_RE = re.compile(r"[0-9a-f]{40,64}")
MAX_REMOTE_BYTES = 64 * 1024 * 1024
MAX_RELEASE_NOTES_BYTES = 1024 * 1024
MAX_RUNTIME_ARTIFACT_BYTES = 16 * 1024 * 1024
MAX_RUNTIME_MARKER_BYTES = 64 * 1024
WORKFLOW_ATTEMPTS = 60
WORKFLOW_POLL_SECONDS = 5.0
STABLE_CONSISTENCY_ATTEMPTS = 8
STABLE_CONSISTENCY_BASE_SECONDS = 1.0
STABLE_CONSISTENCY_MAX_SECONDS = 30.0
EXPECTED_PUBLICATION_COMMAND = (
    "python3",
    "scripts/build_packages.py",
    "--sync-publication",
)
EXPECTED_BUILD_COMMAND = (
    "python3",
    "scripts/build_packages.py",
    "--output",
    "build",
)
EXPECTED_CHECK_COMMAND = ("python3", "scripts/build_packages.py", "--check")
CREDENTIAL_RE = re.compile(
    r"(?:github_pat_[A-Za-z0-9_]{20,}|gh[pousr]_[A-Za-z0-9_]{20,}|"
    r"sk-[A-Za-z0-9_-]{20,}|AKIA[0-9A-Z]{16}|"
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----)",
    re.IGNORECASE,
)

RELEASE_STATES = (
    "NEW",
    "PREPARED",
    "LOCAL_VERIFIED",
    "MERGED",
    "TAGGED",
    "RELEASED",
    "TAG_VERIFIED",
    "STABLE_PROMOTED",
    "RUNTIME_VERIFIED",
    "PARTIAL_REMOTE",
    "PROMOTED_RUNTIME_FAILED",
)
ALLOWED_TRANSITIONS = {
    "NEW": {"PREPARED"},
    "PREPARED": {"LOCAL_VERIFIED"},
    "LOCAL_VERIFIED": {"MERGED"},
    "MERGED": {"TAGGED"},
    "TAGGED": {"RELEASED", "PARTIAL_REMOTE"},
    "RELEASED": {"TAG_VERIFIED", "PARTIAL_REMOTE"},
    "TAG_VERIFIED": {"STABLE_PROMOTED"},
    "STABLE_PROMOTED": {"RUNTIME_VERIFIED", "PROMOTED_RUNTIME_FAILED"},
    "PARTIAL_REMOTE": {"TAGGED", "RELEASED", "TAG_VERIFIED"},
    "RUNTIME_VERIFIED": set(),
    "PROMOTED_RUNTIME_FAILED": set(),
}


class ReleaseError(RuntimeError):
    """发布前置条件或验证失败。"""

    def __init__(self, message: str, *, exit_code: int = 3):
        super().__init__(message)
        self.exit_code = exit_code


class CommandResult(NamedTuple):
    returncode: int
    stdout: str
    stderr: str


class SubprocessRunner:
    """不经过 shell 执行精确参数向量。"""

    def run(
        self,
        arguments: Sequence[str],
        *,
        cwd: Path,
        check: bool = True,
        env: Optional[Dict[str, str]] = None,
    ) -> CommandResult:
        environment = os.environ.copy()
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        if env:
            environment.update(env)
        try:
            completed = subprocess.run(
                list(arguments),
                cwd=cwd,
                env=environment,
                text=True,
                capture_output=True,
                check=False,
            )
        except OSError as exc:
            raise ReleaseError(
                f"could not execute {arguments[0]!r}: {exc}", exit_code=3
            ) from exc
        result = CommandResult(completed.returncode, completed.stdout, completed.stderr)
        if check and result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip() or "command failed"
            raise ReleaseError(
                f"command failed ({result.returncode}): {arguments[0]}: {detail}",
                exit_code=4,
            )
        return result


@dataclass(frozen=True)
class ReleaseConfig:
    repository: str
    main_branch: str
    stable_branch: str
    workflow_file: str
    version_file: str
    skill_root: str
    update_manifest: str
    publication_command: Tuple[str, ...]
    build_command: Tuple[str, ...]
    check_command: Tuple[str, ...]


@dataclass(frozen=True)
class ReleaseState:
    schema_version: int
    target_version: str
    previous_version: str
    repository: str
    baseline_head: str
    release_commit: Optional[str]
    release_state: str
    completed_phases: Tuple[str, ...]
    remote_facts: Mapping[str, Any]
    last_result: Mapping[str, Any]

    @classmethod
    def new(
        cls,
        *,
        target_version: str,
        previous_version: str,
        repository: str,
        baseline_head: str,
    ) -> "ReleaseState":
        parse_stable_version(target_version)
        parse_stable_version(previous_version)
        _validate_repository(repository)
        if SHA_RE.fullmatch(baseline_head) is None:
            raise ReleaseError("baseline_head must be a lowercase Git SHA")
        return cls(
            schema_version=1,
            target_version=target_version,
            previous_version=previous_version,
            repository=repository,
            baseline_head=baseline_head,
            release_commit=None,
            release_state="NEW",
            completed_phases=(),
            remote_facts={},
            last_result={},
        )

    def advance(self, target: str, result: Mapping[str, Any]) -> "ReleaseState":
        require_transition(self.release_state, target)
        return dataclasses.replace(
            self,
            release_state=target,
            completed_phases=(*self.completed_phases, target),
            last_result=dict(result),
        )

    def as_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "target_version": self.target_version,
            "previous_version": self.previous_version,
            "repository": self.repository,
            "baseline_head": self.baseline_head,
            "release_commit": self.release_commit,
            "release_state": self.release_state,
            "completed_phases": list(self.completed_phases),
            "remote_facts": dict(self.remote_facts),
            "last_result": dict(self.last_result),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ReleaseState":
        expected = {
            "schema_version",
            "target_version",
            "previous_version",
            "repository",
            "baseline_head",
            "release_commit",
            "release_state",
            "completed_phases",
            "remote_facts",
            "last_result",
        }
        if set(value) != expected or value.get("schema_version") != 1:
            raise ReleaseError("release state has an invalid schema")
        state = value.get("release_state")
        if state not in RELEASE_STATES:
            raise ReleaseError("release state has an invalid phase")
        phases = value.get("completed_phases")
        if not isinstance(phases, list) or not all(item in RELEASE_STATES for item in phases):
            raise ReleaseError("release state completed_phases is invalid")
        cursor = "NEW"
        for phase in phases:
            if not transition_allowed(cursor, phase):
                raise ReleaseError(
                    f"release state contains an invalid transition: {cursor} -> {phase}"
                )
            cursor = phase
        if cursor != state:
            raise ReleaseError("release state phase differs from its transition history")
        remote_facts = value.get("remote_facts")
        last_result = value.get("last_result")
        if not isinstance(remote_facts, dict) or not isinstance(last_result, dict):
            raise ReleaseError("release state evidence must be JSON objects")
        release_commit = value.get("release_commit")
        if release_commit is not None and (
            not isinstance(release_commit, str) or SHA_RE.fullmatch(release_commit) is None
        ):
            raise ReleaseError("release state release_commit is invalid")
        target_version = _require_string(value.get("target_version"), "target_version")
        previous_version = _require_string(
            value.get("previous_version"), "previous_version"
        )
        repository = _require_string(value.get("repository"), "repository")
        baseline_head = _require_string(value.get("baseline_head"), "baseline_head")
        parse_stable_version(target_version)
        parse_stable_version(previous_version)
        _validate_repository(repository)
        if SHA_RE.fullmatch(baseline_head) is None:
            raise ReleaseError("release state baseline_head is invalid")
        return cls(
            schema_version=1,
            target_version=target_version,
            previous_version=previous_version,
            repository=repository,
            baseline_head=baseline_head,
            release_commit=release_commit,
            release_state=state,
            completed_phases=tuple(phases),
            remote_facts=remote_facts,
            last_result=last_result,
        )


class ReleaseStateStore:
    def __init__(self, directory: Path):
        self.directory = directory

    def path_for(self, version: str) -> Path:
        parse_stable_version(version)
        return self.directory / f"v{version}.json"

    def save(self, state: ReleaseState) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        if self.directory.is_symlink() or not self.directory.is_dir():
            raise ReleaseError("release state directory must be a real directory")
        path = self.path_for(state.target_version)
        _atomic_write(path, _json_bytes(state.as_dict()))

    def load(self, version: str) -> Optional[ReleaseState]:
        path = self.path_for(version)
        if not path.exists():
            return None
        if path.is_symlink() or not path.is_file():
            raise ReleaseError("release state path must be a regular file")
        value = _read_json(path)
        if not isinstance(value, dict):
            raise ReleaseError("release state must be a JSON object")
        return ReleaseState.from_dict(value)

    def ensure_compatible(self, version: str, repository: str) -> Optional[ReleaseState]:
        state = self.load(version)
        if state is not None and state.repository != repository:
            raise ReleaseError("release state belongs to a different repository")
        return state


def _require_string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ReleaseError(f"{label} must be a non-empty string")
    return value


def _validate_repository(value: str) -> str:
    if REPOSITORY_RE.fullmatch(value) is None or any(
        part in {".", ".."} for part in value.split("/")
    ):
        raise ReleaseError("repository must be owner/name")
    return value


def _validate_ref(value: object, label: str) -> str:
    text = _require_string(value, label)
    if (
        REF_RE.fullmatch(text) is None
        or ".." in text
        or "@{" in text
        or text.endswith(("/", ".", ".lock"))
    ):
        raise ReleaseError(f"{label} must be a safe Git ref")
    return text


def _json_pairs(pairs: List[Tuple[str, Any]]) -> Dict[str, Any]:
    value: Dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ReleaseError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def _json_loads(payload: bytes, label: str) -> Any:
    try:
        return json.loads(payload.decode("utf-8"), object_pairs_hook=_json_pairs)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ReleaseError(f"invalid {label}: {exc}") from exc


def _read_json(path: Path) -> Any:
    try:
        return _json_loads(path.read_bytes(), str(path))
    except OSError as exc:
        raise ReleaseError(f"could not read {path}: {exc}") from exc


def _json_bytes(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=True, allow_nan=False, indent=2, sort_keys=True)
        + "\n"
    ).encode("utf-8")


def _atomic_write(path: Path, payload: bytes) -> None:
    if path.exists() and (path.is_symlink() or not path.is_file()):
        raise ReleaseError(f"write target must be a regular file: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    if temporary.exists() or temporary.is_symlink():
        raise ReleaseError(f"temporary write path already exists: {temporary}")
    try:
        temporary.write_bytes(payload)
        os.replace(temporary, path)
    except OSError as exc:
        try:
            temporary.unlink()
        except OSError:
            pass
        raise ReleaseError(f"could not write {path}: {exc}") from exc


def _safe_relative(value: object, label: str) -> str:
    text = _require_string(value, label)
    if "\\" in text or "//" in text or "\x00" in text or text.startswith("/"):
        raise ReleaseError(f"{label} must be a canonical relative POSIX path")
    path = PurePosixPath(text)
    if any(part in {"", ".", ".."} for part in path.parts) or path.as_posix() != text:
        raise ReleaseError(f"{label} must be a canonical relative POSIX path")
    return text


def _command(value: object, label: str) -> Tuple[str, ...]:
    if (
        not isinstance(value, list)
        or not value
        or not all(isinstance(item, str) and item for item in value)
    ):
        raise ReleaseError(f"{label} must be a non-empty string array")
    return tuple(value)


def load_config(root: Path, path: Path) -> ReleaseConfig:
    if root.is_symlink() or not root.is_dir():
        raise ReleaseError("repository root must be a real directory")
    if path.is_symlink() or not path.is_file():
        raise ReleaseError("release config must be a regular file")
    value = _read_json(path)
    if not isinstance(value, dict) or set(value) != CONFIG_KEYS:
        raise ReleaseError("release config has an invalid key set")
    if value["schema_version"] != 1:
        raise ReleaseError("release config schema_version must be integer 1")
    repository = _validate_repository(_require_string(value["repository"], "repository"))
    main_branch = _validate_ref(value["main_branch"], "main_branch")
    stable_branch = _validate_ref(value["stable_branch"], "stable_branch")
    workflow_file = _safe_relative(value["workflow_file"], "workflow_file")
    version_file = _safe_relative(value["version_file"], "version_file")
    skill_root = _safe_relative(value["skill_root"], "skill_root")
    update_manifest = _safe_relative(value["update_manifest"], "update_manifest")
    if update_manifest != f"{skill_root}/update.json":
        raise ReleaseError("update_manifest must be the canonical Skill manifest")
    publication_command = _command(
        value["publication_command"], "publication_command"
    )
    build_command = _command(value["build_command"], "build_command")
    check_command = _command(value["check_command"], "check_command")
    if publication_command != EXPECTED_PUBLICATION_COMMAND:
        raise ReleaseError("publication_command must use the repository builder entrypoint")
    if build_command != EXPECTED_BUILD_COMMAND:
        raise ReleaseError("build_command must use the repository builder output entrypoint")
    if check_command != EXPECTED_CHECK_COMMAND:
        raise ReleaseError("check_command must use the repository builder check entrypoint")
    return ReleaseConfig(
        repository=repository,
        main_branch=main_branch,
        stable_branch=stable_branch,
        workflow_file=workflow_file,
        version_file=version_file,
        skill_root=skill_root,
        update_manifest=update_manifest,
        publication_command=publication_command,
        build_command=build_command,
        check_command=check_command,
    )


def parse_stable_version(value: str) -> Tuple[int, int, int]:
    if not isinstance(value, str) or STABLE_VERSION_RE.fullmatch(value) is None:
        raise ReleaseError(f"version must be strict stable X.Y.Z: {value!r}")
    return tuple(int(part) for part in value.split("."))  # type: ignore[return-value]


def require_newer_version(current: str, target: str) -> None:
    if parse_stable_version(target) <= parse_stable_version(current):
        raise ReleaseError(f"target version {target} must be newer than {current}")


def transition_allowed(source: str, target: str) -> bool:
    return source in ALLOWED_TRANSITIONS and target in ALLOWED_TRANSITIONS[source]


def require_transition(source: str, target: str) -> None:
    if not transition_allowed(source, target):
        raise ReleaseError(f"release transition is not allowed: {source} -> {target}")


def _read_version(path: Path) -> str:
    if path.is_symlink() or not path.is_file():
        raise ReleaseError(f"VERSION must be a regular file: {path}")
    try:
        text = path.read_bytes().decode("ascii")
    except (OSError, UnicodeError) as exc:
        raise ReleaseError(f"could not read VERSION: {exc}") from exc
    if not text.endswith("\n") or text.count("\n") != 1:
        raise ReleaseError("VERSION must contain one newline-terminated line")
    version = text[:-1]
    parse_stable_version(version)
    return version


def load_updater(skill_root: Path) -> Any:
    script = skill_root / "scripts" / "update_skill.py"
    if script.is_symlink() or not script.is_file():
        raise ReleaseError("canonical updater is missing")
    name = "vibe_diagram_release_updater_" + str(abs(hash(str(script))))
    spec = importlib.util.spec_from_file_location(name, script)
    if spec is None or spec.loader is None:
        raise ReleaseError("could not load canonical updater")
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        raise ReleaseError(f"could not import canonical updater: {exc}") from exc
    return module


def _manifest(path: Path) -> Dict[str, object]:
    value = _read_json(path)
    if not isinstance(value, dict) or set(value) != MANIFEST_KEYS:
        raise ReleaseError("update manifest has an invalid key set")
    if value["schema_version"] != 1 or value["channel"] != "stable":
        raise ReleaseError("update manifest identity is invalid")
    if not isinstance(value["version"], str):
        raise ReleaseError("update manifest version is invalid")
    parse_stable_version(value["version"])
    if value["ref"] != f"v{value['version']}":
        raise ReleaseError("update manifest ref does not match its version")
    if not isinstance(value["tree_sha256"], str) or DIGEST_RE.fullmatch(
        value["tree_sha256"]
    ) is None:
        raise ReleaseError("update manifest tree_sha256 is invalid")
    return value


def _validate_metadata(root: Path, config: ReleaseConfig, version: str) -> Dict[str, object]:
    skill_root = root / config.skill_root
    root_version = _read_version(root / config.version_file)
    skill_version = _read_version(skill_root / "VERSION")
    if root_version != version or skill_version != version:
        raise ReleaseError("repository and canonical Skill versions differ from the target")
    manifest = _manifest(root / config.update_manifest)
    updater = load_updater(skill_root)
    if manifest["version"] != version or manifest["ref"] != f"v{version}":
        raise ReleaseError("update manifest differs from the target version")
    if manifest["tree_sha256"] != updater.tree_sha256(skill_root):
        raise ReleaseError("update manifest tree digest drifted")
    return manifest


def _candidate_digest(skill_root: Path, target: str) -> str:
    load_updater(skill_root).tree_sha256(skill_root)
    with tempfile.TemporaryDirectory() as temporary:
        candidate = Path(temporary) / "vibe-diagram"
        shutil.copytree(skill_root, candidate, symlinks=True)
        _atomic_write(candidate / "VERSION", (target + "\n").encode("ascii"))
        return load_updater(candidate).tree_sha256(candidate)


def prepare_release(
    root: Path,
    config: ReleaseConfig,
    target: str,
    runner: Any,
    *,
    dry_run: bool = False,
) -> Dict[str, object]:
    parse_stable_version(target)
    skill_root = root / config.skill_root
    current = _read_version(root / config.version_file)
    skill_version = _read_version(skill_root / "VERSION")
    if current != skill_version:
        raise ReleaseError("repository and canonical Skill versions do not match")
    current_manifest = _manifest(root / config.update_manifest)
    updater = load_updater(skill_root)
    if (
        current_manifest["version"] != current
        or current_manifest["ref"] != f"v{current}"
        or current_manifest["tree_sha256"] != updater.tree_sha256(skill_root)
    ):
        raise ReleaseError("current release metadata is not internally consistent")
    if target != current:
        require_newer_version(current, target)
    digest = _candidate_digest(skill_root, target)
    result: Dict[str, object] = {
        "status": "planned" if dry_run else "prepared",
        "previous_version": current,
        "version": target,
        "tree_sha256": digest,
        "local_validation": "unverified",
        "runtime_validation": "unverified",
        "mutations": [
            config.version_file,
            f"{config.skill_root}/VERSION",
            config.update_manifest,
            "plugins/vibe-diagram",
            ".agents/plugins/marketplace.json",
        ],
    }
    if dry_run:
        return result
    _atomic_write(root / config.version_file, (target + "\n").encode("ascii"))
    _atomic_write(skill_root / "VERSION", (target + "\n").encode("ascii"))
    manifest = {
        "schema_version": 1,
        "channel": "stable",
        "version": target,
        "ref": f"v{target}",
        "tree_sha256": digest,
    }
    _atomic_write(root / config.update_manifest, _json_bytes(manifest))
    runner.run(config.publication_command, cwd=root, check=True)
    _validate_metadata(root, config, target)
    return result


def _write_canonical_archive(skill_root: Path, version: str, target: Path) -> None:
    prefix = f"vibe-diagram-{version}/skills/vibe-diagram"
    try:
        with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for source in sorted(skill_root.rglob("*")):
                if source.is_symlink():
                    raise ReleaseError(f"canonical archive source contains a symlink: {source}")
                if source.is_file():
                    relative = source.relative_to(skill_root).as_posix()
                    archive.write(source, f"{prefix}/{relative}")
    except OSError as exc:
        raise ReleaseError(f"could not create canonical archive: {exc}", exit_code=4) from exc


def _validate_archive_path(
    root: Path,
    config: ReleaseConfig,
    version: str,
    archive_path: Path,
) -> Dict[str, object]:
    updater = load_updater(root / config.skill_root)
    with tempfile.TemporaryDirectory() as temporary:
        staging = Path(temporary)
        try:
            candidate = updater.stage_archive(archive_path, staging)
            manifest_value = _json_loads(
                (candidate / "update.json").read_bytes(), "archive update manifest"
            )
            manifest = updater.validate_manifest(manifest_value)
            updater._verify_candidate(candidate, manifest)
            candidate_version = updater.read_version(candidate)
        except Exception as exc:
            if isinstance(exc, ReleaseError):
                raise
            raise ReleaseError(f"release archive validation failed: {exc}", exit_code=5) from exc
        if candidate_version != version:
            raise ReleaseError("release archive version differs from the target", exit_code=5)
        if manifest.get("version") != version or manifest.get("ref") != f"v{version}":
            raise ReleaseError(
                "release archive manifest differs from the immutable tag",
                exit_code=5,
            )
        return dict(manifest)


def _validate_archive_bytes(
    root: Path,
    config: ReleaseConfig,
    version: str,
    payload: bytes,
) -> Dict[str, object]:
    if len(payload) > MAX_REMOTE_BYTES:
        raise ReleaseError("release archive exceeds the size limit", exit_code=5)
    with tempfile.TemporaryDirectory() as temporary:
        path = Path(temporary) / "release.zip"
        path.write_bytes(payload)
        return _validate_archive_path(root, config, version, path)


def _verification_commands(config: ReleaseConfig, current_python: str) -> List[Tuple[str, ...]]:
    suite39 = ("python3.9", "-m", "unittest", "discover", "-s", "tests", "-v")
    current = (
        current_python,
        "-m",
        "unittest",
        "discover",
        "-s",
        "tests",
        "-v",
    )
    return [
        suite39,
        current,
        config.check_command,
        config.build_command,
        ("diff", "-qr", "build/codex", "plugins/vibe-diagram"),
        ("git", "diff", "--check"),
        suite39,
        current,
    ]


def _run_verification_round(
    root: Path,
    runner: Any,
    commands: Sequence[Tuple[str, ...]],
) -> List[CommandResult]:
    """并行执行同一轮受支持 Python，按声明顺序返回确定性结果。"""

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=len(commands),
        thread_name_prefix="release-verify",
    ) as executor:
        futures = [
            executor.submit(runner.run, command, cwd=root, check=True)
            for command in commands
        ]
        return [future.result() for future in futures]


def verify_release(
    root: Path,
    config: ReleaseConfig,
    version: str,
    runner: Any,
    *,
    current_python: str = sys.executable,
) -> Dict[str, object]:
    metadata = _validate_metadata(root, config, version)
    checks: List[Dict[str, object]] = []
    commands = _verification_commands(config, current_python)
    for command, result in zip(
        commands[:2],
        _run_verification_round(root, runner, commands[:2]),
    ):
        checks.append({"command": list(command), "returncode": result.returncode})
    for command in commands[2:-2]:
        result = runner.run(command, cwd=root, check=True)
        checks.append({"command": list(command), "returncode": result.returncode})
    for command, result in zip(
        commands[-2:],
        _run_verification_round(root, runner, commands[-2:]),
    ):
        checks.append({"command": list(command), "returncode": result.returncode})
    with tempfile.TemporaryDirectory() as temporary:
        archive = Path(temporary) / f"vibe-diagram-{version}.zip"
        _write_canonical_archive(root / config.skill_root, version, archive)
        _validate_archive_path(root, config, version, archive)
    return {
        "status": "passed",
        "version": version,
        "local_validation": "static-valid",
        "runtime_validation": "unverified",
        "archive_validation": "passed",
        "tree_sha256": metadata["tree_sha256"],
        "checks": checks,
    }


def remote_urls(config: ReleaseConfig, version: str) -> Dict[str, str]:
    parse_stable_version(version)
    return {
        "stable_manifest": (
            f"https://raw.githubusercontent.com/{config.repository}/"
            f"{config.stable_branch}/{config.update_manifest}"
        ),
        "tag_archive": (
            f"https://github.com/{config.repository}/archive/refs/tags/v{version}.zip"
        ),
    }


def _default_fetch_bytes(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "vibe-diagram-release/1"})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = response.read(MAX_REMOTE_BYTES + 1)
    except OSError as exc:
        raise ReleaseError(f"could not fetch remote release data: {exc}", exit_code=5) from exc
    if len(payload) > MAX_REMOTE_BYTES:
        raise ReleaseError("remote release data exceeds the size limit", exit_code=5)
    return payload


class GitHubReader:
    def __init__(self, repository: str, root: Path, runner: Any):
        self.repository = repository
        self.root = root
        self.runner = runner

    def optional_json(self, endpoint: str) -> Optional[Dict[str, Any]]:
        result = self.runner.run(("gh", "api", endpoint), cwd=self.root, check=False)
        if result.returncode != 0:
            if "404" in result.stderr:
                return None
            detail = result.stderr.strip() or result.stdout.strip() or "GitHub API failed"
            raise ReleaseError(f"GitHub API read failed: {detail}", exit_code=5)
        value = _json_loads(result.stdout.encode("utf-8"), "GitHub API response")
        if not isinstance(value, dict):
            raise ReleaseError("GitHub API response must be a JSON object", exit_code=5)
        return value

    def commit_sha(self, ref: str) -> Optional[str]:
        value = self.optional_json(f"repos/{self.repository}/commits/{ref}")
        if value is None:
            return None
        sha = value.get("sha")
        if not isinstance(sha, str) or SHA_RE.fullmatch(sha) is None:
            raise ReleaseError("GitHub commit response has an invalid SHA", exit_code=5)
        return sha


def _workflow_conclusion(value: Optional[Dict[str, Any]], commit: str) -> str:
    if value is None:
        return "missing"
    runs = value.get("workflow_runs")
    if not isinstance(runs, list):
        raise ReleaseError("GitHub workflow response is invalid", exit_code=5)
    matching = [run for run in runs if isinstance(run, dict) and run.get("head_sha") == commit]
    if not matching:
        return "missing"
    run = matching[0]
    if run.get("status") != "completed":
        return "pending"
    conclusion = run.get("conclusion")
    return conclusion if isinstance(conclusion, str) else "unknown"


def validate_stable_manifest(
    value: Mapping[str, object],
    target_version: str,
    archive_manifest: Optional[Mapping[str, object]],
) -> Tuple[str, str]:
    if set(value) != MANIFEST_KEYS:
        raise ReleaseError("stable update manifest has an invalid key set", exit_code=5)
    if value.get("schema_version") != 1 or value.get("channel") != "stable":
        raise ReleaseError("stable update manifest identity is invalid", exit_code=5)
    stable_version = value.get("version")
    digest = value.get("tree_sha256")
    if not isinstance(stable_version, str):
        raise ReleaseError("stable update manifest version is invalid", exit_code=5)
    if not isinstance(digest, str) or DIGEST_RE.fullmatch(digest) is None:
        raise ReleaseError("stable update manifest tree digest is invalid", exit_code=5)
    stable_tuple = parse_stable_version(stable_version)
    if value.get("ref") != f"v{stable_version}":
        raise ReleaseError("stable update manifest ref is invalid", exit_code=5)
    if stable_tuple > parse_stable_version(target_version):
        raise ReleaseError("stable channel is newer than the candidate", exit_code=5)
    if stable_version == target_version:
        if archive_manifest is None or dict(value) != dict(archive_manifest):
            raise ReleaseError("stable manifest differs from the tag archive", exit_code=5)
        return "passed", stable_version
    return "previous", stable_version


def collect_remote_facts(
    root: Path,
    config: ReleaseConfig,
    version: str,
    runner: Any,
    *,
    fetch_bytes: Callable[[str], bytes] = _default_fetch_bytes,
) -> Dict[str, object]:
    parse_stable_version(version)
    reader = GitHubReader(config.repository, root, runner)
    base = f"repos/{config.repository}"
    main_sha = reader.commit_sha(config.main_branch)
    stable_sha = reader.commit_sha(config.stable_branch)
    tag_sha = reader.commit_sha(f"v{version}")
    release_value = reader.optional_json(f"{base}/releases/tags/v{version}")
    facts: Dict[str, object] = {
        "repository": config.repository,
        "version": version,
        "main_sha": main_sha,
        "stable_sha": stable_sha,
        "tag_sha": tag_sha,
        "tag_status": "available" if tag_sha else "missing",
        "release_status": "available" if release_value else "missing",
        "release_validation": "not-checked",
        "workflow_conclusion": "missing",
        "archive_validation": "not-checked",
        "stable_manifest_validation": "not-checked",
        "stable_fast_forward": False,
        "ready_for_promotion": False,
    }
    if tag_sha is None:
        return facts
    workflow = reader.optional_json(
        f"{base}/actions/workflows/{config.workflow_file}/runs?"
        f"head_sha={tag_sha}&per_page=20"
    )
    conclusion = _workflow_conclusion(workflow, tag_sha)
    facts["workflow_conclusion"] = conclusion
    if stable_sha is not None:
        comparison = reader.optional_json(f"{base}/compare/{stable_sha}...{tag_sha}")
        if comparison is not None:
            merge_base = comparison.get("merge_base_commit")
            status = comparison.get("status")
            facts["stable_fast_forward"] = bool(
                status in {"ahead", "identical"}
                and isinstance(merge_base, dict)
                and merge_base.get("sha") == stable_sha
            )
    urls = remote_urls(config, version)
    archive_manifest: Optional[Dict[str, object]] = None
    try:
        archive_manifest = _validate_archive_bytes(
            root, config, version, fetch_bytes(urls["tag_archive"])
        )
        facts["archive_validation"] = "passed"
        facts["archive_tree_sha256"] = archive_manifest["tree_sha256"]
    except ReleaseError as exc:
        facts["archive_validation"] = "failed"
        facts["archive_error"] = str(exc)
    try:
        stable_value = _json_loads(
            fetch_bytes(urls["stable_manifest"]), "stable update manifest"
        )
        if not isinstance(stable_value, dict):
            raise ReleaseError("stable update manifest must be an object", exit_code=5)
        manifest_status, stable_version = validate_stable_manifest(
            stable_value, version, archive_manifest
        )
        facts["stable_manifest_validation"] = manifest_status
        facts["stable_manifest_version"] = stable_version
    except ReleaseError as exc:
        facts["stable_manifest_validation"] = "failed"
        facts["stable_manifest_error"] = str(exc)
    release_valid = bool(
        release_value
        and release_value.get("tag_name") == f"v{version}"
        and release_value.get("draft") is False
        and release_value.get("prerelease") is False
    )
    facts["release_validation"] = "passed" if release_valid else "failed"
    facts["ready_for_promotion"] = bool(
        main_sha == tag_sha
        and release_valid
        and conclusion == "success"
        and facts["archive_validation"] == "passed"
        and facts["stable_manifest_validation"] in {"passed", "previous"}
        and facts["stable_fast_forward"] is True
    )
    return facts


def read_release_notes(path: Path) -> str:
    """读取发布说明，但不把正文写入状态或命令输出。"""

    if not path.is_absolute():
        raise ReleaseError("--notes-file must be an absolute path")
    if path.is_symlink() or not path.is_file():
        raise ReleaseError("release notes must be a regular non-symlink file")
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise ReleaseError(f"could not inspect release notes: {exc}") from exc
    if size <= 0 or size > MAX_RELEASE_NOTES_BYTES:
        raise ReleaseError("release notes must be non-empty and at most 1 MiB")
    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise ReleaseError(f"could not read UTF-8 release notes: {exc}") from exc
    if not content.strip():
        raise ReleaseError("release notes must contain non-whitespace text")
    if CREDENTIAL_RE.search(content):
        raise ReleaseError("release notes contain a credential-like value")
    return content


def _repository_from_remote_url(value: str) -> Optional[str]:
    text = value.strip()
    patterns = (
        r"https://github\.com/([^/]+/[^/]+?)(?:\.git)?/?",
        r"git@github\.com:([^/]+/[^/]+?)(?:\.git)?",
        r"ssh://git@github\.com/([^/]+/[^/]+?)(?:\.git)?/?",
    )
    for pattern in patterns:
        matched = re.fullmatch(pattern, text)
        if matched:
            return matched.group(1)
    return None


def _require_publish_state(
    state: ReleaseState,
    config: ReleaseConfig,
    version: str,
    metadata: Mapping[str, object],
) -> str:
    if state.target_version != version or state.repository != config.repository:
        raise ReleaseError("release state does not match the publish target")
    allowed = {
        "LOCAL_VERIFIED",
        "MERGED",
        "TAGGED",
        "RELEASED",
        "PARTIAL_REMOTE",
        "TAG_VERIFIED",
    }
    if state.release_state not in allowed:
        raise ReleaseError("publish requires LOCAL_VERIFIED or resumable remote state")
    verified_digest = state.remote_facts.get("verified_tree_sha256")
    if not isinstance(verified_digest, str):
        verified_digest = state.last_result.get("tree_sha256")
    if not isinstance(verified_digest, str) or DIGEST_RE.fullmatch(verified_digest) is None:
        raise ReleaseError("release state lacks static-valid candidate evidence")
    if metadata.get("tree_sha256") != verified_digest:
        raise ReleaseError("merged candidate digest differs from LOCAL_VERIFIED evidence")
    return verified_digest


def _require_local_publish_preconditions(
    root: Path,
    config: ReleaseConfig,
    commit: str,
    runner: Any,
    *,
    operation: str = "publish",
) -> None:
    status = runner.run(
        ("git", "status", "--porcelain=v1", "--untracked-files=all"),
        cwd=root,
        check=True,
    )
    if status.stdout.strip():
        raise ReleaseError(f"{operation} requires a clean worktree and index")
    head = _baseline_head(root, runner)
    if head != commit:
        raise ReleaseError("local HEAD must equal --commit")
    remote = runner.run(
        ("git", "remote", "get-url", "origin"), cwd=root, check=True
    ).stdout.strip()
    remote_repository = _repository_from_remote_url(remote)
    if remote_repository is None or remote_repository.casefold() != config.repository.casefold():
        raise ReleaseError("origin does not match the configured GitHub repository")
    runner.run(
        ("gh", "auth", "status", "--hostname", "github.com"),
        cwd=root,
        check=True,
    )
    repository = GitHubReader(config.repository, root, runner).optional_json(
        f"repos/{config.repository}"
    )
    permissions = repository.get("permissions") if repository else None
    if not isinstance(permissions, dict) or permissions.get("push") is not True:
        raise ReleaseError("GitHub identity lacks push permission for the repository")


def _require_main_publish_preconditions(
    root: Path,
    config: ReleaseConfig,
    commit: str,
    runner: Any,
) -> GitHubReader:
    reader = GitHubReader(config.repository, root, runner)
    main_sha = reader.commit_sha(config.main_branch)
    if main_sha != commit:
        raise ReleaseError("remote main does not equal --commit")
    workflow = reader.optional_json(
        f"repos/{config.repository}/actions/workflows/{config.workflow_file}/runs?"
        f"head_sha={commit}&per_page=20"
    )
    if _workflow_conclusion(workflow, commit) != "success":
        raise ReleaseError("main workflow for --commit has not succeeded")
    return reader


def _validate_release_value(
    value: Optional[Mapping[str, Any]], version: str
) -> bool:
    return bool(
        value
        and value.get("tag_name") == f"v{version}"
        and value.get("draft") is False
        and value.get("prerelease") is False
    )


def _local_tag_commit(
    root: Path, tag: str, runner: Any
) -> Optional[str]:
    result = runner.run(
        ("git", "rev-parse", "--verify", "--quiet", f"refs/tags/{tag}^{{commit}}"),
        cwd=root,
        check=False,
    )
    if result.returncode == 1:
        return None
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "git rev-parse failed"
        raise ReleaseError(f"could not inspect local tag: {detail}")
    value = result.stdout.strip()
    if SHA_RE.fullmatch(value) is None:
        raise ReleaseError("local tag does not resolve to a lowercase Git SHA")
    return value


def _wait_for_workflow(
    root: Path,
    config: ReleaseConfig,
    commit: str,
    runner: Any,
    *,
    attempts: int = WORKFLOW_ATTEMPTS,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> str:
    if attempts < 1:
        raise ReleaseError("workflow attempts must be positive")
    reader = GitHubReader(config.repository, root, runner)
    endpoint = (
        f"repos/{config.repository}/actions/workflows/{config.workflow_file}/runs?"
        f"head_sha={commit}&per_page=20"
    )
    conclusion = "missing"
    for index in range(attempts):
        conclusion = _workflow_conclusion(reader.optional_json(endpoint), commit)
        if conclusion == "success":
            return conclusion
        if conclusion not in {"missing", "pending"}:
            raise ReleaseError(f"tag workflow failed with conclusion: {conclusion}")
        if index + 1 < attempts:
            sleep_fn(WORKFLOW_POLL_SECONDS)
    raise ReleaseError("tag workflow did not succeed before the bounded timeout")


def collect_tag_release_facts(
    root: Path,
    config: ReleaseConfig,
    version: str,
    commit: str,
    runner: Any,
    *,
    fetch_bytes: Callable[[str], bytes] = _default_fetch_bytes,
    workflow_attempts: int = WORKFLOW_ATTEMPTS,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> Dict[str, object]:
    reader = GitHubReader(config.repository, root, runner)
    main_sha = reader.commit_sha(config.main_branch)
    tag_sha = reader.commit_sha(f"v{version}")
    release_value = reader.optional_json(
        f"repos/{config.repository}/releases/tags/v{version}"
    )
    workflow_conclusion = _wait_for_workflow(
        root,
        config,
        commit,
        runner,
        attempts=workflow_attempts,
        sleep_fn=sleep_fn,
    )
    archive_manifest = _validate_archive_bytes(
        root,
        config,
        version,
        fetch_bytes(remote_urls(config, version)["tag_archive"]),
    )
    release_valid = _validate_release_value(release_value, version)
    verified = bool(
        main_sha == commit
        and tag_sha == commit
        and release_valid
        and workflow_conclusion == "success"
    )
    return {
        "main_sha": main_sha,
        "tag_sha": tag_sha,
        "release_status": "available" if release_value else "missing",
        "release_validation": "passed" if release_valid else "failed",
        "release_url": release_value.get("html_url") if release_value else None,
        "workflow_conclusion": workflow_conclusion,
        "archive_validation": "passed",
        "archive_tree_sha256": archive_manifest["tree_sha256"],
        "tag_release_verified": verified,
    }


def _partial_remote_state(
    state: ReleaseState,
    store: ReleaseStateStore,
    phase: str,
    verified_digest: str,
) -> ReleaseState:
    result = {
        "status": "partial-remote",
        "error_phase": phase,
        "tree_sha256": verified_digest,
        "runtime_validation": "unverified",
    }
    if state.release_state in {"TAGGED", "RELEASED"}:
        state = state.advance("PARTIAL_REMOTE", result)
    else:
        state = dataclasses.replace(state, last_result=result)
    store.save(state)
    return state


def publish_release(
    root: Path,
    config: ReleaseConfig,
    version: str,
    commit: str,
    notes_file: Path,
    state: ReleaseState,
    store: ReleaseStateStore,
    runner: Any,
    *,
    fetch_bytes: Callable[[str], bytes] = _default_fetch_bytes,
    workflow_attempts: int = WORKFLOW_ATTEMPTS,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> Dict[str, object]:
    """从已合并的 main 提交发布不可变 tag 与 GitHub Release。"""

    parse_stable_version(version)
    if SHA_RE.fullmatch(commit) is None:
        raise ReleaseError("--commit must be a lowercase Git SHA")
    read_release_notes(notes_file)
    metadata = _validate_metadata(root, config, version)
    verified_digest = _require_publish_state(state, config, version, metadata)
    _require_local_publish_preconditions(root, config, commit, runner)
    reader = _require_main_publish_preconditions(root, config, commit, runner)
    tag = f"v{version}"
    remote_tag = reader.commit_sha(tag)
    release_value = reader.optional_json(
        f"repos/{config.repository}/releases/tags/{tag}"
    )
    if remote_tag is not None and remote_tag != commit:
        raise ReleaseError("remote tag points to a different commit")
    if release_value is not None and not _validate_release_value(release_value, version):
        raise ReleaseError("existing GitHub Release does not match the immutable tag")
    if state.release_commit not in {None, commit}:
        raise ReleaseError("release state commit conflicts with --commit")
    state = dataclasses.replace(
        state,
        release_commit=commit,
        remote_facts={
            **dict(state.remote_facts),
            "verified_tree_sha256": verified_digest,
        },
    )
    merged_result = {
        "status": "merged-main-verified",
        "commit": commit,
        "tree_sha256": verified_digest,
        "runtime_validation": "unverified",
    }
    if state.release_state == "LOCAL_VERIFIED":
        state = state.advance("MERGED", merged_result)
    else:
        state = dataclasses.replace(state, last_result=merged_result)
    store.save(state)

    if remote_tag is None:
        local_tag = _local_tag_commit(root, tag, runner)
        if local_tag is not None and local_tag != commit:
            raise ReleaseError("local tag points to a different commit")
        if local_tag is None:
            runner.run(
                (
                    "git",
                    "tag",
                    "--annotate",
                    tag,
                    commit,
                    "--message",
                    tag,
                ),
                cwd=root,
                check=True,
            )
        runner.run(
            (
                "git",
                "push",
                "--porcelain",
                "origin",
                f"refs/tags/{tag}:refs/tags/{tag}",
            ),
            cwd=root,
            check=True,
        )
    if state.release_state == "MERGED":
        state = state.advance(
            "TAGGED",
            {
                "status": "tag-pushed" if remote_tag is None else "tag-existing",
                "commit": commit,
                "tree_sha256": verified_digest,
                "runtime_validation": "unverified",
            },
        )
        store.save(state)
    try:
        observed_tag = reader.commit_sha(tag)
    except ReleaseError as exc:
        _partial_remote_state(state, store, "tag-readback", verified_digest)
        raise
    if observed_tag != commit:
        message = "remote tag was not observable at the expected commit after push"
        _partial_remote_state(state, store, "tag-readback", verified_digest)
        raise ReleaseError(message)

    if release_value is None:
        create = runner.run(
            (
                "gh",
                "release",
                "create",
                tag,
                "--repo",
                config.repository,
                "--title",
                tag,
                "--notes-file",
                str(notes_file),
                "--verify-tag",
                "--target",
                commit,
            ),
            cwd=root,
            check=False,
        )
        if create.returncode != 0:
            detail = create.stderr.strip() or create.stdout.strip() or "release create failed"
            _partial_remote_state(state, store, "release-create", verified_digest)
            raise ReleaseError(f"GitHub Release creation failed: {detail}", exit_code=5)
        release_value = reader.optional_json(
            f"repos/{config.repository}/releases/tags/{tag}"
        )
    if not _validate_release_value(release_value, version):
        message = "GitHub Release is missing or invalid after creation"
        _partial_remote_state(state, store, "release-readback", verified_digest)
        raise ReleaseError(message, exit_code=5)
    if state.release_state in {"TAGGED", "PARTIAL_REMOTE"}:
        state = state.advance(
            "RELEASED",
            {
                "status": "release-available",
                "commit": commit,
                "tree_sha256": verified_digest,
                "runtime_validation": "unverified",
            },
        )
        store.save(state)

    try:
        facts = collect_tag_release_facts(
            root,
            config,
            version,
            commit,
            runner,
            fetch_bytes=fetch_bytes,
            workflow_attempts=workflow_attempts,
            sleep_fn=sleep_fn,
        )
        if facts["tag_release_verified"] is not True:
            raise ReleaseError("tag, Release, main, or workflow evidence is inconsistent")
        if facts["archive_tree_sha256"] != verified_digest:
            raise ReleaseError("remote tag archive differs from LOCAL_VERIFIED candidate")
    except ReleaseError as exc:
        _partial_remote_state(state, store, "tag-verification", verified_digest)
        raise
    state = dataclasses.replace(
        state,
        remote_facts={
            **dict(state.remote_facts),
            **facts,
            "verified_tree_sha256": verified_digest,
        },
    )
    result = {
        "status": "published",
        "version": version,
        "commit": commit,
        "release_state": "TAG_VERIFIED",
        "tree_sha256": verified_digest,
        "archive_validation": "passed",
        "workflow_conclusion": facts["workflow_conclusion"],
        "runtime_validation": "unverified",
    }
    if state.release_state in {"RELEASED", "PARTIAL_REMOTE"}:
        state = state.advance("TAG_VERIFIED", result)
    else:
        state = dataclasses.replace(state, last_result=result)
    store.save(state)
    return result


def _require_stable_promotion_state(
    state: ReleaseState,
    config: ReleaseConfig,
    version: str,
    metadata: Mapping[str, object],
) -> Tuple[str, str]:
    if state.target_version != version or state.repository != config.repository:
        raise ReleaseError("release state does not match the stable promotion target")
    if state.release_state not in {"TAG_VERIFIED", "STABLE_PROMOTED"}:
        raise ReleaseError("promote-stable requires TAG_VERIFIED state")
    commit = state.release_commit
    if not isinstance(commit, str) or SHA_RE.fullmatch(commit) is None:
        raise ReleaseError("release state lacks the verified release commit")
    verified_digest = state.remote_facts.get("verified_tree_sha256")
    if (
        not isinstance(verified_digest, str)
        or DIGEST_RE.fullmatch(verified_digest) is None
    ):
        raise ReleaseError("release state lacks TAG_VERIFIED archive evidence")
    if metadata.get("tree_sha256") != verified_digest:
        raise ReleaseError("local release metadata differs from TAG_VERIFIED evidence")
    return commit, verified_digest


def _require_stable_promotion_facts(
    facts: Mapping[str, object],
    version: str,
    commit: str,
    verified_digest: str,
) -> None:
    if facts.get("main_sha") != commit or facts.get("tag_sha") != commit:
        raise ReleaseError("remote main or immutable tag differs from the release commit")
    if facts.get("release_validation") != "passed":
        raise ReleaseError("GitHub Release is missing or invalid for the release commit")
    if facts.get("workflow_conclusion") != "success":
        raise ReleaseError("release workflow has not succeeded")
    if facts.get("archive_validation") != "passed":
        raise ReleaseError("immutable tag archive validation did not pass")
    if facts.get("archive_tree_sha256") != verified_digest:
        raise ReleaseError("immutable tag archive differs from TAG_VERIFIED evidence")
    stable_sha = facts.get("stable_sha")
    if not isinstance(stable_sha, str) or SHA_RE.fullmatch(stable_sha) is None:
        raise ReleaseError("remote stable branch is missing or invalid")
    if facts.get("stable_fast_forward") is not True:
        raise ReleaseError("stable cannot fast-forward to the release commit")
    manifest_status = facts.get("stable_manifest_validation")
    stable_version = facts.get("stable_manifest_version")
    if stable_sha == commit:
        if manifest_status not in {"passed", "previous"}:
            raise ReleaseError("stable manifest cannot be verified after promotion")
    else:
        if manifest_status != "previous" or not isinstance(stable_version, str):
            raise ReleaseError("stable manifest is not the prior release before promotion")
        require_newer_version(stable_version, version)
    if facts.get("ready_for_promotion") is not True:
        raise ReleaseError("remote release facts are not ready for stable promotion")


def _stable_promotion_consistent(
    facts: Mapping[str, object],
    version: str,
    commit: str,
    verified_digest: str,
) -> bool:
    return bool(
        facts.get("main_sha") == commit
        and facts.get("tag_sha") == commit
        and facts.get("stable_sha") == commit
        and facts.get("release_validation") == "passed"
        and facts.get("workflow_conclusion") == "success"
        and facts.get("archive_validation") == "passed"
        and facts.get("archive_tree_sha256") == verified_digest
        and facts.get("stable_manifest_validation") == "passed"
        and facts.get("stable_manifest_version") == version
        and facts.get("stable_fast_forward") is True
    )


def _wait_for_stable_consistency(
    root: Path,
    config: ReleaseConfig,
    version: str,
    commit: str,
    verified_digest: str,
    runner: Any,
    *,
    fetch_bytes: Callable[[str], bytes],
    attempts: int,
    sleep_fn: Callable[[float], None],
) -> Dict[str, object]:
    if attempts < 1:
        raise ReleaseError("stable consistency attempts must be positive")
    facts: Dict[str, object] = {}
    for index in range(attempts):
        facts = collect_remote_facts(
            root,
            config,
            version,
            runner,
            fetch_bytes=fetch_bytes,
        )
        if _stable_promotion_consistent(
            facts, version, commit, verified_digest
        ):
            return facts
        if index + 1 < attempts:
            delay = min(
                STABLE_CONSISTENCY_BASE_SECONDS * (2**index),
                STABLE_CONSISTENCY_MAX_SECONDS,
            )
            sleep_fn(delay)
    return facts


def promote_stable(
    root: Path,
    config: ReleaseConfig,
    version: str,
    state: ReleaseState,
    store: ReleaseStateStore,
    runner: Any,
    *,
    fetch_bytes: Callable[[str], bytes] = _default_fetch_bytes,
    consistency_attempts: int = STABLE_CONSISTENCY_ATTEMPTS,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> Dict[str, object]:
    """将 stable 非强制快进到已经完整验证的不可变发行提交。"""

    parse_stable_version(version)
    metadata = _validate_metadata(root, config, version)
    commit, verified_digest = _require_stable_promotion_state(
        state, config, version, metadata
    )
    _require_local_publish_preconditions(
        root,
        config,
        commit,
        runner,
        operation="promote-stable",
    )
    facts = collect_remote_facts(
        root,
        config,
        version,
        runner,
        fetch_bytes=fetch_bytes,
    )
    _require_stable_promotion_facts(facts, version, commit, verified_digest)
    state = dataclasses.replace(
        state,
        remote_facts={**dict(state.remote_facts), **facts},
    )

    pushed = facts.get("stable_sha") != commit
    if pushed:
        push = runner.run(
            (
                "git",
                "push",
                "--porcelain",
                "origin",
                f"{commit}:refs/heads/{config.stable_branch}",
            ),
            cwd=root,
            check=False,
        )
        if push.returncode != 0:
            refreshed = collect_remote_facts(
                root,
                config,
                version,
                runner,
                fetch_bytes=fetch_bytes,
            )
            state = dataclasses.replace(
                state,
                remote_facts={**dict(state.remote_facts), **refreshed},
                last_result={
                    "status": "stable-push-rejected",
                    "commit": commit,
                    "tree_sha256": verified_digest,
                    "runtime_validation": "unverified",
                },
            )
            store.save(state)
            detail = push.stderr.strip() or push.stdout.strip() or "push rejected"
            raise ReleaseError(
                f"stable fast-forward push was rejected; remote facts were refreshed: {detail}",
                exit_code=5,
            )

    pending_result = {
        "status": "stable-pushed" if pushed else "stable-existing",
        "version": version,
        "commit": commit,
        "tree_sha256": verified_digest,
        "consistency_validation": "pending",
        "runtime_validation": "unverified",
    }
    if state.release_state == "TAG_VERIFIED":
        state = state.advance("STABLE_PROMOTED", pending_result)
    else:
        state = dataclasses.replace(state, last_result=pending_result)
    store.save(state)

    final_facts = _wait_for_stable_consistency(
        root,
        config,
        version,
        commit,
        verified_digest,
        runner,
        fetch_bytes=fetch_bytes,
        attempts=consistency_attempts,
        sleep_fn=sleep_fn,
    )
    state = dataclasses.replace(
        state,
        remote_facts={**dict(state.remote_facts), **final_facts},
    )
    if not _stable_promotion_consistent(
        final_facts, version, commit, verified_digest
    ):
        state = dataclasses.replace(
            state,
            last_result={
                "status": "stable-consistency-pending",
                "version": version,
                "commit": commit,
                "tree_sha256": verified_digest,
                "consistency_validation": "pending",
                "runtime_validation": "unverified",
            },
        )
        store.save(state)
        raise ReleaseError(
            "stable consistency confirmation reached the bounded timeout",
            exit_code=5,
        )

    result = {
        "status": "promoted",
        "version": version,
        "commit": commit,
        "release_state": "STABLE_PROMOTED",
        "tree_sha256": verified_digest,
        "stable_validation": "passed",
        "runtime_validation": "unverified",
    }
    state = dataclasses.replace(state, last_result=result)
    store.save(state)
    return result


def _runtime_tag_archive_url(config: ReleaseConfig, version: str) -> str:
    parse_stable_version(version)
    return f"https://github.com/{config.repository}/archive/refs/tags/v{version}.zip"


def _require_runtime_state(
    root: Path,
    config: ReleaseConfig,
    version: str,
    state: ReleaseState,
) -> Tuple[str, str]:
    if state.target_version != version or state.repository != config.repository:
        raise ReleaseError("release state does not match the runtime verification target")
    if state.release_state == "RUNTIME_VERIFIED":
        raise ReleaseError("runtime verification is already complete for this version")
    if state.release_state != "STABLE_PROMOTED":
        raise ReleaseError("verify-runtime requires STABLE_PROMOTED state")
    commit = state.release_commit
    if not isinstance(commit, str) or SHA_RE.fullmatch(commit) is None:
        raise ReleaseError("release state lacks the promoted release commit")
    digest = state.remote_facts.get("verified_tree_sha256")
    if not isinstance(digest, str) or DIGEST_RE.fullmatch(digest) is None:
        raise ReleaseError("release state lacks the promoted archive digest")
    metadata = _validate_metadata(root, config, version)
    if metadata.get("tree_sha256") != digest:
        raise ReleaseError("local release metadata differs from promoted evidence")
    require_newer_version(state.previous_version, version)
    return commit, digest


def _runtime_release_payloads(
    root: Path,
    config: ReleaseConfig,
    version: str,
    verified_digest: str,
    *,
    fetch_bytes: Callable[[str], bytes],
    previous_version: Optional[str] = None,
) -> Tuple[Dict[str, object], bytes, Optional[bytes]]:
    urls = remote_urls(config, version)
    stable_value = _json_loads(
        fetch_bytes(urls["stable_manifest"]), "stable runtime manifest"
    )
    if not isinstance(stable_value, dict):
        raise ReleaseError("stable runtime manifest must be an object", exit_code=5)
    updater = load_updater(root / config.skill_root)
    try:
        stable_manifest = dict(updater.validate_manifest(stable_value))
    except Exception as exc:
        raise ReleaseError("stable runtime manifest is invalid", exit_code=5) from exc
    if (
        stable_manifest.get("version") != version
        or stable_manifest.get("ref") != f"v{version}"
        or stable_manifest.get("tree_sha256") != verified_digest
    ):
        raise ReleaseError(
            "stable runtime manifest differs from promoted evidence", exit_code=5
        )
    target_archive = fetch_bytes(urls["tag_archive"])
    target_manifest = _validate_archive_bytes(
        root, config, version, target_archive
    )
    if target_manifest != stable_manifest:
        raise ReleaseError(
            "stable runtime manifest differs from the immutable archive",
            exit_code=5,
        )
    previous_archive: Optional[bytes] = None
    if previous_version is not None:
        require_newer_version(previous_version, version)
        previous_archive = fetch_bytes(
            _runtime_tag_archive_url(config, previous_version)
        )
        _validate_archive_bytes(root, config, previous_version, previous_archive)
    return stable_manifest, target_archive, previous_archive


def _stage_runtime_archive(
    updater: Any,
    payload: bytes,
    expected_manifest: Mapping[str, object],
    expected_version: str,
    staging_root: Path,
) -> Path:
    archive = staging_root / "release.zip"
    try:
        staging_root.mkdir(parents=True)
        archive.write_bytes(payload)
        candidate = updater.stage_archive(archive, staging_root)
        value = _json_loads(
            (candidate / "update.json").read_bytes(), "runtime archive manifest"
        )
        if not isinstance(value, dict):
            raise ReleaseError("runtime archive manifest must be an object", exit_code=7)
        manifest = updater.validate_manifest(value)
        updater._verify_candidate(candidate, manifest)
        candidate_version = updater.read_version(candidate)
    except ReleaseError:
        raise
    except Exception as exc:
        raise ReleaseError("runtime archive staging failed", exit_code=7) from exc
    if candidate_version != expected_version or dict(manifest) != dict(expected_manifest):
        raise ReleaseError("runtime archive differs from expected release", exit_code=7)
    return candidate


def _runtime_archive_writer(payload: bytes, expected_ref: str) -> Callable[[str, Path], None]:
    def write_archive(ref: str, target: Path) -> None:
        if ref != expected_ref:
            raise OSError("runtime updater requested an unexpected immutable ref")
        target.write_bytes(payload)

    return write_archive


def _record_runtime_failure(
    state: ReleaseState,
    store: ReleaseStateStore,
    *,
    mode: str,
    phase: str,
    rollback_validation: str,
) -> None:
    result = {
        "status": "runtime-failed",
        "mode": mode,
        "phase": phase,
        "rollback_validation": rollback_validation,
        "runtime_validation": "failed",
    }
    if state.release_state == "STABLE_PROMOTED":
        state = state.advance("PROMOTED_RUNTIME_FAILED", result)
    else:
        state = dataclasses.replace(state, last_result=result)
    store.save(state)


def _runtime_lanes(state: ReleaseState) -> Dict[str, object]:
    value = state.remote_facts.get("runtime_lanes")
    return dict(value) if isinstance(value, dict) else {}


def verify_runtime_isolated(
    root: Path,
    config: ReleaseConfig,
    version: str,
    state: ReleaseState,
    store: ReleaseStateStore,
    *,
    fetch_bytes: Callable[[str], bytes] = _default_fetch_bytes,
) -> Dict[str, object]:
    """在临时目录完成公开 updater 的升级、回滚和重升级闭环。"""

    _commit, verified_digest = _require_runtime_state(
        root, config, version, state
    )
    stable_manifest, target_archive, previous_archive = _runtime_release_payloads(
        root,
        config,
        version,
        verified_digest,
        fetch_bytes=fetch_bytes,
        previous_version=state.previous_version,
    )
    if previous_archive is None:
        raise ReleaseError("previous immutable archive is unavailable", exit_code=5)
    previous_manifest = _validate_archive_bytes(
        root, config, state.previous_version, previous_archive
    )
    phase = "install-previous"
    try:
        with tempfile.TemporaryDirectory(prefix="vibe-diagram-runtime-") as temporary:
            runtime_root = Path(temporary)
            canonical_updater = load_updater(root / config.skill_root)
            previous_candidate = _stage_runtime_archive(
                canonical_updater,
                previous_archive,
                previous_manifest,
                state.previous_version,
                runtime_root / "previous-stage",
            )
            installed = runtime_root / "skills" / "vibe-diagram"
            installed.parent.mkdir(parents=True)
            shutil.copytree(previous_candidate, installed)
            if _read_version(installed / "VERSION") != state.previous_version:
                raise ReleaseError("isolated previous installation has the wrong version")

            phase = "upgrade"
            installed_updater = load_updater(installed)
            updated = installed_updater.check_and_update(
                installed,
                fetch_manifest=lambda: dict(stable_manifest),
                fetch_archive=_runtime_archive_writer(
                    target_archive, f"v{version}"
                ),
            )
            if updated.status != "updated" or _read_version(installed / "VERSION") != version:
                raise ReleaseError("isolated updater did not activate the target version")
            if not updated.backup_path or not Path(updated.backup_path).is_dir():
                raise ReleaseError("isolated updater did not create a recoverable backup")

            phase = "current"
            target_updater = load_updater(installed)
            current = target_updater.check_and_update(
                installed,
                fetch_manifest=lambda: dict(stable_manifest),
                fetch_archive=lambda _ref, _target: (_ for _ in ()).throw(
                    OSError("current check unexpectedly requested an archive")
                ),
            )
            if current.status != "current" or _read_version(installed / "VERSION") != version:
                raise ReleaseError("isolated current check did not preserve the target")

            phase = "offline"
            offline = target_updater.check_and_update(
                installed,
                fetch_manifest=lambda: (_ for _ in ()).throw(OSError("offline fixture")),
                fetch_archive=lambda _ref, _target: None,
            )
            if offline.status != "offline" or _read_version(installed / "VERSION") != version:
                raise ReleaseError("isolated offline check did not fail open")

            phase = "rollback"
            rolled_back = target_updater.rollback(installed)
            if (
                rolled_back.status != "rolled_back"
                or _read_version(installed / "VERSION") != state.previous_version
            ):
                raise ReleaseError("isolated rollback did not restore the previous version")

            phase = "reupgrade"
            previous_updater = load_updater(installed)
            reupdated = previous_updater.check_and_update(
                installed,
                fetch_manifest=lambda: dict(stable_manifest),
                fetch_archive=_runtime_archive_writer(
                    target_archive, f"v{version}"
                ),
            )
            if reupdated.status != "updated" or _read_version(installed / "VERSION") != version:
                raise ReleaseError("isolated re-upgrade did not restore the target")

            phase = "fresh-install"
            fresh_candidate = _stage_runtime_archive(
                canonical_updater,
                target_archive,
                stable_manifest,
                version,
                runtime_root / "fresh-stage",
            )
            fresh = runtime_root / "fresh" / "skills" / "vibe-diagram"
            fresh.parent.mkdir(parents=True)
            shutil.copytree(fresh_candidate, fresh)
            if _read_version(fresh / "VERSION") != version:
                raise ReleaseError("isolated fresh installation has the wrong version")

            phase = "removal"
            shutil.rmtree(installed)
            shutil.rmtree(fresh)
            if installed.exists() or fresh.exists():
                raise ReleaseError("isolated removal did not isolate both installations")
    except ReleaseError as exc:
        _record_runtime_failure(
            state,
            store,
            mode="isolated",
            phase=phase,
            rollback_validation="not-applicable",
        )
        raise ReleaseError(
            f"isolated runtime lifecycle failed during {phase}", exit_code=7
        ) from exc
    except Exception as exc:
        _record_runtime_failure(
            state,
            store,
            mode="isolated",
            phase=phase,
            rollback_validation="not-applicable",
        )
        raise ReleaseError(
            f"isolated runtime lifecycle failed during {phase}", exit_code=7
        ) from exc

    lifecycle = {
        "upgrade": "passed",
        "current": "passed",
        "offline": "passed",
        "rollback": "passed",
        "reupgrade": "passed",
        "fresh_install": "passed",
        "removal": "passed",
    }
    lanes = _runtime_lanes(state)
    lanes["isolated"] = {
        "status": "passed",
        "version": version,
        "tree_sha256": verified_digest,
    }
    result = {
        "status": "runtime-isolated-passed",
        "mode": "isolated",
        "version": version,
        "release_state": "STABLE_PROMOTED",
        "isolated_validation": "passed",
        "runtime_validation": "unverified",
        "lifecycle": lifecycle,
    }
    state = dataclasses.replace(
        state,
        remote_facts={**dict(state.remote_facts), "runtime_lanes": lanes},
        last_result=result,
    )
    store.save(state)
    return result


def _validate_runtime_artifact(path: Path) -> Path:
    if not path.is_absolute():
        raise ReleaseError("--artifact must be an absolute path")
    if any(ord(character) < 32 for character in str(path)):
        raise ReleaseError("--artifact must not contain control characters")
    if path.exists() or path.is_symlink():
        raise ReleaseError("--artifact must not already exist")
    parent = path.parent
    if parent.is_symlink() or not parent.is_dir():
        raise ReleaseError("--artifact parent must be a real directory")
    return path


def _runtime_codex_home(override: Optional[Path]) -> Path:
    if override is None:
        configured = os.environ.get("CODEX_HOME")
        path = Path(configured) if configured else Path.home() / ".codex"
    else:
        path = override
    if not path.is_absolute() or path.is_symlink() or not path.is_dir():
        raise ReleaseError("Codex home must be an existing absolute real directory")
    return path


def _read_runtime_marker(path: Path, expected: str) -> None:
    if path.is_symlink() or not path.is_file():
        raise ReleaseError("Codex CLI did not produce the runtime marker", exit_code=7)
    try:
        if path.stat().st_size > MAX_RUNTIME_MARKER_BYTES:
            raise ReleaseError("Codex CLI runtime marker is too large", exit_code=7)
        marker = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise ReleaseError("Codex CLI runtime marker is unreadable", exit_code=7) from exc
    lines = [line.strip() for line in marker.splitlines() if line.strip()]
    if not lines or lines[-1] != expected:
        raise ReleaseError("Codex CLI runtime marker did not confirm the step", exit_code=7)


def _run_codex_runtime_step(
    runner: Any,
    *,
    codex_home: Path,
    workspace: Path,
    prompt: str,
    expected_marker: str,
) -> None:
    with tempfile.TemporaryDirectory(
        prefix=".vibe-diagram-runtime-", dir=workspace
    ) as temporary:
        marker = Path(temporary) / "last-message.txt"
        command = (
            "codex",
            "exec",
            "--ephemeral",
            "--sandbox",
            "workspace-write",
            "--ask-for-approval",
            "never",
            "--skip-git-repo-check",
            "--output-last-message",
            str(marker),
            prompt,
        )
        result = runner.run(
            command,
            cwd=workspace,
            check=False,
            env={"CODEX_HOME": str(codex_home)},
        )
        if result.returncode != 0:
            raise ReleaseError("Codex CLI invocation failed", exit_code=7)
        _read_runtime_marker(marker, expected_marker)


def _validate_runtime_artifact_result(path: Path) -> str:
    if path.is_symlink() or not path.is_file():
        raise ReleaseError("Codex CLI did not create the runtime artifact", exit_code=7)
    try:
        size = path.stat().st_size
        if size <= 0 or size > MAX_RUNTIME_ARTIFACT_BYTES:
            raise ReleaseError("runtime artifact size is invalid", exit_code=7)
        payload = path.read_bytes()
    except OSError as exc:
        raise ReleaseError("runtime artifact is unreadable", exit_code=7) from exc
    return hashlib.sha256(payload).hexdigest()


def _require_isolated_runtime_evidence(
    state: ReleaseState, version: str, verified_digest: str
) -> None:
    lanes = _runtime_lanes(state)
    isolated = lanes.get("isolated")
    if not isinstance(isolated, dict) or not (
        isolated.get("status") == "passed"
        and isolated.get("version") == version
        and isolated.get("tree_sha256") == verified_digest
    ):
        raise ReleaseError("installed-client requires matching isolated runtime evidence")


def _rollback_installed_runtime(
    skill_root: Path,
    previous_version: str,
    recovery_backup: Optional[Path],
) -> str:
    try:
        current = _read_version(skill_root / "VERSION")
        if current == previous_version:
            return "passed"
        if (
            recovery_backup is not None
            and recovery_backup.is_absolute()
            and not recovery_backup.is_symlink()
            and recovery_backup.is_dir()
            and recovery_backup.parent.resolve()
            == (skill_root.parent.parent / "backups" / "skills").resolve()
            and _read_version(recovery_backup / "VERSION") == previous_version
        ):
            backups = recovery_backup.parent
            stamp = time.strftime("%Y%m%d%H%M%S", time.gmtime())
            displaced = backups / f"vibe-diagram-{current}-runtime-failed-{stamp}"
            suffix = 1
            while displaced.exists():
                displaced = backups / (
                    f"vibe-diagram-{current}-runtime-failed-{stamp}-{suffix}"
                )
                suffix += 1
            os.replace(skill_root, displaced)
            try:
                os.replace(recovery_backup, skill_root)
            except BaseException:
                os.replace(displaced, skill_root)
                raise
            if _read_version(skill_root / "VERSION") == previous_version:
                return "passed"
        updater = load_updater(skill_root)
        result = updater.rollback(skill_root)
        if (
            result.status == "rolled_back"
            and _read_version(skill_root / "VERSION") == previous_version
        ):
            return "passed"
    except Exception:
        pass
    return "failed"


def verify_runtime_installed(
    root: Path,
    config: ReleaseConfig,
    version: str,
    artifact: Path,
    state: ReleaseState,
    store: ReleaseStateStore,
    runner: Any,
    *,
    codex_home: Optional[Path] = None,
    fetch_bytes: Callable[[str], bytes] = _default_fetch_bytes,
) -> Dict[str, object]:
    """在显式授权后验证真实 Codex CLI 直装 Skill 生命周期。"""

    _commit, verified_digest = _require_runtime_state(
        root, config, version, state
    )
    _require_isolated_runtime_evidence(state, version, verified_digest)
    artifact = _validate_runtime_artifact(artifact)
    codex_root = _runtime_codex_home(codex_home)
    skills_root = codex_root / "skills"
    if skills_root.is_symlink() or not skills_root.is_dir():
        raise ReleaseError("Codex skills directory must be a real directory")
    backups_root = codex_root / "backups"
    if backups_root.exists() and (backups_root.is_symlink() or not backups_root.is_dir()):
        raise ReleaseError("Codex backups directory must be a real directory")
    installed = skills_root / "vibe-diagram"
    if installed.is_symlink() or not installed.is_dir():
        raise ReleaseError("installed vibe-diagram Skill must be a real directory")
    try:
        installed_version = _read_version(installed / "VERSION")
    except ReleaseError as exc:
        raise ReleaseError("installed vibe-diagram version is invalid") from exc
    if installed_version != state.previous_version:
        raise ReleaseError(
            "installed-client requires the previous stable version before mutation"
        )
    stable_manifest, target_archive, _previous = _runtime_release_payloads(
        root,
        config,
        version,
        verified_digest,
        fetch_bytes=fetch_bytes,
    )

    phase = "upgrade"
    mutation_started = False
    recovery_backup: Optional[Path] = None
    quarantine: Optional[Path] = None
    displaced: Optional[Path] = None
    remove_quarantine_parent = False
    try:
        previous_updater = load_updater(installed)
        upgraded = previous_updater.check_and_update(
            installed,
            fetch_manifest=lambda: dict(stable_manifest),
            fetch_archive=_runtime_archive_writer(target_archive, f"v{version}"),
        )
        mutation_started = upgraded.status == "updated"
        if not mutation_started or _read_version(installed / "VERSION") != version:
            raise ReleaseError("installed updater did not activate the target", exit_code=7)
        recovery_backup = Path(upgraded.backup_path) if upgraded.backup_path else None

        phase = "rollback"
        target_updater = load_updater(installed)
        rolled_back = target_updater.rollback(installed)
        if (
            rolled_back.status != "rolled_back"
            or _read_version(installed / "VERSION") != state.previous_version
        ):
            raise ReleaseError("installed rollback did not restore the previous version", exit_code=7)
        recovery_backup = None

        phase = "reupgrade"
        previous_updater = load_updater(installed)
        reupgraded = previous_updater.check_and_update(
            installed,
            fetch_manifest=lambda: dict(stable_manifest),
            fetch_archive=_runtime_archive_writer(target_archive, f"v{version}"),
        )
        if reupgraded.status != "updated" or _read_version(installed / "VERSION") != version:
            raise ReleaseError("installed re-upgrade did not restore the target", exit_code=7)
        recovery_backup = (
            Path(reupgraded.backup_path) if reupgraded.backup_path else None
        )

        phase = "codex-invocation"
        prompt = (
            "Use $vibe-diagram to create one evidence-backed, self-contained HTML "
            "system architecture diagram at the exact absolute path "
            f"{artifact}. Write no other files. End the final response with "
            "VIBE_DIAGRAM_RUNTIME_OK."
        )
        _run_codex_runtime_step(
            runner,
            codex_home=codex_root,
            workspace=artifact.parent,
            prompt=prompt,
            expected_marker="VIBE_DIAGRAM_RUNTIME_OK",
        )
        artifact_digest = _validate_runtime_artifact_result(artifact)

        phase = "artifact-lint"
        lint = runner.run(
            (
                sys.executable,
                str(installed / "scripts" / "vibe_diagram_lint.py"),
                str(artifact),
                "--type",
                "system-architecture",
            ),
            cwd=artifact.parent,
            check=False,
            env={"PYTHONDONTWRITEBYTECODE": "1"},
        )
        if lint.returncode != 0:
            raise ReleaseError("bundled runtime artifact linter failed", exit_code=7)

        phase = "uninstall-isolation"
        quarantine_parent = codex_root / "backups" / "runtime-verification"
        if quarantine_parent.exists() and (
            quarantine_parent.is_symlink() or not quarantine_parent.is_dir()
        ):
            raise ReleaseError("runtime quarantine must be a real directory", exit_code=7)
        remove_quarantine_parent = not quarantine_parent.exists()
        quarantine_parent.mkdir(parents=True, exist_ok=True)
        quarantine = Path(
            tempfile.mkdtemp(prefix="vibe-diagram-", dir=quarantine_parent)
        )
        displaced = quarantine / "vibe-diagram"
        os.replace(installed, displaced)
        unavailable_prompt = (
            "Confirm that $vibe-diagram is unavailable in this fresh Codex process. "
            "Do not create or modify files. End with VIBE_DIAGRAM_UNAVAILABLE_OK "
            "only when the Skill is not discoverable."
        )
        _run_codex_runtime_step(
            runner,
            codex_home=codex_root,
            workspace=artifact.parent,
            prompt=unavailable_prompt,
            expected_marker="VIBE_DIAGRAM_UNAVAILABLE_OK",
        )
        if installed.exists():
            raise ReleaseError("uninstall isolation unexpectedly recreated the Skill", exit_code=7)
        os.replace(displaced, installed)
        displaced = None
        if _read_version(installed / "VERSION") != version:
            raise ReleaseError("uninstall isolation did not restore the target", exit_code=7)
        if _validate_runtime_artifact_result(artifact) != artifact_digest:
            raise ReleaseError("uninstall isolation changed the runtime artifact", exit_code=7)
        shutil.rmtree(quarantine)
        quarantine = None
        if remove_quarantine_parent:
            quarantine_parent.rmdir()
            remove_quarantine_parent = False
    except Exception as exc:
        if displaced is not None and displaced.exists() and not installed.exists():
            try:
                os.replace(displaced, installed)
                displaced = None
            except OSError:
                pass
        rollback_validation = (
            _rollback_installed_runtime(
                installed, state.previous_version, recovery_backup
            )
            if mutation_started and installed.exists()
            else "not-required"
        )
        _record_runtime_failure(
            state,
            store,
            mode="installed-client",
            phase=phase,
            rollback_validation=rollback_validation,
        )
        if isinstance(exc, ReleaseError):
            raise
        raise ReleaseError(
            f"installed runtime lifecycle failed during {phase}", exit_code=7
        ) from exc
    finally:
        if quarantine is not None and quarantine.exists() and displaced is None:
            shutil.rmtree(quarantine, ignore_errors=True)

    lanes = _runtime_lanes(state)
    lanes["installed-client"] = {
        "status": "passed",
        "version": version,
        "tree_sha256": verified_digest,
        "runtime_lane": "github-path-codex-cli",
        "artifact_sha256": artifact_digest,
        "artifact_validation": "passed",
        "discovery_validation": "passed",
        "uninstall_validation": "passed",
    }
    result = {
        "status": "runtime-verified",
        "mode": "installed-client",
        "version": version,
        "release_state": "RUNTIME_VERIFIED",
        "runtime_lane": "github-path-codex-cli",
        "artifact_sha256": artifact_digest,
        "artifact_validation": "passed",
        "discovery_validation": "passed",
        "uninstall_validation": "passed",
        "runtime_validation": "runtime-verified",
    }
    state = dataclasses.replace(
        state,
        remote_facts={**dict(state.remote_facts), "runtime_lanes": lanes},
    ).advance("RUNTIME_VERIFIED", result)
    store.save(state)
    return result


def _state_directory(root: Path, runner: Any, override: Optional[str]) -> Path:
    if override:
        path = Path(override)
        return path if path.is_absolute() else root / path
    result = runner.run(
        ("git", "rev-parse", "--git-path", "vibe-diagram-release"),
        cwd=root,
        check=True,
    )
    text = result.stdout.strip()
    if not text:
        raise ReleaseError("git did not return a release state path")
    path = Path(text)
    return path if path.is_absolute() else root / path


def _baseline_head(root: Path, runner: Any) -> str:
    result = runner.run(("git", "rev-parse", "HEAD"), cwd=root, check=True)
    value = result.stdout.strip()
    if SHA_RE.fullmatch(value) is None:
        raise ReleaseError("git HEAD is not a lowercase SHA")
    return value


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    subparsers = parser.add_subparsers(dest="command", required=True)

    def common(name: str) -> argparse.ArgumentParser:
        command = subparsers.add_parser(name, allow_abbrev=False)
        command.add_argument("--version", required=True)
        command.add_argument("--repo")
        command.add_argument("--config", default=str(CONFIG_RELATIVE))
        command.add_argument("--root")
        command.add_argument("--state-dir")
        command.add_argument("--json", action="store_true")
        return command

    prepare = common("prepare")
    prepare.add_argument("--dry-run", action="store_true")
    verify = common("verify")
    verify.add_argument("--current-python", default=sys.executable)
    status = common("status")
    status.add_argument("--refresh", action="store_true")
    publish = common("publish")
    publish.add_argument("--commit")
    publish.add_argument("--notes-file")
    publish.add_argument("--confirm-remote-actions", action="store_true")
    promote = common("promote-stable")
    promote.add_argument("--confirm-stable-promotion", action="store_true")
    runtime = common("verify-runtime")
    runtime.add_argument("--mode", choices=("isolated", "installed-client"), default="isolated")
    runtime.add_argument("--confirm-installed-skill-mutation", action="store_true")
    runtime.add_argument("--artifact")
    return parser.parse_args(argv)


def _command_result(
    command: str, repository: str, payload: Mapping[str, object]
) -> Dict[str, object]:
    reserved = {"schema_version", "command", "repository"}
    if reserved & set(payload):
        raise ReleaseError("command result payload contains reserved fields")
    return {
        "schema_version": 1,
        "command": command,
        "repository": repository,
        **dict(payload),
    }


def execute(
    args: argparse.Namespace,
    *,
    root: Path = ROOT,
    runner: Optional[Any] = None,
    fetch_bytes: Callable[[str], bytes] = _default_fetch_bytes,
) -> Dict[str, object]:
    runner = runner or SubprocessRunner()
    if args.root:
        root = Path(args.root).resolve()
    else:
        root = root.resolve()
    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = root / config_path
    config = load_config(root, config_path)
    if args.repo:
        try:
            repository = _validate_repository(args.repo)
        except ReleaseError as exc:
            raise ReleaseError("--repo must be owner/name") from exc
        config = dataclasses.replace(config, repository=repository)
    parse_stable_version(args.version)
    if args.command == "verify-runtime" and args.mode == "installed-client":
        if not args.confirm_installed_skill_mutation:
            raise ReleaseError(
                "installed-client requires --confirm-installed-skill-mutation"
            )
        if not args.artifact:
            raise ReleaseError("installed-client requires --artifact")
    if args.command == "verify-runtime" and args.mode == "isolated" and args.artifact:
        raise ReleaseError("--artifact is only valid with --mode installed-client")
    if args.command == "promote-stable" and not args.confirm_stable_promotion:
        raise ReleaseError("promote-stable requires --confirm-stable-promotion")
    if args.command == "publish":
        if not args.confirm_remote_actions:
            raise ReleaseError("publish requires --confirm-remote-actions")
        if not args.commit:
            raise ReleaseError("publish requires --commit")
        if not args.notes_file:
            raise ReleaseError("publish requires --notes-file")
    state_dir = _state_directory(root, runner, args.state_dir)
    store = ReleaseStateStore(state_dir)
    state = store.ensure_compatible(args.version, config.repository)
    if args.command == "prepare":
        previous = _read_version(root / config.version_file)
        result = prepare_release(root, config, args.version, runner, dry_run=args.dry_run)
        if args.dry_run:
            return _command_result(args.command, config.repository, result)
        if state is None:
            state = ReleaseState.new(
                target_version=args.version,
                previous_version=previous,
                repository=config.repository,
                baseline_head=_baseline_head(root, runner),
            )
        if state.release_state == "NEW":
            state = state.advance("PREPARED", result)
        store.save(state)
        return _command_result(
            args.command,
            config.repository,
            dict(result, release_state=state.release_state),
        )
    if args.command == "verify":
        result = verify_release(
            root,
            config,
            args.version,
            runner,
            current_python=args.current_python,
        )
        if state is None:
            state = ReleaseState.new(
                target_version=args.version,
                previous_version=args.version,
                repository=config.repository,
                baseline_head=_baseline_head(root, runner),
            ).advance("PREPARED", {"status": "reconstructed"})
        if state.release_state == "PREPARED":
            state = state.advance("LOCAL_VERIFIED", result)
        elif state.release_state != "LOCAL_VERIFIED":
            raise ReleaseError("verify requires PREPARED or LOCAL_VERIFIED state")
        state = dataclasses.replace(
            state,
            remote_facts={
                **dict(state.remote_facts),
                "verified_tree_sha256": result["tree_sha256"],
            },
        )
        store.save(state)
        return _command_result(
            args.command,
            config.repository,
            dict(result, release_state=state.release_state),
        )
    if args.command == "status":
        facts: Dict[str, object] = {}
        if args.refresh:
            facts = collect_remote_facts(
                root,
                config,
                args.version,
                runner,
                fetch_bytes=fetch_bytes,
            )
            if state is not None:
                state = dataclasses.replace(
                    state,
                    remote_facts={**dict(state.remote_facts), **facts},
                )
                store.save(state)
        return _command_result(
            args.command,
            config.repository,
            {
                "status": "available",
                "version": args.version,
                "release_state": state.release_state if state else "NEW",
                "remote_facts": facts,
                "runtime_validation": "unverified",
            },
        )
    if args.command == "publish":
        if state is None:
            raise ReleaseError("publish requires persisted LOCAL_VERIFIED state")
        result = publish_release(
            root,
            config,
            args.version,
            args.commit,
            Path(args.notes_file),
            state,
            store,
            runner,
            fetch_bytes=fetch_bytes,
        )
        return _command_result(args.command, config.repository, result)
    if args.command == "promote-stable":
        if state is None:
            raise ReleaseError("promote-stable requires persisted TAG_VERIFIED state")
        result = promote_stable(
            root,
            config,
            args.version,
            state,
            store,
            runner,
            fetch_bytes=fetch_bytes,
        )
        return _command_result(args.command, config.repository, result)
    if args.command == "verify-runtime":
        if state is None:
            raise ReleaseError("verify-runtime requires persisted STABLE_PROMOTED state")
        if args.mode == "isolated":
            result = verify_runtime_isolated(
                root,
                config,
                args.version,
                state,
                store,
                fetch_bytes=fetch_bytes,
            )
        else:
            result = verify_runtime_installed(
                root,
                config,
                args.version,
                Path(args.artifact),
                state,
                store,
                runner,
                fetch_bytes=fetch_bytes,
            )
        return _command_result(args.command, config.repository, result)
    raise ReleaseError(f"unsupported command: {args.command}", exit_code=2)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    try:
        result = execute(args)
    except ReleaseError as exc:
        if getattr(args, "json", False):
            print(
                json.dumps(
                    {
                        "schema_version": 1,
                        "command": getattr(args, "command", None),
                        "status": "failed",
                        "message": str(exc),
                    },
                    ensure_ascii=True,
                    allow_nan=False,
                    sort_keys=True,
                )
            )
        else:
            print(str(exc), file=sys.stderr)
        return exc.exit_code
    if getattr(args, "json", False):
        print(json.dumps(result, ensure_ascii=True, allow_nan=False, sort_keys=True))
    else:
        print(result.get("status", "ok"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
