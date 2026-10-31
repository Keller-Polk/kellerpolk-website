/* kellerpolk.com — theme + playground wiring.
   The playgrounds talk to the small local demo server (demo/server/server.py).
   If that server isn't running, the Run buttons disable themselves and say so —
   the rest of the site works fine without it. */

(function () {
  "use strict";

  /* ——— theme ——— */

  var root = document.documentElement;
  var FAV_ICONS = {
    light:
      "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' fill='%23f7f5f0'/%3E%3Ctext x='16' y='23' font-family='Georgia,serif' font-size='20' text-anchor='middle' fill='%23191714'%3EK%3C/text%3E%3C/svg%3E",
    dark:
      "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' fill='%23121110'/%3E%3Ctext x='16' y='23' font-family='Georgia,serif' font-size='20' text-anchor='middle' fill='%23e9e4da'%3EK%3C/text%3E%3C/svg%3E",
  };

  function currentTheme() {
    return root.getAttribute("data-theme") === "dark" ? "dark" : "light";
  }

  function readSavedTheme() {
    try {
      var t = localStorage.getItem("kp-theme");
      return t === "light" || t === "dark" ? t : null;
    } catch (e) {
      return null;
    }
  }

  function applyTheme(t) {
    root.setAttribute("data-theme", t);
    var icon = document.querySelector('link[rel="icon"]');
    if (icon) icon.href = FAV_ICONS[t];
    var btns = document.querySelectorAll("[data-theme-toggle]");
    for (var i = 0; i < btns.length; i++) {
      btns[i].textContent = t === "dark" ? "Light" : "Dark";
      btns[i].setAttribute("aria-pressed", t === "dark" ? "true" : "false");
      btns[i].title = t === "dark" ? "Switch to light mode" : "Switch to dark mode";
    }
  }

  applyTheme(currentTheme());

  var toggles = document.querySelectorAll("[data-theme-toggle]");
  for (var i = 0; i < toggles.length; i++) {
    toggles[i].addEventListener("click", function () {
      var next = currentTheme() === "dark" ? "light" : "dark";
      try {
        localStorage.setItem("kp-theme", next);
      } catch (e) {}
      applyTheme(next);
    });
  }

  // Follow the OS while the visitor hasn't chosen explicitly.
  if (window.matchMedia) {
    var media = window.matchMedia("(prefers-color-scheme: dark)");
    var onOsChange = function (e) {
      if (!readSavedTheme()) applyTheme(e.matches ? "dark" : "light");
    };
    if (media.addEventListener) media.addEventListener("change", onOsChange);
    else if (media.addListener) media.addListener(onOsChange);
  }

  /* ——— playgrounds ——— */

  var MAX_OUTPUT = 20000;

  // Same origin when served by the demo server; absolute when someone opens
  // the page from disk (file://), where relative fetch paths can't work.
  var apiBase =
    location.protocol === "file:" ? "http://127.0.0.1:8642" : "";

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
    var text =
      (res.stdout || "") +
      (res.stderr ? (res.stdout ? "\n" : "") + res.stderr : "");
    if (text.length > MAX_OUTPUT) {
      text = text.slice(0, MAX_OUTPUT) + "\n… [output truncated]";
    }
    if (text) parts.push(escapeHtml(text));

    if (res.timedOut) {
      parts.push(
        '<span class="err">[timed out — killed after ' +
          (res.timeoutSecs || "?") +
          "s]</span>"
      );
    } else if (res.exitCode !== undefined && res.exitCode !== 0 && !text) {
      // Only show an exit code for runs that actually completed, and only
      // when there is no server-reported failure to show instead.
      parts.push(
        '<span class="err">[exited with code ' + res.exitCode + "]</span>"
      );
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

  var serverOk = false;

  function busy(p, msg) {
    p.run.disabled = true;
    if (p.status) p.status.textContent = msg;
  }

  function idle(p, msg) {
    p.run.disabled = !serverOk;
    if (p.status) p.status.textContent = msg;
  }

  var OFFLINE_MSG =
    "playground server offline — start demo/server/server.py (see README)";

  function setOffline() {
    plays.forEach(function (p) {
      if (p.run) p.run.disabled = true;
      if (p.status) p.status.textContent = OFFLINE_MSG;
    });
  }

  var plays = [];

  document.querySelectorAll(".playground[data-lang]").forEach(function (article) {
    var lang = article.getAttribute("data-lang");
    var p = {
      lang: lang,
      code: article.querySelector(".editor-code"),
      stdin: article.querySelector(".editor-stdin"),
      run: article.querySelector(".btn-run"),
      reset: article.querySelector(".btn-reset"),
      status: article.querySelector(".status"),
      console: article.querySelector(".console"),
      sample: document.getElementById("sample-" + lang) || null,
    };
    if (!p.code || !p.run || !p.console) return;
    plays.push(p);

    if (p.sample) p.code.value = sampleText(p.sample);

    // Tab key inserts four spaces instead of leaving the editor.
    p.code.addEventListener("keydown", function (e) {
      if (e.key === "Tab") {
        e.preventDefault();
        var s = p.code.selectionStart;
        var epos = p.code.selectionEnd;
        p.code.value =
          p.code.value.slice(0, s) + "    " + p.code.value.slice(epos);
        p.code.selectionStart = p.code.selectionEnd = s + 4;
      }
    });

    if (p.reset) {
      p.reset.addEventListener("click", function () {
        if (p.sample) p.code.value = sampleText(p.sample);
        if (p.stdin) p.stdin.value = "";
        p.console.innerHTML =
          '<span class="console-empty">Output appears here.</span>';
        idle(p, "");
      });
    }

    p.run.addEventListener("click", function () {
      busy(p, p.lang === "llvm" ? "compiling…" : "running…");
      var body = {
        lang: p.lang,
        source: p.code.value,
        stdin: p.stdin ? p.stdin.value : "",
      };
      fetch(apiBase + "/api/run", {
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
          renderConsole(
            p.console,
            { error: "Request failed: " + err.message }
          );
          idle(p, "error");
        });
    });
  });

  // Is the demo server present at all?
  fetch(apiBase + "/api/ping")
    .then(function (r) {
      return r.json();
    })
    .then(function (res) {
      serverOk = !!(res && res.ok);
      if (!serverOk) setOffline();
    })
    .catch(function () {
      serverOk = false;
      setOffline();
    });
})();
