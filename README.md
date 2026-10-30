# kellerpolk.com

A small personal site with three working playgrounds:

| Playground | What it is | Where it runs |
|---|---|---|
| **The LLVM compiler** | `llvm-compiler` — a C-like language that compiles to a native executable via LLVM 18 | this server (local) |
| **The APCSP interpreter** | `apcsp-interperter` — a BASIC-style language, interpreted in Rust | this server (local) |
| **Image to art** | `img-to-art` — a photo-to-painting model | [Hugging Face](https://huggingface.co/spaces/Keller-Polk/img-to-art) (embedded) |

## Layout

```
index.html          the site
css/site.css        styles
js/site.js          playground wiring
demo/
  server/server.py  the playground server (Python 3 stdlib only)
  bin/compiler      release build of llvm-compiler (Apple Silicon)
  bin/apcsp2        release build of apcsp-interperter (Apple Silicon)
  lib/              the three dylibs `compiler` needs (resolved via @executable_path/../lib)
src/
  llvm-compiler     git submodule → Keller-Polk/llvm-compiler
  apcsp-interperter git submodule → Keller-Polk/apcsp-interperter
```

## Running it locally

```sh
python3 demo/server/server.py            # http://127.0.0.1:8642
python3 demo/server/server.py --port 9000
```

No dependencies beyond Python 3.8+. The server binds to **127.0.0.1 only**.
It compiles/runs user code in a throwaway temp directory with a 15–20 s timeout.
(If you ever put this on the public internet, add a front-end with auth,
rate limiting, and real sandboxing first.)

Open <http://127.0.0.1:8642> — edit the code, press **Run**.

If the server isn't running, the site still loads; the Run buttons disable
themselves and say why.

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
  The default sample is a guessing game that works with a few guesses typed
  in the input box.

## Deploying

Not yet — deployment of kellerpolk.com is on hold. When it happens: serve
`index.html`, `css/`, `js/` statically, run `demo/server/server.py` behind the
static host (or its `/api/run` + `/api/ping` endpoints), and the Hugging Face
embed works cross-origin as-is.
