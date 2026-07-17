from __future__ import annotations

import json
import unittest
from pathlib import Path
from typing import Any, Dict, List, Tuple


ROOT = Path(__file__).resolve().parents[1]
ADAPTER_ROOT = ROOT / "adapters"
CLIENTS = ("codex", "claude", "gemini", "copilot")
ADAPTER_KEYS = {
    "schema_version",
    "client",
    "documentation",
    "manifest_template",
    "manifest_output",
    "skills_output",
    "extra_files",
}
BOUNDARY = (
    "static package definition only; installation, discovery, invocation, "
    "and HTML delivery are Unverified"
)
OFFICIAL_DOCS = {
    "codex": "https://learn.chatgpt.com/docs/build-plugins",
    "claude": "https://code.claude.com/docs/en/plugins-reference",
    "gemini": "https://geminicli.com/docs/extensions/reference/",
    "copilot": "https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-plugin-reference",
}
EXPECTED_ADAPTERS = {
    "codex": {
        "schema_version": 1,
        "client": "codex",
        "documentation": "README.md",
        "manifest_template": "manifest.template.json",
        "manifest_output": ".codex-plugin/plugin.json",
        "skills_output": "skills/vibe-diagram",
        "extra_files": [
            {
                "source": "files/agents/openai.yaml",
                "output": "skills/vibe-diagram/agents/openai.yaml",
            }
        ],
    },
    "claude": {
        "schema_version": 1,
        "client": "claude",
        "documentation": "README.md",
        "manifest_template": "manifest.template.json",
        "manifest_output": ".claude-plugin/plugin.json",
        "skills_output": "skills/vibe-diagram",
        "extra_files": [],
    },
    "gemini": {
        "schema_version": 1,
        "client": "gemini",
        "documentation": "README.md",
        "manifest_template": "manifest.template.json",
        "manifest_output": "gemini-extension.json",
        "skills_output": "skills/vibe-diagram",
        "extra_files": [],
    },
    "copilot": {
        "schema_version": 1,
        "client": "copilot",
        "documentation": "README.md",
        "manifest_template": "manifest.template.json",
        "manifest_output": "plugin.json",
        "skills_output": "skills/vibe-diagram",
        "extra_files": [],
    },
}


def _read_json_unique(path: Path) -> Dict[str, Any]:
    def reject_duplicates(pairs: List[Tuple[str, Any]]) -> Dict[str, Any]:
        result: Dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=reject_duplicates)
    if not isinstance(value, dict):
        raise ValueError("JSON root must be an object")
    return value


class AdapterDefinitionTests(unittest.TestCase):
    def test_exact_adapter_file_inventory(self) -> None:
        expected = {
            "claude/README.md",
            "claude/adapter.json",
            "claude/manifest.template.json",
            "codex/README.md",
            "codex/adapter.json",
            "codex/files/agents/openai.yaml",
            "codex/manifest.template.json",
            "copilot/README.md",
            "copilot/adapter.json",
            "copilot/manifest.template.json",
            "gemini/README.md",
            "gemini/adapter.json",
            "gemini/manifest.template.json",
        }
        actual = {
            path.relative_to(ADAPTER_ROOT).as_posix()
            for path in ADAPTER_ROOT.rglob("*")
            if path.is_file()
        }
        self.assertEqual(expected, actual)

    def test_adapter_definitions_use_exact_schema_and_paths(self) -> None:
        for client in CLIENTS:
            with self.subTest(client=client):
                adapter = _read_json_unique(ADAPTER_ROOT / client / "adapter.json")
                self.assertEqual(ADAPTER_KEYS, set(adapter))
                self.assertEqual(EXPECTED_ADAPTERS[client], adapter)
                self.assertIs(type(adapter["schema_version"]), int)

    def test_manifest_and_extra_outputs_are_the_complete_derived_whitelist(self) -> None:
        expected_outputs = {
            "codex": {
                ".codex-plugin/plugin.json",
                "skills/vibe-diagram/agents/openai.yaml",
            },
            "claude": {".claude-plugin/plugin.json"},
            "gemini": {"gemini-extension.json"},
            "copilot": {"plugin.json"},
        }
        for client in CLIENTS:
            with self.subTest(client=client):
                adapter = _read_json_unique(ADAPTER_ROOT / client / "adapter.json")
                outputs = {adapter["manifest_output"]}
                outputs.update(item["output"] for item in adapter["extra_files"])
                self.assertEqual(expected_outputs[client], outputs)

    def test_manifest_templates_are_the_documented_minimal_subsets(self) -> None:
        common = {
            "name": "vibe-diagram",
            "version": "${VERSION}",
            "description": "Create polished, self-contained HTML diagrams.",
        }
        author_and_license = {
            "author": {"name": "imchenway"},
            "license": "Apache-2.0",
        }
        expected = {
            "codex": {
                **common,
                **author_and_license,
                "skills": "./skills/",
                "interface": {
                    "displayName": "Vibe Diagram",
                    "shortDescription": "Self-contained HTML diagrams for complex ideas",
                    "longDescription": (
                        "Turn architecture, workflows, sequences, state, debugging, design, "
                        "decisions, and delivery acceptance into self-contained HTML diagrams."
                    ),
                    "developerName": "imchenway",
                    "category": "Developer Tools",
                    "capabilities": ["Read", "Write"],
                    "defaultPrompt": [
                        "Use Vibe Diagram to create a self-contained HTML diagram for this request."
                    ],
                    "brandColor": "#1F6FB2",
                },
            },
            "claude": {**common, **author_and_license},
            "gemini": common,
            "copilot": {**common, **author_and_license},
        }
        for client in CLIENTS:
            with self.subTest(client=client):
                manifest = _read_json_unique(ADAPTER_ROOT / client / "manifest.template.json")
                self.assertEqual(expected[client], manifest)

        gemini = _read_json_unique(ADAPTER_ROOT / "gemini" / "manifest.template.json")
        self.assertTrue({"author", "license", "skills"}.isdisjoint(gemini))

    def test_codex_openai_interface_yaml_is_exact(self) -> None:
        expected = (
            'interface:\n'
            '  display_name: "vibe-diagram"\n'
            '  short_description: "Create self-contained HTML diagrams for complex ideas."\n'
            '  default_prompt: "Use $vibe-diagram to create a self-contained HTML diagram for this request."\n'
        )
        path = ADAPTER_ROOT / "codex" / "files" / "agents" / "openai.yaml"
        self.assertEqual(expected, path.read_text(encoding="utf-8"))

    def test_readmes_preserve_the_static_unverified_boundary(self) -> None:
        for client in CLIENTS:
            with self.subTest(client=client):
                text = (ADAPTER_ROOT / client / "README.md").read_text(encoding="utf-8")
                adapter = EXPECTED_ADAPTERS[client]
                self.assertIn(adapter["manifest_output"], text)
                self.assertIn(adapter["skills_output"], text)
                self.assertIn(OFFICIAL_DOCS[client], text)
                self.assertIn(BOUNDARY, text)


if __name__ == "__main__":
    unittest.main()
