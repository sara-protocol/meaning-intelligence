from pathlib import Path
import re
import unittest

from meaning_agent.constants import SKILL_NAMES

ROOT = Path(__file__).resolve().parents[1]


class SkillDocumentTests(unittest.TestCase):
    def test_six_valid_bilingual_skill_definitions(self):
        for name in SKILL_NAMES:
            with self.subTest(name=name):
                path = ROOT / "skills" / name / "SKILL.md"
                self.assertTrue(path.is_file())
                content = path.read_text(encoding="utf-8")
                self.assertTrue(content.startswith("---\n"))
                frontmatter, body = content[4:].split("\n---\n", 1)
                fields = {}
                for line in frontmatter.splitlines():
                    if ":" in line:
                        key, value = line.split(":", 1)
                        fields[key.strip()] = value.strip()
                self.assertEqual(fields["name"], name)
                self.assertRegex(fields["name"], r"^[a-z0-9-]+$")
                self.assertTrue(fields["description"])
                self.assertLessEqual(len(fields["description"]), 1024)
                self.assertLess(len(body.splitlines()), 500)
                self.assertNotIn("TODO:", content)
                self.assertTrue(re.search(r"[\u4e00-\u9fff]", body))
                self.assertTrue(re.search(r"\b(?:Runner|Workflow|Limits|Overview)\b", body))
                self.assertIn("/", body)

    def test_no_extra_readme_in_skill_directories(self):
        for name in SKILL_NAMES:
            files = [item.name for item in (ROOT / "skills" / name).iterdir() if item.is_file()]
            self.assertEqual(files, ["SKILL.md"])

    def test_project_readme_has_required_sections(self):
        content = (ROOT / "README.md").read_text(encoding="utf-8")
        for heading in ("## Architecture", "## Quick start", "## White-paper mapping", "## MCP server", "## Tests", "## Limits and safety"):
            self.assertIn(heading, content)
        self.assertIn("weighted summation forbidden", content)
        self.assertIn("127.0.0.1", content)


if __name__ == "__main__":
    unittest.main()
