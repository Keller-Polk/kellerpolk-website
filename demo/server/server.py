#!/usr/bin/env python3
"""
Local playground server for kellerpolk.com.

Serves the static site and runs the two local playgrounds:

  POST /api/run   {"lang": "llvm" | "apcsp", "source": "...", "stdin": "..."}
    llvm  -> compiles the .lang source with demo/bin/compiler (LLVM 18)
             into a temporary directory, then runs the resulting binary
    apcsp -> runs the .ap source with demo/bin/apcsp2

  GET  /api/ping  -> {"ok": true}

Pure standard library. Binds to 127.0.0.1 only — never expose it to a
network without a front-end, auth, and better process isolation.

Usage:
    python3 demo/server/server.py [--port 8642]
Then open http://127.0.0.1:8642/
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent.parent  # repo root
BIN = Path(__file__).resolve().parent.parent / "bin"

BUILD_TIMEOUT = 20  # seconds: compile step (llvm)
RUN_TIMEOUT = 15    # seconds: run step
APCSP_TIMEOUT = 20  # seconds: whole apcsp run
MAX_SOURCE = 100_000
MAX_STDIN = 10_000
MAX_OUTPUT = 20_000


def temp_base() -> Optional[Path]:
    """Pick a directory that actually exists for per-run work dirs.

    A long-lived process started inside a short-lived session may inherit a
    TMPDIR that gets deleted out from under it (e.g. a per-run scratch dir).
    Re-check on every call and fall back to stable locations.
    """
    cands: list[Path] = []
    for var in ("TMPDIR", "TEMP", "TMP"):
        v = os.environ.get(var)
        if v:
            cands.append(Path(v).expanduser())
    cands.append(Path("/private/tmp"))
    cands.append(Path(tempfile.gettempdir()))
    cands.append(Path.home() / ".cache" / "kellerpolk-demo")
    seen: set[Path] = set()
    for c in cands:
        if c in seen:
            continue
        seen.add(c)
        try:
            c.mkdir(parents=True, exist_ok=True)
            if c.is_dir() and os.access(c, os.W_OK):
                return c
        except OSError:
            continue
    return None


def truncate(text: str) -> str:
    if len(text) > MAX_OUTPUT:
        return text[:MAX_OUTPUT] + "\n… [output truncated]"
    return text


def run_llvm(source: str, stdin: str) -> dict:
    base = temp_base()
    if base is None:
        return {"error": "no usable temp directory on the server"}
    workdir = tempfile.mkdtemp(prefix="kellerpolk-llvm-", dir=base)
    try:
        src = Path(workdir) / "program.lang"
        src.write_text(source)
        compiler = BIN / "compiler"
        try:
            proc = subprocess.run(
                [str(compiler), str(src)],
                cwd=workdir,
                capture_output=True,
                text=True,
                timeout=BUILD_TIMEOUT,
            )
        except subprocess.TimeoutExpired:
            return {"buildError": "compile timed out"}
        except OSError as e:
            return {"buildError": f"could not run the compiler: {e}"}
        if proc.returncode != 0:
            return {
                "stdout": "",
                "stderr": truncate(proc.stderr or proc.stdout),
                "exitCode": proc.returncode,
                "buildError": truncate(proc.stderr or proc.stdout),
                "ms": 0,
            }
        try:
            out = subprocess.run(
                [str(Path(workdir) / "program")],
                cwd=workdir,
                input=stdin,
                capture_output=True,
                text=True,
                timeout=RUN_TIMEOUT,
            )
        except subprocess.TimeoutExpired:
            return {"stdout": "", "stderr": "", "timedOut": True, "timeoutSecs": RUN_TIMEOUT}
        except OSError as e:
            return {
                "stdout": "",
                "stderr": "",
                "error": f"could not run the compiled program: {e}",
            }
        return {
            "stdout": truncate(out.stdout),
            "stderr": truncate(out.stderr),
            "exitCode": out.returncode,
            "ms": 0,
        }
    except subprocess.TimeoutExpired:
        return {"stdout": "", "stderr": "", "timedOut": True, "timeoutSecs": RUN_TIMEOUT}
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def run_apcsp(source: str, stdin: str) -> dict:
    base = temp_base()
    if base is None:
        return {"error": "no usable temp directory on the server"}
    workdir = tempfile.mkdtemp(prefix="kellerpolk-apcsp-", dir=base)
    try:
        src = Path(workdir) / "program.ap"
        src.write_text(source)
        try:
            out = subprocess.run(
                [str(BIN / "apcsp2"), str(src)],
                cwd=workdir,
                input=stdin,
                capture_output=True,
                text=True,
                timeout=APCSP_TIMEOUT,
            )
        except subprocess.TimeoutExpired:
            return {"stdout": "", "stderr": "", "timedOut": True, "timeoutSecs": APCSP_TIMEOUT}
        except OSError as e:
            return {
                "stdout": "",
                "stderr": "",
                "error": f"could not start the APCSP interpreter: {e}",
            }
        return {
            "stdout": truncate(out.stdout),
            "stderr": truncate(out.stderr),
            "exitCode": out.returncode,
            "ms": 0,
        }
    except subprocess.TimeoutExpired:
        return {"stdout": "", "stderr": "", "timedOut": True, "timeoutSecs": APCSP_TIMEOUT}
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


class Handler(BaseHTTPRequestHandler):
    server_version = "kellerpolk-demo/1.0"

    def log_message(self, fmt, *args):  # quieter logs
        sys.stderr.write("%s %s\n" % (self.address_string(), fmt % args))

    def _send_json(self, obj, status=200):
        body = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        # Lets the site work even if someone opens it from disk or another host.
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        if self.path.startswith("/api/"):
            self._send_json({"ok": True})
        else:
            self._send_json({"error": "not found"}, 404)

    def do_GET(self):
        if self.path == "/api/ping":
            self._send_json({"ok": True})
            return
        self._serve_static()

    def do_POST(self):
        if self.path != "/api/run":
            self._send_json({"error": "not found"}, 404)
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
            payload = json.loads(self.rfile.read(length) or b"{}")
        except Exception:
            self._send_json({"error": "bad request: expected JSON"}, 400)
            return

        lang = payload.get("lang")
        source = payload.get("source") or ""
        stdin = payload.get("stdin") or ""
        if len(source) > MAX_SOURCE or len(stdin) > MAX_STDIN:
            self._send_json({"error": "source or stdin too large"}, 400)
            return

        if lang == "llvm":
            try:
                self._send_json(run_llvm(source, stdin))
            except Exception as e:
                # Never drop the connection — a dead socket makes browsers
                # show "Load failed" with no information.
                self._send_json({"error": f"internal error: {type(e).__name__}: {e}"}, 500)
        elif lang == "apcsp":
            try:
                self._send_json(run_apcsp(source, stdin))
            except Exception as e:
                self._send_json({"error": f"internal error: {type(e).__name__}: {e}"}, 500)
        else:
            self._send_json({"error": f"unknown lang {lang!r}"}, 400)

    def _serve_static(self):
        rel = self.path.split("?", 1)[0].split("#", 1)[0]
        if rel == "/" or rel == "":
            rel = "/index.html"
        # Never serve dotfiles (e.g. .git config, which holds push credentials).
        parts = [p for p in rel.split("/") if p not in ("", ".")]
        if any(p.startswith(".") for p in parts):
            self.send_error(403)
            return
        # Resolve and make sure we stay inside ROOT.
        target = (ROOT / rel.lstrip("/")).resolve()
        if not str(target).startswith(str(ROOT.resolve())):
            self.send_error(403)
            return
        if target.is_dir():
            target = target / "index.html"
        if not target.is_file():
            self.send_error(404)
            return
        data = target.read_bytes()
        ctype = {
            ".html": "text/html; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".js": "text/javascript; charset=utf-8",
            ".svg": "image/svg+xml",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".ico": "image/x-icon",
            ".txt": "text/plain; charset=utf-8",
            ".md": "text/plain; charset=utf-8",
        }.get(target.suffix.lower(), "application/octet-stream")
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(data)


def main():
    port = 8642
    args = sys.argv[1:]
    if "--port" in args:
        port = int(args[args.index("--port") + 1])
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"kellerpolk.com demo server on http://127.0.0.1:{port}/  (Ctrl-C to stop)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
