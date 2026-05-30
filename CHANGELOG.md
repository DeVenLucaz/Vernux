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

## [v0.8.0] — Phase 7 — Unified AI Backend — 2026-05-30

### Changed

- **`modules/interpreter.py` — complete rewrite.** The previous version had persistent, unfixable problems with llama.cpp output parsing on Android: banner leaking into responses, empty output on older builds, retry logic that didn't cover all failure modes. Rather than patching it again, the local inference engine was replaced wholesale with the battle-tested stack from [llamdrop](https://github.com/ypatole035-ai/llamdrop) — a separate project purpose-built for running local LLMs on Android/Termux. The subprocess threading pattern, `_extract_response()`, the prompt marker extraction, `_NOISE`/`_META_LINES` filters, and the retry-on-unsupported-flags logic are all ported directly from llamdrop's `chat.py`.

- **Local backend now uses llamdrop's shared binary and models.** Instead of managing its own llama-cli binary, VERNUX now looks for `~/.llamdrop/bin/llama-cli` first — the same binary llamdrop installs. Models in `~/.llamdrop/models/` are detected automatically. If you already have llamdrop and a downloaded model, VERNUX's AI fallback works immediately with no extra setup. `~/.vernux/models/` is still checked as a fallback so existing downloads continue to work.

### Added

- **API backend — any OpenAI-compatible provider.** VERNUX can now use an external AI API instead of (or in addition to) a local model. Supported providers out of the box: OpenAI (ChatGPT), Google Gemini, xAI Grok, Anthropic Claude, OpenRouter, Groq, Mistral, and any custom OpenAI-compatible endpoint (Ollama server, LM Studio, llama.cpp server, etc.). Implemented using only `urllib` from the Python standard library — no `requests` package required.

- **`vernux ai-setup` — interactive AI configuration wizard.** New command that walks the user through choosing and configuring their AI backend. Accessible as `vernux ai-setup` (CLI), `ai-setup` (REPL), or `setup ai` / `configure ai`. The wizard presents:
  - Option 1: API provider — choose from a numbered list of known providers (each showing where to get a key), or enter a custom base URL. Shows a one-time privacy notice explaining exactly where the key is stored and that it never leaves the device except to the chosen provider.
  - Option 2: Local model — checks for llamdrop binary and installed models, shows status, enables local backend.
  - Option 3 (shown only if API is configured): remove the current API config.

- **API key storage — `~/.vernux/api_keys.json`.** Keys are stored in a dedicated file separate from `config.json`. File permissions are set to `0o600` (owner read/write only) immediately after write. A one-time privacy notice is shown before any key is entered — it explains the file location, that it is readable only by the device owner, and that VERNUX is open source and can be audited. The notice is shown exactly once and never repeated.

- **Anthropic Claude native API support.** Claude uses a different authentication header (`x-api-key` instead of `Authorization: Bearer`) and a different message structure. This is handled as a separate code path within the API backend — transparent to the user.

- **`get_active_api_config()` / `set_api_config()` / `clear_api_config()`.** Public functions for reading, writing, and removing the active API configuration from `api_keys.json`.

- **`run_ai_setup_wizard()`.** Public function that `vernux.py` calls for the `ai-setup` command. Also callable programmatically by other parts of the codebase if needed.

- **`is_available()` now returns `True` for either backend.** Previously required `llm_enabled=True` + binary + model. Now also returns `True` if an API config exists — no local model needed.

- **Unified response cache.** Both backends share the same `~/.vernux/llm_cache.json`. Cache keys are namespaced by query type (`cmd` vs `explain`) so a cached command response and a cached explanation for the same input don't collide.

- **`ai status` REPL command updated.** Shows API provider and model if API backend is active; shows local model name and size if local backend is active.

### Fixed

- **Persistent llama.cpp output corruption on Android.** The previous `_strip_banner()` / `validate_output()` approach was fragile against the variety of llama-cli build versions found on Android. The new `_extract_response()` uses prompt marker detection first (reliable on all modern builds), falling back to line-by-line noise filtering only when no marker is found. The `_NOISE` and `_META_LINES` filter sets are tighter and more accurate.

- **Retry on unsupported flags.** If the llama-cli binary is too old to support `--single-turn`, `--no-display-prompt`, `--simple-io`, or `--log-disable`, the subprocess now automatically retries without those flags rather than returning empty output.

- **Spinner no longer freezes during inference.** Stdout is collected in a daemon thread using line-by-line iteration, releasing the GIL between reads. This was a known bug in the previous version where the spinner animation stopped while the model was running.

