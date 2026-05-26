# =============================================================================
# modules/interpreter.py — Local LLM Fallback Engine
# Version: 0.5.0 | Phase 4 — Local AI
# =============================================================================
#
# Called only when pattern matching fails (confidence < threshold).
# Runs a local GGUF model via llama.cpp — fully offline, no API, no cost.
# Optional: VERNUX works without this if no model is installed.
# =============================================================================

import json
import os
import re
import shutil
import subprocess
import hashlib
import time

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
MODELS_FILE  = os.path.join(os.path.dirname(__file__), "../models.json")
MODELS_DIR   = os.path.expanduser("~/.vernux/models")
CACHE_FILE   = os.path.expanduser("~/.vernux/llm_cache.json")

# ---------------------------------------------------------------------------
# System prompt — tightly constrained, Termux-aware
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """You are a bash expert running inside Termux on Android.
Your ONLY job is to output the exact bash command(s) to accomplish what the user asks.

STRICT RULES:
- Reply with ONLY the bash command(s). Nothing else.
- No explanation. No markdown. No code blocks. No backticks.
- No preamble like "Here's the command:" or "To do this:".
- Use 'pkg' not 'apt' or 'apt-get'. Termux uses pkg.
- Never use 'sudo'. Termux doesn't have sudo (use 'tsu' if root is needed).
- Use 'python3' not 'python'.
- For multi-step tasks, separate commands with ' && '.
- If the task is impossible in Termux, reply with exactly: IMPOSSIBLE
- If you are unsure, reply with the closest reasonable command.

Examples:
User: install nodejs
Output: pkg install nodejs -y

User: show disk usage sorted by size
Output: du -sh ~/* | sort -rh | head -20

User: compress the project folder
Output: zip -r project.zip project/"""

# ---------------------------------------------------------------------------
# Model loader
# ---------------------------------------------------------------------------
_MODELS_DATA = None

def _load_models() -> dict:
    global _MODELS_DATA
    if _MODELS_DATA:
        return _MODELS_DATA
    try:
        with open(os.path.abspath(MODELS_FILE)) as f:
            _MODELS_DATA = json.load(f)
    except Exception:
        _MODELS_DATA = {"models": [], "prompt_formats": {}}
    return _MODELS_DATA


def select_model(ram_total_gb: float) -> dict | None:
    """
    Auto-select the best installed model for the device's RAM.
    Prefers higher quality within the device's tier.
    Returns the model dict or None if no model is installed.
    """
    data   = _load_models()
    models = data.get("models", [])

    # Filter to models that fit in RAM and are installed
    candidates = []
    for m in models:
        model_path = os.path.join(MODELS_DIR, m["file"])
        if not os.path.exists(model_path):
            continue
        if ram_total_gb >= m["min_ram_gb"]:
            candidates.append(m)

    if not candidates:
        return None

    # Sort by recommended_ram_gb descending (best quality that fits)
    candidates.sort(key=lambda m: m["recommended_ram_gb"], reverse=True)

    # Pick the best one that's comfortably within RAM
    for c in candidates:
        if ram_total_gb >= c["recommended_ram_gb"]:
            return c

    # Fallback: the lightest available
    candidates.sort(key=lambda m: m["min_ram_gb"])
    return candidates[0]


def get_model_path(model: dict) -> str:
    return os.path.join(MODELS_DIR, model["file"])


def list_installed_models() -> list[dict]:
    """Return all models that are downloaded and ready."""
    data   = _load_models()
    result = []
    for m in data.get("models", []):
        path = os.path.join(MODELS_DIR, m["file"])
        if os.path.exists(path):
            size_mb = os.path.getsize(path) // (1024 * 1024)
            result.append({**m, "installed": True, "actual_size_mb": size_mb})
    return result


# ---------------------------------------------------------------------------
# llama.cpp detection
# ---------------------------------------------------------------------------

