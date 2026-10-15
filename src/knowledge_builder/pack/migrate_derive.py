"""pack migrate --plan: values the plan derives from the legacy ledger and modules (ids, backfill atoms, sources)."""

from collections import Counter

from knowledge_builder.ontology.claim_state import host_of, slug
from knowledge_builder.ontology.hosting_hosts import is_hosting_host
from knowledge_builder.ontology.source_checks import LOCAL_PUBLISHER
from knowledge_builder.pack.init_pack import PackError

NEEDS_KIND, NEEDS_PUBLISHER, NEEDS_CONTRADICTS = "NEEDS_KIND", "NEEDS_PUBLISHER", "NEEDS_CONTRADICTS"


def flat_atoms(runs):
    """Every legacy atom, ledger order. An id must be unique across the legacy runs."""
    seen, atoms = {}, []
    for run, data in runs.items():
        for atom in data["atoms"]:
            if atom["id"] in seen:
                raise PackError(f"atom id {atom['id']} is in runs {seen[atom['id']]} and {run}: ids must be unique across the legacy runs")
            seen[atom["id"]] = run
            atoms.append(atom)
    return atoms


def free_id(taken, prefix="bf-"):
    number = 1
    while f"{prefix}{number:03d}" in taken:
        number += 1
    taken.add(f"{prefix}{number:03d}")
    return f"{prefix}{number:03d}"


def _most_common(values, default):
    values = [v for v in values if v]
    return Counter(values).most_common(1)[0][0] if values else default


def backfill(hit, siblings, capture):
    """The atom an anchor without an exact atom gets. siblings are the legacy atoms on the same capture file."""
    coded = next((a for a in siblings if a.get("verified_by_code") is True and (a.get("metadata") or {}).get("command")), None)
    return {
        "statement": hit["above"] or hit["quote"],
        "claim_type": "FAILURE_MODE" if hit["heading"].startswith("## Failure Modes") else "FACT",
        "confidence": _most_common([a.get("confidence") for a in siblings], "HIGH"),
        "claim": _most_common([(a.get("metadata") or {}).get("claim") for a in siblings], None),
        "verified_by_code": coded is not None,
        "command": coded["metadata"]["command"] if coded else None,
        "captured_at": capture["fetched"] or _most_common([a.get("captured_at") for a in siblings], None),
    }


def assign_claim_ids(anchors, taken, atoms):
    """claim_id for every anchor: a kebab slug of the atom statement, unique among claims and module ids."""
    taken, statements = set(taken), {a["id"]: a["statement"] for a in atoms if isinstance(a.get("statement"), str)}
    for anchor in anchors:
        text = anchor["backfill"]["statement"] if anchor["backfill"] else statements.get(anchor["atom"], anchor["quote"])
        base, number = slug(text, 60) or "claim", 1
        ident = base
        while ident in taken:
            number += 1
            ident = f"{base}-{number}"
        taken.add(ident)
        anchor["claim_id"] = ident


def source_entry(uri, item, target, used):
    """A plan row for one captured file. A hosting host, or no url at all, never names the publisher."""
    url = item["url"]
    if url and "://" in url:
        host = host_of(url)
        publisher = NEEDS_PUBLISHER if not host or is_hosting_host(host) else host
    else:
        publisher = LOCAL_PUBLISHER if url else NEEDS_PUBLISHER  # a name like `local-execution` is not a web publisher
    return {"legacy_uri": uri, "evidence_uri": target, "sha256": item["sha256"], "url": url, "publisher": publisher, "kind": NEEDS_KIND, "used": used}


def contradiction_rows(anchors, atoms, runs):
    """One row per promoted CONTRADICTION atom: its partner (or a placeholder) and the legacy resolution note."""
    by_id, notes, found = {a["id"]: a for a in atoms}, {}, []
    for data in runs.values():
        notes.update(data["state"].get("resolution_notes") or {})
    for anchor in anchors:
        atom = by_id.get(anchor["atom"])
        if atom and atom.get("claim_type") == "CONTRADICTION":
            other = (atom.get("metadata") or {}).get("contradicts")
            found.append({"atom": atom["id"], "contradicts": other if isinstance(other, str) and other else NEEDS_CONTRADICTS, "resolution": notes.get(atom["id"])})
    return found
