from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
README_ZH = ROOT / "README.zh-CN.md"
CHANGELOG = ROOT / "CHANGELOG.md"
PUBLIC_DOCS = ROOT / "docs" / "public"
PUBLIC_OVERCLAIM_PATTERNS = (
    r"production.ready",
    r"works with all four clients",
    r"officially supported",
    r"fully compatible",
    r"\bpublicly\s+installable\b",
    r"\bready\s+for\s+installation\b",
    r"\bruntime\s+is\s+verified\b",
    r"\bsupports\s+all\s+four\s+clients\b",
    r"现已公开\s*可安装",
    r"运行时\s*已验证",
    r"四端\s*均已支持",
    r"runtime\s*[:=]?\s*passed",
    r"released on",
    r"https?://[^\s)]*/releases",
    r"/plugin\s+install",
    r"available (?:now )?to install",
    r"现在(?:即可|可以)安装",
    r"all GitHub users",
    r"所有\s*GitHub\s*用户",
    r"(?:ready|eligible) for stable promotion",
    r"可(?:直接|立即)?提升(?:为|至)?稳定版",
    r"!\[[^]]*badge[^]]*\]",
)


def _version() -> str:
    return (ROOT / "VERSION").read_text(encoding="ascii").strip()


class DocumentationContractTests(unittest.TestCase):
    def test_public_document_inventory_and_language_boundary(self) -> None:
        expected = {"PRIVACY.md", "SUPPORT.md", "TERMS.md"}
        actual = {path.name for path in PUBLIC_DOCS.iterdir() if path.is_file()}
        self.assertEqual(expected, actual)

        english = README.read_text(encoding="utf-8")
        chinese = README_ZH.read_text(encoding="utf-8")
        self.assertIsNone(re.search(r"[\u3400-\u9fff]", english))
        self.assertIsNotNone(re.search(r"[\u3400-\u9fff]", chinese))
        self.assertIn("README.zh-CN.md", english)

    def test_readmes_state_static_and_runtime_boundaries(self) -> None:
        version = _version()
        english = README.read_text(encoding="utf-8")
        chinese = README_ZH.read_text(encoding="utf-8")

        english_required = (
            f"Unreleased {version} release-candidate snapshot",
            "skills/vibe-diagram/",
            "plugins/vibe-diagram/",
            ".agents/plugins/marketplace.json",
            "zero third-party runtime dependencies",
            "python3.9 -m unittest discover -s tests -v",
            "python3 -m unittest discover -s tests -v",
            "python3 scripts/build_packages.py --check",
            "python3 scripts/build_packages.py --sync-publication",
            "package-static-valid",
            "does not prove the complete unit suite",
            "evidence remains in command or CI output",
            "Runtime verification remains `Unverified` for RC.2",
            "No installation, discovery, invocation, HTML-delivery, upgrade, or uninstall result is inherited",
        )
        for value in english_required:
            with self.subTest(document="README.md", value=value):
                self.assertIn(value, english)

        chinese_required = (
            f"Unreleased {version} release-candidate snapshot",
            "skills/vibe-diagram/",
            "plugins/vibe-diagram/",
            ".agents/plugins/marketplace.json",
            "零第三方运行时依赖",
            "python3.9 -m unittest discover -s tests -v",
            "python3 -m unittest discover -s tests -v",
            "python3 scripts/build_packages.py --check",
            "python3 scripts/build_packages.py --sync-publication",
            "package-static-valid",
            "不能证明完整 unit suite",
            "证据保留在命令或 CI 输出中",
            "RC.2 的运行时验证仍为 `Unverified`",
            "不继承旧标签的安装、发现、调用、HTML 交付、升级或卸载结论",
        )
        for value in chinese_required:
            with self.subTest(document="README.zh-CN.md", value=value):
                self.assertIn(value, chinese)

    def test_readmes_publish_exact_rc2_install_and_uninstall_paths(self) -> None:
        english = README.read_text(encoding="utf-8")
        chinese = README_ZH.read_text(encoding="utf-8")
        shared = (
            "https://github.com/imchenway/vibe-diagram",
            "codex plugin marketplace add imchenway/vibe-diagram --ref v0.1.0-rc.2",
            "codex plugin add vibe-diagram@imchenway",
            "codex plugin remove vibe-diagram@imchenway",
            "codex plugin marketplace remove imchenway",
            "https://github.com/imchenway/vibe-diagram/tree/v0.1.0-rc.2/skills/vibe-diagram",
            "$skill-installer",
        )
        for value in shared:
            with self.subTest(value=value):
                self.assertIn(value, english)
                self.assertIn(value, chinese)

    def test_changelog_is_an_unreleased_rc2_snapshot(self) -> None:
        text = CHANGELOG.read_text(encoding="utf-8")
        self.assertEqual(1, text.count("## [Unreleased]"))
        self.assertIn(f"{_version()} release-candidate snapshot", text)
        self.assertIn("Runtime verification remains Unverified", text)
        self.assertIsNone(re.search(r"\b20\d{2}-\d{2}-\d{2}\b", text))
        self.assertNotIn("Release URL", text)

    def test_public_documents_do_not_overclaim_release_or_compatibility(self) -> None:
        documents = [README, README_ZH, CHANGELOG, *sorted(PUBLIC_DOCS.iterdir())]
        text = "\n".join(path.read_text(encoding="utf-8") for path in documents)
        for pattern in PUBLIC_OVERCLAIM_PATTERNS:
            with self.subTest(pattern=pattern):
                self.assertIsNone(re.search(pattern, text, re.IGNORECASE))

    def test_public_overclaim_patterns_detect_each_required_claim_family(self) -> None:
        violations = (
            "This package is PUBLICLY   INSTALLABLE.",
            "The package is ready\tfor   installation.",
            "Runtime \t is   verified.",
            "The project SUPPORTS   ALL FOUR CLIENTS.",
            "现已公开 \t 可安装",
            "运行时 \t 已验证",
            "四端 \t 均已支持",
        )
        for statement in violations:
            with self.subTest(statement=statement):
                self.assertTrue(
                    any(
                        re.search(pattern, statement, re.IGNORECASE)
                        for pattern in PUBLIC_OVERCLAIM_PATTERNS
                    )
                )


if __name__ == "__main__":
    unittest.main()
