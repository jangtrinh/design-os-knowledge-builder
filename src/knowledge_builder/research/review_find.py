"""Which atoms a review must find again on the live page.

A required claim's verifying atom must be found, unless its capture was
executed. The caller already decided which captures count as executed.
"""


def must_find_atoms(root, run_id, state, atoms, rows, unattested):
    """Atom id to capture path for a required claim's verifying atom that was not executed."""
    from knowledge_builder.ontology.claim_coverage import verified_pack_claims
    from knowledge_builder.research import ledger_gate as gate
    from knowledge_builder.research.capture_log import capture_origin

    verified_ids = [atom.id for atom in atoms if gate._atom_is_verified(root, run_id, atom, rows, unattested)]
    pack = verified_pack_claims(root, run_id, verified_ids)
    if pack is None:
        wanted = [
            atom for atom in atoms
            if any(
                gate._atom_verifies_claim(root, run_id, atom, claim_id, rows, unattested)
                for claim_id in gate._required_ids(state)
            )
        ]
    else:
        wanted = _pack_wanted(root, run_id, state, atoms, rows, unattested, pack, set(verified_ids))
    found = {}
    for atom in wanted:
        rel = gate._repo_relative(atom.source_uri)
        if rel is None or capture_origin(rows, rel, atom.source_digest) == "executed":
            continue
        found[atom.id] = rel
    return found


def _pack_wanted(root, run_id, state, atoms, rows, unattested, pack, verified_set):
    from knowledge_builder.ontology.objects import load_graph
    from knowledge_builder.research import ledger_gate as gate

    active_ids, _verified_claims = pack
    required = gate._required_ids(state) or list(active_ids)
    active_set = set(active_ids)
    by_claim = {claim.id: claim for claim in load_graph(root).all}
    ids = []
    for claim_id in required:
        claim = by_claim.get(claim_id)
        if claim_id not in active_set or claim is None or not claim.data:
            continue
        for entry in claim.data.get("evidence") or []:
            if isinstance(entry, dict) and entry.get("run") == run_id and entry.get("atom") in verified_set:
                ids.append(entry["atom"])
    by_id = {atom.id: atom for atom in atoms}
    wanted = [by_id[atom_id] for atom_id in ids if atom_id in by_id]
    if state.get("required_claim_ids"):
        for claim_id in required:
            if claim_id in active_set:
                continue
            for atom in atoms:
                if gate._atom_verifies_claim(root, run_id, atom, claim_id, rows, unattested):
                    wanted.append(atom)
    return wanted
