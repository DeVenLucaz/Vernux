# Changelog

All notable changes to VERNUX are documented here.  
Format: [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)

---

## Version Scheme

```
v MAJOR . MINOR . PATCH

MAJOR  — Increments on breaking rewrite. v0.x = pre-release, v1.0.0 = first public release.
MINOR  — Maps to build phase. Phase 0=.1, Phase 1=.2 ... Phase 5=.6 (public → v1.0.0)
PATCH  — Bug fixes within a phase. Resets to 0 each MINOR bump.
```

| Phase | Version range | Name |
|---|---|---|
| Phase 0 | v0.1.x | Foundation |
| Phase 1 | v0.2.x | Core Engine |
| Phase 2 | v0.3.x | Knowledge Base |
| Phase 3 | v0.4.x | Recipes |
| Phase 4 | v0.5.x | Local AI |
| Phase 5 | v0.6.x → v1.0.0 | Polish & Release |
| Phase 6+ | v1.1.x, v1.2.x... | Community |

---

## [v0.7.2] — Phase 6 — Library Auto-suggest — 2026-05-27

### Added
- **`library_auto_suggest()`** — new function in `vernux.py` that checks the offline library whenever pattern matching fails, before Vernux hits a dead end. It tries two strategies:
  1. **Direct token match** — extracts command-like words from natural language input ("what is ripgrep" → checks `rg`/`ripgrep`) and shows a compact info card with synopsis, short description, and an example.
  2. **Keyword search** — if no direct token hits, searches the library for the most relevant matches and shows up to 4 results with examples.
- **`_extract_command_tokens()`** — helper that strips question/filler words from natural language to pull candidate command names.
- **Smarter dead-end message** — when nothing is found anywhere, the "I don't know" message now includes a context-aware tip: `explain <command>` or `library search <term>` (if library is built), or `install-model` (if no AI).

### Changed
- **`process_match` fallback chain** is now 4 layers deep:
  1. `try_llm_fallback` — LLM if model installed
  2. `library_auto_suggest` — offline library (new, no model needed)
  3. `ui.print_did_you_mean` — fuzzy pattern candidates
  4. Dead-end message with contextual tip
- Import line updated: `lookup` now imported as `lib_lookup` from `modules.explainer`.

### Behaviour examples
```
VERNUX > what does ripgrep do
  📚 Found in library:  ripgrep  [text]
  rg [options] pattern [path]
  ripgrep: fast recursive regex search, faster than grep.
  Example: rg 'TODO' .
  Full entry: library rg  |  Explain: explain rg

VERNUX > search for text in files
  📚 Library suggestions for 'search for text in files':
  grep                  Search text. -r recursive, -i case insensitive...
    eg: grep -rn 'TODO' .
  rg                    ripgrep: fast recursive regex search...
    eg: rg 'TODO' .
  More: library search search text files
```

---

## [v0.7.1] — Phase 6 — Library Polish — 2026-05-27

### Added
- **`library related <cmd>`** — new subcommand: shows all commands in the same category as the given command. Displayed as a 4-column grid.
- **`library categories`** — new subcommand: lists every category with a count of how many commands it contains.
- **`library search` / `library find`** — search results now show category tags inline and print two lines per result (name + description) for readability.
- **`library <cmd>` rich card** — command lookups now append a `library related <cmd>` hint at the bottom (Noob/Learner modes) so users can naturally discover sibling commands.
- **`library` (no args)** — status screen now shows a category preview line listing the first 8 categories.

### Fixed
- **`handle_explain` cascade bug** — `explain <cmd>` previously skipped the library layer on cache misses due to an incorrect string check. It now properly falls through: `COMMAND_DICT → library.json → close-match suggestions → LLM`.
- **`explain <cmd>` close-match suggestions** — when a command isn't found in any offline source, Vernux now suggests similar commands from the library before saying "I don't know", instead of going straight to LLM.
- **REPL library routing** — `library <cmd>` was stripping 8 chars instead of 7, causing `library grep` to look up `rep` instead of `grep`. Fixed.
- **`explain` no-arg hint** — now shows library size in the usage hint so users know how many commands are available.

