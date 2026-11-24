"""Local web app for Inside Joke. Stdlib only.

    .venv/bin/python serve.py --port 8765

Routes: GET /, POST /api/generate, GET /api/jobs/<id>, GET /out/<path>,
POST /api/rate, GET /api/runs. The pipeline is imported lazily inside each job
thread, so the server starts even when inside_joke/pipeline.py is missing.
"""
from __future__ import annotations

import argparse
import datetime as dt
import importlib
import json
import pathlib
import re
import threading
import time
import traceback
import urllib.parse
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = pathlib.Path(__file__).resolve().parent
try:
    from inside_joke.config import ROOT as _CFG_ROOT
    ROOT = pathlib.Path(_CFG_ROOT)
except Exception:  # config import should never block the UI
    ROOT = HERE
OUT_ROOT = ROOT / "out"
WEB_DIR = HERE / "web"

FORMATS = ["meme", "headline", "comic", "card", "reply"]
ARTS = {"auto", "image", "svg", "placeholder"}
PROSPECT_KEYS = ["first_name", "last_name", "title", "company", "domain", "industry",
                 "location", "linkedin_headline", "notes", "brand_color"]
REQUIRED = ["first_name", "company", "title"]
MAX_STR = 4000
MAX_BODY = 64 * 1024
MAX_RUNNING = 3
MAX_JOBS_KEPT = 100
RATING_KEYS = ["funny", "thoughtful", "creepy", "would_reply"]
DISCLOSURES = {"ai_disclosed", "not_disclosed"}
CTYPES = {".gif": "image/gif", ".png": "image/png", ".json": "application/json",
          ".svg": "image/svg+xml", ".webp": "image/webp", ".jpg": "image/jpeg"}
HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
RUN_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,200}$")
RATER = re.compile(r"^[A-Za-z0-9_-]{1,40}$")


class BadRequest(ValueError):
    pass


class UnsupportedMedia(BadRequest):
    pass


def _now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds")


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:40] or "run"


# ---------------- validation ----------------

def _str(v, name: str) -> str:
    if v is None:
        return ""
    if not isinstance(v, str):
        raise BadRequest(f"{name} must be a string")
    if len(v) > MAX_STR:
        raise BadRequest(f"{name} is longer than {MAX_STR} characters")
    return v.strip()


def validate_generate(body) -> dict:
    if not isinstance(body, dict):
        raise BadRequest("body must be a JSON object")
    raw = body.get("prospect")
    if not isinstance(raw, dict):
        raise BadRequest("prospect must be an object")
    prospect = {}
    for k in PROSPECT_KEYS:
        v = _str(raw.get(k), k)
        if v:
            prospect[k] = v
    for k in REQUIRED:
        if not prospect.get(k):
            raise BadRequest(f"{k} is required")
    if "brand_color" in prospect and not HEX.match(prospect["brand_color"]):
        raise BadRequest("brand_color must look like #2f6fed")
    fmts = body.get("formats")
    if not isinstance(fmts, list) or not fmts:
        raise BadRequest("pick at least one format")
    clean = []
    for f in fmts:
        if f not in FORMATS:
            raise BadRequest(f"unknown format: {str(f)[:40]}")
        if f not in clean:
            clean.append(f)
    context = _str(body.get("context"), "context") or None
    art = body.get("art", "auto") or "auto"
    if not isinstance(art, str) or art not in ARTS:
        raise BadRequest("art must be one of auto, image, svg, placeholder")
    for flag in ("fast", "research"):
        if not isinstance(body.get(flag, False), bool):
            raise BadRequest(f"{flag} must be true or false")
    return {"prospect": prospect, "formats": clean, "context": context, "art": art,
            "fast": bool(body.get("fast", False)), "research": bool(body.get("research", False))}


def validate_rate(body, out_root: pathlib.Path) -> dict:
    if not isinstance(body, dict):
        raise BadRequest("body must be a JSON object")
    run = body.get("run") or body.get("out_dir_slug") or body.get("run_folder")
    if not isinstance(run, str) or not RUN_NAME.match(run) or ".." in run:
        raise BadRequest("run must be a run folder name")
    if not (out_root / run).is_dir():
        raise BadRequest("unknown run")
    fmt = body.get("format")
    if not isinstance(fmt, str) or fmt not in FORMATS:
        raise BadRequest("unknown format")
    ratings = body.get("ratings")
    if not isinstance(ratings, dict):
        raise BadRequest("ratings must be an object")
    clean = {}
    for k in RATING_KEYS:
        v = ratings.get(k)
        if isinstance(v, bool) or not isinstance(v, int) or not 1 <= v <= 7:
            raise BadRequest(f"{k} must be a whole number from 1 to 7")
        clean[k] = v
    disc = body.get("disclosure")
    if not isinstance(disc, str) or disc not in DISCLOSURES:
        raise BadRequest("disclosure must be ai_disclosed or not_disclosed")
    rater = body.get("rater_id")
    if not isinstance(rater, str) or not RATER.match(rater):
        raise BadRequest("rater_id must be 1-40 letters, digits, _ or -")
    return {"ts": _now_iso(), "run": run, "format": fmt, "ratings": clean,
            "disclosure": disc, "rater_id": rater}


