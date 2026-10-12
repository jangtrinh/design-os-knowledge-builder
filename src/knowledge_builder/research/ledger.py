"""File-backed atomic ledger for incremental auto-research.
Prevents 64K token cutoff by streaming discrete evidence entries to disk.
"""

from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
import fcntl
import json
import os

from knowledge_builder.containment import (
    ContainmentError,
    atomic_write,
    ensure_real_dir,
    open_append_nofollow,
    open_lock_nofollow,
    read_text_nofollow,
    reject_symlink,
    require_inside,
)


CLAIM_TYPES = {"FACT", "INFERENCE", "FAILURE_MODE", "BENCHMARK", "CONTRADICTION"}
_STRING_FIELDS = (
    "id",
    "run_id",
    "claim_type",
    "statement",
    "source_uri",
    "source_digest",
    "captured_at",
    "confidence",
)


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


def validate_atom(atom, run_id):
    """Field types, allowed claim_type, and run identity. Reject anything else."""
    if not isinstance(atom, EvidenceAtom):
        raise ValueError("atom must be an EvidenceAtom")
    for field in _STRING_FIELDS:
        value = getattr(atom, field)
        if not isinstance(value, str) or value == "":
            raise ValueError(f"{field} must be a non-empty string")
    if atom.claim_type not in CLAIM_TYPES:
        raise ValueError(f"claim_type is not allowed: {atom.claim_type}")
    if atom.run_id != run_id:
        raise ValueError(f"run_id must be {run_id}")
    if not isinstance(atom.verified_by_code, bool):
        raise ValueError("verified_by_code must be a boolean")
    if atom.metadata is not None and not isinstance(atom.metadata, dict):
        raise ValueError("metadata must be an object")
    if atom.quote is not None and not isinstance(atom.quote, str):
        raise ValueError("quote must be a string")
    atom.source_uri = require_relative_source_uri(atom.source_uri)
    return atom


class AtomicResearchLedger:
    def __init__(self, run_id: str, base_dir: Path = Path(".knowledge_staging")):
        self.run_id = run_id
        self.base_dir = Path(base_dir)
        reject_symlink(self.base_dir)
        if not self.base_dir.exists():
            ensure_real_dir(self.base_dir)
        elif not self.base_dir.is_dir():
            raise ContainmentError(f"not a directory: {self.base_dir}")
        self.stage_dir = ensure_real_dir(self.base_dir / run_id)
        require_inside(self.stage_dir, self.base_dir)
        self.evidence_path = self.stage_dir / "evidence.jsonl"
        self.state_path = self.stage_dir / "state.json"

    def record_atom(self, atom: EvidenceAtom) -> None:
        """Append one evidence atom under an exclusive sibling lock, then fsync.

        The lock file is evidence.jsonl.lock, next to the ledger. Writers
        block each other for the append and the fsync, then release it.
        A symlinked evidence.jsonl or lock is refused.
        """
        validate_atom(atom, self.run_id)
        reject_symlink(self.stage_dir)
        lock_path = self.evidence_path.with_name(self.evidence_path.name + ".lock")
        lock_fd = open_lock_nofollow(lock_path)
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX)
            fd = open_append_nofollow(self.evidence_path)
            try:
                os.write(fd, (atom.to_jsonl() + "\n").encode("utf-8"))
                os.fsync(fd)
            finally:
                os.close(fd)
        finally:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            os.close(lock_fd)

    def load_atoms(self) -> List[EvidenceAtom]:
        """Read atoms from disk. A symlink or an invalid atom fails closed."""
        if os.path.islink(self.evidence_path):
            raise ContainmentError(f"refusing symlinked output: {self.evidence_path}")
        if not self.evidence_path.exists():
            return []
        atoms = []
        for line in read_text_nofollow(self.evidence_path).splitlines():
            if not line.strip():
                continue
            data = json.loads(line)
            if not isinstance(data, dict):
                raise ValueError("atom must be a JSON object")
            atoms.append(validate_atom(EvidenceAtom(**data), self.run_id))
        return atoms

    def save_state(self, state: Dict[str, Any]) -> None:
        """Save state machine cursor for idempotent resume."""
        payload = json.dumps(state, indent=2, ensure_ascii=False).encode("utf-8")
        atomic_write(self.stage_dir, self.state_path.name, payload)

    def load_state(self) -> Dict[str, Any]:
        """Load state machine cursor. A symlinked state.json is refused."""
        if os.path.islink(self.state_path):
            raise ContainmentError(f"refusing symlinked output: {self.state_path}")
        if not self.state_path.exists():
            return {
                "run_id": self.run_id,
                "round": 0,
                "status": "RUNNING",
                "budget_used": 0,
                "gaps": [],
            }
        return json.loads(read_text_nofollow(self.state_path))
