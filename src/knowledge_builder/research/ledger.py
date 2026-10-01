"""File-backed atomic ledger for incremental auto-research.
Prevents 64K token cutoff by streaming discrete evidence entries to disk.
"""

from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
import hashlib
import json
import os


@dataclass
class EvidenceAtom:
    id: str
    run_id: str
    claim_type: str  # FACT | INFERENCE | FAILURE_MODE | BENCHMARK | CONTRADICTION
    statement: str
    source_uri: str
    source_digest: str
    captured_at: str
    confidence: str  # HIGH | MEDIUM | LOW
    verified_by_code: bool = False
    metadata: Dict[str, Any] = None

    def to_jsonl(self) -> str:
        d = asdict(self)
        if self.metadata is None:
            d["metadata"] = {}
        return json.dumps(d, ensure_ascii=False)


class AtomicResearchLedger:
    def __init__(self, run_id: str, base_dir: Path = Path(".knowledge_staging")):
        self.run_id = run_id
        self.stage_dir = Path(base_dir) / run_id
        self.stage_dir.mkdir(parents=True, exist_ok=True)
        self.evidence_path = self.stage_dir / "evidence.jsonl"
        self.state_path = self.stage_dir / "state.json"

    def record_atom(self, atom: EvidenceAtom) -> None:
        """Append a single evidence atom (500B - 2KB) directly to disk."""
        with open(self.evidence_path, "a", encoding="utf-8") as f:
            f.write(atom.to_jsonl() + "\n")

    def load_atoms(self) -> List[EvidenceAtom]:
        """Read all verified atoms from disk."""
        if not self.evidence_path.exists():
            return []
        atoms = []
        with open(self.evidence_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    data = json.loads(line)
                    atoms.append(EvidenceAtom(**data))
        return atoms

    def save_state(self, state: Dict[str, Any]) -> None:
        """Save state machine cursor for idempotent resume."""
        tmp = self.state_path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
        os.replace(tmp, self.state_path)

    def load_state(self) -> Dict[str, Any]:
        """Load state machine cursor."""
        if not self.state_path.exists():
            return {
                "run_id": self.run_id,
                "round": 0,
                "status": "RUNNING",
                "budget_used": 0,
                "gaps": [],
            }
        with open(self.state_path, "r", encoding="utf-8") as f:
            return json.load(f)
