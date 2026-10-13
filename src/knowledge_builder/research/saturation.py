"""`run measure`: per-round novelty from the ledger. Reads; writes only with --write-state.

An atom belongs to round metadata.round (none means round 1). It is novel when
metadata.novel is true. delta(round r) = novel atoms in r / atoms before r. The
first round present is the baseline and has no delta. With --material an atom
counts as novel only when its quote is cited by an ease:source anchor in a
module under the root, so it changed a claim, a failure mode, or a Decision.
"""

import re
from collections import defaultdict
from pathlib import Path

from knowledge_builder.anchors import AnchorSyntaxError, parse_attributes, tokenize_document
from knowledge_builder.containment import ContainmentError, read_text_inside
from knowledge_builder.quote_check import normalise_newlines
from knowledge_builder.research.ledger import AtomicResearchLedger

THRESHOLD = 0.02
_ANCHOR_PREFIX = re.compile(r"\s*ease:source\b")


def validate_round_metadata(metadata):
    """round is an integer >= 1 and novel is a boolean, when present."""
    if not isinstance(metadata, dict):
        return
    if "round" in metadata:
        value = metadata["round"]
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise ValueError("metadata.round must be an integer >= 1")
    if "novel" in metadata and not isinstance(metadata["novel"], bool):
        raise ValueError("metadata.novel must be a boolean")


def register_measure(commands):
    measure = commands.add_parser("measure", help="Per-round novelty delta from the ledger")
    measure.add_argument("--root", required=True, help="External knowledge repository root")
    measure.add_argument("--id", required=True, help="Run id")
    measure.add_argument(
        "--material",
        action="store_true",
        help="Count only novel atoms whose quote an anchor in a module cites",
    )
    measure.add_argument(
        "--write-state",
        action="store_true",
        help="Write consecutive_low_delta_rounds and last_weighted_delta into state.json",
    )
    measure.set_defaults(func=cmd_run_measure)


def cited_quotes(root):
    """Quotes of every top-level anchor in the modules under root."""
    from knowledge_builder.verify import _markdown_files

    root = Path(root).resolve()
    files, _errors = _markdown_files(root)
    quotes = set()
    for path in files:
        try:
            text = read_text_inside(path, root)
        except (ContainmentError, OSError, UnicodeError):
            continue
        for token in tokenize_document(text):
            if token.kind != "anchor":
                continue
            try:
                attrs = parse_attributes(_ANCHOR_PREFIX.sub("", token.text, count=1))
            except AnchorSyntaxError:
                continue
            quote = attrs.get("quote")
            if isinstance(quote, str) and quote.strip():
                quotes.add(normalise_newlines(quote))
    return quotes


def measure_rounds(atoms, cited=None):
    """([(round, atoms, novel, before, delta)], trailing_low_rounds, last_delta)."""
    groups = defaultdict(list)
    for atom in atoms:
        meta = atom.metadata if isinstance(atom.metadata, dict) else {}
        rnd = meta.get("round")
        rnd = rnd if isinstance(rnd, int) and not isinstance(rnd, bool) and rnd >= 1 else 1
        novel = meta.get("novel") is True
        if novel and cited is not None:
            quote = atom.quote if isinstance(atom.quote, str) else ""
            novel = bool(quote.strip()) and normalise_newlines(quote) in cited
        groups[rnd].append(novel)
    rows = []
    before = 0
    trailing = 0
    last = None
    for index, rnd in enumerate(sorted(groups)):
        flags = groups[rnd]
        novel = sum(flags)
        delta = None if index == 0 else novel / before
        if delta is None or delta > THRESHOLD:
            trailing = 0
        else:
            trailing += 1
        if delta is not None:
            last = delta
        rows.append((rnd, len(flags), novel, before, delta))
        before += len(flags)
    return rows, trailing, last


def cmd_run_measure(args):
    from knowledge_builder.research.run_state import load_run_state, save_run_state
    from knowledge_builder.research.run_driver import _fail

    ledger, state = load_run_state(args.root, args.id)
    try:
        atoms = ledger.load_atoms()
    except (ContainmentError, OSError, ValueError) as exc:
        _fail(f"unreadable ledger: {exc}")
    cited = cited_quotes(args.root) if args.material else None
    rows, trailing, last = measure_rounds(atoms, cited)
    for rnd, count, novel, before, delta in rows:
        shown = "n/a (baseline)" if delta is None else f"{delta:.4f}"
        print(f"round {rnd}: atoms {count}, novel {novel}, before {before}, delta {shown}")
    print(f"consecutive_low_delta_rounds={trailing} last_weighted_delta={last}")
    if not args.write_state:
        return
    if last is None:
        print("nothing to write: only a baseline round is recorded")
        return
    state = dict(state)
    state["consecutive_low_delta_rounds"] = trailing
    state["last_weighted_delta"] = last
    save_run_state(ledger, state)
    print("state.json updated")