def find_llama_cpp() -> str | None:
    """
    Find the llama.cpp binary. Checks common Termux locations.
    Returns path or None.
    """
    candidates = [
        "llama-cli",                       # newer llama.cpp name
        "llama.cpp",
        os.path.expanduser("~/.vernux/bin/llama-cli"),
        os.path.expanduser("~/.vernux/bin/llama.cpp"),
        "/data/data/com.termux/files/usr/bin/llama-cli",
        "/data/data/com.termux/files/usr/bin/llama.cpp",
    ]
    for c in candidates:
        try:
            r = subprocess.run(
                ["which", c.split("/")[-1]] if "/" not in c else [c, "--version"],
                capture_output=True, text=True, timeout=3
            )
            if r.returncode == 0:
                return c
        except Exception:
            continue
    return None


def is_available() -> bool:
    """Returns True if llama.cpp binary + at least one model are present."""
    from modules.config import get as config_get
    if not config_get("llm_enabled", False):
        return False
    if find_llama_cpp() is None:
        return False
    return len(list_installed_models()) > 0


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------
_CACHE: dict | None = None


def _load_cache() -> dict:
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE) as f:
                _CACHE = json.load(f)
            return _CACHE
        except Exception:
            pass
    _CACHE = {}
    return _CACHE


def _save_cache(cache: dict):
    try:
        os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
        with open(CACHE_FILE, "w") as f:
            json.dump(cache, f, indent=2)
    except Exception:
        pass


def _cache_key(user_input: str) -> str:
    return hashlib.md5(user_input.lower().strip().encode()).hexdigest()


def _get_cached(user_input: str) -> str | None:
    cache = _load_cache()
    return cache.get(_cache_key(user_input))


def _set_cached(user_input: str, command: str):
    cache = _load_cache()
    cache[_cache_key(user_input)] = command
    # Keep cache bounded to 500 entries
    if len(cache) > 500:
        keys = list(cache.keys())
        for k in keys[:100]:
            del cache[k]
    _save_cache(cache)


# ---------------------------------------------------------------------------
# Output validation
# ---------------------------------------------------------------------------

# Patterns that indicate a valid bash command
VALID_CMD_STARTS = re.compile(
    r"^(pkg|pip|python3?|node|npm|git|wget|curl|tar|zip|unzip|rm|cp|mv|ls|cd|"
    r"mkdir|touch|chmod|chown|cat|grep|find|echo|export|source|ssh|scp|"
    r"tmux|nano|vim|htop|top|ps|kill|pkill|df|du|free|uname|date|which|"
    r"ffmpeg|yt-dlp|sqlite3|php|ruby|go|cargo|make|cmake|sh|bash|tsu|"
    r"termux-|openssl|sed|awk|sort|head|tail|wc|tr|cut|xargs|nohup|"
    r"./|~|/)",
    re.IGNORECASE
)

IMPOSSIBLE_MARKER = "IMPOSSIBLE"

# Phrases that indicate non-command output (model being chatty)
CHATTY_PATTERNS = [
    r"^here(\'s| is) the",
    r"^to (do|accomplish|run|execute|install)",
    r"^you (can|should|need to)",
    r"^i (would|suggest|recommend)",
    r"^the command",
    r"^this (will|command)",
    r"^sure[,!]",
    r"^of course",
]
CHATTY_RE = re.compile("|".join(CHATTY_PATTERNS), re.IGNORECASE)


def validate_output(raw_output: str) -> str | None:
    """
    Validate and clean LLM output.
    Returns clean command string, or None if output is unusable.
    """
    if not raw_output:
        return None

    text = raw_output.strip()

    # IMPOSSIBLE marker
    if text.upper().startswith(IMPOSSIBLE_MARKER):
        return None

    # Strip markdown code blocks
    text = re.sub(r"```(?:bash|sh|shell)?[\s]*", "", text)
    text = re.sub(r"```", "", text).strip()

    # Try to extract command after common chatty prefixes
    # Handles: "Here is the command: CMD", "Run: CMD", "Sure! CMD", etc.
    colon_extract = re.search(
        r"(?:here(?:'s| is).*?:|to .+?:|you should.*?:|sure[!,]?\s|run:|use:|try:)\s*(.+)",
        text, re.IGNORECASE | re.DOTALL
    )
    if colon_extract:
        candidate = colon_extract.group(1).strip().strip("`'\"").splitlines()[0].strip()
        if candidate and VALID_CMD_STARTS.match(candidate):
            return candidate

    # Walk lines to find first valid command
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    for line in lines:
        line = line.strip().strip("`'\"").strip()
        if not line or line.upper() == IMPOSSIBLE_MARKER:
            continue
        # Skip obvious natural language
        first = line.split()[0].lower() if line.split() else ""
        if first in {
            "the","this","that","you","i","to","a","an","in","for",
            "with","and","or","not","but","if","when","here","note",
            "first","then","also","please","just","of","sure","ok"
        }:
            # Still try colon extraction on this line
            m = re.search(r":\s*(.+)$", line)
            if m:
                after = m.group(1).strip().strip("`")
                if after and VALID_CMD_STARTS.match(after):
                    return after
            continue
        if VALID_CMD_STARTS.match(line):
            return line

    return None

# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

def _build_prompt(user_input: str, model: dict) -> str:
    """Build the full prompt string for the given model's format."""
    data   = _load_models()
    fmts   = data.get("prompt_formats", {})
    fmt_id = model.get("prompt_format", "chatml")
    fmt    = fmts.get(fmt_id, fmts.get("chatml", {}))

    sp = fmt.get("system_prefix", "")
    ss = fmt.get("system_suffix", "")
    up = fmt.get("user_prefix", "")
    us = fmt.get("user_suffix", "")
    ap = fmt.get("assistant_prefix", "")

    return f"{sp}{SYSTEM_PROMPT}{ss}{up}{user_input}{us}{ap}"


# ---------------------------------------------------------------------------
# Main query function
# ---------------------------------------------------------------------------

DEFAULT_TIMEOUT = 45   # seconds


def query(user_input: str, timeout: int = DEFAULT_TIMEOUT) -> str | None:
    """
    Query the local LLM with a user input.
    Returns a validated bash command string, or None on failure.

    Flow:
      1. Check cache — return instantly if seen before
      2. Check llama.cpp + model available
      3. Select best model for device RAM
      4. Build prompt
      5. Run llama.cpp subprocess with timeout
      6. Validate output
      7. Cache result
    """
    from modules.config import get as config_get
    from modules.device import load_profile

    # Config check
    if not config_get("llm_enabled", False):
        return None

    # Cache hit
    cached = _get_cached(user_input)
    if cached:
        return cached

    # Find binary
    binary = find_llama_cpp()
    if not binary:
        return None

    # Select model
    profile    = load_profile()
    ram_gb     = profile.get("ram", {}).get("total_gb", 2.0)
    model      = select_model(ram_gb)
    if model is None:
        return None

    model_path = get_model_path(model)
    prompt     = _build_prompt(user_input, model)

    # Build llama.cpp command
    stop_tokens = _load_models().get(
        "prompt_formats", {}
    ).get(model.get("prompt_format", "chatml"), {}).get("stop_tokens", [])

    cmd = [
        binary,
        "--model",      model_path,
        "--prompt",     prompt,
        "--n-predict",  "128",
        "--ctx-size",   "2048",
        "--temp",       "0.1",
        "--top-p",      "0.9",
        "--threads",    str(max(1, (profile.get("cpu", {}).get("cores", 2)) - 1)),
        "--no-display-prompt",
        "--log-disable",
    ]
    for st in stop_tokens:
        cmd += ["--reverse-prompt", st]

    # Run with timeout
    # stderr=DEVNULL suppresses llama.cpp startup banner (version 0/unknown ignores --log-disable)
    try:
        start  = time.time()
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=timeout,
        )
        elapsed = round(time.time() - start, 1)
        raw     = result.stdout.strip()
    except subprocess.TimeoutExpired:
        return None
    except Exception:
        return None

    # Validate
    command = validate_output(raw)
    if command:
        _set_cached(user_input, command)

    return command


# ---------------------------------------------------------------------------
# Explain prompt + query — for natural language explanation queries
# ---------------------------------------------------------------------------

EXPLAIN_SYSTEM_PROMPT = """You are a helpful assistant for Termux on Android.
The user wants a plain English explanation. Answer clearly and concisely in 3-5 lines.
No markdown. No bullet points. No code blocks. Just plain readable text."""


