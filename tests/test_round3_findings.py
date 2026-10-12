"""Round-3 reproductions. Each case starts from a passing fixture and breaks one thing."""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from knowledge_builder.anchors import AnchorSyntaxError, heading_present, parse_attributes, visible_lines
from knowledge_builder.containment import ContainmentError, atomic_write
from knowledge_builder.research.ledger import AtomicResearchLedger, EvidenceAtom
from knowledge_builder.research.stopping_gate import TerminationState, evaluate_stopping_gate
from .test_review_findings import _gate, _knowledge, _run, _sha, _write_sufficient
from .test_stopping_gate import _passing


def _shows(text, heading="## Purpose"):
    return heading_present(visible_lines(text), heading)


def _short_once(real):
    state = {"used": False}

    def fake(fd, data):
        if not state["used"] and len(data) > 1:
            state["used"] = True
            half = max(1, len(data) // 2)
            return real(fd, data[:half])
        return real(fd, data)

    return fake


class TestRound3Findings(unittest.TestCase):
    def test_f06_missing_minimum_blocks_stop(self):
        """Deleting minimum_independent_sources must not default to 2 and STOP."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run = _write_sufficient(root)
            code, out, err = _gate(root)
            self.assertEqual(code, 0, out + err)
            self.assertIn("STOP_SUFFICIENT", out)
            state = json.loads((run / "state.json").read_text(encoding="utf-8"))
            state.pop("minimum_independent_sources")
            (run / "state.json").write_text(json.dumps(state), encoding="utf-8")
            code, out, err = _gate(root)
            self.assertNotEqual(code, 0, out + err)
            self.assertNotIn("STOP_SUFFICIENT", out)
            self.assertIn("minimum_independent_sources", out + err)

    def test_f16_evaluator_rejects_invalid_minimum_sources(self):
        """minimum_independent_sources below 1 or non-int must not STOP."""
        self.assertEqual(evaluate_stopping_gate(_passing()).state, TerminationState.STOP_SUFFICIENT)
        for bad in (0, -1, True, False, 1.0, "2", None):
            with self.subTest(bad=bad):
                try:
                    decision = evaluate_stopping_gate(_passing(minimum_independent_sources=bad))
                except (TypeError, ValueError):
                    continue
                self.assertNotEqual(decision.state, TerminationState.STOP_SUFFICIENT)
                self.assertIsNone(decision.certificate)

    def test_f15_short_write_is_not_success(self):
        """A half-length os.write must not publish truncated bytes."""
        payload = b'{"phase":"complete","pad":"0123456789"}\n'
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            import knowledge_builder.containment as containment

            with patch.object(containment.os, "write", _short_once(containment.os.write)):
                atomic_write(directory, "state.json", payload)
            self.assertEqual((directory / "state.json").read_bytes(), payload)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ledger = AtomicResearchLedger("run-1", base_dir=root / "_evidence")
            atom = EvidenceAtom(
                id="atom-1",
                run_id="run-1",
                claim_type="FACT",
                statement="support for c1",
                source_uri="_evidence/run-1/sources/a.txt",
                source_digest="a" * 64,
                captured_at="2026-10-12T00:00:00Z",
                confidence="HIGH",
                verified_by_code=False,
                metadata={},
                quote="keep",
            )
            import knowledge_builder.containment as containment
            import knowledge_builder.research.ledger as ledger_mod

            expected = (atom.to_jsonl() + "\n").encode("utf-8")
            with (
                patch.object(ledger_mod.os, "write", _short_once(ledger_mod.os.write)),
                patch.object(containment.os, "write", _short_once(containment.os.write)),
            ):
                ledger.record_atom(atom)
            self.assertEqual(ledger.evidence_path.read_bytes(), expected)
            self.assertEqual(ledger.load_atoms()[0].id, "atom-1")

        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            import knowledge_builder.containment as containment

            def stall(_fd, data):
                if len(data) > 0:
                    return 0
                return 0

            with patch.object(containment.os, "write", stall):
                with self.assertRaises(OSError):
                    atomic_write(directory, "state.json", payload)
            self.assertFalse((directory / "state.json").exists())

    def test_f10_glued_attributes_are_rejected(self):
        """quote="a" uri="b" parses. quote="a"uri="b" does not."""
        self.assertEqual(parse_attributes('quote="a" uri="b"'), {"quote": "a", "uri": "b"})
        with self.assertRaises(AnchorSyntaxError):
            parse_attributes('quote="a"uri="b"')

        uri = "_evidence/run-1/sources/note.txt"
        source = b"alpha holds\n"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / uri
            src.parent.mkdir(parents=True)
            src.write_bytes(source)
            digest = _sha(source)
            anchor = f'<!-- ease:source uri={uri} sha256={digest} quote="alpha holds" -->'
            text = _knowledge(digest, uri, anchor_line=anchor)
            (root / "note.md").write_text(text, encoding="utf-8")
            code, out, err = _run(["knowledge-builder", "verify", "--claims", str(root)])
            self.assertEqual(code, 0, out + err)
            glued = text.replace('quote="alpha holds"', 'quote="alpha holds"extra="x"', 1)
            (root / "note.md").write_text(glued, encoding="utf-8")
            code, out, err = _run(["knowledge-builder", "verify", "--claims", str(root)])
            self.assertNotEqual(code, 0, out + err)
            self.assertNotIn("failures: 0", out)

    def test_f11_hidden_headings_do_not_count(self):
        """Headings in ~~~ fences, 4-space code, or an unclosed comment do not count."""
        self.assertTrue(_shows("## Purpose\n"))
        cases = {
            "tilde": "~~~\n## Purpose\n~~~\n",
            "indent": "    ## Purpose\n",
            "unclosed-comment": "<!--\n## Purpose\n",
        }
        for name, text in cases.items():
            with self.subTest(name=name):
                self.assertFalse(_shows(text))

        uri = "_evidence/run-1/sources/note.txt"
        source = b'He said "no".\n'
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / uri
            src.parent.mkdir(parents=True)
            src.write_bytes(source)
            digest = _sha(source)
            anchor = f"<!-- ease:source uri={uri} sha256={digest} -->"
            base = _knowledge(digest, uri, anchor_line=anchor)
            note = root / "note.md"
            note.write_text(base, encoding="utf-8")
            code, out, err = _run(["knowledge-builder", "verify", str(root)])
            self.assertEqual(code, 0, out + err)

            mutations = {
                "tilde": (
                    base.replace("\n## Purpose\n", "\n~~~\n## Purpose\n", 1).replace(
                        "\n## Failure Modes\n", "\n## Failure Modes\n~~~\n", 1
                    )
                ),
                "indent": base.replace("\n## ", "\n    ## "),
                "unclosed-comment": base.replace(
                    "\n## Failure Modes\n", "\n<!--\n## Failure Modes\n", 1
                ),
            }
            for name, text in mutations.items():
                with self.subTest(name=name):
                    note.write_text(text, encoding="utf-8")
                    code, out, err = _run(["knowledge-builder", "verify", str(root)])
                    self.assertNotEqual(code, 0, out + err)
                    self.assertIn("heading", out.lower())

    def test_f14_directory_swap_does_not_publish_outside(self):
        """Renaming the dir and planting an outside symlink must not publish outside."""
        payload = b'{"kept": true}\n'
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            directory = base / "pinned"
            renamed = base / "renamed"
            outside = base / "outside"
            directory.mkdir()
            outside.mkdir()
            (outside / "index.json").write_bytes(b"OUTSIDE")
            import knowledge_builder.containment as containment

            real_replace = containment.os.replace
            seen = {}

            def swap(src, dst, *args, **kwargs):
                if not seen.get("done"):
                    seen["done"] = True
                    seen["src"] = src
                    seen["dst"] = dst
                    seen["kwargs"] = dict(kwargs)
                    directory.rename(renamed)
                    os.symlink(outside, directory, target_is_directory=True)
                return real_replace(src, dst, *args, **kwargs)

            with patch.object(containment.os, "replace", swap):
                atomic_write(directory, "index.json", payload)

            self.assertIn("src_dir_fd", seen["kwargs"])
            self.assertIn("dst_dir_fd", seen["kwargs"])
            self.assertNotIn("/", seen["src"])
            self.assertNotIn("/", seen["dst"])
            self.assertEqual((outside / "index.json").read_bytes(), b"OUTSIDE")
            self.assertEqual((renamed / "index.json").read_bytes(), payload)

    def test_f01_reused_ledger_revalidates_on_write(self):
        """Replacing _evidence after construction must not redirect later writes."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            outside = base / "outside"
            root.mkdir()
            outside.mkdir()
            (outside / "run-1").mkdir()
            ledger = AtomicResearchLedger("run-1", base_dir=root / "_evidence")
            atom = EvidenceAtom(
                id="atom-1",
                run_id="run-1",
                claim_type="FACT",
                statement="support for c1",
                source_uri="_evidence/run-1/sources/a.txt",
                source_digest="a" * 64,
                captured_at="2026-10-12T00:00:00Z",
                confidence="HIGH",
                verified_by_code=False,
                metadata={},
                quote="keep",
            )
            ledger.save_state({"run_id": "run-1", "phase": "ok"})
            ledger.record_atom(atom)
            stage = root / "_evidence" / "run-1"
            self.assertIn("ok", (stage / "state.json").read_text(encoding="utf-8"))
            self.assertIn("atom-1", (stage / "evidence.jsonl").read_text(encoding="utf-8"))

            real_evidence = base / "real-evidence"
            (root / "_evidence").rename(real_evidence)
            os.symlink(outside, root / "_evidence", target_is_directory=True)

            with self.assertRaises(ContainmentError):
                ledger.record_atom(atom)
            with self.assertRaises(ContainmentError):
                ledger.save_state({"run_id": "run-1", "phase": "hijack"})

            self.assertFalse((outside / "run-1" / "evidence.jsonl").exists())
            self.assertFalse((outside / "run-1" / "evidence.jsonl.lock").exists())
            self.assertFalse((outside / "run-1" / "state.json").exists())
            self.assertNotIn("hijack", (real_evidence / "run-1" / "state.json").read_text(encoding="utf-8"))

    def test_f12_markdown_reread_stays_inside_root(self):
        """Swapping a discovered markdown file for an outside symlink must fail closed."""
        uri = "_evidence/run-1/sources/note.txt"
        source = b'He said "no".\n'
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            outside = base / "outside"
            root.mkdir()
            outside.mkdir()
            src = root / uri
            src.parent.mkdir(parents=True)
            src.write_bytes(source)
            digest = _sha(source)
            anchor = f"<!-- ease:source uri={uri} sha256={digest} -->"
            text = _knowledge(digest, uri, anchor_line=anchor)
            note = root / "note.md"
            note.write_text(text, encoding="utf-8")
            outside_note = outside / "note.md"
            outside_note.write_text(text, encoding="utf-8")
            code, out, err = _run(["knowledge-builder", "verify", str(root)])
            self.assertEqual(code, 0, out + err)

            import knowledge_builder.verify as verify_mod

            real_verify = verify_mod._markdown_files

            def swap_verify(root_arg):
                found, errors = real_verify(root_arg)
                target = Path(root_arg) / "note.md"
                target.unlink()
                os.symlink(outside_note, target)
                return found, errors

            with patch.object(verify_mod, "_markdown_files", swap_verify):
                code, out, err = _run(["knowledge-builder", "verify", str(root)])
            self.assertNotEqual(code, 0, out + err)
            self.assertNotIn("failures: 0", out)

        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            outside = base / "outside"
            root.mkdir()
            outside.mkdir()
            note = root / "note.md"
            note.write_text(
                '---\nid: note\ntitle: "A note"\n---\n\n# Note\n\nBody.\n',
                encoding="utf-8",
            )
            outside_note = outside / "note.md"
            outside_note.write_text(note.read_text(encoding="utf-8"), encoding="utf-8")
            code, out, err = _run(["knowledge-builder", "index", "--root", str(root)])
            self.assertEqual(code, 0, out + err)
            (root / "index.json").unlink()

            import knowledge_builder.index as index_mod

            real_index = index_mod._markdown_files

            def swap_index(root_arg, patterns):
                found, errors = real_index(root_arg, patterns)
                target = Path(root_arg) / "note.md"
                target.unlink()
                os.symlink(outside_note, target)
                return found, errors

            with patch.object(index_mod, "_markdown_files", swap_index):
                code, out, err = _run(["knowledge-builder", "index", "--root", str(root)])
            self.assertNotEqual(code, 0, out + err)
            self.assertFalse((root / "index.json").exists())


if __name__ == "__main__":
    unittest.main()
