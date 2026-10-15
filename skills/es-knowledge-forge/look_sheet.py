"""HTML for the look sheet: one self-contained 1440px page, no external requests, no scripts."""
import html
import sys

sys.dont_write_bytecode = True
WIDTH = 1440
MAX_ROWS = 24

CSS = """
:root{--bg:#ffffff;--ink:#14171c;--mute:#5b6472;--line:#d9dde3;--panel:#f5f7fa;--ok:#14663b;--warn:#8a5300;--bad:#a12020}
@media (prefers-color-scheme: dark){:root{--bg:#14171c;--ink:#e8ebf0;--mute:#9aa4b2;--line:#2c323b;--panel:#1c2128;--ok:#6fcf97;--warn:#f2c94c;--bad:#ff8a8a}}
*{box-sizing:border-box}body{margin:0;padding:32px 40px;background:var(--bg);color:var(--ink);font:15px/1.45 -apple-system,"Segoe UI",Helvetica,Arial,sans-serif}
h1{margin:0 0 4px;font-size:24px}h2{margin:28px 0 10px;font-size:13px;letter-spacing:.08em;text-transform:uppercase;color:var(--mute)}
.sub{color:var(--mute);font-size:13px;word-break:break-all}.gate{margin-top:16px;padding:12px 16px;border:1px solid var(--line);border-radius:8px;background:var(--panel)}
.gate b{font-size:16px}.flow{display:flex;align-items:stretch;gap:12px;margin-top:8px}
.flow div.n{flex:1;padding:14px 16px;border:1px solid var(--line);border-radius:8px;background:var(--panel)}
.flow div.n span{display:block;font-size:34px;font-weight:600}.flow div.n small{color:var(--mute);text-transform:uppercase;letter-spacing:.08em;font-size:12px}
.flow i{align-self:center;color:var(--mute);font-style:normal;font-size:22px}
.cols{display:grid;grid-template-columns:1fr 1fr;gap:32px}table{width:100%;border-collapse:collapse;font-size:14px}
th,td{text-align:left;padding:6px 10px;border-bottom:1px solid var(--line)}th{color:var(--mute);font-weight:500}td.num{text-align:right;font-variant-numeric:tabular-nums}
.ok{color:var(--ok)}.warn{color:var(--warn)}.bad{color:var(--bad)}ul{margin:0;padding-left:20px}
"""


def esc(value):
    return html.escape(str(value), quote=True)


def counts_rows(status):
    claims, objects = status["claims"], status["objects"]
    rows = [(f"objects: {name}", count, "") for name, count in objects["by_type"].items()]
    rows += [
        ("claims with 2+ publishers", claims["with_2_publishers"], ""),
        ("duplicate statements", len(claims["duplicate_statements"]), "bad" if claims["duplicate_statements"] else ""),
        ("uncited claims", status["uncited_claims"], "bad" if status["uncited_claims"] else "ok"),
        ("documents without claims", status["documents_without_claims"], "bad" if status["documents_without_claims"] else "ok"),
        ("unpromoted atoms", "n/a" if status["unpromoted_atoms"] is None else status["unpromoted_atoms"], ""),
        ("derived blocks", status["derived_blocks"], ""),
        ("verify --claims failures", status["verify"]["failures"], "bad" if status["verify"]["failures"] else "ok"),
    ]
    return "".join(f'<tr><td>{esc(a)}</td><td class="num {c}">{esc(b)}</td></tr>' for a, b, c in rows)


def table(head, rows, empty):
    if not rows:
        return f'<p class="sub">{esc(empty)}</p>'
    numeric = [all(isinstance(row[i], int) for row in rows) for i in range(len(head))]
    body = "".join("<tr>" + "".join(f'<td class="{"num" if numeric[i] else ""}">{esc(cell)}</td>' for i, cell in enumerate(row)) + "</tr>" for row in rows)
    cells = "".join(f'<th class="{"num" if numeric[i] else ""}">{esc(name)}</th>' for i, name in enumerate(head))
    return f"<table><tr>{cells}</tr>{body}</table>"


def sheet_html(status, graph):
    gate = status["gate"]
    saturation = status["saturation"]
    sat = "n/a" if saturation is None else "; ".join(f"r{r['round']} {r['novel']}/{r['atoms']} novel" for r in saturation["rounds"]) or "no atoms"
    warnings = [f"publisher {c['publisher']} appears as {', '.join(c['kinds'])}: pick one kind" for c in status["publisher_kind_conflicts"]]
    warnings += [f"deprecated claim {d['claim']} still cited by {', '.join(d['documents'])}" for d in status["deprecated_claims_cited"]]
    docs = graph["documents"]
    shown = docs[:MAX_ROWS]
    more = f'<p class="sub">… {len(docs) - MAX_ROWS} more documents not shown</p>' if len(docs) > MAX_ROWS else ""
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>knowledge pack look sheet</title>
<meta name="viewport" content="width=device-width,initial-scale=1"><style>{CSS}</style></head><body>
<h1 id="topic">{esc(status['topic'] or '(no topic)')}</h1>
<div class="sub">run {esc(status['run'])} · {esc(status['root'])}</div>
<div class="gate"><b id="gate">gate: {esc(gate['decision'] or 'n/a')}</b><div class="sub">{esc(gate['reason'])}</div><div class="sub">saturation (material): {esc(sat)}</div></div>
<h2>Pipeline</h2>
<div class="flow"><div class="n"><span id="n-documents">{len(docs)}</span><small>documents</small></div><i>→</i>
<div class="n"><span id="n-claims">{graph['cited_claims']}</span><small>cited claims</small></div><i>→</i>
<div class="n"><span id="n-sources">{graph['sources']}</span><small>sources</small></div><i>·</i>
<div class="n"><span id="n-entities">{len(graph['entities'])}</span><small>entities</small></div></div>
<div class="cols"><div><h2>Counts</h2><table>{counts_rows(status)}</table></div>
<div><h2>Entities</h2>{table(['entity', 'type', 'documents about it'], graph['entities'], 'no entities')}
<h2>Warnings</h2>{('<ul>' + ''.join(f'<li class="warn">{esc(w)}</li>' for w in warnings) + '</ul>') if warnings else '<p class="sub">none</p>'}</div></div>
<h2>Documents → claims → sources</h2>{table(['document', 'type', 'claims cited', 'sources reached'], shown, 'no documents')}{more}
</body></html>"""
