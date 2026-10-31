# kellerpolk.com

A small personal site — a portfolio home page with a link to each project, and a
page for each one:

| Page | What it is | Where it runs |
|---|---|---|
| [The LLVM compiler](llvm-compiler.html) | `llvm-compiler` — a C-like language that compiles to a native executable via LLVM 18 | this server (local) |
| [The APCSP interpreter](apcsp-interpreter.html) | `apcsp-interperter` — a BASIC-style language, interpreted in Rust | this server (local) |
| [Image to art](image-to-art.html) | `img-to-art` — a photo-to-painting model | [Hugging Face](https://keller-polk-img-to-art.hf.space) (embedded) |

The site has a light (warm paper) and a dark (warm charcoal) theme. It follows
your OS preference by default; the **Dark/Light** button in the header switches
it, and the choice is remembered in `localStorage`. No framework, no build step.

## Layout

```
index.html               the portfolio home page (links to the three projects)
llvm-compiler.html       project page: the compiler playground
apcsp-interpreter.html   project page: the interpreter playground (+ stdin box)
image-to-art.html        project page: the embedded Hugging Face Space
css/site.css             styles (light + dark design tokens)
js/site.js               theme toggle + playground wiring
demo/
  server/server.py       the playground server (Python 3 stdlib only)
  bin/compiler           release build of llvm-compiler (Apple Silicon)
  bin/apcsp2             release build of apcsp-interperter (Apple Silicon)
  lib/                   the three dylibs `compiler` needs (resolved via @executable_path/../lib)
src/
  llvm-compiler          git submodule → Keller-Polk/llvm-compiler
  apcsp-interperter      git submodule → Keller-Polk/apcsp-interperter
```

## Running it locally

```sh
python3 demo/server/server.py            # http://127.0.0.1:8642
python3 demo/server/server.py --port 9000
```

No dependencies beyond Python 3.8+. The server binds to **127.0.0.1 only**.
What it does:

- Serves the static site and the `POST /api/run` / `GET /api/ping` endpoints.
- Compiles/runs user code in a throwaway temp directory (20 s build / 15 s run /
  20 s APCSP timeouts, 20 KB output cap).
- Picks its temp directory defensively: it re-checks `TMPDIR` on every request
  and falls back to `/private/tmp` etc. if the inherited temp dir has been
  deleted out from under it (a real failure mode for daemons started inside a
  short-lived session).
- Never drops a request connection: server-side errors come back as JSON, so a
  browser shows a message instead of "Load failed".
- Refuses dotfiles (`.git`, `.gitmodules`, …) — the checkout's `.git/config`
  holds push credentials and must never be served.

Open <http://127.0.0.1:8642> — the home page links to the three projects; on a
playground page, edit the code, press **Run**.

If the server isn't running, the site still loads; the Run buttons disable
themselves and say why. The two playgrounds also work if you open the pages
straight from disk (`file://`) — the JavaScript falls back to
`http://127.0.0.1:8642` for the API in that case.

## The Hugging Face embed

The Space's *page* URL (`huggingface.co/spaces/...`) sends
`X-Frame-Options: DENY`, so it cannot be iframed. The embed uses the Space's
direct app domain instead — the canonical, frameable URL for Gradio Spaces:

```
https://keller-polk-img-to-art.hf.space
```

The Space sleeps when idle, so the first load after a quiet period shows a short
"booting" splash; the page notes that.

## Rebuilding the binaries

The committed `demo/bin/*` binaries are **Apple Silicon (arm64) macOS** builds,
built from:

- `llvm-compiler` @ `24e83e5` (2026-09-14) — `src/llvm-compiler`
- `apcsp-interperter` @ `35c046f` (2026-09-07) — `src/apcsp-interperter`

Those are the submodule pins in this repo, so `git submodule update` gives you
exactly the source the binaries were made from. To rebuild on other machines:

```sh
git submodule update --init --recursive

# APCSP interpreter — plain Rust
cd src/apcsp-interperter
cargo build --release
# → target/release/apcsp2

# LLVM compiler — needs LLVM 18 (e.g. `brew install llvm@18`)
cd src/llvm-compiler
LLVM_SYS_180_PREFIX=$(brew --prefix llvm@18) cargo build --release
# → target/release/compiler
```

> Do **not** set `DYLD_LIBRARY_PATH` while running cargo for the LLVM build:
> rustc will find the foreign `libLLVM` dylib and refuse to start.
> `LLVM_SYS_180_PREFIX` alone is enough for the build; the built binary finds
> its dylibs at runtime through the rpath baked into `demo/bin/compiler`.
> If you rebuild into a new location, add the rpath back:
> `install_name_tool -add_rpath @executable_path/../lib demo/bin/compiler`

### Known quirks of the upstream tools (as of Oct 2026)

- **llvm-compiler**: `while` loops that iterate at least once produce broken
  code (segfault or silent miscompilation); `for` is not implemented in the
  parser; mixing `i64` variables with integer literals fails module
  verification. Everything else — variables, `if`/`else`, functions, recursion,
  pointers, `malloc`/`free`, arrays, `print` — works. The default sample uses
  recursion for this reason.
- **apcsp-interperter**: string concatenation with `&` overflows the stack;
  `INPUTI()` panics (rather than erroring gracefully) when stdin runs out.
  The default sample is a one-round guessing game: it reads exactly one number,
  so whatever you type, it ends cleanly.

## Deploying

Not yet — deployment of kellerpolk.com is on hold. When it happens: serve the
five files at the repo root (`index.html`, the three project pages, `css/`,
`js/`) statically, run `demo/server/server.py` behind the static host (or its
`/api/run` + `/api/ping` endpoints), and the Hugging Face embed
(`keller-polk-img-to-art.hf.space`) works cross-origin as-is.
