"""Ledger atoms a promote-claim run reads: lookup, verification against the frozen file, capture header."""

import re
from pathlib import Path

from knowledge_builder.containment import ContainmentError
from knowledge_builder.ontology.action_plan import ActionError
from knowledge_builder.ontology.functions import _capture_header
from knowledge_builder.quote_check import file_contains_quote
from knowledge_builder.research.ledger import AtomicResearchLedger
from knowledge_builder.research.ledger_gate import _source_file


class Atoms:
    """Atoms per run, loaded once per plan."""

    def __init__(self, root):
        self.root, self._runs = Path(root), {}

    def run_atoms(self, run):
        if run not in self._runs:
            try:
                loaded = AtomicResearchLedger(run, base_dir=self.root / "_evidence").load_atoms()
            except (ContainmentError, OSError, ValueError, TypeError) as exc:
                raise ActionError(f"run '{run}': unreadable ledger: {exc}") from exc
            self._runs[run] = {atom.id: atom for atom in loaded}
        return self._runs[run]

    def find(self, atom_id, run=None):
        """(run, atom). Without run, the atom id must exist in exactly one run under _evidence/."""
        if run:
            atom = self.run_atoms(run).get(atom_id) if (self.root / "_evidence" / run / "evidence.jsonl").is_file() else None
            return self._found(atom_id, [(run, atom)] if atom else [])
        runs = sorted(p.parent.name for p in (self.root / "_evidence").glob("*/evidence.jsonl")) if (self.root / "_evidence").is_dir() else []
        return self._found(atom_id, [(r, self.run_atoms(r)[atom_id]) for r in runs if atom_id in self.run_atoms(r)])

    @staticmethod
    def _found(atom_id, hits):
        if not hits:
            raise ActionError(f"atom '{atom_id}' not found in any run ledger")
        if len(hits) > 1:
            raise ActionError(f"atom '{atom_id}' exists in runs {', '.join(r for r, _ in hits)}: pass --param run=<run>")
        return hits[0]


def verified_file(root, run, atom):
    """The frozen file when the ledger digest matches its bytes and the quote occurs in it; ActionError otherwise."""
    real = _source_file(root, run, atom.source_uri, atom.source_digest)
    if real is None:
        raise ActionError(f"atom '{atom.id}': the frozen file is missing or its sha256 does not match the ledger")
    if not file_contains_quote(real, atom.quote):
        raise ActionError(f"atom '{atom.id}': quote is not in the frozen file (or the atom has no quote)")
    return real


def header_field(path, name):
    """Value of `Name: value` in the capture header lines, or None."""
    match = re.search(rf"^{re.escape(name)}:[ \t]*(\S.*?)\s*$", _capture_header(path), re.MULTILINE)
    return match.group(1) if match else None
