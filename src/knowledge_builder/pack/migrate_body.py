"""pack migrate: turn a v1 module body into a claim-anchored body, and list the claims it cites."""

from knowledge_builder.anchors import AnchorSyntaxError, parse_attributes
from knowledge_builder.pack.init_pack import PackError
from knowledge_builder.pack.migrate_scan import ANCHOR


def port_body(body, claim_ids, label):
    """Replace every `<!-- ease:source uri=.. quote=.. -->` with `<!-- ease:claim id=<claim id> -->`; the rest is untouched.

    claim_ids maps (legacy uri, quote) to the claim id the plan chose.
    """
    def swap(match):
        try:
            attrs = parse_attributes(match.group(1))
        except AnchorSyntaxError as exc:
            raise PackError(f"{label}: malformed ease:source anchor: {exc}") from exc
        ident = claim_ids.get((attrs.get("uri"), attrs.get("quote")))
        if ident is None:
            raise PackError(f"{label}: an anchor ({attrs.get('uri')}) is not in the plan: plan again")
        return f"<!-- ease:claim id={ident} -->"

    return ANCHOR.sub(swap, body)


def cited_in_order(ported):
    """Distinct claim ids of the ease:claim anchors in a ported body, first appearance first."""
    from knowledge_builder.ontology.claim_anchors import well_formed_ids

    return list(dict.fromkeys(well_formed_ids(ported)))
