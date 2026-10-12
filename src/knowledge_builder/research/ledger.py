"""File-backed atomic ledger for incremental auto-research.
Prevents 64K token cutoff by streaming discrete evidence entries to disk.
"""

from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
import fcntl
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
    quote: Optional[str] = None

    def to_jsonl(self) -> str:
        d = asdict(self)
        if self.metadata is None:
            d["metadata"] = {}
        return json.dumps(d, ensure_ascii=False)


def require_relative_source_uri(uri):
    """Accept a repo-relative path. Reject schemes and absolute paths.

    An absolute file:// URI is never stored. The caller copies the bytes
    into _evidence/<id>/sources/ and records that relative path instead.
    """
    if not isinstance(uri, str):
        raise ValueError("source_uri must be a relative path")
    text = uri.strip()
    if not text or "://" in text or text.lower().startswith("file:"):
        raise ValueError(f"source_uri must be relative, not {uri}")
    if text.startswith(("/", "\\")) or Path(text).is_absolute():
        raise ValueError(f"source_uri must be relative, not {uri}")
    if len(text) >= 3 and text[0].isalpha() and text[1] == ":" and text[2] in "/\\":
        raise ValueError(f"source_uri must be relative, not {uri}")
    if ".." in Path(text).parts:
        raise ValueError(f"source_uri escapes the knowledge root: {uri}")
    return text


class AtomicResearchLedger:
    def __init__(self, run_id: str, base_dir: Path = Path(".knowledge_staging")):
        self.run_id = run_id
        self.stage_dir = Path(base_dir) / run_id
        self.stage_dir.mkdir(parents=True, exist_ok=True)
        self.evidence_path = self.stage_dir / "evidence.jsonl"
        self.state_path = self.stage_dir / "state.json"

    def record_atom(self, atom: EvidenceAtom) -> None:
        """Append one evidence atom under an exclusive sibling lock, then fsync.

        The lock file is evidence.jsonl.lock, next to the ledger. Writers
        block each other for the append and the fsync, then release it.
        """
        atom.source_uri = require_relative_source_uri(atom.source_uri)
        self.stage_dir.mkdir(parents=True, exist_ok=True)
        lock_path = self.evidence_path.with_name(self.evidence_path.name + ".lock")
        lock_fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o644)
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX)
            with open(self.evidence_path, "a", encoding="utf-8") as handle:
                handle.write(atom.to_jsonl() + "\n")
                handle.flush()
                os.fsync(handle.fileno())
        finally:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            os.close(lock_fd)

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
