# Contributing to VERNUX

Thanks for wanting to make VERNUX better. This guide covers every way to contribute.

---

## Ways to Contribute

### 1. Report a Bug

Use the **Bug Report** issue template. Include:
- What you typed
- What VERNUX did
- What you expected
- Your device info (run `vernux doctor` and paste the output)
- Your VERNUX mode (Noob / Learner / Pro)

### 2. Suggest a Pattern

A pattern is a single-command task. If you tried to do something in VERNUX and it said "I don't know how to do that yet", open a **Feature Request**.

Include:
- What natural language phrase you tried
- What bash command you expected

Good candidates: things you do in Termux regularly that aren't in the 151 built-in patterns.

### 3. Submit a Recipe

A recipe is a multi-step workflow. See [RECIPES.md](RECIPES.md) for the full schema and submission guide.

Recipes are submitted as Pull Requests — add your recipe to `data/recipes.json` under the `recipes` array.

### 4. Add Device Notes

If you've found quirks on your specific device, add them to [DEVICES.md](DEVICES.md) via Pull Request.

Format:
```
## Brand / Model (e.g. Xiaomi Redmi Note 12)
Android version: 13  
Termux version: 0.118.0

### Issue
Describe what breaks.

### Fix
Describe the exact fix.
```

### 5. Add a Reality Bridge Scenario

Reality Bridge scenarios cover the non-obvious Android/Termux gotchas. If you know a common problem that isn't already covered, add it to `modules/reality_bridge.py` or as a JSON file in `data/universal/reality_bridge/`.

---

## Code Contributions

### Setup

```bash
# Fork the repo on GitHub, then:
git clone https://github.com/YOUR_USERNAME/Vernux.git
cd Vernux
python3 tools/build_db.py    # build data files
python3 vernux.py            # test it works
```

### Making Changes

```bash
git checkout -b your-feature-name
# make changes
python3 -m py_compile vernux.py modules/*.py   # syntax check
python3 tools/build_db.py                       # rebuild data if needed
# test manually
git add .
git commit -m "describe what you changed"
git push origin your-feature-name
# open a Pull Request
```

### Code Standards

- Python 3.8 compatible (no walrus operator, no 3.10+ match statements in non-critical paths)
- All new modules need syntax-clean (`python3 -m py_compile`)
- New patterns need: `id`, `triggers` (3+ phrases), `command`, all three `description_*` fields, `safety`, `category`
- Safety levels set honestly — when in doubt, use `yellow` not `green`
- No external Python dependencies (stdlib only — no pip requirements)

### What the CI Checks

Every pull request runs:
- Python syntax check on all `.py` files
- JSON validation on all data files
- Minimum count checks (patterns ≥100, recipes ≥5)
- Recipe schema validation
- build_db.py smoke test

---

## Architecture Overview

```
vernux.py               Entry point, REPL, CLI routing
modules/
  config.py             User config (~/.vernux/config.json)
  device.py             Device profiling (RAM, brand, tier)
  matcher.py            NL → pattern matching engine
  safety.py             Context-aware risk classifier
  executor.py           Command runner + error translation
  mode.py               Noob/Learner/Pro output filtering
  ui.py                 ANSI terminal display
  explainer.py          Offline command dictionary (60+ commands)
  packages.py           Package name resolution + intelligence
  reality_bridge.py     Android/Termux gotcha scenarios
  recipes.py            Multi-step workflow engine
  notify.py             Long task notices + brand warnings
  context.py            Session state tracking
  interpreter.py        Local LLM fallback (llama.cpp)
  updater.py            Self-update + data refresh
  doctor.py             Health check (23 checks)
data/
  patterns.json         151 curated NL patterns
  pkg_cache.json        62 Termux packages with metadata
  recipes.json          10 built-in recipes
  universal/
    reality_bridge/     Android/Termux scenario JSON files
models.json             5 curated GGUF model definitions
tools/
  build_db.py           Data ingestion + build pipeline
```

---

## Commit Message Format

```
type: short description

Types: fix, feat, data, docs, refactor, test, chore

Examples:
  fix: matcher not finding check_storage with 'storage left' phrase
  feat: add reality bridge scenario for git push rejected
  data: add 10 new patterns for Node.js ecosystem
  docs: update CONTRIBUTING.md with recipe schema
```

---

## Code of Conduct

Be helpful. Be honest. Be patient with beginners — that's literally what VERNUX is built for.

---

*VERNUX — Built by [@DeVenLucaz](https://github.com/DeVenLucaz)*
