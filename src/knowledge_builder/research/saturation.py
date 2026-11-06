"""`run measure`: per-round novelty from the ledger. Reads; writes only with --write-state.

An atom belongs to round metadata.round (none means round 1). It is novel when
its quote, after newline normalisation, did not occur on any atom of an earlier
round. Backfill atoms count as earlier quotes and are left out of the numerator
and the denominator. metadata.novel is ignored. delta(round r) = novel atoms in
r / atoms before r. The first round present is the baseline and has no delta.
A round with fewer than five non-backfill atoms is printed and does not extend
or reset the low-delta streak. With --material an atom counts as novel only
when its quote is also cited by an ease:source anchor in a module under the
root, so it changed a claim, a failure mode, or a Decision.
"""

import re
from collections import defaultdict
from pathlib import Path

from knowledge_builder.anchors import AnchorSyntaxError, parse_attributes, tokenize_document
from knowledge_builder.containment import ContainmentError, read_text_inside
from knowledge_builder.quote_check import normalise_newlines
from knowledge_builder.research.ledger import AtomicResearchLedger

THRESHOLD = 0.02
MIN_COUNTED = 5
_ANCHOR_PREFIX = re.compile(r"\s*ease:source\b")


def validate_round_metadata(metadata):
    """round is an integer >= 1; novel and backfill are booleans, when present."""
    if not isinstance(metadata, dict):
        return
    if "round" in metadata:
        value = metadata["round"]
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise ValueError("metadata.round must be an integer >= 1")
    if "novel" in metadata and not isinstance(metadata["novel"], bool):
        raise ValueError("metadata.novel must be a boolean")
    if "backfill" in metadata and not isinstance(metadata["backfill"], bool):
        raise ValueError("metadata.backfill must be a boolean")


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
    if (root / "ontology.yaml").is_file():
        from knowledge_builder.ontology.claim_quotes import cited_claim_quotes

        quotes |= cited_claim_quotes(root)
    return quotes


def is_backfill(atom):
    return isinstance(atom.metadata, dict) and atom.metadata.get("backfill") is True


def backfill_count(atoms):
    return sum(1 for atom in atoms if is_backfill(atom))


def _round_number(atom):
    meta = atom.metadata if isinstance(atom.metadata, dict) else {}
    rnd = meta.get("round")
    if isinstance(rnd, int) and not isinstance(rnd, bool) and rnd >= 1:
        return rnd
    return 1


def _quote_key(atom):
    quote = atom.quote if isinstance(atom.quote, str) else ""
    return normalise_newlines(quote)


def _novel_by_history(atoms):
    """True when the quote is absent from every earlier round, backfill included."""
    by_round = defaultdict(list)
    for atom in atoms:
        by_round[_round_number(atom)].append(atom)
    seen = set()
    novel = {}
    for rnd in sorted(by_round):
        for atom in by_round[rnd]:
            if not is_backfill(atom):
                novel[id(atom)] = _quote_key(atom) not in seen
        for atom in by_round[rnd]:
            seen.add(_quote_key(atom))
    return novel


def _cited_novel(atom, is_novel, cited):
    if not is_novel or cited is None:
        return is_novel
    quote = atom.quote if isinstance(atom.quote, str) else ""
    return bool(quote.strip()) and normalise_newlines(quote) in cited


def measure_rounds(atoms, cited=None):
    """([(round, atoms, novel, before, delta)], trailing_low_rounds, last_delta). Backfill atoms are not measured."""
    history = _novel_by_history(atoms)
    groups = defaultdict(list)
    for atom in atoms:
        if is_backfill(atom):
            continue
        groups[_round_number(atom)].append(_cited_novel(atom, history[id(atom)], cited))
    rows = []
    before = 0
    trailing = 0
    last = None
    for index, rnd in enumerate(sorted(groups)):
        flags = groups[rnd]
        novel = sum(flags)
        count = len(flags)
        delta = None if index == 0 else novel / before
        if count >= MIN_COUNTED:
            if delta is None or delta > THRESHOLD:
                trailing = 0
            else:
                trailing += 1
            if delta is not None:
                last = delta
        rows.append((rnd, count, novel, before, delta))
        before += count
    return rows, trailing, last


def _latest_round_all_novel_uncited(atoms, cited):
    """True when nothing is cited, or a counted post-baseline round has new quotes and none are cited."""
    if not cited:
        return True
    history = _novel_by_history(atoms)
    rounds = defaultdict(list)
    for atom in atoms:
        if is_backfill(atom):
            continue
        rounds[_round_number(atom)].append(atom)
    measured = sorted(rounds)
    for rnd in measured[1:]:
        group = rounds[rnd]
        if len(group) < MIN_COUNTED:
            continue
        raw_novel = [atom for atom in group if history[id(atom)]]
        if raw_novel and not any(
            isinstance(atom.quote, str) and atom.quote.strip() and normalise_newlines(atom.quote) in cited
            for atom in raw_novel
        ):
            return True
    return False


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
        suffix = f" (too small: {count} < {MIN_COUNTED}, not counted)" if count < MIN_COUNTED else ""
        print(f"round {rnd}: atoms {count}, novel {novel}, before {before}, delta {shown}{suffix}")
    if backfill_count(atoms):
        print(f"backfill atoms: {backfill_count(atoms)} (excluded)")
    print(f"consecutive_low_delta_rounds={trailing} last_weighted_delta={last}")
    if not args.write_state:
        return
    if last is None:
        print("nothing to write: only a baseline round is recorded")
        return
    if args.material and _latest_round_all_novel_uncited(atoms, cited):
        print("nothing to write: no novel atom in the measured round is cited yet for --material (cite claims in a document before writing state)")
        return
    state = dict(state)
    state["consecutive_low_delta_rounds"] = trailing
    state["last_weighted_delta"] = last
    save_run_state(ledger, state)
    print("state.json updated")
