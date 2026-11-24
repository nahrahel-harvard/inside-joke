"""Tests for serve.py with a fake pipeline. Run:
    .venv/bin/python -m unittest tests.test_serve -v
"""
from __future__ import annotations

import datetime as dt
import http.client
import json
import pathlib
import sys
import tempfile
import threading
import time
import types
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PIL import Image  # noqa: E402

import serve  # noqa: E402


def fake_run(prospect, formats, *, context=None, art="auto", fast=False, research=False,
             out_dir=None, on_event=None):
    out_dir = pathlib.Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    results = {}
    for fmt in formats:
        if fmt == "reply" and not context:
            results[fmt] = {"ok": False, "error": "needs conversation context"}
            continue
        for stage in ("concept", "art", "render"):
            on_event and on_event({"format": fmt, "stage": stage, "message": stage, "t": time.time() - t0})
            time.sleep(0.02)
        frames = [Image.new("RGB", (16, 16), c) for c in ("red", "blue")]
        frames[0].save(out_dir / f"{fmt}.gif", save_all=True, append_images=frames[1:], duration=100, loop=0)
        frames[0].save(out_dir / f"{fmt}.png")
        results[fmt] = {
            "ok": True, "error": None, "gif": f"{fmt}.gif", "png": f"{fmt}.png", "gif_kb": 1,
            "seconds": 0.1, "art_backend": "placeholder",
            "concept": {"id": "c1", "mechanism": "exaggeration", "joke_target": "status meetings",
                        "grounding": [{"fact": prospect["title"], "field": "title"}]},
            "scores": {"c1": {"funny": 8, "specific": 7, "kind": 9, "glance": 8, "total": 7.9}},
            "candidates": [{"id": "c1"}], "rejected": [], "email_line": "Made you something.",
            "alt_text": "A cartoon clipboard sighing.",
        }
        on_event and on_event({"format": fmt, "stage": "done", "message": "ok", "t": time.time() - t0})
    manifest = {
        "slug": out_dir.name, "out_dir": str(out_dir.resolve()), "created": dt.datetime.now().isoformat(),
        "prospect": prospect, "context": context, "total_seconds": round(time.time() - t0, 2),
        "cost_usd": 0.0, "results": results, "ledger": [],
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest))
    return manifest


GOOD = {"prospect": {"first_name": "Dana", "last_name": "Reyes", "title": "VP Supply Chain",
                     "company": "Acme Pallets", "brand_color": "#2f6fed"},
        "formats": ["meme", "card"], "context": None, "art": "placeholder", "fast": True, "research": False}


class ServeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._saved = sys.modules.get("inside_joke.pipeline")
        stub = types.ModuleType("inside_joke.pipeline")
        stub.run = fake_run
        sys.modules["inside_joke.pipeline"] = stub
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = pathlib.Path(cls.tmp.name) / "out"
        cls.out.mkdir()
        serve.Handler.log_request = lambda *a, **k: None  # keep test output clean
        cls.srv = serve.make_server("127.0.0.1", 0, out_root=cls.out)
        cls.port = cls.srv.server_address[1]
        cls.th = threading.Thread(target=cls.srv.serve_forever, daemon=True)
        cls.th.start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()
        cls.tmp.cleanup()
        if cls._saved is not None:
            sys.modules["inside_joke.pipeline"] = cls._saved
        else:
            sys.modules.pop("inside_joke.pipeline", None)

    def req(self, method, path, body=None):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        data = json.dumps(body).encode() if body is not None else None
        c.request(method, path, body=data, headers={"Content-Type": "application/json"} if data else {})
        r = c.getresponse()
        raw = r.read()
        c.close()
        return r.status, r.getheader("Content-Type") or "", raw

    def jreq(self, method, path, body=None):
        s, _, raw = self.req(method, path, body)
        return s, json.loads(raw)

    def generate_and_wait(self, body=GOOD):
        s, j = self.jreq("POST", "/api/generate", body)
        self.assertEqual(s, 200, j)
        jid = j["job_id"]
        for _ in range(100):
            s, job = self.jreq("GET", f"/api/jobs/{jid}")
            self.assertEqual(s, 200)
            if job["status"] != "running":
                return job
            time.sleep(0.05)
        self.fail("job never finished")

    def test_index(self):
        s, ct, raw = self.req("GET", "/")
        self.assertEqual(s, 200)
        self.assertIn("text/html", ct)
        self.assertIn(b"Inside Joke", raw)
        self.assertLess(len(raw), 40 * 1024)
        self.assertNotIn("—".encode(), raw)

    def test_generate_poll_done_and_serve_gif(self):
        job = self.generate_and_wait()
        self.assertEqual(job["status"], "done", job)
        self.assertIsNone(job["error"])
        stages = {(e["format"], e["stage"]) for e in job["events"]}
        self.assertIn(("meme", "done"), stages)
        m = job["manifest"]
        self.assertTrue(m["results"]["meme"]["ok"])
        run = pathlib.Path(m["out_dir"]).name
        s, ct, raw = self.req("GET", f"/out/{run}/meme.gif")
        self.assertEqual(s, 200)
        self.assertEqual(ct, "image/gif")
        self.assertTrue(raw.startswith(b"GIF8"))
        s, ct, _ = self.req("GET", f"/out/{run}/card.png")
        self.assertEqual((s, ct), (200, "image/png"))
        s, ct, _ = self.req("GET", f"/out/{run}/manifest.json")
        self.assertEqual((s, ct), (200, "application/json"))

    def test_reply_without_context_is_skipped(self):
        job = self.generate_and_wait({**GOOD, "formats": ["reply"]})
        self.assertEqual(job["status"], "done")
        r = job["manifest"]["results"]["reply"]
        self.assertFalse(r["ok"])
        self.assertEqual(r["error"], "needs conversation context")

    def test_validation_400s(self):
        bad = [
            {**GOOD, "prospect": {**GOOD["prospect"], "first_name": ""}},
            {**GOOD, "prospect": {k: v for k, v in GOOD["prospect"].items() if k != "company"}},
            {**GOOD, "prospect": {**GOOD["prospect"], "title": "  "}},
            {**GOOD, "formats": []},
            {**GOOD, "formats": ["meme", "sonnet"]},
            {**GOOD, "art": "oil"},
            {**GOOD, "fast": "yes"},
            {**GOOD, "prospect": {**GOOD["prospect"], "notes": "x" * 4001}},
            {**GOOD, "context": "y" * 4001},
            {**GOOD, "prospect": {**GOOD["prospect"], "brand_color": "blue"}},
            {**GOOD, "prospect": "Dana"},
        ]
        for b in bad:
            s, j = self.jreq("POST", "/api/generate", b)
            self.assertEqual(s, 400, b)
            self.assertIn("error", j)
        s, _, _ = self.req("POST", "/api/generate", None)
        self.assertEqual(s, 415)  # no Content-Type: refused before parsing

    def raw_post(self, headers, body=b"{}"):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        c.putrequest("POST", "/api/generate", skip_host=True)
        for k, v in headers.items():
            c.putheader(k, v)
        c.putheader("Content-Length", str(len(body)))
        c.endheaders(body)
        r = c.getresponse()
        r.read()
        c.close()
        return r.status

    def test_cross_site_requests_refused(self):
        here = f"127.0.0.1:{self.port}"
        good = json.dumps(GOOD).encode()
        # A page on another site can send text/plain without a CORS preflight.
        self.assertEqual(self.raw_post({"Host": here, "Content-Type": "text/plain"}, good), 415)
        # DNS rebinding: the browser sends the attacker's hostname as Host.
        self.assertEqual(self.raw_post({"Host": f"evil.example:{self.port}",
                                        "Content-Type": "application/json"}, good), 403)
        self.assertEqual(self.raw_post({"Host": here, "Origin": "https://evil.example",
                                        "Content-Type": "application/json"}, good), 403)
        # Bad Content-Length and non-string enum values give a clean 400.
        self.assertEqual(self.raw_post({"Host": here, "Content-Type": "application/json",
                                        "Content-Length-Override": "x"}, b'{"art": ["x"]}'), 400)

    def test_unknown_job_404(self):
        s, _ = self.jreq("GET", "/api/jobs/nope")
        self.assertEqual(s, 404)

    def test_path_traversal_blocked(self):
        (self.out / "x").mkdir(exist_ok=True)
        for p in ("/out/../serve.py", "/out/%2e%2e/serve.py", "/out/x/../../serve.py",
                  "/out/..%2fserve.py", "/out/%2fetc%2fpasswd", "/out/../../../../etc/passwd",
                  "/out/ratings.jsonl", "/out/"):
            s, _, raw = self.req("GET", p)
            self.assertIn(s, (403, 404), p)
            self.assertNotIn(b"ThreadingHTTPServer", raw)

    def test_rate(self):
        job = self.generate_and_wait()
        run = pathlib.Path(job["manifest"]["out_dir"]).name
        good = {"run": run, "format": "meme", "ratings": {"funny": 6, "thoughtful": 5, "creepy": 1, "would_reply": 7},
                "disclosure": "ai_disclosed", "rater_id": "r_abc123"}
        s, j = self.jreq("POST", "/api/rate", good)
        self.assertEqual(s, 200, j)
        alias = {**good, "out_dir_slug": run, "disclosure": "not_disclosed"}
        del alias["run"]
        s, j = self.jreq("POST", "/api/rate", alias)
        self.assertEqual(s, 200, j)
        lines = (self.out / "ratings.jsonl").read_text().strip().splitlines()
        row = json.loads(lines[-1])
        self.assertEqual(row["run"], run)
        self.assertIn("ts", row)
        bads = [
            {**good, "ratings": {**good["ratings"], "funny": 8}},
            {**good, "ratings": {**good["ratings"], "creepy": 0}},
            {**good, "ratings": {**good["ratings"], "thoughtful": 4.5}},
            {**good, "ratings": {**good["ratings"], "would_reply": True}},
            {**good, "ratings": {"funny": 5}},
            {**good, "disclosure": "maybe"},
            {**good, "rater_id": "x" * 41},
            {**good, "format": "sonnet"},
            {**good, "run": "../etc"},
            {**good, "run": "does-not-exist"},
        ]
        for b in bads:
            s, _ = self.jreq("POST", "/api/rate", b)
            self.assertEqual(s, 400, b)
        self.assertEqual(len((self.out / "ratings.jsonl").read_text().strip().splitlines()), len(lines))

    def test_runs_lists_fake_run(self):
        job = self.generate_and_wait()
        run = pathlib.Path(job["manifest"]["out_dir"]).name
        s, j = self.jreq("GET", "/api/runs")
        self.assertEqual(s, 200)
        names = [r["run"] for r in j["runs"]]
        self.assertIn(run, names)
        row = next(r for r in j["runs"] if r["run"] == run)
        self.assertEqual(row["company"], "Acme Pallets")
        self.assertEqual(row["name"], "Dana Reyes")
        self.assertEqual(sorted(row["formats_ok"]), ["card", "meme"])
        created = [r["created"] for r in j["runs"]]
        self.assertEqual(created, sorted(created, reverse=True))


class MissingPipelineTest(unittest.TestCase):
    def test_import_error_becomes_job_error(self):
        saved = sys.modules.get("inside_joke.pipeline")
        sys.modules["inside_joke.pipeline"] = None  # forces ImportError on import
        tmp = tempfile.TemporaryDirectory()
        try:
            jobs = serve.Jobs()
            jid = jobs.create()
            req = serve.validate_generate(GOOD)
            serve._run_job(jobs, jid, req, pathlib.Path(tmp.name))
            snap = jobs.snapshot(jid)
            self.assertEqual(snap["status"], "error")
            self.assertIn("pipeline is not available", snap["error"])
        finally:
            tmp.cleanup()
            if saved is not None:
                sys.modules["inside_joke.pipeline"] = saved
            else:
                sys.modules.pop("inside_joke.pipeline", None)


if __name__ == "__main__":
    unittest.main()
