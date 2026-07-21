from __future__ import annotations

import io
import json
import shutil
import tempfile
import threading
import unittest
import zipfile
import contextlib
from pathlib import Path
from unittest import mock

from scripts import release_github_skill as release


ROOT = Path(__file__).resolve().parents[1]
UPDATE_SCRIPT = ROOT / "skills" / "vibe-diagram" / "scripts" / "update_skill.py"


class FakeRunner:
    def __init__(self, responses: dict[tuple[str, ...], release.CommandResult] | None = None):
        self.responses = responses or {}
        self.calls: list[tuple[str, ...]] = []

    def run(
        self,
        arguments: list[str] | tuple[str, ...],
        *,
        cwd: Path,
        check: bool = True,
        env: dict[str, str] | None = None,
    ) -> release.CommandResult:
        del cwd, env
        key = tuple(arguments)
        self.calls.append(key)
        result = self.responses.get(key, release.CommandResult(0, "", ""))
        if check and result.returncode != 0:
            raise release.ReleaseError(result.stderr or "command failed", exit_code=4)
        return result


class ScriptedRunner(FakeRunner):
    def __init__(
        self,
        responses: dict[
            tuple[str, ...],
            release.CommandResult | list[release.CommandResult],
        ],
    ):
        super().__init__()
        self.scripted_responses = {
            command: list(value) if isinstance(value, list) else [value]
            for command, value in responses.items()
        }

    def run(
        self,
        arguments: list[str] | tuple[str, ...],
        *,
        cwd: Path,
        check: bool = True,
        env: dict[str, str] | None = None,
    ) -> release.CommandResult:
        del cwd, env
        key = tuple(arguments)
        self.calls.append(key)
        scripted = self.scripted_responses.get(key)
        if scripted:
            result = scripted.pop(0) if len(scripted) > 1 else scripted[0]
        else:
            result = release.CommandResult(0, "", "")
        if check and result.returncode != 0:
            raise release.ReleaseError(result.stderr or "command failed", exit_code=4)
        return result


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _tree_sha256(skill_root: Path) -> str:
    return release.load_updater(skill_root).tree_sha256(skill_root)


def _write_repository(root: Path, version: str = "0.1.3") -> release.ReleaseConfig:
    skill = root / "skills" / "vibe-diagram"
    (skill / "scripts").mkdir(parents=True)
    (skill / "references").mkdir()
    (root / "scripts").mkdir()
    (root / "release").mkdir()
    (root / "build" / "codex").mkdir(parents=True)
    (root / "plugins" / "vibe-diagram").mkdir(parents=True)
    (root / "tests").mkdir()
    (root / "VERSION").write_text(version + "\n", encoding="ascii")
    (skill / "VERSION").write_text(version + "\n", encoding="ascii")
    (skill / "SKILL.md").write_text(
        "---\nname: vibe-diagram\ndescription: Use when diagrams are needed.\n---\n",
        encoding="utf-8",
    )
    shutil.copy2(UPDATE_SCRIPT, skill / "scripts" / "update_skill.py")
    (skill / "scripts" / "vibe_diagram_lint.py").write_text(
        "#!/usr/bin/env python3\n",
        encoding="utf-8",
    )
    (skill / "references" / "runtime-workflow.md").write_text(
        "# Runtime workflow\n",
        encoding="utf-8",
    )
    (root / "scripts" / "build_packages.py").write_text("# fixture\n", encoding="utf-8")
    _write_json(
        skill / "update.json",
        {
            "schema_version": 1,
            "channel": "stable",
            "version": version,
            "ref": f"v{version}",
            "tree_sha256": _tree_sha256(skill),
        },
    )
    config_value = {
        "schema_version": 1,
        "repository": "owner/repository",
        "main_branch": "main",
        "stable_branch": "stable",
        "workflow_file": "static-validation.yml",
        "version_file": "VERSION",
        "skill_root": "skills/vibe-diagram",
        "update_manifest": "skills/vibe-diagram/update.json",
        "publication_command": [
            "python3",
            "scripts/build_packages.py",
            "--sync-publication",
        ],
        "build_command": [
            "python3",
            "scripts/build_packages.py",
            "--output",
            "build",
        ],
        "check_command": ["python3", "scripts/build_packages.py", "--check"],
    }
    _write_json(root / "release" / "github-skill.json", config_value)
    return release.load_config(root, root / "release" / "github-skill.json")


def _archive_bytes(skill: Path, version: str) -> bytes:
    output = io.BytesIO()
    prefix = f"vibe-diagram-{version}/skills/vibe-diagram"
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for source in sorted(path for path in skill.rglob("*") if path.is_file()):
            archive.write(source, f"{prefix}/{source.relative_to(skill).as_posix()}")
    return output.getvalue()


def _verified_state(
    root: Path,
    config: release.ReleaseConfig,
    version: str,
    commit: str,
) -> tuple[release.ReleaseStateStore, release.ReleaseState]:
    release.prepare_release(root, config, version, FakeRunner())
    digest = json.loads(
        (root / config.update_manifest).read_text(encoding="utf-8")
    )["tree_sha256"]
    state = release.ReleaseState.new(
        target_version=version,
        previous_version="0.1.3",
        repository=config.repository,
        baseline_head="a" * 40,
    )
    state = state.advance("PREPARED", {"status": "prepared"})
    state = state.advance(
        "LOCAL_VERIFIED",
        {
            "status": "passed",
            "local_validation": "static-valid",
            "tree_sha256": digest,
        },
    )
    store = release.ReleaseStateStore(root / "state")
    store.save(state)
    return store, state


def _publish_responses(
    notes: Path,
    commit: str,
    *,
    tag_sequence: list[release.CommandResult],
    release_sequence: list[release.CommandResult],
    release_create: release.CommandResult | None = None,
) -> dict[tuple[str, ...], release.CommandResult | list[release.CommandResult]]:
    repository = "owner/repository"
    base = f"repos/{repository}"
    workflow = json.dumps(
        {
            "workflow_runs": [
                {
                    "head_sha": commit,
                    "status": "completed",
                    "conclusion": "success",
                }
            ]
        }
    )
    responses: dict[
        tuple[str, ...],
        release.CommandResult | list[release.CommandResult],
    ] = {
        ("git", "status", "--porcelain=v1", "--untracked-files=all"): release.CommandResult(
            0, "", ""
        ),
        ("git", "rev-parse", "HEAD"): release.CommandResult(0, commit + "\n", ""),
        ("git", "remote", "get-url", "origin"): release.CommandResult(
            0, "git@github.com:owner/repository.git\n", ""
        ),
        ("gh", "auth", "status", "--hostname", "github.com"): release.CommandResult(
            0, "", ""
        ),
        ("gh", "api", base): release.CommandResult(
            0, json.dumps({"permissions": {"push": True}}), ""
        ),
        ("gh", "api", f"{base}/commits/main"): release.CommandResult(
            0, json.dumps({"sha": commit}), ""
        ),
        (
            "gh",
            "api",
            f"{base}/actions/workflows/static-validation.yml/runs?head_sha={commit}&per_page=20",
        ): release.CommandResult(0, workflow, ""),
        ("gh", "api", f"{base}/commits/v0.1.4"): tag_sequence,
        ("gh", "api", f"{base}/releases/tags/v0.1.4"): release_sequence,
        (
            "git",
            "rev-parse",
            "--verify",
            "--quiet",
            "refs/tags/v0.1.4^{commit}",
        ): release.CommandResult(1, "", ""),
        (
            "git",
            "tag",
            "--annotate",
            "v0.1.4",
            commit,
            "--message",
            "v0.1.4",
        ): release.CommandResult(0, "", ""),
        (
            "git",
            "push",
            "--porcelain",
            "origin",
            "refs/tags/v0.1.4:refs/tags/v0.1.4",
        ): release.CommandResult(0, "", ""),
        (
            "gh",
            "release",
            "create",
            "v0.1.4",
            "--repo",
            repository,
            "--title",
            "v0.1.4",
            "--notes-file",
            str(notes),
            "--verify-tag",
            "--target",
            commit,
        ): release_create or release.CommandResult(0, "", ""),
    }
    return responses