### Changed (vernux.py)

- Import block extended with `run_ai_setup_wizard`, `get_active_api_config`.
- `print_help()` — AI status line now shows API provider/model when API backend is active, or local model name when local backend is active. Dead-end tip updated from `'install-model'` to `'ai-setup'`.
- `handle_ai_setup()` added — thin wrapper that calls `run_ai_setup_wizard(mode)`.
- `handle_cli_args()` — `ai-setup`, `ai_setup`, `setup-ai` all route to `handle_ai_setup()`.
- REPL — `ai-setup`, `setup ai`, `configure ai`, `ai setup` all route to `handle_ai_setup()`.
- REPL — `ai status` shows API config if active, local model otherwise.
- `modules/__init__.py` — version bumped to `0.8.0`, `PHASE = 7`, `PHASE_NAME = "Unified AI Backend"`.

---

## [v0.7.6] — Phase 6 — Recipe Preview — 2026-05-28

### Fixed

- **Recipe confirmation had no context.** When a recipe matched (e.g. "push my project to github"), VERNUX showed the title, description, step count, and estimated time — then immediately asked "Start this recipe? [y/N]". The user had no idea what the recipe would actually do or what information it would ask for before committing. Fixed by adding a full step preview before the confirmation prompt.

### Added

- **Recipe step preview** — before asking "Start this recipe?", VERNUX now shows:
  - A numbered list of every step with a plain English description (mode-aware: noob gets the noob description, learner gets the learner description)
  - A "It will ask you for:" section listing every input the recipe needs from the user (e.g. "Your GitHub username", "Repository name on GitHub", "Your GitHub email")
  - This gives the user full context to decide yes or no before anything runs

---

## [v0.7.5] — Phase 6 — Database Expansion — 2026-05-28

### Added

- **`tools/build_library_tldr.py`** — new build tool that downloads the tldr-pages zip (~5MB, CC0 public domain), parses `pages/android/`, `pages/linux/`, and `pages/common/` platforms, and converts them into VERNUX's offline library format. Key features:
  - Mode-aware output generation — noob gets description + first example walkthrough, learner gets description + up to 3 annotated examples, pro gets one-line summary
  - Smart merge — by default, existing LCL entries win (richer data), tldr fills gaps only. `--overwrite` flag available for reverse priority
  - `--quick` mode for android + common only (faster for low-storage devices)
  - `--cmd <name>` for testing a single command parse
  - Placeholder cleanup — converts `{{arg}}` syntax to readable `<arg>`
  - Category auto-detection using the same category map as the rest of VERNUX
  - Full meta block written to library.json tracking entry counts per source

- **710+ command offline library** — tldr-pages adds ~200 entries not covered by LinuxCommandLibrary, including all major git subcommands (`git-clone`, `git-checkout`, `git-stash`, etc.), termux-specific tools, and modern CLI utilities (`fzf`, `bat`, `ripgrep`, `fd`, `httpie`).

- **Automatic library build on install** — `install.sh` now runs `build_library_tldr.py --quiet` automatically as Step 7b. New users get the full 710+ command library immediately after install with no manual steps.

- **Automatic library refresh on update** — `modules/updater.py` now includes `refresh_library()` which runs `build_library_tldr.py --quiet` as part of the `run_full_update()` pipeline. Every `vernux update` now refreshes the command library alongside patterns, recipes, and pkg cache. `handle_update()` in `vernux.py` shows "Command library refreshed" in the update summary.

### Changed

- **README.md** — removed manual library build instructions (now automatic), updated tldr-pages credits section, updated library badge to 700+.
- **`modules/updater.py`** — added `refresh_library()` function and `"library"` key to `run_full_update()` results dict.
- **`vernux.py`** — `handle_update()` now shows library refresh status in the update summary output.
- **`modules/__init__.py`** — version bumped to `0.7.5`.

### Why this matters

Before this, VERNUX's AI fallback was the only way to answer `what is git stash` or `explain fzf`. Now the offline library handles hundreds more queries without touching the model at all — faster, works without a downloaded model, and gives mode-aware answers with real examples. And it all happens automatically.

---

## [v0.7.4] — Phase 6 — AI Fallback Fix — 2026-05-27

### Fixed

