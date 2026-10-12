"""Gap report over evidence atoms.

Names three holes: no FAILURE_MODE atom, no BENCHMARK atom, and a
verified_by_code atom whose metadata.command is missing. There is no
council_pass. The stopping gate does not read this report.
"""

from typing import Any, Dict, List


def _as_mapping(atom: Any) -> Dict[str, Any]:
    if isinstance(atom, dict):
        metadata = atom.get("metadata")
        return {
            "id": atom.get("id"),
            "claim_type": atom.get("claim_type"),
            "verified_by_code": bool(atom.get("verified_by_code", False)),
            "metadata": metadata if isinstance(metadata, dict) else {},
        }
    metadata = getattr(atom, "metadata", None)
    return {
        "id": getattr(atom, "id", None),
        "claim_type": getattr(atom, "claim_type", None),
        "verified_by_code": bool(getattr(atom, "verified_by_code", False)),
        "metadata": metadata if isinstance(metadata, dict) else {},
    }


def _command(atom: Dict[str, Any]):
    command = atom["metadata"].get("command")
    if isinstance(command, str) and command.strip():
        return command
    return None


def run_council_audit(claims: List[Any], license_name: str = "MIT") -> Dict[str, Any]:
    """List gaps. license_name is ignored, so a non-GPL license cannot pass."""
    del license_name
    atoms = [_as_mapping(claim) for claim in claims]
    gaps: List[Dict[str, Any]] = []
    if not any(atom["claim_type"] == "FAILURE_MODE" for atom in atoms):
        gaps.append({"name": "FAILURE_MODE", "detail": "missing FAILURE_MODE"})
    if not any(atom["claim_type"] == "BENCHMARK" for atom in atoms):
        gaps.append({"name": "BENCHMARK", "detail": "missing BENCHMARK"})
    for atom in atoms:
        if not atom["verified_by_code"] or _command(atom) is not None:
            continue
        gap = {
            "name": "verified_by_code",
            "detail": "missing a command on a verified_by_code atom",
        }
        if atom["id"]:
            gap["atom_id"] = atom["id"]
        gaps.append(gap)
    return {"gaps": gaps}