def _tag_verified_state(
    root: Path,
    config: release.ReleaseConfig,
    version: str,
    commit: str,
) -> tuple[release.ReleaseStateStore, release.ReleaseState]:
    store, state = _verified_state(root, config, version, commit)
    digest = state.last_result["tree_sha256"]
    state = release.dataclasses.replace(
        state,
        release_commit=commit,
        remote_facts={"verified_tree_sha256": digest},
    )
    for target in ("MERGED", "TAGGED", "RELEASED", "TAG_VERIFIED"):
        state = state.advance(
            target,
            {
                "status": target.lower(),
                "commit": commit,
                "tree_sha256": digest,
                "runtime_validation": "unverified",
            },
        )
    store.save(state)
    return store, state


def _promotion_responses(
    commit: str,
    *,
    stable_sequence: list[str],
    old_stable: str = "a" * 40,
) -> dict[tuple[str, ...], release.CommandResult | list[release.CommandResult]]:
    repository = "owner/repository"
    base = f"repos/{repository}"
    workflow = json.dumps(
        {
            "workflow_runs": [
                {
                    "head_sha": commit,
                    "status": "completed",
                    "conclusion": "success",
                }
            ]
        }
    )
    stable_values = [
        release.CommandResult(0, json.dumps({"sha": value}), "")
        for value in stable_sequence
    ]
    return {
        ("git", "status", "--porcelain=v1", "--untracked-files=all"): release.CommandResult(
            0, "", ""
        ),
        ("git", "rev-parse", "HEAD"): release.CommandResult(0, commit + "\n", ""),
        ("git", "remote", "get-url", "origin"): release.CommandResult(
            0, "git@github.com:owner/repository.git\n", ""
        ),
        ("gh", "auth", "status", "--hostname", "github.com"): release.CommandResult(
            0, "", ""
        ),
        ("gh", "api", base): release.CommandResult(
            0, json.dumps({"permissions": {"push": True}}), ""
        ),
        ("gh", "api", f"{base}/commits/main"): release.CommandResult(
            0, json.dumps({"sha": commit}), ""
        ),
        ("gh", "api", f"{base}/commits/stable"): stable_values,
        ("gh", "api", f"{base}/commits/v0.1.4"): release.CommandResult(
            0, json.dumps({"sha": commit}), ""
        ),
        ("gh", "api", f"{base}/releases/tags/v0.1.4"): release.CommandResult(
            0,
            json.dumps(
                {
                    "tag_name": "v0.1.4",
                    "draft": False,
                    "prerelease": False,
                    "html_url": "https://example.invalid/v0.1.4",
                }
            ),
            "",
        ),
        (
            "gh",
            "api",
            f"{base}/actions/workflows/static-validation.yml/runs?head_sha={commit}&per_page=20",
        ): release.CommandResult(0, workflow, ""),
        ("gh", "api", f"{base}/compare/{old_stable}...{commit}"): release.CommandResult(
            0,
            json.dumps(
                {
                    "status": "ahead",
                    "merge_base_commit": {"sha": old_stable},
                }
            ),
            "",
        ),
        ("gh", "api", f"{base}/compare/{commit}...{commit}"): release.CommandResult(
            0,
            json.dumps(
                {
                    "status": "identical",
                    "merge_base_commit": {"sha": commit},
                }
            ),
            "",
        ),
        (
            "git",
            "push",
            "--porcelain",
            "origin",
            f"{commit}:refs/heads/stable",
        ): release.CommandResult(0, "", ""),
    }


class PromotionFetcher:
    def __init__(self, archive: bytes, manifests: list[bytes]):
        self.archive = archive
        self.manifests = list(manifests)
        self.calls: list[str] = []

    def __call__(self, url: str) -> bytes:
        self.calls.append(url)
        if "/archive/refs/tags/" in url:
            return self.archive
        if not self.manifests:
            raise AssertionError("stable manifest response sequence was exhausted")
        return self.manifests.pop(0) if len(self.manifests) > 1 else self.manifests[0]


def _stable_promoted_state(
    root: Path,
    config: release.ReleaseConfig,
    version: str,
    commit: str,
) -> tuple[release.ReleaseStateStore, release.ReleaseState]:
    store, state = _tag_verified_state(root, config, version, commit)
    state = state.advance(
        "STABLE_PROMOTED",
        {
            "status": "promoted",
            "version": version,
            "commit": commit,
            "tree_sha256": state.remote_facts["verified_tree_sha256"],
            "runtime_validation": "unverified",
        },
    )
    store.save(state)
    return store, state


def _record_isolated_runtime_evidence(
    store: release.ReleaseStateStore,
    state: release.ReleaseState,
) -> release.ReleaseState:
    digest = state.remote_facts["verified_tree_sha256"]
    state = release.dataclasses.replace(
        state,
        remote_facts={
            **dict(state.remote_facts),
            "runtime_lanes": {
                "isolated": {
                    "status": "passed",
                    "version": state.target_version,
                    "tree_sha256": digest,
                }
            },
        },
    )
    store.save(state)
    return state


class RuntimeFetcher:
    def __init__(
        self,
        *,
        previous_archive: bytes | None,
        target_archive: bytes,
        stable_manifest: bytes,
    ):
        self.previous_archive = previous_archive
        self.target_archive = target_archive
        self.stable_manifest = stable_manifest
        self.calls: list[str] = []

    def __call__(self, url: str) -> bytes:
        self.calls.append(url)
        if url.endswith("/v0.1.3.zip"):
            if self.previous_archive is None:
                raise AssertionError("previous archive was not configured")
            return self.previous_archive
        if url.endswith("/v0.1.4.zip"):
            return self.target_archive
        if url.endswith("/stable/skills/vibe-diagram/update.json"):
            return self.stable_manifest
        raise AssertionError(f"unexpected runtime URL: {url}")


class RuntimeRunner(FakeRunner):
    def __init__(self, artifact: Path, *, fail_invocation: bool = False):
        super().__init__()
        self.artifact = artifact
        self.fail_invocation = fail_invocation
        self.codex_calls = 0

    def run(
        self,
        arguments: list[str] | tuple[str, ...],
        *,
        cwd: Path,
        check: bool = True,
        env: dict[str, str] | None = None,
    ) -> release.CommandResult:
        del cwd
        key = tuple(arguments)
        self.calls.append(key)
        if key[:2] == ("codex", "exec"):
            self.codex_calls += 1
            marker = Path(key[key.index("--output-last-message") + 1])
            prompt = key[-1]
            if self.fail_invocation and self.codex_calls == 1:
                return release.CommandResult(1, "", "runtime invocation failed")
            if "VIBE_DIAGRAM_UNAVAILABLE_OK" in prompt:
                marker.write_text("VIBE_DIAGRAM_UNAVAILABLE_OK\n", encoding="utf-8")
            else:
                self.artifact.write_text(
                    "<!doctype html><html><body>runtime artifact</body></html>\n",
                    encoding="utf-8",
                )
                marker.write_text("VIBE_DIAGRAM_RUNTIME_OK\n", encoding="utf-8")
            return release.CommandResult(0, "", "")
        result = self.responses.get(key, release.CommandResult(0, "", ""))
        if check and result.returncode != 0:
            raise release.ReleaseError(result.stderr or "command failed", exit_code=4)
        return result


