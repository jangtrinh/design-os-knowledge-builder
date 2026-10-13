"""B4: `ingest --freeze <url>` writes the page text into a run's sources/.

A local loopback server stands in for the web. The text is plain, the request
asks for identity encoding, a gzip body is decoded anyway, an existing file is
never overwritten, and the printed sha256 is the digest of the file written.
"""

import gzip
import hashlib
import io
import socket
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest.mock import patch

PAGE = (
    "<html><head><title>T</title><style>.x{}</style><script>var a=1;</script></head>"
    "<body><h1>Heading</h1><p>First paragraph with enough words to be real content here.</p>"
    "<p>Second paragraph &amp; more text that goes on and on for a while so it is long.</p>"
    "<ul><li>item one of the list</li><li>item two of the list</li></ul>"
    "<p>" + ("Filler sentence to pass the minimum length check. " * 6) + "</p></body></html>"
)
SEEN = {}


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        SEEN["accept-encoding"] = self.headers.get("Accept-Encoding")
        if self.path.startswith("/redirect-to/"):
            self.send_response(302)
            self.send_header("Location", self.path[len("/redirect-to/"):])
            self.end_headers()
            return
        if self.path == "/small":
            body = b"<html><body>tiny</body></html>"
            gz = False
        else:
            body = PAGE.encode("utf-8")
            gz = self.path == "/gz"
        if gz:
            body = gzip.compress(body)
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def _run(argv):
    import knowledge_builder.cli as cli_mod

    stdout = io.StringIO()
    stderr = io.StringIO()
    with patch("sys.argv", argv), patch("sys.stdout", stdout), patch("sys.stderr", stderr):
        try:
            cli_mod.main()
            code = 0
        except SystemExit as caught:
            code = caught.code
    return code, stdout.getvalue(), stderr.getvalue()


class _FreezeBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), _Handler)
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def _init(self, root):
        code, out, err = _run(
            ["knowledge-builder", "run", "init", "--root", str(root), "--id", "run-1", "--budget", "3"]
        )
        self.assertEqual(code, 0, out + err)

    def _freeze(self, root, path, stem="page-one", run="run-1"):
        return _run(
            ["knowledge-builder", "ingest", "--freeze", self.base + path,
             "--root", str(root), "--run", run, "--stem", stem]
        )


