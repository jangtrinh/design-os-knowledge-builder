"""Freeze one web page as plain text under a run's sources/ directory.

The quote in an evidence atom must come from this file, not from a summary.
The request asks for identity encoding; a gzip body is decoded anyway because
some servers compress regardless. An existing file is never overwritten.
"""

import gzip
import hashlib
import html
import os
import re
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

from knowledge_builder.containment import ContainmentError, ensure_real_dir, require_inside

MIN_CHARS = 200
STEM = re.compile(r"[a-z0-9][a-z0-9-]*")
_SKIP = {"script", "style", "noscript", "svg", "head"}
_BLOCK = {
    "p", "div", "li", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "br", "pre",
    "section", "article", "td", "th", "dt", "dd",
}


class FreezeError(Exception):
    """The page could not be frozen. Nothing was written."""


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in _SKIP:
            self.skip_depth += 1
        elif tag in _BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in _SKIP and self.skip_depth:
            self.skip_depth -= 1
        elif tag in _BLOCK:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.skip_depth:
            self.parts.append(data)


def page_text(raw_html):
    parser = _TextExtractor()
    parser.feed(raw_html)
    text = html.unescape("".join(parser.parts))
    lines = [re.sub(r"[ \t ]+", " ", line).strip() for line in text.split("\n")]
    return "\n".join(line for line in lines if line)


def fetch_html(url):
    if not url.startswith(("http://", "https://")):
        raise FreezeError(f"--freeze needs an http or https url: {url}")
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh) knowledge-builder-freeze",
            "Accept-Encoding": "identity",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            blob = resp.read()
    except OSError as exc:
        raise FreezeError(f"could not fetch {url}: {exc}") from exc
    if blob[:2] == b"\x1f\x8b":
        try:
            blob = gzip.decompress(blob)
        except (OSError, EOFError) as exc:
            raise FreezeError(f"could not decompress {url}: {exc}") from exc
    return blob.decode("utf-8", errors="replace")


def freeze_web_source(url, root, run_id, stem, run_dir):
    """Write <run_dir>/sources/<stem>.txt and return (relative path, sha256, chars)."""
    if STEM.fullmatch(stem or "") is None:
        raise FreezeError("--stem must be kebab-case: lowercase letters, digits, hyphens")
    body = page_text(fetch_html(url))
    if len(body) < MIN_CHARS:
        raise FreezeError(
            f"extracted only {len(body)} chars from {url}; page is likely client-rendered, pick another source"
        )
    fetched = datetime.now(timezone.utc).isoformat(timespec="seconds")
    payload = f"Source-URL: {url}\nFetched: {fetched}\n\n{body}\n".encode("utf-8")
    try:
        sources = ensure_real_dir(Path(run_dir) / "sources")
        require_inside(sources, Path(root))
    except ContainmentError as exc:
        raise FreezeError(str(exc)) from exc
    target = sources / f"{stem}.txt"
    try:
        fd = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o644)
    except FileExistsError:
        raise FreezeError(f"refusing to overwrite frozen source {target}") from None
    except OSError as exc:
        raise FreezeError(f"refusing output {target}: {exc}") from exc
    try:
        view = memoryview(payload)
        while view:
            view = view[os.write(fd, view):]
        os.fsync(fd)
    finally:
        os.close(fd)
    return f"_evidence/{run_id}/sources/{stem}.txt", hashlib.sha256(payload).hexdigest(), len(body)
