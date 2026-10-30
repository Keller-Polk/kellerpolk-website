/* kellerpolk.com — playground wiring.
   Talks to the small local demo server (demo/server/server.py).
   If that server isn't running, the Run buttons disable themselves
   and say so — the rest of the site works fine without it. */

(function () {
  "use strict";

  var MAX_OUTPUT = 20000;

  var play = [
    {
      key: "llvm",
      lang: "llvm",
      code: document.getElementById("llvm-code"),
      stdin: null,
      run: document.getElementById("llvm-run"),
      reset: document.getElementById("llvm-reset"),
      status: document.getElementById("llvm-status"),
      console: document.getElementById("llvm-console"),
      sample: document.getElementById("sample-llvm"),
    },
    {
      key: "apcsp",
      lang: "apcsp",
      code: document.getElementById("apcsp-code"),
      stdin: document.getElementById("apcsp-stdin"),
      run: document.getElementById("apcsp-run"),
      reset: document.getElementById("apcsp-reset"),
      status: document.getElementById("apcsp-status"),
      console: document.getElementById("apcsp-console"),
      sample: document.getElementById("sample-apcsp"),
    },
  ];

  function sampleText(el) {
    // The <script type="text/plain"> blocks have a leading newline.
    return (el && el.textContent || "").replace(/^\n/, "").replace(/\s+$/, "") + "\n";
  }

  function escapeHtml(s) {
    return s
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  function renderConsole(out, res) {
    var parts = [];
    var text = (res.stdout || "") + (res.stderr ? (res.stdout ? "\n" : "") + res.stderr : "");
    if (!text) text = "";
    if (text.length > MAX_OUTPUT) {
      text = text.slice(0, MAX_OUTPUT) + "\n… [output truncated]";
    }
    if (text) parts.push(escapeHtml(text));
    if (res.stderr && res.stdout) {
      // stderr already merged above; nothing extra.
    }
    if (res.timedOut) {
      parts.push('<span class="err">[timed out — killed after ' + res.timeoutSecs + "s]</span>");
    } else if (res.exitCode !== 0 && !text) {
      parts.push('<span class="err">[exited with code ' + res.exitCode + "]</span>");
    }
    if (res.buildError) {
      parts.push('<span class="err">' + escapeHtml(res.buildError) + "</span>");
    }
    if (res.error) {
      parts.push('<span class="err">' + escapeHtml(res.error) + "</span>");
    }
    if (!parts.length) parts.push('<span class="dim">(no output)</span>');
    out.innerHTML = parts.join("\n");
  }

  function busy(p, msg) {
    p.run.disabled = true;
    if (p.status) p.status.textContent = msg;
  }

  function idle(p, msg) {
    p.run.disabled = !serverOk;
    if (p.status) p.status.textContent = msg;
  }

  var serverOk = false;

  function wire(p) {
    if (p.sample) p.code.value = sampleText(p.sample);
    if (p.stdin && !p.stdin.value) p.stdin.placeholder = p.stdin.placeholder || "";

    // Tab key inserts four spaces instead of leaving the editor.
    p.code.addEventListener("keydown", function (e) {
      if (e.key === "Tab") {
        e.preventDefault();
        var s = p.code.selectionStart;
        var epos = p.code.selectionEnd;
        p.code.value = p.code.value.slice(0, s) + "    " + p.code.value.slice(epos);
        p.code.selectionStart = p.code.selectionEnd = s + 4;
      }
    });

    if (p.reset) {
      p.reset.addEventListener("click", function () {
        p.code.value = sampleText(p.sample);
        if (p.stdin) p.stdin.value = "";
        p.console.innerHTML = '<span class="console-empty">Output appears here.</span>';
        idle(p, "");
      });
    }

    if (p.run) {
      p.run.addEventListener("click", function () {
        busy(p, p.lang === "llvm" ? "compiling…" : "running…");
        var body = {
          lang: p.lang,
          source: p.code.value,
          stdin: p.stdin ? p.stdin.value : "",
        };
        fetch("/api/run", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        })
          .then(function (r) {
            return r.json().catch(function () {
              return { error: "Bad response from server (HTTP " + r.status + ")" };
            });
          })
          .then(function (res) {
            renderConsole(p.console, res);
            if (res.error) idle(p, "error");
            else if (res.timedOut) idle(p, "timed out");
            else idle(p, "done" + (res.ms ? " · " + res.ms + " ms" : ""));
          })
          .catch(function (err) {
            renderConsole(p.console, { error: "Request failed: " + err.message });
            idle(p, "error");
          });
      });
    }
  }

  play.forEach(wire);

  // Is the demo server present at all?
  fetch("/api/ping")
    .then(function (r) {
      return r.json();
    })
    .then(function (res) {
      serverOk = !!(res && res.ok);
      play.forEach(function (p) {
        if (p.run) p.run.disabled = !serverOk;
        if (p.status && !serverOk) {
          p.status.textContent =
            "playground server offline — start demo/server/server.py (see README)";
        }
      });
    })
    .catch(function () {
      serverOk = false;
      play.forEach(function (p) {
        if (p.run) p.run.disabled = true;
        if (p.status) {
          p.status.textContent =
            "playground server offline — start demo/server/server.py (see README)";
        }
      });
    });
})();