def query_explain(user_input: str, timeout: int = DEFAULT_TIMEOUT) -> str | None:
    """
    Query the local LLM for a plain-text explanation (not a bash command).
    Returns raw model output string, or None on failure.
    Used by handle_explain() in vernux.py when the offline dict has no answer.
    """
    from modules.config import get as config_get
    from modules.device import load_profile

    if not config_get("llm_enabled", False):
        return None

    binary = find_llama_cpp()
    if not binary:
        return None

    profile   = load_profile()
    ram_gb    = profile.get("ram", {}).get("total_gb", 2.0)
    model     = select_model(ram_gb)
    if model is None:
        return None

    model_path = get_model_path(model)

    # Build prompt using model's format but with explain system prompt
    data   = _load_models()
    fmts   = data.get("prompt_formats", {})
    fmt_id = model.get("prompt_format", "chatml")
    fmt    = fmts.get(fmt_id, fmts.get("chatml", {}))

    sp = fmt.get("system_prefix", "")
    ss = fmt.get("system_suffix", "")
    up = fmt.get("user_prefix", "")
    us = fmt.get("user_suffix", "")
    ap = fmt.get("assistant_prefix", "")

    prompt = f"{sp}{EXPLAIN_SYSTEM_PROMPT}{ss}{up}{user_input}{us}{ap}"

    stop_tokens = data.get("prompt_formats", {}).get(fmt_id, {}).get("stop_tokens", [])

    cmd = [
        binary,
        "--model",      model_path,
        "--prompt",     prompt,
        "--n-predict",  "200",
        "--ctx-size",   "2048",
        "--temp",       "0.3",
        "--top-p",      "0.9",
        "--threads",    str(max(1, (profile.get("cpu", {}).get("cores", 2)) - 1)),
        "--no-display-prompt",
        "--log-disable",
    ]
    for st in stop_tokens:
        cmd += ["--reverse-prompt", st]

    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=timeout,
        )
        raw = result.stdout.strip()
    except subprocess.TimeoutExpired:
        return None
    except Exception:
        return None

    return raw if raw else None


# ---------------------------------------------------------------------------
# Model downloader
# ---------------------------------------------------------------------------

def download_model(model: dict, on_progress=None) -> bool:
    """
    Download a model file to MODELS_DIR using wget (with curl fallback).
    Follows redirects, retries once on failure, cleans up partial files.
    Returns True on success.
    """
    os.makedirs(MODELS_DIR, exist_ok=True)
    dest = get_model_path(model)

    if os.path.exists(dest):
        return True  # Already downloaded

    url = model.get("url")
    if not url:
        return False

    def _cleanup():
        if os.path.exists(dest):
            os.remove(dest)

    # Try wget first (follows redirects, shows progress)
    wget_cmd = [
        "wget",
        "-L",                      # follow redirects (critical for HuggingFace)
        "--show-progress",
        "--progress=dot:mega",
        "--tries=2",               # one retry on failure
        "--timeout=30",            # 30s connect timeout
        "-O", dest,
        url
    ]

    # Fallback: curl
    curl_cmd = [
        "curl",
        "-L",                      # follow redirects
        "--progress-bar",
        "--retry", "2",
        "--connect-timeout", "30",
        "-o", dest,
        url
    ]

    for cmd in [wget_cmd, curl_cmd]:
        tool = cmd[0]
        # shutil.which works on Termux (no 'which' binary needed)
        if shutil.which(tool) is None:
            continue
        try:
            proc = subprocess.run(cmd, timeout=7200)
            if proc.returncode == 0 and os.path.exists(dest) and os.path.getsize(dest) > 1024 * 1024:
                return True
            else:
                _cleanup()
        except Exception:
            _cleanup()

    return False


def get_download_advice(model: dict, device_tier: str, mode: str) -> str:
    """
    Return a warning message for downloading on low-end devices.
    """
    size_mb = model.get("size_mb", 0)
    size_str = f"{size_mb}MB" if size_mb < 1000 else f"{size_mb/1000:.1f}GB"
    lines = []

    if device_tier in ("micro", "low"):
        lines.append(
            f"  ⚠  This model ({size_str}) may run slowly on your device."
        )
        if mode == "noob":
            lines.append(
                "  The AI responses will take 10–60 seconds. That's normal."
            )
        else:
            lines.append(
                f"  Expect 10–60s per query on {device_tier} tier devices."
            )

    lines.append(f"  📦 Download size: {size_str}")
    lines.append(f"  📍 Saved to: {MODELS_DIR}/")

    return "\n".join(lines)
