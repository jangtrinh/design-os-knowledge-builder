"""Freeze one web page as plain text under a run's sources/ directory.

The quote in an evidence atom must come from this file, not from a summary.
The request asks for identity encoding; a gzip body is decoded anyway because
some servers compress regardless. An existing file is never overwritten.
"""

import gzip
import hashlib
import html
import io
import os
import re
import stat
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

from knowledge_builder.containment import ContainmentError, read_text_nofollow


MIN_CHARS = 200
_BOT_STATUS_CODES = {401, 403, 429}
_BOT_FALLBACK_HINT = (
    "site blocks automated fetch; save the page from a browser and re-run with "
    "--from-file <saved.html>, or copy plain text into _evidence/<run>/sources/<stem>.txt"
)
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


class _HttpOnlyRedirect(urllib.request.HTTPRedirectHandler):
    """Check the scheme of every redirect before it is followed."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        scheme = urllib.parse.urlsplit(newurl).scheme.lower()
        if scheme not in ("http", "https"):
            raise FreezeError(f"refusing redirect to a non-http(s) url: {newurl}")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_MAX_BYTES = 10 * 1024 * 1024


def _validate_url(url):
    if not isinstance(url, str) or any(ch in url for ch in ("\r", "\n", "\t", " ")):
        raise FreezeError(f"--freeze needs an http or https url without whitespace: {url!r}")
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme.lower() not in ("http", "https") or not parsed.netloc or not parsed.hostname:
        raise FreezeError(f"--freeze needs an http or https url: {url}")
    return url


def fetch_html(url):
    _validate_url(url)
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh) knowledge-builder-freeze",
            "Accept-Encoding": "identity",
        },
    )
    try:
        with urllib.request.build_opener(_HttpOnlyRedirect).open(req, timeout=30) as resp:
            blob = resp.read(_MAX_BYTES + 1)
    except urllib.error.HTTPError as exc:
        code = exc.code
        exc.close()
        if code in _BOT_STATUS_CODES:
            raise FreezeError(f"could not fetch {url}: {exc} ({_BOT_FALLBACK_HINT})") from exc
        raise FreezeError(f"could not fetch {url}: {exc}") from exc
    except OSError as exc:
        raise FreezeError(f"could not fetch {url}: {exc}") from exc
    if len(blob) > _MAX_BYTES:
        raise FreezeError(f"response from {url} exceeds {_MAX_BYTES} bytes")
    if blob[:2] == b"\x1f\x8b":
        try:
            with gzip.GzipFile(fileobj=io.BytesIO(blob)) as gz:
                blob = gz.read(_MAX_BYTES + 1)
        except (OSError, EOFError) as exc:
            raise FreezeError(f"could not decompress {url}: {exc}") from exc
        if len(blob) > _MAX_BYTES:
            raise FreezeError(f"decompressed response from {url} exceeds {_MAX_BYTES} bytes")
    return blob.decode("utf-8", errors="replace")


def read_local_html(from_file):
    path = Path(from_file)
    try:
        info = os.lstat(path)
    except OSError as exc:
        raise FreezeError(f"could not read --from-file {from_file}: {exc}") from exc
    if stat.S_ISLNK(info.st_mode):
        raise FreezeError(f"could not read --from-file {from_file}: refusing symlinked file")
    if not stat.S_ISREG(info.st_mode):
        raise FreezeError(f"could not read --from-file {from_file}: not a regular file")
    if info.st_size > _MAX_BYTES:
        raise FreezeError(f"could not read --from-file {from_file}: exceeds {_MAX_BYTES} bytes")
    try:
        return read_text_nofollow(path)
    except (ContainmentError, OSError, UnicodeError) as exc:
        raise FreezeError(f"could not read --from-file {from_file}: {exc}") from exc


def _open_dir(name, dir_fd=None):
    flags = os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_DIRECTORY", 0)
    return os.open(name, flags, dir_fd=dir_fd)


def _open_run_sources(root, run_id):
    """Descriptor of _evidence/<run>/sources, walked one name at a time with no symlink followed.

    The returned descriptor names the directory inode itself, so a later swap
    of any path component cannot redirect a write made through it.
    """
    if run_id in {"", ".", ".."} or "/" in run_id or "\\" in run_id:
        raise FreezeError(f"run id is not a single path segment: {run_id}")
    fds = []
    try:
        try:
            fds.append(_open_dir(os.path.realpath(root)))
            fds.append(_open_dir("_evidence", fds[-1]))
            fds.append(_open_dir(run_id, fds[-1]))
            info = os.stat("state.json", dir_fd=fds[-1], follow_symlinks=False)
        except FileNotFoundError:
            raise FreezeError(f"run is not initialized: {run_id}") from None
        except OSError as exc:
            raise FreezeError(f"refusing symlinked or non-directory output for run {run_id}: {exc}") from exc
        if not stat.S_ISREG(info.st_mode):
            raise FreezeError(f"run is not initialized: {run_id}")
        return fds.pop(), fds
    except BaseException:
        for fd in fds:
            os.close(fd)
        raise


def _open_sources(run_fd):
    try:
        try:
            return _open_dir("sources", run_fd)
        except FileNotFoundError:
            os.mkdir("sources", 0o755, dir_fd=run_fd)
            return _open_dir("sources", run_fd)
    except OSError as exc:
        raise FreezeError(f"refusing sources directory: {exc}") from exc


def freeze_web_source(url, root, run_id, stem, from_file=None):
    """Write _evidence/<run>/sources/<stem>.txt and return (relative path, sha256, chars).

    The run directory is pinned before the fetch and written through that
    descriptor, so the destination cannot move while the page downloads.
    """
    if STEM.fullmatch(stem or "") is None:
        raise FreezeError("--stem must be kebab-case: lowercase letters, digits, hyphens")
    _validate_url(url)
    run_fd, extra = _open_run_sources(root, run_id)
    sources_fd = None
    try:
        raw_html = read_local_html(from_file) if from_file is not None else fetch_html(url)
        body = page_text(raw_html)
        if len(body) < MIN_CHARS:
            raise FreezeError(
                f"extracted only {len(body)} chars from {url}; page is likely client-rendered, pick another source"
            )
        fetched = datetime.now(timezone.utc).isoformat(timespec="seconds")
        payload = f"Source-URL: {url}\nFetched: {fetched}\n\n{body}\n".encode("utf-8")
        sources_fd = _open_sources(run_fd)
        name = f"{stem}.txt"
        try:
            fd = os.open(name, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o644, dir_fd=sources_fd)
        except FileExistsError:
            raise FreezeError(f"refusing to overwrite frozen source {name}") from None
        except OSError as exc:
            raise FreezeError(f"refusing output {name}: {exc}") from exc
        try:
            view = memoryview(payload)
            while view:
                view = view[os.write(fd, view):]
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        for descriptor in [run_fd, sources_fd, *extra]:
            if descriptor is not None:
                os.close(descriptor)
    return f"_evidence/{run_id}/sources/{name}", hashlib.sha256(payload).hexdigest(), len(body)