### Changed
- `handle_library` fully rewritten — cleaner separation of subcommands, consistent color usage, 4-column grid for category browsing, better not-found messages with suggestions.
- `handle_explain` rewritten — cleaner 3-step cascade with explicit not-found markers list.
- Help listing updated with all new `library` subcommands.

---

## [v0.7.0] — Phase 6 — Library Enrichment — 2026-05-27

### Added
- **`data/library.json`** — offline command reference database built from LinuxCommandLibrary.com (Apache 2.0, 500+ commands). Ships with Vernux, works 100% offline after install.
- **`tools/fetch_library.py`** — dev tool to build/update `data/library.json`. Fetches command pages from linuxcommandlibrary.com, parses synopsis, description, and real examples, assigns Termux-relevant categories. Supports `--quick` (60 priority commands), `--merge` (keep existing entries), `--cmd` (single command debug), `--quiet`.
- **`modules/explainer.py` — library layer** — `explain()` now checks a second lookup layer: `data/library.json`, after the curated `COMMAND_DICT` and before the LLM fallback. This means 500+ commands that weren't in the built-in dict now resolve offline with real man page data and examples.
- **`vernux library` command** — new in-REPL and CLI command for direct library browsing:
  - `library grep` — full entry for any command
  - `library search <term>` — keyword search across all 500+ commands
  - `library category <name>` — list commands by category
  - `library categories` — list all available categories
- **Library status in `help` and `stats`** — both screens now show how many commands are in the library, or a build hint if it hasn't been fetched yet.
- **`list_categories()`** in `explainer.py` — returns all categories from both the curated dict and the library, used by the `library categories` command.

### Changed
- `explain()` no longer says "I don't have offline documentation" for commands covered by the library — it now shows the library entry with a `[Linux Command Library]` source tag (Learner mode only).
- `search_commands()` now searches both `COMMAND_DICT` and `library.json`, returning up to 20 results combined.
- `list_commands()` now returns commands from both layers.

