from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType


ROOT = Path(__file__).resolve().parents[1]


def load_release_module() -> ModuleType:
    path = ROOT / "scripts" / "release_github_skill.py"
    spec = importlib.util.spec_from_file_location("release_github_skill", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load release_github_skill")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class RecordingRunner:
    def __init__(self, expected_marker: str) -> None:
        self.expected_marker = expected_marker
        self.command: tuple[str, ...] | None = None
        self.env: dict[str, str] | None = None

    def run(
        self,
        command: tuple[str, ...],
        *,
        cwd: Path,
        check: bool,
        env: dict[str, str],
    ) -> object:
        del cwd, check
        self.command = command
        self.env = env
        marker = Path(command[command.index("--output-last-message") + 1])
        marker.write_text(f"{self.expected_marker}\n", encoding="utf-8")
        return type("Result", (), {"returncode": 0})()


class ReleaseRuntimeContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.release = load_release_module()

    def test_codex_approval_option_precedes_exec(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            runner = RecordingRunner("RUNTIME_OK")
            self.release._run_codex_runtime_step(
                runner,
                codex_home=workspace,
                workspace=workspace,
                prompt="test",
                expected_marker="RUNTIME_OK",
            )
        self.assertIsNotNone(runner.command)
        command = runner.command or ()
        self.assertLess(command.index("--ask-for-approval"), command.index("exec"))
        self.assertEqual(runner.env, {"CODEX_HOME": str(workspace)})

    def test_explicit_shared_skill_root_is_independent_of_codex_home(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            codex_home = root / ".codex"
            installed = root / ".agents" / "skills" / "vibe-diagram"
            codex_home.mkdir()
            installed.mkdir(parents=True)
            resolved = self.release._runtime_installed_skill_root(
                codex_home,
                installed,
            )
        self.assertEqual(resolved, installed)

    def test_ambiguous_default_skill_roots_require_explicit_selection(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            codex_home = root / ".codex"
            local = codex_home / "skills" / "vibe-diagram"
            local.mkdir(parents=True)
            with self.assertRaisesRegex(
                self.release.ReleaseError,
                "exactly one discoverable",
            ):
                self.release._runtime_installed_skill_root(codex_home, None)


if __name__ == "__main__":
    unittest.main()
