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

## [v0.6.3] — Phase 5 — Hotfix 3 — 2026-05-26

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
