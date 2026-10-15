"""es-knowledge-forge follows the tool-product profile: shape (A1, A2, A9, M3), size limits."""

import json
import re
import unittest

from tests.skill_support import REPO, SKILL

SKILL_MD = (SKILL / "SKILL.md").read_text(encoding="utf-8")
RULES = (SKILL / "rules.md").read_text(encoding="utf-8")
CHECKS = ("contract", "verify", "index", "uncited-claims", "documents-without-claims",
          "hosting-publisher", "publisher-kind", "contradictions", "review")


class TestSkillShape(unittest.TestCase):
    def test_a1_router_size_and_frontmatter(self):
        self.assertLessEqual(len(SKILL_MD.splitlines()), 120)
        head = re.match(r"---\n(.*?)\n---\n", SKILL_MD, re.S)
        self.assertIsNotNone(head)
        name = re.search(r"^name: (.+)$", head.group(1), re.M).group(1).strip()
        self.assertEqual(name, SKILL.name)
        self.assertEqual(name, "es-knowledge-forge")
        self.assertRegex(name, r"^[a-z0-9]+(-[a-z0-9]+)*$")
        description = re.search(r'^description: "?(.+?)"?$', head.group(1), re.M).group(1)
        self.assertTrue(description.startswith("Use when"), description)
        self.assertLessEqual(len(description), 200)

    def test_a2_every_sibling_file_is_named_and_every_link_exists(self):
        files = [p for p in SKILL.rglob("*") if p.is_file() and p.name != "SKILL.md" and "__pycache__" not in p.parts]
        self.assertTrue(files)
        for path in files:
            rel = path.relative_to(SKILL).as_posix()
            self.assertIn(rel, SKILL_MD, f"SKILL.md does not name {rel}")
        for target in re.findall(r"\]\(([^)#]+)\)", SKILL_MD):
            if "://" not in target:
                self.assertTrue((SKILL / target).exists(), f"SKILL.md links to missing {target}")

    def test_reference_files_stay_under_300_lines(self):
        for path in [*SKILL.glob("references/*.md"), SKILL / "rules.md", SKILL / "concepts.md", SKILL / "look.md"]:
            self.assertLess(len(path.read_text(encoding="utf-8").splitlines()), 300, path.name)

    def test_m3_every_rule_has_keep_it_rejected_when_and_a_home(self):
        blocks = re.split(r"^## (R\d+)\. ", RULES, flags=re.M)[1:]
        self.assertGreaterEqual(len(blocks) // 2, 15)
        validate_py = (SKILL / "validate.py").read_text(encoding="utf-8")
        for ident, body in zip(blocks[0::2], blocks[1::2]):
            self.assertIn("Keep it:", body, ident)
            self.assertIn("Rejected when:", body, ident)
            home = re.search(r"^Home: (.+)$", body, re.M)
            self.assertIsNotNone(home, ident)
            for check in re.findall(r"validate:([a-z-]+)", home.group(1)):
                self.assertIn(check, CHECKS, f"{ident} names unknown check {check}")
                self.assertIn(f"{check}:", validate_py, f"validate.py has no {check} line")
            if "validate:" not in home.group(1):
                self.assertRegex(home.group(1), r"^(tool|hand-over|look L\d)", ident)

    def test_every_validate_check_is_owned_by_a_rule_and_the_router(self):
        for check in CHECKS[1:]:
            self.assertIn(f"validate:{check}", RULES, check)
        for check in CHECKS:
            self.assertIn(check, SKILL_MD, check)

    def test_look_md_numbers_machine_and_eye_items_and_has_the_no_browser_clause(self):
        look = (SKILL / "look.md").read_text(encoding="utf-8")
        self.assertIn("## Without a browser", look)
        for number in range(1, 9):
            self.assertIn(f"| L{number} |", look)
        look_py = (SKILL / "look.py").read_text(encoding="utf-8")
        for number in range(1, 5):
            self.assertIn(f'"L{number}"', look_py)

    def test_what_goes_wrong_covers_open_frictions(self):
        section = SKILL_MD.split("| What goes wrong |", 1)[1]
        for needle in ("metadata.url", "actions.jsonl", "--linked-to", "0/N novel", "add-link"):
            self.assertIn(needle, section)

    def test_a9_attribution_lists_hairline_and_its_licence(self):
        text = (SKILL / "ATTRIBUTION.md").read_text(encoding="utf-8")
        self.assertIn("github.com/lucasmarkes/hairline", text)
        self.assertIn("MIT", text)
        self.assertIn("Lucas Marques", text)

    def test_scripts_use_only_the_standard_library_and_no_network(self):
        banned = re.compile(r"^\s*(import|from)\s+(urllib|requests|http|socket|pip|setuptools)\b", re.M)
        for path in SKILL.glob("*.py"):
            self.assertIsNone(banned.search(path.read_text(encoding="utf-8")), path.name)

    def test_examples_are_at_least_two_and_one_has_an_entity(self):
        specs = sorted((SKILL / "examples").glob("*.json"))
        self.assertGreaterEqual(len(specs), 2)
        self.assertTrue(any('"entities"' in p.read_text(encoding="utf-8") for p in specs))


class TestSkillHasOneHome(unittest.TestCase):
    """A8: the bundles point at ./skills/, and no second copy of the skill can drift."""

    def test_a8_the_skill_exists_only_under_skills(self):
        found = [p.relative_to(REPO).as_posix() for p in REPO.rglob("SKILL.md")
                 if not {".git", ".brv", "node_modules"} & set(p.relative_to(REPO).parts)]
        self.assertEqual(found, ["skills/es-knowledge-forge/SKILL.md"])
        self.assertEqual([p.name for p in REPO.rglob("es-knowledge-forge") if ".git" not in p.parts], ["es-knowledge-forge"])

    def test_a8_bundle_manifests_point_at_the_skills_folder(self):
        manifest = json.loads((REPO / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["skills"], "./skills/")
        self.assertTrue((REPO / manifest["skills"] / SKILL.name / "SKILL.md").is_file())