- **`handle_update` NameError crash** — `vernux update` was crashing with `NameError: name 'handle_update' is not defined` because the function was called in `handle_cli_args()` and the main loop but never actually defined. Added `handle_update()` which runs `run_full_update()` and prints a clean mode-aware summary (noob gets friendly message, learner/pro get compact output).
- **llama.cpp banner leak** — Old llama.cpp builds (`b0-unknown`) ignore `--log-disable` and dump the full startup banner, available commands menu, and echoed system prompt to **stdout** instead of stderr. Fixed with `--simple-io -e` flags and `_strip_banner()` helper in `modules/interpreter.py`.
- **`_strip_banner()` over-stripping real AI output** — Strategy 2 of the banner stripper used a broad prefix list including words like `"model"`, `"version"`, `"cli"`, `"cpu"` which appear in normal English answers (e.g. `"A monorepo is a version..."`). This silently ate the AI's actual response. Fixed: Strategy 2 now first checks for definitive llama.cpp banner markers (`llama.cpp`, `available commands:`, `ggml_`, etc.) before doing any line-skipping. If no banner is detected, raw output is returned as-is. Skip prefix list tightened to only exact llama.cpp UI patterns.
- **AI fallback ignoring question/explanation queries** — The system prompt told the AI to output only bash commands. When users asked questions like `"what is json"`, `validate_output()` rejected the natural language answer. Fixed by adding intent detection — question queries now route to `llm_query_explain()`.

### Added

- **`handle_update()`** — properly defined update handler in `vernux.py`.
- **`_is_question()`** — intent classifier covering `what is`, `how does`, `explain`, `why is`, `difference between`, `how do i`, and similar phrasings.
- **`_extract_topic()`** — strips question prefixes to extract core topic for follow-up hints.
- **`_llm_explain_flow()`** — routes question queries to explain flow with mode-aware output (noob: plain English + learn more hint; learner: explanation + related command; pro: one line + shortcut).
- **`try_llm_fallback()` reworked** — intent detection first, then routes to explain or command flow accordingly.

### Changed

- `modules/interpreter.py` — `_strip_banner()` rewritten with safer detection logic.
- `modules/__init__.py` — version bumped to `0.7.4`.

---

## [v0.7.3] — Phase 6 — Pattern Builder — 2026-05-27

### Fixed

- **`handle_update` NameError crash** — `vernux update` was crashing with `NameError: name 'handle_update' is not defined` because the function was called in `handle_cli_args()` and the main loop but never actually defined. Added `handle_update()` which runs `run_full_update()` and prints a clean mode-aware summary (noob gets friendly message, learner/pro get compact output).
- **llama.cpp banner leak** — Old llama.cpp builds (`b0-unknown`) ignore `--log-disable` and dump the full startup banner, available commands menu, and echoed system prompt to **stdout** instead of stderr, causing all of that noise to appear in the terminal and corrupt the AI output. Fixed with two layers:
  1. Added `--simple-io` and `-e` flags to the llama-cli invocation — these suppress interactive UI on older builds.
  2. Added `_strip_banner()` helper in `modules/interpreter.py` — strips everything before the actual AI response using the prompt tail as an anchor, with a heuristic line-scanner fallback for builds that mangle the output differently.
- **AI fallback ignoring question/explanation queries** — The system prompt told the AI to output only bash commands. When users asked questions like `"what is json"` or `"explain grep"`, `validate_output()` correctly rejected the natural language answer as not a command, so the fallback silently returned nothing. Fixed by adding intent detection before the AI is called.

### Added

- **`handle_update()`** — properly defined update handler in `vernux.py`. Calls `run_full_update()`, prints version status and data file refresh results. Mode-aware finish message.
- **`_is_question()`** — intent classifier in `vernux.py` that detects explanation/question queries using a regex pattern covering `what is`, `how does`, `explain`, `why is`, `difference between`, `how do i`, and similar phrasings.
- **`_extract_topic()`** — strips question prefixes from user input to extract the core topic word(s), used for follow-up hints.
- **`_llm_explain_flow()`** — new function that routes question queries to `llm_query_explain()` instead of `llm_query()`, with full mode-aware output:
  - **Noob** — plain English answer + `"Want to learn more? Try: explain <topic>"` hint
  - **Learner** — full explanation + related command surfaced from offline library with breakdown hint
  - **Pro** — first paragraph only + `→ explain <command>` shortcut, no hand-holding
- **`try_llm_fallback()` reworked** — now routes through intent detection first. Question → `_llm_explain_flow()`. Action → bash command flow (unchanged). If action query returns no command, falls back to explain flow as last resort.
- **Pro mode AI action output** — pro mode now shows `$ command` directly without the `🤖 AI generated:` label.

### Changed

- `modules/interpreter.py` — `query()` and `query_explain()` both now call `_strip_banner()` on raw stdout before processing.
- `modules/__init__.py` — version bumped to `0.7.4`.

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
