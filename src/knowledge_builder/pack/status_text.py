"""One-screen text rendering of a pack status report."""


def status_text(report):
    objects, claims, gate = report["objects"], report["claims"], report["gate"]
    kinds = ", ".join(f"{name} {count}" for name, count in objects["by_type"].items()) or "none"
    lines = [
        f"pack: {report['topic'] or '(no topic)'}   run: {report['run'] or '(none)'}   root: {report['root']}",
        f"objects: {objects['total']} ({kinds})",
        "status:  " + (", ".join(f"{name} {count}" for name, count in objects["by_status"].items()) or "none"),
        f"claims: {claims['count']}  with 2+ sources: {claims['with_2_sources_by_file']} by file, {claims['with_2_publishers']} by publisher",
        f"duplicate statements: {len(claims['duplicate_statements'])}",
        f"unpromoted atoms: {_value(report['unpromoted_atoms'])}",
        f"uncited claims: {report['uncited_claims']}",
        f"documents without claims: {report['documents_without_claims']}",
        f"derived blocks: {report['derived_blocks']}",
        f"verify --claims failures: {report['verify']['failures']}",
    ]
    for item in report["deprecated_claims_cited"]:
        lines.append(f"deprecated claim {item['claim']} (use {item['superseded_by']}) still cited by: {', '.join(item['documents'])}  (re-link or re-word)")
    lines.append(f"gate: {_value(gate['decision'])} - {gate['reason']}")
    saturation = report["saturation"]
    if saturation is None:
        lines.append("saturation: n/a")
    else:
        rounds = "; ".join(f"r{r['round']} {r['novel']}/{r['atoms']} novel" for r in saturation["rounds"]) or "no atoms"
        lines.append(f"saturation (material): {rounds}; low-delta rounds {saturation['consecutive_low_delta_rounds']}")
    return "\n".join(lines)


def _value(value):
    return "n/a" if value is None else str(value)
