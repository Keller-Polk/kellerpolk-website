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

ROOT = Path(__file__).resolve().parent.parent.parent  # repo root
BIN = Path(__file__).resolve().parent.parent / "bin"

BUILD_TIMEOUT = 20  # seconds: compile step (llvm)
RUN_TIMEOUT = 15    # seconds: run step
APCSP_TIMEOUT = 20  # seconds: whole apcsp run
MAX_SOURCE = 100_000
MAX_STDIN = 10_000
MAX_OUTPUT = 20_000


def truncate(text: str) -> str:
    if len(text) > MAX_OUTPUT:
        return text[:MAX_OUTPUT] + "\n… [output truncated]"
    return text


def run_llvm(source: str, stdin: str) -> dict:
    workdir = tempfile.mkdtemp(prefix="kellerpolk-llvm-")
    try:
        src = Path(workdir) / "program.lang"
        src.write_text(source)
        compiler = BIN / "compiler"
        proc = subprocess.run(
            [str(compiler), str(src)],
            cwd=workdir,
            capture_output=True,
            text=True,
            timeout=BUILD_TIMEOUT,
        )
        if proc.returncode != 0:
            return {
                "stdout": "",
                "stderr": truncate(proc.stderr or proc.stdout),
                "exitCode": proc.returncode,
                "buildError": truncate(proc.stderr or proc.stdout),
                "ms": 0,
            }
        out = subprocess.run(
            [str(Path(workdir) / "program")],
            cwd=workdir,
            input=stdin,
            capture_output=True,
            text=True,
            timeout=RUN_TIMEOUT,
        )
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
    workdir = tempfile.mkdtemp(prefix="kellerpolk-apcsp-")
    try:
        src = Path(workdir) / "program.ap"
        src.write_text(source)
        out = subprocess.run(
            [str(BIN / "apcsp2"), str(src)],
            cwd=workdir,
            input=stdin,
            capture_output=True,
            text=True,
            timeout=APCSP_TIMEOUT,
        )
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
        self.end_headers()
        self.wfile.write(body)

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
            self._send_json(run_llvm(source, stdin))
        elif lang == "apcsp":
            self._send_json(run_apcsp(source, stdin))
        else:
            self._send_json({"error": f"unknown lang {lang!r}"}, 400)

    def _serve_static(self):
        rel = self.path.split("?", 1)[0].split("#", 1)[0]
        if rel == "/" or rel == "":
            rel = "/index.html"
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