# ---------------- jobs ----------------

class Jobs:
    def __init__(self):
        self.lock = threading.Lock()
        self.jobs: dict[str, dict] = {}

    def running(self) -> int:
        with self.lock:
            return sum(1 for j in self.jobs.values() if j["status"] == "running")

    def create(self) -> str:
        jid = uuid.uuid4().hex[:12]
        with self.lock:
            self.jobs[jid] = {"status": "running", "events": [], "manifest": None,
                              "error": None, "started": time.time()}
            if len(self.jobs) > MAX_JOBS_KEPT:
                for old in sorted(self.jobs, key=lambda k: self.jobs[k]["started"])[:len(self.jobs) - MAX_JOBS_KEPT]:
                    if self.jobs[old]["status"] != "running":
                        del self.jobs[old]
        return jid

    def event(self, jid: str, ev: dict):
        with self.lock:
            job = self.jobs.get(jid)
            if job is not None and len(job["events"]) < 2000:
                job["events"].append(ev)

    def finish(self, jid: str, *, manifest=None, error=None):
        with self.lock:
            job = self.jobs[jid]
            job["manifest"] = manifest
            job["error"] = error
            job["status"] = "error" if error else "done"

    def snapshot(self, jid: str):
        with self.lock:
            job = self.jobs.get(jid)
            if job is None:
                return None
            return {"status": job["status"], "events": list(job["events"]),
                    "manifest": job["manifest"], "error": job["error"]}


def _run_job(jobs: Jobs, jid: str, req: dict, out_root: pathlib.Path):
    t0 = time.time()

    def on_event(ev):
        if isinstance(ev, dict):
            jobs.event(jid, {k: ev.get(k) for k in ("format", "stage", "message", "t")})

    try:
        try:
            pipeline = importlib.import_module("inside_joke.pipeline")
        except ImportError as e:
            raise RuntimeError(f"pipeline is not available: {e}") from e
        out_dir = None
        if out_root.resolve() != (ROOT / "out").resolve():
            stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
            out_dir = out_root / f"{_slug(req['prospect']['company'] + '-' + req['prospect']['first_name'])}-{stamp}-{jid[:4]}"
        manifest = pipeline.run(req["prospect"], req["formats"], context=req["context"], art=req["art"],
                                fast=req["fast"], research=req["research"], out_dir=out_dir,
                                on_event=on_event)
        jobs.finish(jid, manifest=json.loads(json.dumps(manifest, default=str)))
    except Exception as e:
        traceback.print_exc()
        jobs.event(jid, {"format": None, "stage": "error", "message": str(e)[:500],
                         "t": round(time.time() - t0, 2)})
        jobs.finish(jid, error=f"{e.__class__.__name__}: {e}"[:1000])


# ---------------- runs ----------------

def list_runs(out_root: pathlib.Path, limit: int = 200) -> list[dict]:
    runs = []
    if not out_root.is_dir():
        return runs
    for mf in out_root.glob("*/manifest.json"):
        try:
            m = json.loads(mf.read_text())
        except Exception:
            continue
        p = m.get("prospect") or {}
        res = m.get("results") or {}
        runs.append({
            "run": mf.parent.name,
            "created": m.get("created") or dt.datetime.fromtimestamp(mf.stat().st_mtime).isoformat(),
            "name": " ".join(x for x in (p.get("first_name"), p.get("last_name")) if x),
            "company": p.get("company", ""),
            "formats_ok": [f for f, r in res.items() if isinstance(r, dict) and r.get("ok")],
            "formats_failed": [f for f, r in res.items() if isinstance(r, dict) and not r.get("ok")],
            "cost_usd": m.get("cost_usd"),
            "_mtime": mf.stat().st_mtime,
        })
    runs.sort(key=lambda r: (str(r["created"]), r["_mtime"]), reverse=True)
    for r in runs:
        r.pop("_mtime", None)
    return runs[:limit]


# ---------------- HTTP ----------------

