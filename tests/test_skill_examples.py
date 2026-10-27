"""A4/A5/M7/M8: every example builds and validates; one broken input per validate check gives exactly that line."""

import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.skill_support import EXAMPLES, REPO, SKILL, BuiltExamples, run_script, validate

DOC, ENT = "tiny-document-pack", "tiny-entity-pack"


def cli(*args):
    done = subprocess.run([sys.executable, "-B", "-m", "knowledge_builder.cli", *map(str, args)], capture_output=True, text=True,
                          env={"PYTHONPATH": str(REPO / "src"), "PATH": "/usr/bin:/bin"})
    assert done.returncode == 0, done.stderr + done.stdout
    return done


def edit(path, pattern, replacement):
    text = Path(path).read_text(encoding="utf-8")
    new = re.sub(pattern, replacement, text, count=1, flags=re.M)
    assert new != text, (path, pattern)
    Path(path).write_text(new, encoding="utf-8")


class TestExamplesPass(BuiltExamples):
    def test_a4_each_example_builds_and_validates_ok(self):
        self.assertGreaterEqual(len(EXAMPLES), 2)
        for spec in EXAMPLES:
            code, lines, err = validate(self.packs[spec.stem])
            self.assertEqual(code, 0, (spec.name, lines, err))
            self.assertEqual(lines[0], "ok")
            self.assertTrue(lines[1].startswith("gate: "), lines)

    def test_build_prints_the_path_and_refuses_an_existing_directory(self):
        code, lines, err = run_script("build.py", "--spec", EXAMPLES[0], "--output-dir", self.packs[EXAMPLES[0].stem])
        self.assertEqual(code, 1)
        self.assertIn("exists", err)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "fresh"
            code, lines, err = run_script("build.py", "--spec", EXAMPLES[0], "--output-dir", out)
            self.assertEqual((code, lines), (0, [str(out.resolve())]), err)

    def test_build_reports_a_refused_step_as_exit_1(self):
        spec = json.loads(EXAMPLES[0].read_text(encoding="utf-8"))
        spec["claims"][0]["atom"] = "no-such-atom"
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad.json"
            bad.write_text(json.dumps(spec), encoding="utf-8")
            code, lines, err = run_script("build.py", "--spec", bad, "--output-dir", Path(tmp) / "out")
        self.assertEqual(code, 1)
        self.assertIn("build:", err)
        # Path traversal in source stem is rejected
        spec2 = json.loads(EXAMPLES[0].read_text(encoding="utf-8"))
        spec2["sources"][0]["stem"] = "../../escaped"
        with tempfile.TemporaryDirectory() as tmp:
            bad2 = Path(tmp) / "bad2.json"
            bad2.write_text(json.dumps(spec2), encoding="utf-8")
            code2, _, err2 = run_script("build.py", "--spec", bad2, "--output-dir", Path(tmp) / "out2")
            self.assertEqual(code2, 1)
            self.assertIn("stem", err2)
            self.assertFalse((Path(tmp) / "escaped.txt").exists())

    def test_the_entity_example_exercises_an_entity_and_a_resolved_contradiction(self):
        root = self.packs[ENT]
        self.assertTrue(list((root / "entities").glob("*.md")))
        claims = "".join(p.read_text(encoding="utf-8") for p in (root / "claims").glob("*.md"))
        self.assertIn("CONTRADICTION", claims)
        self.assertIn("resolution:", claims)


class TestBrokenExamples(BuiltExamples):
    def test_verify(self):
        root = self.mutate(DOC)
        with (root / "alpha-and-beta.md").open("a", encoding="utf-8") as handle:
            handle.write("<!-- ease:claim id=ghost -->\n")
        cli("index", "--root", root)
        self.assertIn("ghost", self.only_line(root, "verify"))

    def test_uncited_claims(self):
        root = self.mutate(DOC)
        cli("action", "promote-claim", "--root", root, "--param", "atom=a3", "--param", "id=beta-needs-items", "--param", "kind=official")
        self.assertIn("beta-needs-items", self.only_line(root, "uncited-claims"))

    def test_documents_without_claims(self):
        spec = json.loads((SKILL / "examples" / f"{DOC}.json").read_text(encoding="utf-8"))
        spec["documents"].append({"id": "lonely", "title": "Lonely", "description": "Cites nothing.", "when": ["never"],
                                  "source": ["alpha-page"], "core": []})
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "lonely.json"
            path.write_text(json.dumps(spec), encoding="utf-8")
            code, lines, err = run_script("build.py", "--spec", path, "--output-dir", Path(tmp) / "pack")
            self.assertEqual(code, 0, err)
            self.assertIn("lonely", self.only_line(Path(tmp) / "pack", "documents-without-claims"))

    def test_hosting_publisher(self):
        root = self.mutate(DOC)
        edit(root / "sources" / "example-org-beta.md", r'^publisher: ".*"$', 'publisher: "github.com"')
        cli("index", "--root", root)
        self.assertIn("github.com", self.only_line(root, "hosting-publisher"))

    def test_publisher_kind(self):
        root = self.mutate(DOC)
        edit(root / "sources" / "example-org-beta.md", r'^kind: "official"$', 'kind: "vendor"')
        cli("index", "--root", root)
        self.assertIn("example.org", self.only_line(root, "publisher-kind"))

    def test_contradictions(self):
        root = self.mutate(ENT)
        edit(root / "claims" / "delta-rejects-unknown.md", r"^resolution: .*\n", "")
        cli("index", "--root", root)
        self.assertIn("delta-rejects-unknown", self.only_line(root, "contradictions"))

    def test_review_missing(self):
        root = self.mutate(DOC)
        next((root / "_evidence").glob("*/review.json")).unlink()
        self.assertIn("review.json", self.only_line(root, "review"))

    def test_review_by_the_researcher_runtime(self):
        root = self.mutate(DOC)
        path = next((root / "_evidence").glob("*/review.json"))
        data = json.loads(path.read_text(encoding="utf-8"))
        data["reviewer_runtime"] = "claude-sonnet-5-5"
        path.write_text(json.dumps(data), encoding="utf-8")
        self.assertIn("different runtime", self.only_line(root, "review"))

    def test_index_stale(self):
        root = self.mutate(DOC)
        with (root / "sources" / "example-org-beta.md").open("a", encoding="utf-8") as handle:
            handle.write("\n")
        self.assertIn("not fresh", self.only_line(root, "index"))

    def test_cannot_run_is_exit_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, lines, err = validate(tmp)
        self.assertEqual(code, 2)
        self.assertIn("could not run", err)
        self.assertEqual(lines, [])

    def test_help_exits_zero(self):
        for script in ("build.py", "validate.py", "look.py"):
            done = subprocess.run([sys.executable, "-B", str(SKILL / script), "--help"], capture_output=True, text=True)
            self.assertEqual(done.returncode, 0, script)
