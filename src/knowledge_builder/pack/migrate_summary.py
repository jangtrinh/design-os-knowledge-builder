"""One-screen summary printed after `pack migrate --plan`."""

from knowledge_builder.pack.migrate_check import _needs


def plan_text(path, plan):
    anchors, sources = plan["anchors"], plan["sources"]
    needs = [value for _where, value in _needs(plan)]
    lines = [
        f"[✓] plan written: {path}",
        f"modules {len(plan['modules'])}, distinct anchors {len(anchors)} ({sum(1 for a in anchors if a['backfill'])} without an exact atom: backfilled), "
        f"source files {len(sources)} ({sum(1 for s in sources if s['used'])} cited), contradictions {len(plan['contradictions'])}, skipped atoms {len(plan['skipped_atoms'])}",
    ]
    for name in sorted(set(needs)):
        lines.append(f"  {name}: {needs.count(name)} to fill")
    lines.append(f"next: fill every NEEDS_* value in the plan, then `pack migrate --to {path.parent} --apply {path}`")
    return "\n".join(lines)