class Handler(BaseHTTPRequestHandler):
    server_version = "InsideJoke/1"

    def log_request(self, code="-", size="-"):  # quieter: only log 4xx/5xx
        if str(getattr(code, "value", code)).startswith(("4", "5")):
            super().log_request(code, size)

    # helpers
    def _send(self, code: int, body: bytes, ctype: str, extra: dict | None = None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, code: int, obj):
        self._send(code, json.dumps(obj, ensure_ascii=False).encode(), "application/json; charset=utf-8",
                   {"Cache-Control": "no-store"})

    def _body(self):
        # Only real JSON requests: a browser page on another site can send a
        # "simple" text/plain POST without a preflight, but not application/json.
        ctype = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        if ctype != "application/json":
            raise UnsupportedMedia("Content-Type must be application/json")
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            raise BadRequest("bad Content-Length")
        if n < 0:
            raise BadRequest("bad Content-Length")
        if n > MAX_BODY:
            raise BadRequest("request body too large")
        try:
            return json.loads(self.rfile.read(n) or b"null")
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise BadRequest("body must be valid JSON")

    @property
    def out_root(self) -> pathlib.Path:
        return self.server.out_root

    # routes
    def do_GET(self):
        path = urllib.parse.urlsplit(self.path).path
        if path in ("/", "/index.html"):
            f = self.server.web_dir / "index.html"
            if not f.exists():
                return self._json(404, {"error": "web/index.html missing"})
            return self._send(200, f.read_bytes(), "text/html; charset=utf-8", {"Cache-Control": "no-store"})
        if path == "/api/runs":
            return self._json(200, {"runs": list_runs(self.out_root)})
        if path.startswith("/api/jobs/"):
            snap = self.server.jobs.snapshot(path[len("/api/jobs/"):])
            if snap is None:
                return self._json(404, {"error": "unknown job"})
            return self._json(200, snap)
        if path.startswith("/out/"):
            return self._serve_out(path[len("/out/"):])
        return self._json(404, {"error": "not found"})

    do_HEAD = do_GET

    def _serve_out(self, rel: str):
        rel = urllib.parse.unquote(rel)
        if not rel or "\x00" in rel or rel.startswith("/") or "\\" in rel:
            return self._json(404, {"error": "not found"})
        base = self.out_root.resolve()
        try:
            target = (base / rel).resolve()
        except (OSError, RuntimeError):
            return self._json(404, {"error": "not found"})
        if not target.is_relative_to(base) or target == base:
            return self._json(403, {"error": "forbidden"})
        ctype = CTYPES.get(target.suffix.lower())
        if ctype is None or not target.is_file():
            return self._json(404, {"error": "not found"})
        return self._send(200, target.read_bytes(), ctype, {"Cache-Control": "no-cache"})

    def _host_ok(self) -> bool:
        """Block DNS rebinding: only accept requests addressed to this machine."""
        port = self.server.server_address[1]
        host = (self.headers.get("Host") or "").strip().lower()
        return host in {f"127.0.0.1:{port}", f"localhost:{port}", f"[::1]:{port}"}

    def do_POST(self):
        path = urllib.parse.urlsplit(self.path).path
        if not self._host_ok():
            return self._json(403, {"error": "requests must be addressed to localhost"})
        origin = self.headers.get("Origin")
        if origin and urllib.parse.urlsplit(origin).hostname not in ("127.0.0.1", "localhost", "::1"):
            return self._json(403, {"error": "cross-origin requests are not allowed"})
        try:
            if path == "/api/generate":
                req = validate_generate(self._body())
                if self.server.jobs.running() >= MAX_RUNNING:
                    return self._json(429, {"error": f"{MAX_RUNNING} jobs are already running. Wait for one to finish."})
                jid = self.server.jobs.create()
                threading.Thread(target=_run_job, args=(self.server.jobs, jid, req, self.out_root),
                                 daemon=True, name=f"job-{jid}").start()
                return self._json(200, {"job_id": jid})
            if path == "/api/rate":
                row = validate_rate(self._body(), self.out_root)
                with self.server.rate_lock:
                    self.out_root.mkdir(parents=True, exist_ok=True)
                    with open(self.out_root / "ratings.jsonl", "a", encoding="utf-8") as fh:
                        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
                return self._json(200, {"ok": True, "ts": row["ts"]})
        except UnsupportedMedia as e:
            return self._json(415, {"error": str(e)})
        except BadRequest as e:
            return self._json(400, {"error": str(e)})
        return self._json(404, {"error": "not found"})


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, addr, out_root: pathlib.Path | None = None, web_dir: pathlib.Path | None = None):
        super().__init__(addr, Handler)
        self.out_root = pathlib.Path(out_root or OUT_ROOT)
        self.web_dir = pathlib.Path(web_dir or WEB_DIR)
        self.jobs = Jobs()
        self.rate_lock = threading.Lock()


def make_server(host: str = "127.0.0.1", port: int = 8765, out_root=None, web_dir=None) -> Server:
    return Server((host, port), out_root=out_root, web_dir=web_dir)


def main():
    ap = argparse.ArgumentParser(description="Inside Joke local web app")
    ap.add_argument("--port", type=int, default=8765)
    args = ap.parse_args()
    srv = make_server("127.0.0.1", args.port)
    srv.out_root.mkdir(parents=True, exist_ok=True)
    print(f"Inside Joke running at http://127.0.0.1:{args.port}  (output: {srv.out_root})")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()


if __name__ == "__main__":
    main()