class ReleaseGithubSkillTests(unittest.TestCase):
    def test_stable_version_is_strict_and_must_increase(self) -> None:
        self.assertEqual((0, 1, 4), release.parse_stable_version("0.1.4"))
        release.require_newer_version("0.1.3", "0.1.4")
        for invalid in ("v0.1.4", "0.1", "01.1.4", "0.1.4-rc.1", "0.1.4+meta"):
            with self.subTest(invalid=invalid), self.assertRaises(release.ReleaseError):
                release.parse_stable_version(invalid)
        for target in ("0.1.2", "0.1.3"):
            with self.subTest(target=target), self.assertRaises(release.ReleaseError):
                release.require_newer_version("0.1.3", target)

    def test_release_state_machine_is_fail_closed(self) -> None:
        self.assertTrue(release.transition_allowed("NEW", "PREPARED"))
        self.assertTrue(release.transition_allowed("PREPARED", "LOCAL_VERIFIED"))
        self.assertFalse(release.transition_allowed("NEW", "LOCAL_VERIFIED"))
        self.assertFalse(release.transition_allowed("LOCAL_VERIFIED", "STABLE_PROMOTED"))
        with self.assertRaises(release.ReleaseError):
            release.require_transition("NEW", "TAGGED")

    def test_config_rejects_unknown_keys_and_unsafe_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = _write_repository(root)
            self.assertEqual("owner/repository", config.repository)
            path = root / "release" / "github-skill.json"
            value = json.loads(path.read_text(encoding="utf-8"))
            value["unknown"] = True
            _write_json(path, value)
            with self.assertRaises(release.ReleaseError):
                release.load_config(root, path)
            value.pop("unknown")
            value["skill_root"] = "../outside"
            _write_json(path, value)
            with self.assertRaises(release.ReleaseError):
                release.load_config(root, path)

    def test_config_commands_are_exact_release_entrypoints(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _write_repository(root)
            path = root / "release" / "github-skill.json"
            value = json.loads(path.read_text(encoding="utf-8"))
            value["publication_command"] = ["python3", "unexpected.py"]
            _write_json(path, value)

            with self.assertRaisesRegex(release.ReleaseError, "publication_command"):
                release.load_config(root, path)

            value["publication_command"] = list(release.EXPECTED_PUBLICATION_COMMAND)
            value["build_command"] = ["python3", "unexpected.py"]
            _write_json(path, value)
            with self.assertRaisesRegex(release.ReleaseError, "build_command"):
                release.load_config(root, path)

    def test_prepare_dry_run_computes_candidate_without_writes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = _write_repository(root)
            before = {
                path.relative_to(root).as_posix(): path.read_bytes()
                for path in root.rglob("*")
                if path.is_file()
            }
            runner = FakeRunner()

            result = release.prepare_release(root, config, "0.1.4", runner, dry_run=True)

            after = {
                path.relative_to(root).as_posix(): path.read_bytes()
                for path in root.rglob("*")
                if path.is_file()
            }
            self.assertEqual(before, after)
            self.assertEqual("planned", result["status"])
            self.assertEqual("0.1.4", result["version"])
            self.assertRegex(result["tree_sha256"], r"^[0-9a-f]{64}$")
            self.assertEqual([], runner.calls)

    def test_prepare_updates_metadata_and_calls_only_publication_builder(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = _write_repository(root)
            runner = FakeRunner()

            result = release.prepare_release(root, config, "0.1.4", runner)

            self.assertEqual("0.1.4\n", (root / "VERSION").read_text(encoding="ascii"))
            skill = root / "skills" / "vibe-diagram"
            self.assertEqual("0.1.4\n", (skill / "VERSION").read_text(encoding="ascii"))
            manifest = json.loads((skill / "update.json").read_text(encoding="utf-8"))
            self.assertEqual("0.1.4", manifest["version"])
            self.assertEqual("v0.1.4", manifest["ref"])
            self.assertEqual(_tree_sha256(skill), manifest["tree_sha256"])
            self.assertEqual([tuple(config.publication_command)], runner.calls)
            self.assertNotIn("build", result["mutations"])
            self.assertEqual("prepared", result["status"])
            self.assertEqual("unverified", result["runtime_validation"])

    def test_prepare_builder_failure_preserves_candidate_and_never_calls_git(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = _write_repository(root)
            command = tuple(config.publication_command)
            runner = FakeRunner(
                {command: release.CommandResult(1, "", "builder rejected candidate")}
            )

            with self.assertRaises(release.ReleaseError):
                release.prepare_release(root, config, "0.1.4", runner)

            self.assertEqual("0.1.4\n", (root / "VERSION").read_text(encoding="ascii"))
            self.assertEqual(
                "0.1.4\n",
                (root / "skills" / "vibe-diagram" / "VERSION").read_text(
                    encoding="ascii"
                ),
            )
            self.assertEqual([command], runner.calls)
            self.assertFalse(any(call and call[0] == "git" for call in runner.calls))

    def test_verify_runs_the_exact_double_suite_and_static_checks(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = _write_repository(root)
            runner = FakeRunner()
            release.prepare_release(root, config, "0.1.4", runner)
            runner.calls.clear()

            result = release.verify_release(
                root,
                config,
                "0.1.4",
                runner,
                current_python="python-current",
            )

            suite39 = ("python3.9", "-m", "unittest", "discover", "-s", "tests", "-v")
            suite_current = (
                "python-current",
                "-m",
                "unittest",
                "discover",
                "-s",
                "tests",
                "-v",
            )
            self.assertEqual({suite39, suite_current}, set(runner.calls[:2]))
            self.assertEqual(
                [
                    tuple(config.check_command),
                    tuple(config.build_command),
                    ("diff", "-qr", "build/codex", "plugins/vibe-diagram"),
                    ("git", "diff", "--check"),
                ],
                runner.calls[2:6],
            )
            self.assertEqual({suite39, suite_current}, set(runner.calls[6:]))
            self.assertEqual("static-valid", result["local_validation"])
            self.assertEqual("unverified", result["runtime_validation"])
            self.assertEqual("passed", result["archive_validation"])

    def test_verify_runs_each_python_round_in_parallel(self) -> None:
        class ParallelProbeRunner(FakeRunner):
            def __init__(self) -> None:
                super().__init__()
                self.barrier = threading.Barrier(2)

            def run(self, arguments, *, cwd, check=True, env=None):
                key = tuple(arguments)
                if key[1:5] == ("-m", "unittest", "discover", "-s"):
                    self.barrier.wait(timeout=1)
                return super().run(
                    arguments,
                    cwd=cwd,
                    check=check,
                    env=env,
                )

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = _write_repository(root)
            release.prepare_release(root, config, "0.1.4", FakeRunner())

            result = release.verify_release(
                root,
                config,
                "0.1.4",
                ParallelProbeRunner(),
                current_python="python-current",
            )

            self.assertEqual("static-valid", result["local_validation"])

    def test_verify_stops_after_a_failed_parallel_round(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = _write_repository(root)
            prepare_runner = FakeRunner()
            release.prepare_release(root, config, "0.1.4", prepare_runner)
            failed = (
                "python3.9",
                "-m",
                "unittest",
                "discover",
                "-s",
                "tests",
                "-v",
            )
            runner = FakeRunner({failed: release.CommandResult(1, "", "tests failed")})

            with self.assertRaises(release.ReleaseError):
                release.verify_release(root, config, "0.1.4", runner)

            self.assertEqual(2, len(runner.calls))
            self.assertIn(failed, runner.calls)
            self.assertTrue(
                all(call[1:] == failed[1:] for call in runner.calls)
            )

    def test_state_store_is_scoped_and_rejects_conflicting_release(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            state_dir = Path(temporary)
            store = release.ReleaseStateStore(state_dir)
            state = release.ReleaseState.new(
                target_version="0.1.4",
                previous_version="0.1.3",
                repository="owner/repository",
                baseline_head="a" * 40,
            )
            store.save(state)
            self.assertEqual(state, store.load("0.1.4"))
            payload = (state_dir / "v0.1.4.json").read_text(encoding="utf-8")
            self.assertNotIn("token", payload.lower())
            with self.assertRaises(release.ReleaseError):
                store.ensure_compatible("0.1.4", "other/repository")

    def test_state_store_rejects_an_impossible_persisted_transition(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            state_dir = Path(temporary)
            store = release.ReleaseStateStore(state_dir)
            state = release.ReleaseState.new(
                target_version="0.1.4",
                previous_version="0.1.3",
                repository="owner/repository",
                baseline_head="a" * 40,
            )
            payload = state.as_dict()
            payload["release_state"] = "STABLE_PROMOTED"
            payload["completed_phases"] = ["STABLE_PROMOTED"]
            _write_json(state_dir / "v0.1.4.json", payload)

            with self.assertRaisesRegex(release.ReleaseError, "transition"):
                store.load("0.1.4")

    def test_remote_facts_require_consistent_main_tag_release_ci_archive_and_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = _write_repository(root)
            release.prepare_release(root, config, "0.1.4", FakeRunner())
            commit = "b" * 40
            stable = "a" * 40
            base = "repos/owner/repository"
            responses = {
                ("gh", "api", f"{base}/commits/main"): release.CommandResult(
                    0, json.dumps({"sha": commit}), ""
                ),
                ("gh", "api", f"{base}/commits/stable"): release.CommandResult(
                    0, json.dumps({"sha": stable}), ""
                ),
                ("gh", "api", f"{base}/commits/v0.1.4"): release.CommandResult(
                    0, json.dumps({"sha": commit}), ""
                ),
                ("gh", "api", f"{base}/releases/tags/v0.1.4"): release.CommandResult(
                    0,
                    json.dumps(
                        {
                            "tag_name": "v0.1.4",
                            "draft": False,
                            "prerelease": False,
                            "html_url": "https://example.invalid/release",
                        }
                    ),
                    "",
                ),
                (
                    "gh",
                    "api",
                    f"{base}/actions/workflows/static-validation.yml/runs?head_sha={commit}&per_page=20",
                ): release.CommandResult(
                    0,
                    json.dumps(
                        {
                            "workflow_runs": [
                                {
                                    "head_sha": commit,
                                    "status": "completed",
                                    "conclusion": "success",
                                }
                            ]
                        }
                    ),
                    "",
                ),
                (
                    "gh",
                    "api",
                    f"{base}/compare/{stable}...{commit}",
                ): release.CommandResult(
                    0,
                    json.dumps({"status": "ahead", "merge_base_commit": {"sha": stable}}),
                    "",
                ),
            }
            runner = FakeRunner(responses)
            skill = root / config.skill_root
            manifest_bytes = (skill / "update.json").read_bytes()
            archive_bytes = _archive_bytes(skill, "0.1.4")
            urls = release.remote_urls(config, "0.1.4")

            def fetch(url: str) -> bytes:
                return {
                    urls["stable_manifest"]: manifest_bytes,
                    urls["tag_archive"]: archive_bytes,
                }[url]

            facts = release.collect_remote_facts(
                root, config, "0.1.4", runner, fetch_bytes=fetch
            )

            self.assertEqual(commit, facts["main_sha"])
            self.assertEqual(commit, facts["tag_sha"])
            self.assertEqual("success", facts["workflow_conclusion"])
            self.assertEqual("passed", facts["archive_validation"])
            self.assertEqual("passed", facts["stable_manifest_validation"])
            self.assertTrue(facts["stable_fast_forward"])
            self.assertTrue(facts["ready_for_promotion"])

    def test_stable_manifest_validation_rejects_invalid_identity_and_digest(self) -> None:
        target_manifest = {
            "schema_version": 1,
            "channel": "stable",
            "version": "0.1.4",
            "ref": "v0.1.4",
            "tree_sha256": "a" * 64,
        }
        self.assertEqual(
            ("passed", "0.1.4"),
            release.validate_stable_manifest(target_manifest, "0.1.4", target_manifest),
        )
        previous = dict(target_manifest, version="0.1.3", ref="v0.1.3")
        self.assertEqual(
            ("previous", "0.1.3"),
            release.validate_stable_manifest(previous, "0.1.4", target_manifest),
        )
        for invalid in (
            dict(target_manifest, channel="candidate"),
            dict(target_manifest, schema_version=2),
            dict(target_manifest, tree_sha256="not-a-digest"),
        ):
            with self.subTest(invalid=invalid), self.assertRaises(release.ReleaseError):
                release.validate_stable_manifest(invalid, "0.1.4", target_manifest)

    def test_remote_missing_release_is_reported_without_claiming_readiness(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = _write_repository(root)
            commit = "b" * 40
            base = "repos/owner/repository"
            runner = FakeRunner(
                {
                    ("gh", "api", f"{base}/commits/main"): release.CommandResult(
                        0, json.dumps({"sha": commit}), ""
                    ),
                    ("gh", "api", f"{base}/commits/stable"): release.CommandResult(
                        1, "", "HTTP 404"
                    ),
                    ("gh", "api", f"{base}/commits/v0.1.4"): release.CommandResult(
                        1, "", "HTTP 404"
                    ),
                    ("gh", "api", f"{base}/releases/tags/v0.1.4"): release.CommandResult(
                        1, "", "HTTP 404"
                    ),
                }
            )

            facts = release.collect_remote_facts(
                root,
                config,
                "0.1.4",
                runner,
                fetch_bytes=lambda _url: self.fail("missing tag must not fetch archives"),
            )

            self.assertEqual("missing", facts["tag_status"])
            self.assertEqual("missing", facts["release_status"])
            self.assertFalse(facts["ready_for_promotion"])

    def test_status_refresh_preserves_local_verified_candidate_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = _write_repository(root)
            commit = "b" * 40
            store, state = _verified_state(root, config, "0.1.4", commit)
            digest = state.last_result["tree_sha256"]
            base = "repos/owner/repository"
            runner = FakeRunner(
                {
                    ("gh", "api", f"{base}/commits/main"): release.CommandResult(
                        0, json.dumps({"sha": commit}), ""
                    ),
                    ("gh", "api", f"{base}/commits/stable"): release.CommandResult(
                        1, "", "HTTP 404"
                    ),
                    ("gh", "api", f"{base}/commits/v0.1.4"): release.CommandResult(
                        1, "", "HTTP 404"
                    ),
                    ("gh", "api", f"{base}/releases/tags/v0.1.4"): release.CommandResult(
                        1, "", "HTTP 404"
                    ),
                }
            )
            arguments = release.parse_args(
                [
                    "status",
                    "--version",
                    "0.1.4",
                    "--root",
                    str(root),
                    "--state-dir",
                    str(root / "state"),
                    "--refresh",
                    "--json",
                ]
            )

            release.execute(arguments, root=root, runner=runner)

            refreshed = store.load("0.1.4")
            self.assertEqual(digest, refreshed.last_result["tree_sha256"])
            self.assertEqual("LOCAL_VERIFIED", refreshed.release_state)

    def test_publish_requires_literal_confirmation_before_runner_calls(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _write_repository(root)
            notes = root / "notes.md"
            notes.write_text("Release notes\n", encoding="utf-8")
            arguments = release.parse_args(
                [
                    "publish",
                    "--version",
                    "0.1.4",
                    "--commit",
                    "b" * 40,
                    "--notes-file",
                    str(notes),
                    "--root",
                    str(root),
                    "--state-dir",
                    str(root / "state"),
                    "--json",
                ]
            )
            runner = FakeRunner()

            with self.assertRaisesRegex(release.ReleaseError, "confirm-remote-actions"):
                release.execute(arguments, root=root, runner=runner)

            self.assertEqual([], runner.calls)

    def test_publish_creates_annotated_tag_release_and_verifies_remote_archive(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = _write_repository(root)
            commit = "b" * 40
            notes = root / "release-notes.md"
            notes.write_text("Release notes\n", encoding="utf-8")
            store, state = _verified_state(root, config, "0.1.4", commit)
            missing = release.CommandResult(1, "", "HTTP 404")
            available_tag = release.CommandResult(
                0, json.dumps({"sha": commit}), ""
            )
            available_release = release.CommandResult(
                0,
                json.dumps(
                    {
                        "tag_name": "v0.1.4",
                        "draft": False,
                        "prerelease": False,
                        "html_url": "https://example.invalid/v0.1.4",
                    }
                ),
                "",
            )
            runner = ScriptedRunner(
                _publish_responses(
                    notes,
                    commit,
                    tag_sequence=[missing, available_tag, available_tag],
                    release_sequence=[missing, available_release],
                )
            )

            result = release.publish_release(
                root,
                config,
                "0.1.4",
                commit,
                notes,
                state,
                store,
                runner,
                fetch_bytes=lambda _url: _archive_bytes(
                    root / config.skill_root, "0.1.4"
                ),
            )

            self.assertEqual("published", result["status"])
            self.assertEqual("TAG_VERIFIED", result["release_state"])
            self.assertEqual("passed", result["archive_validation"])
            self.assertEqual(commit, store.load("0.1.4").release_commit)
            self.assertIn(
                (
                    "git",
                    "tag",
                    "--annotate",
                    "v0.1.4",
                    commit,
                    "--message",
                    "v0.1.4",
                ),
                runner.calls,
            )
            self.assertIn(
                (
                    "git",
                    "push",
                    "--porcelain",
                    "origin",
                    "refs/tags/v0.1.4:refs/tags/v0.1.4",
                ),
                runner.calls,
            )
            self.assertFalse(any("--force" in call for call in runner.calls))
            forbidden_prefixes = {
                ("git", "commit"),
                ("git", "merge"),
                ("git", "remote", "set-url"),
                ("git", "tag", "--delete"),
                ("git", "push", "--delete"),
            }
            self.assertFalse(
                any(
                    call[: len(prefix)] == prefix
                    for call in runner.calls
                    for prefix in forbidden_prefixes
                )
            )

    def test_publish_cli_dispatches_confirmed_release_and_returns_json_envelope(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = _write_repository(root)
            commit = "b" * 40
            notes = root / "release-notes.md"
            notes.write_text("Release notes\n", encoding="utf-8")
            _verified_state(root, config, "0.1.4", commit)
            missing = release.CommandResult(1, "", "HTTP 404")
            tag = release.CommandResult(0, json.dumps({"sha": commit}), "")
            available_release = release.CommandResult(
                0,
                json.dumps(
                    {
                        "tag_name": "v0.1.4",
                        "draft": False,
                        "prerelease": False,
                    }
                ),
                "",
            )
            runner = ScriptedRunner(
                _publish_responses(
                    notes,
                    commit,
                    tag_sequence=[missing, tag, tag],
                    release_sequence=[missing, available_release],
                )
            )
            arguments = release.parse_args(
                [
                    "publish",
                    "--version",
                    "0.1.4",
                    "--commit",
                    commit,
                    "--notes-file",
                    str(notes),
                    "--confirm-remote-actions",
                    "--root",
                    str(root),
                    "--state-dir",
                    str(root / "state"),
                    "--json",
                ]
            )

            result = release.execute(
                arguments,
                root=root,
                runner=runner,
                fetch_bytes=lambda _url: _archive_bytes(
                    root / config.skill_root, "0.1.4"
                ),
            )

            self.assertEqual(1, result["schema_version"])
            self.assertEqual("publish", result["command"])
            self.assertEqual("owner/repository", result["repository"])
            self.assertEqual("TAG_VERIFIED", result["release_state"])

    def test_publish_existing_same_commit_tag_and_release_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = _write_repository(root)
            commit = "b" * 40
            notes = root / "release-notes.md"
            notes.write_text("Release notes\n", encoding="utf-8")
            store, state = _verified_state(root, config, "0.1.4", commit)
            tag = release.CommandResult(0, json.dumps({"sha": commit}), "")
            release_value = release.CommandResult(
                0,
                json.dumps(
                    {
                        "tag_name": "v0.1.4",
                        "draft": False,
                        "prerelease": False,
                    }
                ),
                "",
            )
            runner = ScriptedRunner(
                _publish_responses(
                    notes,
                    commit,
                    tag_sequence=[tag, tag],
                    release_sequence=[release_value, release_value],
                )
            )

            result = release.publish_release(
                root,
                config,
                "0.1.4",
                commit,
                notes,
                state,
                store,
                runner,
                fetch_bytes=lambda _url: _archive_bytes(
                    root / config.skill_root, "0.1.4"
                ),
            )

            self.assertEqual("TAG_VERIFIED", result["release_state"])
            self.assertFalse(any(call[:2] == ("git", "tag") for call in runner.calls))
            self.assertFalse(any(call[:2] == ("git", "push") for call in runner.calls))
            self.assertFalse(any(call[:3] == ("gh", "release", "create") for call in runner.calls))

    def test_publish_conflicting_remote_tag_fails_before_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = _write_repository(root)
            commit = "b" * 40
            notes = root / "release-notes.md"
            notes.write_text("Release notes\n", encoding="utf-8")
            store, state = _verified_state(root, config, "0.1.4", commit)
            conflicting = release.CommandResult(
                0, json.dumps({"sha": "c" * 40}), ""
            )
            runner = ScriptedRunner(
                _publish_responses(
                    notes,
                    commit,
                    tag_sequence=[conflicting],
                    release_sequence=[release.CommandResult(1, "", "HTTP 404")],
                )
            )

            with self.assertRaisesRegex(release.ReleaseError, "different commit"):
                release.publish_release(
                    root,
                    config,
                    "0.1.4",
                    commit,
                    notes,
                    state,
                    store,
                    runner,
                )

            self.assertFalse(any(call[:2] == ("git", "tag") for call in runner.calls))
            self.assertFalse(any(call[:2] == ("git", "push") for call in runner.calls))

    def test_publish_release_failure_records_partial_remote_and_can_resume(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = _write_repository(root)
            commit = "b" * 40
            notes = root / "release-notes.md"
            notes.write_text("Release notes\n", encoding="utf-8")
            store, state = _verified_state(root, config, "0.1.4", commit)
            missing = release.CommandResult(1, "", "HTTP 404")
            tag = release.CommandResult(0, json.dumps({"sha": commit}), "")
            runner = ScriptedRunner(
                _publish_responses(
                    notes,
                    commit,
                    tag_sequence=[missing, tag],
                    release_sequence=[missing],
                    release_create=release.CommandResult(1, "", "release rejected"),
                )
            )

            with self.assertRaisesRegex(release.ReleaseError, "release rejected"):
                release.publish_release(
                    root,
                    config,
                    "0.1.4",
                    commit,
                    notes,
                    state,
                    store,
                    runner,
                )

            partial = store.load("0.1.4")
            self.assertEqual("PARTIAL_REMOTE", partial.release_state)
            self.assertEqual(commit, partial.release_commit)
            self.assertIn("TAGGED", partial.completed_phases)
            state_payload = (root / "state" / "v0.1.4.json").read_text(
                encoding="utf-8"
            )
            self.assertNotIn("release rejected", state_payload)
            self.assertNotIn(str(notes), state_payload)

            available_release = release.CommandResult(
                0,
                json.dumps(
                    {
                        "tag_name": "v0.1.4",
                        "draft": False,
                        "prerelease": False,
                    }
                ),
                "",
            )
            resume = ScriptedRunner(
                _publish_responses(
                    notes,
                    commit,
                    tag_sequence=[tag, tag],
                    release_sequence=[missing, available_release],
                )
            )

            result = release.publish_release(
                root,
                config,
                "0.1.4",
                commit,
                notes,
                partial,
                store,
                resume,
                fetch_bytes=lambda _url: _archive_bytes(
                    root / config.skill_root, "0.1.4"
                ),
            )

            self.assertEqual("TAG_VERIFIED", result["release_state"])
            self.assertFalse(any(call[:2] == ("git", "tag") for call in resume.calls))
            self.assertFalse(any(call[:2] == ("git", "push") for call in resume.calls))

    def test_publish_tag_workflow_timeout_records_partial_remote(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = _write_repository(root)
            commit = "b" * 40
            notes = root / "release-notes.md"
            notes.write_text("Release notes\n", encoding="utf-8")
            store, state = _verified_state(root, config, "0.1.4", commit)
            missing = release.CommandResult(1, "", "HTTP 404")
            tag = release.CommandResult(0, json.dumps({"sha": commit}), "")
            available_release = release.CommandResult(
                0,
                json.dumps(
                    {
                        "tag_name": "v0.1.4",
                        "draft": False,
                        "prerelease": False,
                    }
                ),
                "",
            )
            responses = _publish_responses(
                notes,
                commit,
                tag_sequence=[missing, tag, tag],
                release_sequence=[missing, available_release],
            )
            workflow_key = (
                "gh",
                "api",
                "repos/owner/repository/actions/workflows/"
                f"static-validation.yml/runs?head_sha={commit}&per_page=20",
            )
            responses[workflow_key] = [
                release.CommandResult(
                    0,
                    json.dumps(
                        {
                            "workflow_runs": [
                                {
                                    "head_sha": commit,
                                    "status": "completed",
                                    "conclusion": "success",
                                }
                            ]
                        }
                    ),
                    "",
                ),
                release.CommandResult(
                    0,
                    json.dumps(
                        {
                            "workflow_runs": [
                                {
                                    "head_sha": commit,
                                    "status": "in_progress",
                                    "conclusion": None,
                                }
                            ]
                        }
                    ),
                    "",
                ),
            ]
            runner = ScriptedRunner(responses)
            sleeps: list[float] = []

            with self.assertRaisesRegex(release.ReleaseError, "bounded timeout"):
                release.publish_release(
                    root,
                    config,
                    "0.1.4",
                    commit,
                    notes,
                    state,
                    store,
                    runner,
                    workflow_attempts=2,
                    sleep_fn=sleeps.append,
                )

            self.assertEqual([release.WORKFLOW_POLL_SECONDS], sleeps)
            self.assertEqual("PARTIAL_REMOTE", store.load("0.1.4").release_state)

    def test_publish_dirty_worktree_fails_before_remote_write_commands(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = _write_repository(root)
            commit = "b" * 40
            notes = root / "release-notes.md"
            notes.write_text("Release notes\n", encoding="utf-8")
            store, state = _verified_state(root, config, "0.1.4", commit)
            runner = FakeRunner(
                {
                    (
                        "git",
                        "status",
                        "--porcelain=v1",
                        "--untracked-files=all",
                    ): release.CommandResult(0, " M VERSION\n", "")
                }
            )

            with self.assertRaisesRegex(release.ReleaseError, "clean worktree"):
                release.publish_release(
                    root,
                    config,
                    "0.1.4",
                    commit,
                    notes,
                    state,
                    store,
                    runner,
                )

            self.assertEqual(
                [("git", "status", "--porcelain=v1", "--untracked-files=all")],
                runner.calls,
            )

    def test_publish_rejects_credentials_in_release_notes_without_runner_calls(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = _write_repository(root)
            commit = "b" * 40
            notes = root / "release-notes.md"
            notes.write_text("github_pat_" + "a" * 40 + "\n", encoding="utf-8")
            store, state = _verified_state(root, config, "0.1.4", commit)
            runner = FakeRunner()

            with self.assertRaisesRegex(release.ReleaseError, "credential"):
                release.publish_release(
                    root,
                    config,
                    "0.1.4",
                    commit,
                    notes,
                    state,
                    store,
                    runner,
                )

            self.assertEqual([], runner.calls)

    def test_promote_stable_requires_literal_confirmation_before_runner_calls(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _write_repository(root)
            runner = FakeRunner()
            arguments = release.parse_args(
                ["promote-stable", "--version", "0.1.4", "--root", str(root)]
            )

            with self.assertRaisesRegex(
                release.ReleaseError, "--confirm-stable-promotion"
            ):
                release.execute(arguments, root=root, runner=runner)

            self.assertEqual([], runner.calls)

    def test_promote_stable_fast_forwards_and_waits_for_raw_consistency(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = _write_repository(root)
            commit = "b" * 40
            store, state = _tag_verified_state(root, config, "0.1.4", commit)
            previous_manifest = json.dumps(
                {
                    "schema_version": 1,
                    "channel": "stable",
                    "version": "0.1.3",
                    "ref": "v0.1.3",
                    "tree_sha256": "a" * 64,
                }
            ).encode("utf-8")
            target_manifest = (root / config.update_manifest).read_bytes()
            fetcher = PromotionFetcher(
                _archive_bytes(root / config.skill_root, "0.1.4"),
                [previous_manifest, previous_manifest, target_manifest],
            )
            runner = ScriptedRunner(
                _promotion_responses(commit, stable_sequence=["a" * 40, commit, commit])
            )
            sleeps: list[float] = []

            result = release.promote_stable(
                root,
                config,
                "0.1.4",
                state,
                store,
                runner,
                fetch_bytes=fetcher,
                consistency_attempts=3,
                sleep_fn=sleeps.append,
            )

            push = (
                "git",
                "push",
                "--porcelain",
                "origin",
                f"{commit}:refs/heads/stable",
            )
            self.assertEqual(1, runner.calls.count(push))
            self.assertEqual([release.STABLE_CONSISTENCY_BASE_SECONDS], sleeps)
            self.assertEqual("promoted", result["status"])
            self.assertEqual("STABLE_PROMOTED", result["release_state"])
            self.assertEqual("unverified", result["runtime_validation"])
            promoted = store.load("0.1.4")
            self.assertEqual("STABLE_PROMOTED", promoted.release_state)
            self.assertEqual(commit, promoted.remote_facts["stable_sha"])
            self.assertEqual("passed", promoted.remote_facts["stable_manifest_validation"])
            self.assertFalse(
                any("--force" in argument for call in runner.calls for argument in call)
            )

    def test_promote_stable_rejects_non_fast_forward_before_push(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = _write_repository(root)
            commit = "b" * 40
            old_stable = "a" * 40
            store, state = _tag_verified_state(root, config, "0.1.4", commit)
            responses = _promotion_responses(
                commit, stable_sequence=[old_stable], old_stable=old_stable
            )
            responses[
                (
                    "gh",
                    "api",
                    f"repos/owner/repository/compare/{old_stable}...{commit}",
                )
            ] = release.CommandResult(
                0,
                json.dumps(
                    {
                        "status": "diverged",
                        "merge_base_commit": {"sha": "c" * 40},
                    }
                ),
                "",
            )
            runner = ScriptedRunner(responses)
            previous_manifest = json.dumps(
                {
                    "schema_version": 1,
                    "channel": "stable",
                    "version": "0.1.3",
                    "ref": "v0.1.3",
                    "tree_sha256": "a" * 64,
                }
            ).encode("utf-8")
            fetcher = PromotionFetcher(
                _archive_bytes(root / config.skill_root, "0.1.4"),
                [previous_manifest],
            )

            with self.assertRaisesRegex(release.ReleaseError, "fast-forward"):
                release.promote_stable(
                    root,
                    config,
                    "0.1.4",
                    state,
                    store,
                    runner,
                    fetch_bytes=fetcher,
                )

            self.assertFalse(any(call[:2] == ("git", "push") for call in runner.calls))
            self.assertEqual("TAG_VERIFIED", store.load("0.1.4").release_state)

    def test_promote_stable_revalidates_tag_main_release_ci_and_archive(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = _write_repository(root)
            commit = "b" * 40
            store, state = _tag_verified_state(root, config, "0.1.4", commit)
            responses = _promotion_responses(commit, stable_sequence=["a" * 40])
            responses[("gh", "api", "repos/owner/repository/commits/v0.1.4")] = (
                release.CommandResult(0, json.dumps({"sha": "c" * 40}), "")
            )
            responses[
                (
                    "gh",
                    "api",
                    f"repos/owner/repository/compare/{'a' * 40}...{'c' * 40}",
                )
            ] = release.CommandResult(
                0,
                json.dumps(
                    {
                        "status": "ahead",
                        "merge_base_commit": {"sha": "a" * 40},
                    }
                ),
                "",
            )
            responses[
                (
                    "gh",
                    "api",
                    "repos/owner/repository/actions/workflows/"
                    f"static-validation.yml/runs?head_sha={'c' * 40}&per_page=20",
                )
            ] = release.CommandResult(
                0,
                json.dumps(
                    {
                        "workflow_runs": [
                            {
                                "head_sha": "c" * 40,
                                "status": "completed",
                                "conclusion": "success",
                            }
                        ]
                    }
                ),
                "",
            )
            runner = ScriptedRunner(responses)
            previous_manifest = json.dumps(
                {
                    "schema_version": 1,
                    "channel": "stable",
                    "version": "0.1.3",
                    "ref": "v0.1.3",
                    "tree_sha256": "a" * 64,
                }
            ).encode("utf-8")
            fetcher = PromotionFetcher(
                _archive_bytes(root / config.skill_root, "0.1.4"),
                [previous_manifest],
            )

            with self.assertRaisesRegex(release.ReleaseError, "release commit"):
                release.promote_stable(
                    root,
                    config,
                    "0.1.4",
                    state,
                    store,
                    runner,
                    fetch_bytes=fetcher,
                )

            self.assertFalse(any(call[:2] == ("git", "push") for call in runner.calls))

    def test_promote_stable_is_idempotent_when_stable_already_matches(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = _write_repository(root)
            commit = "b" * 40
            store, state = _tag_verified_state(root, config, "0.1.4", commit)
            runner = ScriptedRunner(
                _promotion_responses(commit, stable_sequence=[commit, commit])
            )
            target_manifest = (root / config.update_manifest).read_bytes()
            fetcher = PromotionFetcher(
                _archive_bytes(root / config.skill_root, "0.1.4"),
                [target_manifest, target_manifest],
            )

            result = release.promote_stable(
                root,
                config,
                "0.1.4",
                state,
                store,
                runner,
                fetch_bytes=fetcher,
            )

            self.assertEqual("promoted", result["status"])
            self.assertFalse(any(call[:2] == ("git", "push") for call in runner.calls))
            self.assertEqual("STABLE_PROMOTED", store.load("0.1.4").release_state)

    def test_promote_stable_timeout_keeps_promoted_state_without_rollback(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = _write_repository(root)
            commit = "b" * 40
            store, state = _tag_verified_state(root, config, "0.1.4", commit)
            previous_manifest = json.dumps(
                {
                    "schema_version": 1,
                    "channel": "stable",
                    "version": "0.1.3",
                    "ref": "v0.1.3",
                    "tree_sha256": "a" * 64,
                }
            ).encode("utf-8")
            fetcher = PromotionFetcher(
                _archive_bytes(root / config.skill_root, "0.1.4"),
                [previous_manifest, previous_manifest, previous_manifest],
            )
            runner = ScriptedRunner(
                _promotion_responses(commit, stable_sequence=["a" * 40, commit, commit])
            )
            sleeps: list[float] = []

            with self.assertRaisesRegex(release.ReleaseError, "consistency.*timeout"):
                release.promote_stable(
                    root,
                    config,
                    "0.1.4",
                    state,
                    store,
                    runner,
                    fetch_bytes=fetcher,
                    consistency_attempts=2,
                    sleep_fn=sleeps.append,
                )

            promoted = store.load("0.1.4")
            self.assertEqual("STABLE_PROMOTED", promoted.release_state)
            self.assertEqual("stable-consistency-pending", promoted.last_result["status"])
            self.assertEqual([release.STABLE_CONSISTENCY_BASE_SECONDS], sleeps)
            forbidden = {"--force", "--force-with-lease", "--delete"}
            self.assertFalse(
                any(argument in forbidden for call in runner.calls for argument in call)
            )

    def test_promote_stable_push_rejection_refreshes_facts_without_advancing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = _write_repository(root)
            commit = "b" * 40
            old_stable = "a" * 40
            store, state = _tag_verified_state(root, config, "0.1.4", commit)
            responses = _promotion_responses(
                commit,
                stable_sequence=[old_stable, old_stable],
                old_stable=old_stable,
            )
            push = (
                "git",
                "push",
                "--porcelain",
                "origin",
                f"{commit}:refs/heads/stable",
            )
            responses[push] = release.CommandResult(1, "", "non-fast-forward")
            runner = ScriptedRunner(responses)
            previous_manifest = json.dumps(
                {
                    "schema_version": 1,
                    "channel": "stable",
                    "version": "0.1.3",
                    "ref": "v0.1.3",
                    "tree_sha256": "a" * 64,
                }
            ).encode("utf-8")
            fetcher = PromotionFetcher(
                _archive_bytes(root / config.skill_root, "0.1.4"),
                [previous_manifest, previous_manifest],
            )

            with self.assertRaisesRegex(release.ReleaseError, "facts were refreshed"):
                release.promote_stable(
                    root,
                    config,
                    "0.1.4",
                    state,
                    store,
                    runner,
                    fetch_bytes=fetcher,
                )

            observed = store.load("0.1.4")
            self.assertEqual("TAG_VERIFIED", observed.release_state)
            self.assertEqual("stable-push-rejected", observed.last_result["status"])
            stable_read = ("gh", "api", "repos/owner/repository/commits/stable")
            self.assertEqual(2, runner.calls.count(stable_read))
            self.assertEqual(1, runner.calls.count(push))

    def test_promote_stable_cli_dispatches_confirmed_promotion(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = _write_repository(root)
            commit = "b" * 40
            _tag_verified_state(root, config, "0.1.4", commit)
            runner = ScriptedRunner(
                _promotion_responses(commit, stable_sequence=[commit, commit])
            )
            target_manifest = (root / config.update_manifest).read_bytes()
            fetcher = PromotionFetcher(
                _archive_bytes(root / config.skill_root, "0.1.4"),
                [target_manifest, target_manifest],
            )
            arguments = release.parse_args(
                [
                    "promote-stable",
                    "--version",
                    "0.1.4",
                    "--confirm-stable-promotion",
                    "--root",
                    str(root),
                    "--state-dir",
                    str(root / "state"),
                    "--json",
                ]
            )

            result = release.execute(
                arguments,
                root=root,
                runner=runner,
                fetch_bytes=fetcher,
            )

            self.assertEqual(1, result["schema_version"])
            self.assertEqual("promote-stable", result["command"])
            self.assertEqual("owner/repository", result["repository"])
            self.assertEqual("STABLE_PROMOTED", result["release_state"])

    def test_verify_runtime_isolated_covers_update_rollback_reupdate_and_removal(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = _write_repository(root)
            previous_archive = _archive_bytes(root / config.skill_root, "0.1.3")
            store, state = _stable_promoted_state(root, config, "0.1.4", "b" * 40)
            target_archive = _archive_bytes(root / config.skill_root, "0.1.4")
            stable_manifest = (root / config.update_manifest).read_bytes()
            fetcher = RuntimeFetcher(
                previous_archive=previous_archive,
                target_archive=target_archive,
                stable_manifest=stable_manifest,
            )

            result = release.verify_runtime_isolated(
                root,
                config,
                "0.1.4",
                state,
                store,
                fetch_bytes=fetcher,
            )

            self.assertEqual("runtime-isolated-passed", result["status"])
            self.assertEqual("isolated", result["mode"])
            self.assertEqual("passed", result["isolated_validation"])
            self.assertEqual("unverified", result["runtime_validation"])
            self.assertEqual(
                {
                    "upgrade": "passed",
                    "current": "passed",
                    "offline": "passed",
                    "rollback": "passed",
                    "reupgrade": "passed",
                    "fresh_install": "passed",
                    "removal": "passed",
                },
                result["lifecycle"],
            )
            observed = store.load("0.1.4")
            self.assertEqual("STABLE_PROMOTED", observed.release_state)
            self.assertEqual(
                "passed", observed.remote_facts["runtime_lanes"]["isolated"]["status"]
            )
            state_payload = (root / "state" / "v0.1.4.json").read_text(
                encoding="utf-8"
            )
            self.assertNotIn(temporary, state_payload)

    def test_verify_runtime_isolated_cli_dispatches_without_client_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = _write_repository(root)
            previous_archive = _archive_bytes(root / config.skill_root, "0.1.3")
            _stable_promoted_state(root, config, "0.1.4", "b" * 40)
            fetcher = RuntimeFetcher(
                previous_archive=previous_archive,
                target_archive=_archive_bytes(root / config.skill_root, "0.1.4"),
                stable_manifest=(root / config.update_manifest).read_bytes(),
            )
            runner = FakeRunner()
            arguments = release.parse_args(
                [
                    "verify-runtime",
                    "--version",
                    "0.1.4",
                    "--mode",
                    "isolated",
                    "--root",
                    str(root),
                    "--state-dir",
                    str(root / "state"),
                    "--json",
                ]
            )

            result = release.execute(
                arguments,
                root=root,
                runner=runner,
                fetch_bytes=fetcher,
            )

            self.assertEqual("verify-runtime", result["command"])
            self.assertEqual("runtime-isolated-passed", result["status"])
            self.assertEqual([], runner.calls)

    def test_verify_runtime_installed_requires_confirmation_before_runner_calls(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _write_repository(root)
            artifact = root / "runtime-smoke.html"
            runner = FakeRunner()
            arguments = release.parse_args(
                [
                    "verify-runtime",
                    "--version",
                    "0.1.4",
                    "--mode",
                    "installed-client",
                    "--artifact",
                    str(artifact),
                    "--root",
                    str(root),
                ]
            )

            with self.assertRaisesRegex(
                release.ReleaseError, "--confirm-installed-skill-mutation"
            ):
                release.execute(arguments, root=root, runner=runner)

            self.assertEqual([], runner.calls)
            self.assertFalse(artifact.exists())

    def test_verify_runtime_installed_requires_isolated_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = _write_repository(root)
            codex_home = root / "codex-home"
            installed = codex_home / "skills" / "vibe-diagram"
            installed.parent.mkdir(parents=True)
            shutil.copytree(root / config.skill_root, installed)
            store, state = _stable_promoted_state(root, config, "0.1.4", "b" * 40)
            artifact = root / "runtime-smoke.html"
            runner = RuntimeRunner(artifact)

            with self.assertRaisesRegex(release.ReleaseError, "isolated.*evidence"):
                release.verify_runtime_installed(
                    root,
                    config,
                    "0.1.4",
                    artifact,
                    state,
                    store,
                    runner,
                    codex_home=codex_home,
                    fetch_bytes=lambda _url: b"",
                )

            self.assertEqual([], runner.calls)
            self.assertFalse(artifact.exists())

    def test_verify_runtime_installed_invokes_codex_lints_and_restores_target(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = _write_repository(root)
            codex_home = root / "codex-home"
            installed = codex_home / "skills" / "vibe-diagram"
            installed.parent.mkdir(parents=True)
            shutil.copytree(root / config.skill_root, installed)
            store, state = _stable_promoted_state(root, config, "0.1.4", "b" * 40)
            state = _record_isolated_runtime_evidence(store, state)
            target_archive = _archive_bytes(root / config.skill_root, "0.1.4")
            fetcher = RuntimeFetcher(
                previous_archive=None,
                target_archive=target_archive,
                stable_manifest=(root / config.update_manifest).read_bytes(),
            )
            artifact = root / "runtime-smoke.html"
            runner = RuntimeRunner(artifact)

            result = release.verify_runtime_installed(
                root,
                config,
                "0.1.4",
                artifact,
                state,
                store,
                runner,
                codex_home=codex_home,
                fetch_bytes=fetcher,
            )

            self.assertEqual("runtime-verified", result["status"])
            self.assertEqual("installed-client", result["mode"])
            self.assertEqual("github-path-codex-cli", result["runtime_lane"])
            self.assertEqual("runtime-verified", result["runtime_validation"])
            self.assertRegex(result["artifact_sha256"], r"^[0-9a-f]{64}$")
            self.assertEqual("0.1.4", (installed / "VERSION").read_text().strip())
            self.assertTrue(artifact.is_file())
            self.assertEqual(2, runner.codex_calls)
            codex_calls = [call for call in runner.calls if call[:2] == ("codex", "exec")]
            self.assertTrue(all("--ephemeral" in call for call in codex_calls))
            self.assertTrue(all("workspace-write" in call for call in codex_calls))
            self.assertTrue(all("never" in call for call in codex_calls))
            self.assertFalse(any("danger-full-access" in call for call in codex_calls))
            self.assertTrue(
                any(
                    call[0] == release.sys.executable
                    and str(installed / "scripts" / "vibe_diagram_lint.py") in call
                    for call in runner.calls
                )
            )
            observed = store.load("0.1.4")
            self.assertEqual("RUNTIME_VERIFIED", observed.release_state)
            state_payload = (root / "state" / "v0.1.4.json").read_text(
                encoding="utf-8"
            )
            self.assertNotIn(str(codex_home), state_payload)
            self.assertNotIn(str(artifact), state_payload)

    def test_verify_runtime_installed_failure_rolls_back_and_records_terminal_state(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = _write_repository(root)
            codex_home = root / "codex-home"
            installed = codex_home / "skills" / "vibe-diagram"
            installed.parent.mkdir(parents=True)
            shutil.copytree(root / config.skill_root, installed)
            store, state = _stable_promoted_state(root, config, "0.1.4", "b" * 40)
            state = _record_isolated_runtime_evidence(store, state)
            fetcher = RuntimeFetcher(
                previous_archive=None,
                target_archive=_archive_bytes(root / config.skill_root, "0.1.4"),
                stable_manifest=(root / config.update_manifest).read_bytes(),
            )
            artifact = root / "runtime-smoke.html"
            runner = RuntimeRunner(artifact, fail_invocation=True)

            with self.assertRaisesRegex(release.ReleaseError, "Codex CLI invocation"):
                release.verify_runtime_installed(
                    root,
                    config,
                    "0.1.4",
                    artifact,
                    state,
                    store,
                    runner,
                    codex_home=codex_home,
                    fetch_bytes=fetcher,
                )

            self.assertEqual("0.1.3", (installed / "VERSION").read_text().strip())
            observed = store.load("0.1.4")
            self.assertEqual("PROMOTED_RUNTIME_FAILED", observed.release_state)
            self.assertEqual("runtime-failed", observed.last_result["status"])
            self.assertEqual("passed", observed.last_result["rollback_validation"])
            self.assertFalse(artifact.exists())

    def test_verify_runtime_installed_cli_dispatches_confirmed_lifecycle(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = _write_repository(root)
            codex_home = root / "codex-home"
            installed = codex_home / "skills" / "vibe-diagram"
            installed.parent.mkdir(parents=True)
            shutil.copytree(root / config.skill_root, installed)
            store, state = _stable_promoted_state(root, config, "0.1.4", "b" * 40)
            _record_isolated_runtime_evidence(store, state)
            fetcher = RuntimeFetcher(
                previous_archive=None,
                target_archive=_archive_bytes(root / config.skill_root, "0.1.4"),
                stable_manifest=(root / config.update_manifest).read_bytes(),
            )
            artifact = root / "runtime-smoke.html"
            runner = RuntimeRunner(artifact)
            arguments = release.parse_args(
                [
                    "verify-runtime",
                    "--version",
                    "0.1.4",
                    "--mode",
                    "installed-client",
                    "--artifact",
                    str(artifact),
                    "--confirm-installed-skill-mutation",
                    "--root",
                    str(root),
                    "--state-dir",
                    str(root / "state"),
                    "--json",
                ]
            )

            with mock.patch.dict(
                release.os.environ, {"CODEX_HOME": str(codex_home)}
            ):
                result = release.execute(
                    arguments,
                    root=root,
                    runner=runner,
                    fetch_bytes=fetcher,
                )

            self.assertEqual("verify-runtime", result["command"])
            self.assertEqual("runtime-verified", result["status"])
            self.assertEqual("RUNTIME_VERIFIED", result["release_state"])
            self.assertEqual("owner/repository", result["repository"])

    def test_verify_runtime_installed_rejects_existing_artifact_before_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = _write_repository(root)
            codex_home = root / "codex-home"
            installed = codex_home / "skills" / "vibe-diagram"
            installed.parent.mkdir(parents=True)
            shutil.copytree(root / config.skill_root, installed)
            store, state = _stable_promoted_state(root, config, "0.1.4", "b" * 40)
            state = _record_isolated_runtime_evidence(store, state)
            artifact = root / "runtime-smoke.html"
            artifact.write_text("user data\n", encoding="utf-8")
            runner = RuntimeRunner(artifact)

            with self.assertRaisesRegex(release.ReleaseError, "must not already exist"):
                release.verify_runtime_installed(
                    root,
                    config,
                    "0.1.4",
                    artifact,
                    state,
                    store,
                    runner,
                    codex_home=codex_home,
                    fetch_bytes=lambda _url: b"",
                )

            self.assertEqual([], runner.calls)
            self.assertEqual("user data\n", artifact.read_text(encoding="utf-8"))
            self.assertEqual("0.1.3", (installed / "VERSION").read_text().strip())

    def test_prepare_cli_dry_run_does_not_create_release_state(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "repository"
            root.mkdir()
            _write_repository(root)
            state_dir = root / "state"
            arguments = release.parse_args(
                [
                    "prepare",
                    "--version",
                    "0.1.4",
                    "--root",
                    str(root),
                    "--state-dir",
                    str(state_dir),
                    "--dry-run",
                    "--json",
                ]
            )

            result = release.execute(arguments, root=root, runner=FakeRunner())

            self.assertEqual("planned", result["status"])
            self.assertEqual(1, result["schema_version"])
            self.assertEqual("prepare", result["command"])
            self.assertEqual("owner/repository", result["repository"])
            self.assertFalse(state_dir.exists())

    def test_parser_rejects_abbreviated_options(self) -> None:
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
            release.parse_args(["prepare", "--vers", "0.1.4"])
        self.assertEqual(2, raised.exception.code)


if __name__ == "__main__":
    unittest.main()