class TestIngestFreeze(_FreezeBase):
    def test_freeze_writes_plain_text_and_prints_matching_sha256(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._init(root)
            code, out, err = self._freeze(root, "/page")
            target = root / "_evidence" / "run-1" / "sources" / "page-one.txt"
            data = target.read_bytes()
            text = data.decode("utf-8")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(SEEN["accept-encoding"], "identity")
        self.assertIn(hashlib.sha256(data).hexdigest(), out)
        self.assertIn("_evidence/run-1/sources/page-one.txt", out)
        self.assertTrue(text.startswith(f"Source-URL: {self.base}/page\nFetched: "))
        self.assertIn("First paragraph with enough words to be real content here.", text)
        self.assertIn("Second paragraph & more text", text)
        self.assertNotIn("<p>", text)
        self.assertNotIn("var a=1", text)
        self.assertNotIn(".x{}", text)

    def test_gzip_body_is_decoded_even_when_identity_was_requested(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._init(root)
            code, out, err = self._freeze(root, "/gz")
            text = (root / "_evidence/run-1/sources/page-one.txt").read_text(encoding="utf-8")
        self.assertEqual(code, 0, out + err)
        self.assertIn("First paragraph with enough words", text)

    def test_existing_frozen_source_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._init(root)
            target = root / "_evidence/run-1/sources/page-one.txt"
            target.write_text("frozen earlier\n", encoding="utf-8")
            code, out, err = self._freeze(root, "/page")
            self.assertEqual(code, 1)
            self.assertIn("refusing to overwrite", err)
            self.assertEqual(target.read_text(encoding="utf-8"), "frozen earlier\n")

    def test_a_symlinked_target_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._init(root)
            outside = root / "outside.txt"
            target = root / "_evidence/run-1/sources/page-one.txt"
            target.symlink_to(outside)
            code, out, err = self._freeze(root, "/page")
            self.assertEqual(code, 1)
            self.assertFalse(outside.exists())

    def test_client_rendered_page_is_refused_and_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._init(root)
            code, out, err = self._freeze(root, "/small")
            files = list((root / "_evidence/run-1/sources").iterdir())
        self.assertEqual(code, 1)
        self.assertIn("client-rendered", err)
        self.assertEqual(files, [])

    def test_stem_must_be_kebab_case(self):
        for stem in ("../x", "Bad", "a/b", "", "-lead"):
            with self.subTest(stem=stem), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                self._init(root)
                code, out, err = self._freeze(root, "/page", stem=stem)
                self.assertEqual(code, 1, out + err)
                self.assertEqual(list((root / "_evidence/run-1/sources").iterdir()), [])

    def test_uninitialised_run_and_missing_flags_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, out, err = self._freeze(Path(tmp), "/page")
            self.assertEqual(code, 1)
            self.assertIn("run is not initialized", err)
            code, out, err = _run(["knowledge-builder", "ingest", "--freeze", self.base + "/page"])
            self.assertEqual(code, 1)
            self.assertIn("--root", err)

    def test_freeze_needs_an_http_url(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._init(root)
            code, out, err = _run(
                ["knowledge-builder", "ingest", "--freeze", "file:///etc/passwd",
                 "--root", str(root), "--run", "run-1", "--stem", "x"]
            )
        self.assertEqual(code, 1)
        self.assertIn("http", err)


class TestFreezeHardening(_FreezeBase):
    """Same loopback server. Redirect schemes and directory pinning."""

    def test_redirect_to_a_non_http_scheme_is_refused_before_it_is_followed(self):
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        listener.setblocking(False)
        port = listener.getsockname()[1]
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                self._init(root)
                for target in (f"ftp://127.0.0.1:{port}/x", "file:///etc/passwd"):
                    with self.subTest(target=target):
                        code, out, err = self._freeze(root, f"/redirect-to/{target}")
                        self.assertEqual(code, 1, out + err)
                        # urllib rejects file: itself; our handler rejects ftp: and the rest.
                        if target.startswith("ftp:"):
                            self.assertIn("refusing redirect to a non-http(s) url", err)
                        else:
                            self.assertIn("is not allowed", err)
                        self.assertEqual(list((root / "_evidence/run-1/sources").iterdir()), [])
            with self.assertRaises(BlockingIOError):
                listener.accept()
        finally:
            listener.close()

    def test_redirect_to_http_is_followed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._init(root)
            code, out, err = self._freeze(root, f"/redirect-to/{self.base}/page")
            self.assertEqual(code, 0, out + err)

    def test_run_dir_swapped_for_a_symlink_during_fetch_cannot_redirect_the_write(self):
        import knowledge_builder.processors.web_freeze as wf

        real_fetch = wf.fetch_html
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._init(root)
            other = root / "_evidence" / "other-run"
            (other / "sources").mkdir(parents=True)
            run = root / "_evidence" / "run-1"

            def swapping_fetch(url):
                text = real_fetch(url)
                run.rename(root / "_evidence" / "moved-run")
                run.symlink_to(other)
                return text

            with patch.object(wf, "fetch_html", swapping_fetch):
                code, out, err = self._freeze(root, "/page")
            self.assertEqual(list((other / "sources").iterdir()), [], out + err)
            # The write stays in the directory that was pinned before the fetch.
            self.assertEqual(code, 0, out + err)
            self.assertEqual(
                [p.name for p in (root / "_evidence" / "moved-run" / "sources").iterdir()],
                ["page-one.txt"],
            )


if __name__ == "__main__":
    unittest.main()