### Credits
- Command reference data: [LinuxCommandLibrary](https://github.com/SimonSchubert/LinuxCommandLibrary) by Simon Schubert, Apache 2.0 license.

---

## [v0.6.4] — Phase 5 — Hotfix 4 — 2026-05-27

### Fixed
- **llama.cpp banner leaking to terminal** — the full llama.cpp startup UI (build info, model info, available commands, system prompt) was printing directly to the terminal during AI queries. Root cause: `capture_output=True` does not suppress stderr on older Termux llama.cpp builds (version 0/unknown) that ignore `--log-disable`. Fixed by replacing `capture_output=True` with explicit `stdout=subprocess.PIPE, stderr=subprocess.DEVNULL` in both `query()` and the new `query_explain()`.
- **AI answer silently dropped for explain queries** — `what is JSON`, `what is grep`, and similar explanation queries were running through `validate_output()` which only accepts bash commands matching `VALID_CMD_STARTS`. The model's plain-text answer was always rejected, falling through to "I don't have offline documentation". Fixed by adding a separate `query_explain()` function in `interpreter.py` with its own `EXPLAIN_SYSTEM_PROMPT` (asks for plain English, 3-5 lines) and a dedicated display path in `handle_explain()` that prints the raw AI response directly without command validation.

---



### Fixed
- **`explain` phrase queries ignored AI** — `explain what a zombie process is` and similar natural language explain queries were hitting the offline dict (failing), then showing "I don't have offline documentation" without ever trying the LLM. Now falls back to LLM automatically when offline dict has no result.

---

## [v0.6.2] — Phase 5 — Hotfix 2 — 2026-05-26

### Fixed
- **Model download always failing** — `wget` was missing `-L` (follow redirects) flag; HuggingFace URLs redirect before serving the file, causing silent failure
- **No curl fallback** — if `wget` unavailable or fails, now retries with `curl -L`
- **Partial file not validated** — success now requires file exists AND is >1MB; partial downloads cleaned up on failure
- **Installer banner showed v0.5.0** — hardcoded version string updated to v0.6.1 (now reads from installer correctly)

---

## [v0.6.1] — Phase 5 — Hotfix — 2026-05-25

### Fixed
- **Param extraction: connector words** (`called`, `named`, `for`, `into`, etc.) no longer get picked as the argument value — e.g. `create a folder called myproject` now correctly produces `mkdir -p myproject` instead of `mkdir -p called`
- **Filename extension splitting** — filenames like `test.txt` were being tokenized into `test` and `txt` separately; now preserved as a single token so `delete file test.txt` produces `rm test.txt`
- **Multi-placeholder fallback** — commands with two placeholders (e.g. `zip -r {output}.zip {folder}/`) now use the extracted arg for both slots instead of leaving `<output>` unfilled
- **Question-word false matches** — `what`, `which`, `who`, `does`, `explain` added to STOP_WORDS; prevents `what is grep` from scoring against pattern commands
- **`show storage` false-routing to setup_storage** — added `show storage`, `storage space`, `view storage`, `storage usage` triggers to `check_storage` pattern; tightened `setup_storage` triggers to require explicit permission/setup intent
- **`install.sh` command not found on line 201** — binary path now uses `$PREFIX/bin` (standard Termux path) instead of hardcoded `/data/data/com.termux/files/usr/bin`; `chmod` result now checked explicitly; alias always written as a reliable fallback
- **Noob mode raw output** — `ls -la`, `df -h`, `free`, `ping`, `git status` output now translated to plain English in Noob mode instead of dumping raw terminal lines; Learner and Pro modes unaffected
- **`print_result` signature** — added `command` parameter so output translator knows which command ran; all call sites updated

---

## [v0.6.0] — Phase 5 — Polish & Release — 2026-05-25

### Added
- `modules/updater.py` — full self-update + data refresh
  - `check_for_update()` — queries GitHub releases API
  - `do_code_update()` — git pull on VERNUX install dir
  - `refresh_pkg_cache()` — fetches latest from GitHub raw
  - `refresh_patterns()` — fetches latest patterns.json
  - `refresh_recipes()` — fetches latest recipes.json
  - `compare_versions()` — semver comparison
  - `run_full_update()` — full pipeline: code + data
- `modules/doctor.py` — rebuilt from scratch, 23 checks across 6 categories
  - Runtime: VERNUX version, Python version, stdlib deps
  - Storage: Termux home space, SD card space, permission
  - RAM: available memory with % used
  - Network: ping + curl fallback
  - Packages: git, curl, wget, zip, git config, termux-api
  - VERNUX data: patterns, pkg_cache, recipes, models.json, device profile, config
  - Git repo health (can VERNUX auto-update?)
  - LLM: llama.cpp binary, installed models
  - Android: brand quirks, battery optimization / wake lock
  - `run_quick_checks()` — 7-check fast subset
- `vernux stats` — session summary (commands, packages installed, cwd, device)
- `vernux update` — fully implemented (was stub in Phase 4)
- `quick-doctor` — fast health check inside REPL
- Exit message shows session command count
- `.github/workflows/code-check.yml` — CI on every push: syntax, JSON, data counts, recipe schema, build_db smoke test
- `.github/workflows/release-validation.yml` — release gate: version tag match, CHANGELOG entry, full test suite, docs existence, install.sh syntax
- `README.md` — full public README with install instructions, usage, modes, safety table, recipes table, features, requirements, status table
- `CHANGELOG.md` — complete history from Phase 0 to Phase 5
- `docs/CONTRIBUTING.md` — full guide: bug reports, pattern suggestions, recipe submissions, code standards, architecture overview, commit format
- `docs/DEVICES.md` — OEM quirk database: Xiaomi, OPPO/Realme, Vivo/iQOO, Samsung, OnePlus + device submission template
- `docs/RECIPES.md` — community recipe contribution guide (written in Phase 3, finalized)

### Changed
- `modules/__init__.py` — version `0.6.0`, PHASE_NAME = "Polish & Release"
- `vernux.py` — `vernux update` fully wired to updater; `stats` command added; exit message improved
- `install.sh` — production-ready: Python/git checks, storage check, device profile, OEM brand warnings, optional model download, creates `vernux` binary in PATH

### Deliverable
VERNUX is publicly installable with one curl command. 23-check doctor. Self-updating. Community infrastructure ready.

---

## [v0.5.0] — Phase 4 — Local AI — 2026-05-25

### Added
- `modules/interpreter.py` — local LLM fallback via llama.cpp
  - Auto-model selection by device RAM
  - Tightly constrained Termux-aware system prompt
  - Output validation: strips markdown, chatty prefixes, natural language (12/12 cases)
  - Result caching (~/.vernux/llm_cache.json), bounded to 500 entries
  - 45s timeout with graceful failure
  - LLM output always classified + requires confirmation
- `models.json` — 5 curated GGUF models (Qwen2.5-Coder 1.5B Q4/Q6, Phi-4 Mini Q4/Q6, Qwen2.5-Coder 3B Q4)
- `install-model` — interactive model downloader inside REPL
- `ai status` command

---

## [v0.4.0] — Phase 3 — Recipes — 2026-05-25

### Added
- `modules/recipes.py` — stateful recipe engine
  - Prerequisite checking + auto-install
  - Interactive parameter collection (lazy, per-step)
  - Per-step safety classification with confirmation
  - Conditional step logic (if_output_contains, if_empty_run)
  - pause_after for human actions (e.g. add SSH key to GitHub)
  - Checkpoint on failure
  - Retry/skip/quit on step failure (Learner/Pro)
- `data/recipes.json` — 10 built-in recipes (60 total steps)
- `modules/notify.py` — long task notices, brand warnings, tmux suggestions
- `docs/RECIPES.md` — community recipe guide with full schema

---

## [v0.3.0] — Phase 2 — Knowledge Base — 2026-05-25

### Added
- `modules/explainer.py` — offline command dictionary, 60+ commands, 3 mode depths
- `modules/reality_bridge.py` — 14+ Android/Termux gotcha scenarios, brand-specific notes
- `modules/packages.py` — 70+ package name remappings, RAM warnings, alternatives
- `modules/context.py` — SessionContext singleton
- `data/patterns.json` — expanded to 151 patterns
- `data/pkg_cache.json` — expanded to 62 packages
- `vernux explain <cmd>` — inline explainer in REPL

---

## [v0.2.0] — Phase 1 — Core Engine — 2026-05-25

### Added
- `modules/matcher.py` — keyword extraction + fuzzy scoring, 50 patterns
- `modules/safety.py` — context-aware risk classifier (🟢🟡🔴☠️)
- `modules/executor.py` — subprocess runner, 30+ error translations
- `modules/mode.py` — Noob/Learner/Pro output filtering
- `modules/ui.py` — full ANSI terminal display
- `modules/doctor.py` — 12 health checks (initial version)
- Full REPL: matcher → safety → confirm → executor pipeline

---

## [v0.1.0] — Phase 0 — Foundation — 2026-05-25

### Added
- Project structure, all module stubs with documented interfaces
- `modules/config.py` — user config manager
- `modules/device.py` — device profiler (RAM, CPU, storage, brand, tier classification)
- `tools/build_db.py` — data pipeline with 30 seed patterns + 30 packages
- `vernux.py` — entry point with first-run setup and REPL stub
- `install.sh` — installer skeleton
- `README.md`, `LICENSE` (GPL v3), `CHANGELOG.md`
- GitHub Actions stubs, issue templates
