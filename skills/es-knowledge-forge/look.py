"""Render a pack's status and graph summary to ONE sheet PNG with headless Chrome/Chromium; print machine items.

Exit 0 all machine items pass / 1 any machine item fails / 2 could not run (no browser, no pack, no product).
Writes only the sheet (default: a new temp directory) and a temp profile; installs nothing, no network.
"""
import argparse
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
from forge_common import CannotRun, product_src, run_cli  # noqa: E402
from look_sheet import MAX_ROWS, WIDTH, sheet_html  # noqa: E402

MIN_SHEET_BYTES = 10_000
NAMES = ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome", "microsoft-edge")
APPS = (
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "/usr/bin/google-chrome", "/usr/bin/chromium", "/usr/bin/chromium-browser", "/snap/bin/chromium",
)


def find_browser(explicit):
    for candidate in (explicit, os.environ.get("CHROME_BIN")):
        if candidate:
            if Path(candidate).is_file():
                return str(candidate)
            raise CannotRun(f"browser {candidate} is not a file")
    for name in NAMES:
        found = shutil.which(name)
        if found:
            return found
    for path in APPS:
        if Path(path).is_file():
            return path
    raise CannotRun("no browser: install Chrome or Chromium, or pass --browser / set CHROME_BIN")


def graph_summary(index):
    """Documents, cited claims, sources and entities counted from index.json links."""
    rows = {row["id"]: row for row in index}
    out_links = lambda row, kind: [link["target_id"] for link in row.get("links_out", []) if link["link_type"] == kind]  # noqa: E731
    documents, cited, sources, entities = [], set(), set(), {}
    for row in index:
        claims = out_links(row, "cites")
        if not claims:
            continue
        reached = {s for claim in claims if claim in rows for s in out_links(rows[claim], "supported-by")}
        documents.append((row["id"], row.get("object_type"), len(set(claims)), len(reached)))
        cited.update(claims)
        sources.update(reached)
    for row in index:
        for target in out_links(row, "about"):
            entities.setdefault(target, set()).add(row["id"])
    entity_rows = [(i, (rows.get(i) or {}).get("object_type", "?"), len(docs)) for i, docs in sorted(entities.items())]
    return {"documents": sorted(documents), "cited_claims": len(cited), "sources": len(sources), "entities": entity_rows}


def screenshot(browser, html_path, sheet, height):
    with tempfile.TemporaryDirectory() as profile:
        cmd = [browser, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=1",
               *(["--no-sandbox"] if hasattr(os, "geteuid") and os.geteuid() == 0 else []),
               f"--window-size={WIDTH},{height}", f"--user-data-dir={profile}", f"--screenshot={sheet}", html_path.as_uri()]
        done = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
    if not Path(sheet).is_file():
        raise CannotRun(f"browser produced no screenshot (exit {done.returncode}): {done.stderr.strip()[-200:]}")


def png_width(path):
    head = Path(path).read_bytes()[:24]
    if head[:8] != b"\x89PNG\r\n\x1a\n" or head[12:16] != b"IHDR":
        return None
    return struct.unpack(">I", head[16:20])[0]


def machine_items(status, graph, html_text, sheet, indexed):
    size, width = Path(sheet).stat().st_size, png_width(sheet)
    cited_expected = status["claims"]["count"] - status["uncited_claims"]
    external = re.findall(r'(?:src|href)=["\']https?:|url\(\s*["\']?https?:', html_text)
    return [
        ("L1", width == WIDTH and size >= MIN_SHEET_BYTES, f"sheet PNG width {width}, {size} bytes (need {WIDTH} wide, >= {MIN_SHEET_BYTES})"),
        ("L2", status["objects"]["total"] == indexed, f"sheet objects {status['objects']['total']} vs index.json entries {indexed}"),
        ("L3", graph["cited_claims"] == cited_expected, f"index cites reach {graph['cited_claims']} claims vs status claims - uncited = {cited_expected}"),
        ("L4", not external, f"{len(external)} external reference(s) in the sheet HTML"),
    ]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", required=True, type=Path, help="Pack root")
    parser.add_argument("--run", default=None, help="Run id (default: pack.json)")
    parser.add_argument("--sheet", type=Path, default=None, help="Output PNG (default: new temp directory)")
    parser.add_argument("--browser", default=None, help="Chrome/Chromium executable (default: CHROME_BIN, PATH, standard app paths)")
    parser.add_argument("--repo-root", type=Path, default=None, help="knowledge-builder checkout (default: this repo or the installed package)")
    args = parser.parse_args()
    root = args.root.expanduser().resolve()
    try:
        if not (root / "ontology.yaml").is_file() or not (root / "index.json").is_file():
            raise CannotRun(f"{root} needs ontology.yaml and index.json (run `knowledge-builder index --root`)")
        browser = find_browser(args.browser)
        done = run_cli(product_src(args.repo_root), ["pack", "status", "--root", root, "--json", *(["--run", args.run] if args.run else [])])
        if done.returncode != 0:
            raise CannotRun(done.stderr.strip() or "pack status failed")
        status = json.loads(done.stdout)
        index = json.loads((root / "index.json").read_text(encoding="utf-8"))
        graph = graph_summary(index)
        sheet = (args.sheet or Path(tempfile.mkdtemp(prefix="knowledge-look-")) / "look-sheet.png").expanduser().resolve()
        sheet.parent.mkdir(parents=True, exist_ok=True)
        text = sheet_html(status, graph)
        with tempfile.TemporaryDirectory() as work:
            page = Path(work) / "sheet.html"
            page.write_text(text, encoding="utf-8")
            side = max(len(status["objects"]["by_type"]) + 7, len(graph["entities"]) + 3)
            screenshot(browser, page, sheet, 560 + 34 * (side + min(len(graph["documents"]), MAX_ROWS)))
        items = machine_items(status, graph, text, sheet, len(index))
    except (CannotRun, OSError, ValueError, KeyError, subprocess.TimeoutExpired) as exc:
        print(f"runtime: could not run: {exc}", file=sys.stderr)
        return 2
    for name, passed, detail in items:
        print(f"{name} {'ok' if passed else 'FAIL'}: {detail}")
    print(f"sheet: {sheet}")
    return 0 if all(passed for _n, passed, _d in items) else 1


if __name__ == "__main__":
    raise SystemExit(main())
