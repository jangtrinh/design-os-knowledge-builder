"""pack status: one report dict for a pack root. Reads only; the CLI renders it as text or JSON."""

from pathlib import Path

from knowledge_builder.containment import ContainmentError
from knowledge_builder.ontology.objects import load_graph
from knowledge_builder.ontology.schema import OntologyError, load_ontology
from knowledge_builder.pack import graph_counts
from knowledge_builder.pack.init_pack import PackError, read_pack
from knowledge_builder.pack.publisher_kinds import publisher_kind_conflicts
from knowledge_builder.research.ledger import AtomicResearchLedger
from knowledge_builder.research.ledger_gate import LedgerGateError, ledger_evaluation_input
from knowledge_builder.research.saturation import cited_quotes, measure_rounds
from knowledge_builder.research.stopping_gate import evaluate_stopping_gate
from knowledge_builder.verify import verify_root


def load_pack(root):
    root = Path(root).expanduser().resolve()
    try:
        ontology = load_ontology(root)
    except OntologyError as exc:
        raise PackError(str(exc)) from exc
    if ontology is None:
        raise PackError(f"{root} has no ontology.yaml: not an ontology-first pack (run `pack init` on a new root)")
    return root, ontology, load_graph(root)


def gate_report(root, run):
    if not run:
        return {"decision": None, "reason": "no run: pass --run or add pack.json", "hard_gates_passed": None, "saturation_passed": None}
    try:
        decision = evaluate_stopping_gate(ledger_evaluation_input(root, run))
    except (LedgerGateError, ContainmentError, OSError, ValueError) as exc:
        return {"decision": None, "reason": f"not evaluated: {exc}", "hard_gates_passed": None, "saturation_passed": None}
    return {"decision": decision.state.value, "reason": decision.reason,
            "hard_gates_passed": decision.hard_gates_passed, "saturation_passed": decision.saturation_passed}


def ledger_report(root, run, promoted):
    """(unpromoted atom count or None, saturation dict or None)."""
    if not run:
        return None, None
    try:
        atoms = AtomicResearchLedger(run, base_dir=root / "_evidence").load_atoms()
    except (ContainmentError, OSError, ValueError, TypeError):
        return None, None
    rows, trailing, last = measure_rounds(atoms, cited_quotes(root))
    saturation = {
        "rounds": [{"round": r, "atoms": n, "novel": novel, "before": before, "delta": delta} for r, n, novel, before, delta in rows],
        "consecutive_low_delta_rounds": trailing,
        "last_weighted_delta": last,
        "material": True,
    }
    return len([a for a in atoms if (run, a.id) not in promoted]), saturation


def build_status(root, run=None):
    root, ontology, graph = load_pack(root)
    meta = read_pack(root)
    run = run or meta.get("run")
    _files, _anchors, failures, derived = verify_root(root, claims=True)
    promoted = {
        (e.get("run"), e.get("atom"))
        for claim in graph_counts.of_interface(ontology, graph, "evidence-claim")
        for e in claim.data.get("evidence") or [] if isinstance(e, dict)
    }
    unpromoted, saturation = ledger_report(root, run, promoted)
    return {
        "root": str(root),
        "topic": meta.get("topic"),
        "run": run,
        "objects": graph_counts.object_counts(graph),
        "claims": graph_counts.claim_figures(root, ontology, graph),
        **graph_counts.coverage(ontology, graph),
        "unpromoted_atoms": unpromoted,
        "derived_blocks": derived,
        "deprecated_claims_cited": graph_counts.deprecated_cited(ontology, graph),
        "publisher_kind_conflicts": publisher_kind_conflicts(ontology, graph),
        "verify": {"failures": len(failures)},
        "gate": gate_report(root, run),
        "saturation": saturation,
    }
