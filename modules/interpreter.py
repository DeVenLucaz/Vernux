# =============================================================================
# modules/interpreter.py — AI Backend (Local + Any API)
# Version: 0.8.0 | Phase 7 — Unified AI Backend
# =============================================================================
#
# Two backends, one interface:
#
#   LocalBackend  — uses llamdrop's proven llama-cli binary + GGUF models.
#                   Binary:  ~/.llamdrop/bin/llama-cli  (or PATH)
#                   Models:  ~/.llamdrop/models/  (or ~/.vernux/models/)
#                   Output cleaning: ported directly from llamdrop's
#                   battle-tested _extract_response() + retry logic.
#
#   APIBackend    — any OpenAI-compatible HTTP endpoint.
#                   Works with: OpenAI, Gemini (via openai compat), Grok,
#                   Claude (via openai compat), OpenRouter, Mistral, Groq,
#                   or any local server (Ollama, llama.cpp server, LM Studio).
#                   Keys stored in ~/.vernux/api_keys.json (local only).
#
# Public API (unchanged — vernux.py needs zero edits):
#   query(user_input)         → bash command str | None
#   query_explain(user_input) → explanation str | None
#   is_available()            → bool
#   list_installed_models()   → list[dict]
#   select_model(ram_gb)      → dict | None
#   download_model(model)     → bool
#   get_download_advice(...)  → str
#   _load_models()            → dict  (used by vernux.py handle_install_model)
# =============================================================================

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_HERE        = os.path.dirname(os.path.abspath(__file__))
MODELS_FILE  = os.path.join(_HERE, "../models.json")
MODELS_DIR   = os.path.expanduser("~/.vernux/models")

# llamdrop paths — shared binary and model store
LLAMDROP_BIN_DIR    = os.path.expanduser("~/.llamdrop/bin")
LLAMDROP_MODELS_DIR = os.path.expanduser("~/.llamdrop/models")

CACHE_FILE   = os.path.expanduser("~/.vernux/llm_cache.json")
API_KEYS_FILE = os.path.expanduser("~/.vernux/api_keys.json")

# ---------------------------------------------------------------------------
# System prompts
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

EXPLAIN_SYSTEM_PROMPT = """You are a helpful assistant for Termux on Android.
The user wants a plain English explanation. Answer clearly and concisely in 3-5 lines.
No markdown. No bullet points. No code blocks. Just plain readable text."""

# ---------------------------------------------------------------------------
# Models metadata loader
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


# ---------------------------------------------------------------------------
# Model selection + listing (unchanged API, extended to cover both dirs)
# ---------------------------------------------------------------------------

def _get_model_path(model: dict) -> str:
    """
    Return the path to a model file.
    Checks ~/.llamdrop/models/ first (shared with llamdrop, no duplication),
    then falls back to ~/.vernux/models/ for Vernux-only downloads.
    """
    for directory in [LLAMDROP_MODELS_DIR, MODELS_DIR]:
        candidate = os.path.join(directory, model["file"])
        if os.path.exists(candidate):
            return candidate
    # Default write target for new downloads
    return os.path.join(MODELS_DIR, model["file"])


def get_model_path(model: dict) -> str:
    return _get_model_path(model)


def list_installed_models() -> list:
    """Return all models that are downloaded and ready (either directory)."""
    data   = _load_models()
    result = []
    for m in data.get("models", []):
        path = _get_model_path(m)
        if os.path.exists(path):
            size_mb = os.path.getsize(path) // (1024 * 1024)
            result.append({**m, "installed": True, "actual_size_mb": size_mb,
                           "path": path})
    return result


def select_model(ram_total_gb: float) -> dict | None:
    """
    Auto-select the best installed model for the device's RAM.
    Prefers highest quality that fits comfortably. Returns None if nothing installed.
    """
    data       = _load_models()
    candidates = []
    for m in data.get("models", []):
        path = _get_model_path(m)
        if os.path.exists(path) and ram_total_gb >= m["min_ram_gb"]:
            candidates.append(m)

    if not candidates:
        return None

    candidates.sort(key=lambda m: m["recommended_ram_gb"], reverse=True)
    for c in candidates:
        if ram_total_gb >= c["recommended_ram_gb"]:
            return c
    candidates.sort(key=lambda m: m["min_ram_gb"])
    return candidates[0]


# ---------------------------------------------------------------------------
# llamdrop binary finder
# ---------------------------------------------------------------------------

def find_llama_cpp() -> str | None:
    """
    Find the llama-cli binary.
    Checks ~/.llamdrop/bin/ first (the shared llamdrop install),
    then Termux system paths, then PATH.
    """
    candidates = [
        os.path.join(LLAMDROP_BIN_DIR, "llama-cli"),   # llamdrop managed — preferred
        os.path.join(LLAMDROP_BIN_DIR, "main"),
        os.path.expanduser("~/.vernux/bin/llama-cli"),  # vernux-only fallback
        os.path.expanduser("~/.vernux/bin/llama.cpp"),
        "/data/data/com.termux/files/usr/bin/llama-cli",
        "/data/data/com.termux/files/usr/bin/llama.cpp",
    ]
    for path in candidates:
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return path
    # Last resort: shutil.which (checks PATH)
    for name in ["llama-cli", "llama.cpp", "main"]:
        found = shutil.which(name)
        if found:
            return found
    return None


def _get_env() -> dict:
    """Build env with llamdrop's bin dir on LD_LIBRARY_PATH."""
    env      = os.environ.copy()
    existing = env.get("LD_LIBRARY_PATH", "")
    env["LD_LIBRARY_PATH"] = LLAMDROP_BIN_DIR + (":" + existing if existing else "")
    return env


# ---------------------------------------------------------------------------
# API keys management
# ---------------------------------------------------------------------------

# Known providers with their base URLs and model defaults.
# Any provider not listed here can be added as "custom".
KNOWN_PROVIDERS = {
    "openai": {
        "label":     "OpenAI (ChatGPT)",
        "base_url":  "https://api.openai.com/v1",
        "model":     "gpt-4o-mini",
        "hint":      "Get key at: platform.openai.com/api-keys",
    },
    "gemini": {
        "label":     "Google Gemini",
        "base_url":  "https://generativelanguage.googleapis.com/v1beta/openai/",
        "model":     "gemini-2.0-flash",
        "hint":      "Get key at: aistudio.google.com/apikey",
    },
    "grok": {
        "label":     "xAI Grok",
        "base_url":  "https://api.x.ai/v1",
        "model":     "grok-3-mini",
        "hint":      "Get key at: console.x.ai",
    },
    "claude": {
        "label":     "Anthropic Claude",
        "base_url":  "https://api.anthropic.com/v1",
        "model":     "claude-haiku-4-5",
        "hint":      "Get key at: console.anthropic.com",
    },
    "openrouter": {
        "label":     "OpenRouter (free models available)",
        "base_url":  "https://openrouter.ai/api/v1",
        "model":     "mistralai/mistral-7b-instruct:free",
        "hint":      "Get key at: openrouter.ai/keys  (free tier available)",
    },
    "groq": {
        "label":     "Groq (fast + free tier)",
        "base_url":  "https://api.groq.com/openai/v1",
        "model":     "llama-3.1-8b-instant",
        "hint":      "Get key at: console.groq.com/keys  (free tier available)",
    },
    "mistral": {
        "label":     "Mistral AI",
        "base_url":  "https://api.mistral.ai/v1",
        "model":     "mistral-small-latest",
        "hint":      "Get key at: console.mistral.ai",
    },
    "custom": {
        "label":     "Custom / Self-hosted (Ollama, LM Studio, etc.)",
        "base_url":  "",     # user fills in
        "model":     "",     # user fills in
        "hint":      "Enter the base URL of your OpenAI-compatible server",
    },
}


def _load_api_keys() -> dict:
    """Load api_keys.json. Returns {} if missing or unreadable."""
    if not os.path.exists(API_KEYS_FILE):
        return {}
    try:
        with open(API_KEYS_FILE) as f:
            return json.load(f)
    except Exception:
        return {}


def _save_api_keys(data: dict):
    os.makedirs(os.path.dirname(API_KEYS_FILE), exist_ok=True)
    try:
        with open(API_KEYS_FILE, "w") as f:
            json.dump(data, f, indent=2)
        # Restrict permissions — keys visible only to owner
        os.chmod(API_KEYS_FILE, 0o600)
    except Exception:
        pass


def get_active_api_config() -> dict | None:
    """
    Return the active API config dict, or None if no API is configured.
    Dict keys: provider, base_url, model, api_key
    """
    keys = _load_api_keys()
    return keys.get("active") if keys else None


def set_api_config(provider: str, api_key: str, base_url: str, model: str):
    """Save API config. Called from handle_ai_setup() in vernux.py."""
    data = _load_api_keys()
    data["active"] = {
        "provider": provider,
        "base_url":  base_url,
        "model":     model,
        "api_key":   api_key,
    }
    _save_api_keys(data)


def clear_api_config():
    """Remove saved API config."""
    data = _load_api_keys()
    data.pop("active", None)
    _save_api_keys(data)


# ---------------------------------------------------------------------------
# Availability check
# ---------------------------------------------------------------------------

def is_available() -> bool:
    """
    Returns True if at least one backend is ready:
      - Local: llamdrop binary + at least one installed model, AND llm_enabled=True
      - API:   a valid API config is saved (no binary needed)
    """
    from modules.config import get as config_get

    # API backend — always available if configured, no local model needed
    if get_active_api_config():
        return True

    # Local backend
    if not config_get("llm_enabled", False):
        return False
    if find_llama_cpp() is None:
        return False
    return len(list_installed_models()) > 0


# ---------------------------------------------------------------------------
# Response cache (shared across both backends)
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


def _cache_key(user_input: str, kind: str = "cmd") -> str:
    raw = f"{kind}:{user_input.lower().strip()}"
    return hashlib.md5(raw.encode()).hexdigest()


def _get_cached(user_input: str, kind: str = "cmd") -> str | None:
    return _load_cache().get(_cache_key(user_input, kind))


def _set_cached(user_input: str, result: str, kind: str = "cmd"):
    cache = _load_cache()
    cache[_cache_key(user_input, kind)] = result
    if len(cache) > 500:
        keys = list(cache.keys())
        for k in keys[:100]:
            del cache[k]
    _save_cache(cache)


# ---------------------------------------------------------------------------
# Prompt builder (for local backend)
# ---------------------------------------------------------------------------

def _build_local_prompt(user_input: str, model: dict, system_prompt: str) -> str:
    """Build the full formatted prompt for the local GGUF model."""
    data   = _load_models()
    fmts   = data.get("prompt_formats", {})
    fmt_id = model.get("prompt_format", "chatml")
    fmt    = fmts.get(fmt_id, fmts.get("chatml", {}))

    sp = fmt.get("system_prefix", "<|im_start|>system\n")
    ss = fmt.get("system_suffix", "<|im_end|>\n")
    up = fmt.get("user_prefix",   "<|im_start|>user\n")
    us = fmt.get("user_suffix",   "<|im_end|>\n")
    ap = fmt.get("assistant_prefix", "<|im_start|>assistant\n")

    return f"{sp}{system_prompt}{ss}{up}{user_input}{us}{ap}"


# ---------------------------------------------------------------------------
# llamdrop's output extractor — ported verbatim, this is the proven version
# ---------------------------------------------------------------------------

_NOISE = (
    "llama_memory", "load_backend",
    "llama_", "ggml_", "build :", "model :",
    "modalities :", "available commands", "/exit", "/regen",
    "/clear", "/read", "/glob", "[ Prompt:",
)

_META_LINES = (
    "[ Prompt:",
    "Exiting",
    "llama_print_timings",
    "main: llama_",
)

_PROMPT_MARKERS = [
    "<|im_start|>assistant",                              # chatml
    "<|start_header_id|>assistant<|end_header_id|>\n\n", # llama3
    "<start_of_turn>model\n",                            # gemma
    "<|assistant|>\n",                                   # phi3
    "<|assistant|>",                                     # phi3 fallback
]


def _extract_response(raw_output: str) -> str:
    """
    Extract the model's actual response from raw llama-cli stdout.
    Ported from llamdrop's chat.py — the version that works on Android
    across all llama-cli build variants.
    """
    if not raw_output:
        return ""

    marker_found  = False
    response_text = raw_output

    for marker in _PROMPT_MARKERS:
        if marker in raw_output:
            _, _sep, response_text = raw_output.partition(marker)
            marker_found = True
            break

    if not marker_found:
        lines = []
        for line in raw_output.splitlines():
            s = line.rstrip()
            if not s:
                continue
            if any(s.startswith(p) for p in _META_LINES):
                break
            if any(s.startswith(p) for p in _NOISE):
                continue
            lines.append(s)
        return "\n".join(lines).strip()

    lines = []
    response_started = False
    for line in response_text.splitlines():
        s = line.rstrip()

        if not s:
            if response_started:
                lines.append(s)
            continue

        if "<|im_start|>" in s or "<|im_end|>" in s:
            continue

        if any(s.startswith(p) for p in _META_LINES):
            break

        if not response_started and any(s.startswith(p) for p in _NOISE):
            continue

        response_started = True
        lines.append(s)

    return "\n".join(lines).strip()


# ---------------------------------------------------------------------------
# Local backend — runs llama-cli subprocess
# ---------------------------------------------------------------------------

DEFAULT_TIMEOUT = 60


def _run_local(prompt: str, model: dict, max_tokens: int,
               temperature: float, timeout: int) -> str | None:
    """
    Run llama-cli with the given prompt. Returns extracted response or None.
    Uses llamdrop's proven subprocess + threading pattern to avoid freezing
    any spinner in the caller's thread.
    """
    binary = find_llama_cpp()
    if not binary:
        return None

    model_path  = _get_model_path(model)
    data        = _load_models()
    fmts        = data.get("prompt_formats", {})
    fmt_id      = model.get("prompt_format", "chatml")
    stop_tokens = fmts.get(fmt_id, {}).get("stop_tokens", ["<|im_end|>"])

    from modules.device import load_profile
    profile  = load_profile()
    threads  = max(1, profile.get("cpu", {}).get("cores", 2) - 1)

    cmd = [
        binary,
        "--model",            model_path,
        "-p",                 prompt,
        "--predict",          str(max_tokens),
        "--ctx-size",         "2048",
        "--temp",             str(round(temperature, 2)),
        "--top-p",            "0.9",
        "--repeat-penalty",   "1.1",
        "--threads",          str(threads),
        "--single-turn",
        "--no-display-prompt",
        "--simple-io",
        "--log-disable",
        "-co",                "off",
    ]
    for st in stop_tokens:
        cmd += ["--reverse-prompt", st]

    try:
        proc = subprocess.Popen(
            cmd,
            env=_get_env(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )

        stdout_lines = []
        stderr_lines = []

        def _read_stdout():
            for line in proc.stdout:
                stdout_lines.append(line)

        def _read_stderr():
            for line in proc.stderr:
                stderr_lines.append(line.rstrip())

        t_out = threading.Thread(target=_read_stdout, daemon=True)
        t_err = threading.Thread(target=_read_stderr, daemon=True)
        t_out.start()
        t_err.start()

        try:
            t_out.join(timeout=timeout)
        except Exception:
            pass

        proc.wait()
        t_err.join(timeout=2)

        raw = "".join(stdout_lines)
        response = _extract_response(raw)

        # Retry without newer flags if binary is too old to support them
        if not response and stderr_lines:
            unsupported = any(
                "unknown argument" in ln.lower() or
                "unrecognized" in ln.lower() or
                "invalid option" in ln.lower()
                for ln in stderr_lines
            )
            if unsupported:
                retry_cmd = [
                    a for a in cmd
                    if a not in ("--single-turn", "--no-display-prompt",
                                 "--simple-io", "--log-disable")
                ]
                try:
                    proc2 = subprocess.Popen(
                        retry_cmd,
                        env=_get_env(),
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                    )
                    retry_lines = []
                    def _read_retry():
                        for line in proc2.stdout:
                            retry_lines.append(line)
                    t_r = threading.Thread(target=_read_retry, daemon=True)
                    t_r.start()
                    t_r.join(timeout=timeout)
                    proc2.wait()
                    raw = "".join(retry_lines)
                    response = _extract_response(raw)
                except Exception:
                    pass

        return response if response else None

    except subprocess.TimeoutExpired:
        try:
            proc.terminate()
        except Exception:
            pass
        return None
    except KeyboardInterrupt:
        try:
            proc.terminate()
        except Exception:
            pass
        return None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# API backend — OpenAI-compatible HTTP call (urllib, zero dependencies)
# ---------------------------------------------------------------------------

def _run_api(user_input: str, system_prompt: str,
             max_tokens: int, temperature: float,
             timeout: int) -> str | None:
    """
    Call any OpenAI-compatible API endpoint.
    Uses only urllib (stdlib) — no requests, no openai package needed.
    """
    import urllib.request
    import urllib.error

    cfg = get_active_api_config()
    if not cfg:
        return None

    base_url  = cfg["base_url"].rstrip("/")
    api_key   = cfg["api_key"]
    model     = cfg["model"]
    provider  = cfg.get("provider", "")

    # Anthropic Claude uses a different API format — handle separately
    if provider == "claude" or "anthropic.com" in base_url:
        return _run_api_claude(user_input, system_prompt, max_tokens,
                               temperature, timeout, base_url, api_key, model)

    # Standard OpenAI-compatible path
    url     = f"{base_url}/chat/completions"
    payload = {
        "model":       model,
        "messages":    [
            {"role": "system",  "content": system_prompt},
            {"role": "user",    "content": user_input},
        ],
        "max_tokens":  max_tokens,
        "temperature": temperature,
    }

    body    = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type":  "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    # OpenRouter wants an app identifier header
    if "openrouter.ai" in base_url:
        headers["HTTP-Referer"] = "https://github.com/DeVenLucaz/Vernux"
        headers["X-Title"]      = "VERNUX"

    try:
        req      = urllib.request.Request(url, data=body, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data["choices"][0]["message"]["content"].strip()
    except urllib.error.HTTPError as e:
        _api_error_hint(e.code, e.read().decode("utf-8", errors="replace"))
        return None
    except Exception:
        return None


def _run_api_claude(user_input: str, system_prompt: str,
                    max_tokens: int, temperature: float,
                    timeout: int, base_url: str,
                    api_key: str, model: str) -> str | None:
    """
    Anthropic Claude native API format.
    Claude uses x-api-key header and a slightly different messages structure.
    """
    import urllib.request
    import urllib.error

    url     = f"{base_url}/messages"
    payload = {
        "model":      model,
        "max_tokens": max_tokens,
        "system":     system_prompt,
        "messages":   [{"role": "user", "content": user_input}],
    }
    body    = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type":      "application/json",
        "x-api-key":         api_key,
        "anthropic-version": "2023-06-01",
    }

    try:
        req  = urllib.request.Request(url, data=body, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data["content"][0]["text"].strip()
    except urllib.error.HTTPError as e:
        _api_error_hint(e.code, e.read().decode("utf-8", errors="replace"))
        return None
    except Exception:
        return None


def _api_error_hint(code: int, body: str):
    """Print a concise, helpful API error message (non-fatal)."""
    hints = {
        401: "API key rejected. Check your key in: vernux ai-setup",
        403: "Access forbidden. Your key may lack permissions for this model.",
        429: "Rate limit hit. Wait a moment or switch to a different model.",
        500: "Provider server error. Try again in a moment.",
    }
    msg = hints.get(code, f"API error {code}")
    # Only print if not in a spinner context — keep it subtle
    print(f"\n  ⚠  {msg}", flush=True)


# ---------------------------------------------------------------------------
# Output validator (for command queries — shared by both backends)
# ---------------------------------------------------------------------------

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

_CHATTY_FIRST_WORDS = {
    "the", "this", "that", "you", "i", "to", "a", "an", "in", "for",
    "with", "and", "or", "not", "but", "if", "when", "here", "note",
    "first", "then", "also", "please", "just", "of", "sure", "ok",
}


def validate_output(raw_output: str) -> str | None:
    """
    Validate and clean LLM output for command queries.
    Strips markdown, chatty preamble, and natural language.
    Returns clean command or None.
    """
    if not raw_output:
        return None

    text = raw_output.strip()

    if text.upper().startswith(IMPOSSIBLE_MARKER):
        return None

    # Strip markdown code fences
    text = re.sub(r"```(?:bash|sh|shell)?[\s]*", "", text)
    text = re.sub(r"```", "", text).strip()

    # Try to extract command after chatty preamble (e.g. "Here's the command: CMD")
    colon_match = re.search(
        r"(?:here(?:'s| is).*?:|to .+?:|you should.*?:|sure[!,]?\s|run:|use:|try:)\s*(.+)",
        text, re.IGNORECASE | re.DOTALL
    )
    if colon_match:
        candidate = colon_match.group(1).strip().strip("`'\"").splitlines()[0].strip()
        if candidate and VALID_CMD_STARTS.match(candidate):
            return candidate

    # Walk lines to find first valid command
    for line in [l.strip() for l in text.splitlines() if l.strip()]:
        line = line.strip().strip("`'\"").strip()
        if not line or line.upper() == IMPOSSIBLE_MARKER:
            continue
        first = line.split()[0].lower() if line.split() else ""
        if first in _CHATTY_FIRST_WORDS:
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
# Active backend selector
# ---------------------------------------------------------------------------

def _active_backend() -> str:
    """
    Returns 'api', 'local', or 'none'.
    API takes priority if configured — it's faster and needs no model.
    Local is used when llm_enabled=True + binary + model all present.
    """
    if get_active_api_config():
        return "api"
    from modules.config import get as config_get
    if config_get("llm_enabled", False) and find_llama_cpp() and list_installed_models():
        return "local"
    return "none"


# ---------------------------------------------------------------------------
# Public query functions
# ---------------------------------------------------------------------------

def query(user_input: str, timeout: int = DEFAULT_TIMEOUT) -> str | None:
    """
    Generate a bash command for the given user input.
    Returns validated command string, or None on failure.

    Flow:
      1. Cache check (instant)
      2. Route to API backend or local backend
      3. Validate output
      4. Cache result
    """
    backend = _active_backend()
    if backend == "none":
        return None

    cached = _get_cached(user_input, "cmd")
    if cached:
        return cached

    if backend == "api":
        raw = _run_api(user_input, SYSTEM_PROMPT, 150, 0.1, timeout)
    else:
        from modules.device import load_profile
        profile = load_profile()
        ram_gb  = profile.get("ram", {}).get("total_gb", 2.0)
        model   = select_model(ram_gb)
        if not model:
            return None
        prompt = _build_local_prompt(user_input, model, SYSTEM_PROMPT)
        raw    = _run_local(prompt, model, 128, 0.1, timeout)

    if not raw:
        return None

    command = validate_output(raw)
    if command:
        _set_cached(user_input, command, "cmd")
    return command


def query_explain(user_input: str, timeout: int = DEFAULT_TIMEOUT) -> str | None:
    """
    Get a plain-text explanation for the given query.
    Returns explanation string, or None on failure.
    """
    backend = _active_backend()
    if backend == "none":
        return None

    cached = _get_cached(user_input, "explain")
    if cached:
        return cached

    if backend == "api":
        result = _run_api(user_input, EXPLAIN_SYSTEM_PROMPT, 300, 0.3, timeout)
    else:
        from modules.device import load_profile
        profile = load_profile()
        ram_gb  = profile.get("ram", {}).get("total_gb", 2.0)
        model   = select_model(ram_gb)
        if not model:
            return None
        prompt = _build_local_prompt(user_input, model, EXPLAIN_SYSTEM_PROMPT)
        result = _run_local(prompt, model, 200, 0.3, timeout)

    if result:
        _set_cached(user_input, result, "explain")
    return result


# ---------------------------------------------------------------------------
# Model downloader (for vernux-only models, unchanged API)
# ---------------------------------------------------------------------------

def download_model(model: dict, on_progress=None) -> bool:
    """
    Download a model file to MODELS_DIR using wget (curl fallback).
    Returns True on success.
    """
    os.makedirs(MODELS_DIR, exist_ok=True)
    dest = os.path.join(MODELS_DIR, model["file"])

    if os.path.exists(dest):
        return True

    url = model.get("url")
    if not url:
        return False

    def _cleanup():
        if os.path.exists(dest):
            os.remove(dest)

    wget_cmd = [
        "wget", "-L", "--show-progress", "--progress=dot:mega",
        "--tries=2", "--timeout=30", "-O", dest, url,
    ]
    curl_cmd = [
        "curl", "-L", "--progress-bar", "--retry", "2",
        "--connect-timeout", "30", "-o", dest, url,
    ]

    for cmd in [wget_cmd, curl_cmd]:
        if shutil.which(cmd[0]) is None:
            continue
        try:
            proc = subprocess.run(cmd, timeout=7200)
            if proc.returncode == 0 and os.path.exists(dest) and os.path.getsize(dest) > 1024 * 1024:
                return True
            _cleanup()
        except Exception:
            _cleanup()

    return False


def get_download_advice(model: dict, device_tier: str, mode: str) -> str:
    size_mb  = model.get("size_mb", 0)
    size_str = f"{size_mb}MB" if size_mb < 1000 else f"{size_mb/1000:.1f}GB"
    lines    = []
    if device_tier in ("micro", "low"):
        lines.append(f"  ⚠  This model ({size_str}) may run slowly on your device.")
        if mode == "noob":
            lines.append("  The AI responses will take 10–60 seconds. That's normal.")
        else:
            lines.append(f"  Expect 10–60s per query on {device_tier} tier devices.")
    lines.append(f"  📦 Download size: {size_str}")
    lines.append(f"  📍 Saved to: {MODELS_DIR}/")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# AI setup wizard — called from vernux.py handle_ai_setup()
# ---------------------------------------------------------------------------

def run_ai_setup_wizard(mode: str = "noob") -> bool:
    """
    Interactive wizard to configure the AI backend.
    Returns True if setup succeeded.

    Shown when user types: vernux ai-setup
    Also called automatically when user types 'install-model' and no
    local model is present (offers API as a faster alternative).
    """
    try:
        from modules import ui
    except ImportError:
        # Minimal fallback if ui not importable
        class ui:
            CYAN = BOLD = GREEN = YELLOW = RED = GRAY = RESET = ""
            @staticmethod
            def confirm(q, require_yes=False):
                r = input(f"  {q} (y/N): ").strip().lower()
                return r == "y" if not require_yes else r == "yes"

    print()
    print(f"  {ui.CYAN}{ui.BOLD}╔══════════════════════════════════════════╗{ui.RESET}")
    print(f"  {ui.CYAN}{ui.BOLD}║          VERNUX AI Setup                 ║{ui.RESET}")
    print(f"  {ui.CYAN}{ui.BOLD}╚══════════════════════════════════════════╝{ui.RESET}")
    print()
    print("  Choose your AI backend:\n")
    print(f"  {ui.BOLD}[1] 🌐 API provider{ui.RESET}  — use any AI service with an API key")
    print(f"      {ui.GRAY}Faster, no storage needed. Key stored locally on your device only.{ui.RESET}")
    print()
    print(f"  {ui.BOLD}[2] 📱 Local model{ui.RESET}  — run AI fully offline on your phone")
    print(f"      {ui.GRAY}Requires llamdrop + a downloaded GGUF model. 100% private.{ui.RESET}")

    # Show llamdrop status
    binary = find_llama_cpp()
    if binary:
        installed = list_installed_models()
        if installed:
            print(f"      {ui.GREEN}✔ llamdrop ready: {installed[0]['name']}{ui.RESET}")
        else:
            print(f"      {ui.YELLOW}⚠ llamdrop binary found but no models downloaded{ui.RESET}")
    else:
        print(f"      {ui.YELLOW}⚠ llamdrop not installed — install it first, then come back{ui.RESET}")

    current = get_active_api_config()
    if current:
        print()
        print(f"  {ui.BOLD}[3] ❌ Remove current API config{ui.RESET}")
        print(f"      {ui.GRAY}Currently using: {current.get('provider','?')} / {current.get('model','?')}{ui.RESET}")

    print(f"\n  {ui.BOLD}[0] Cancel{ui.RESET}\n")

    try:
        choice = input("  Your choice: ").strip()
    except (KeyboardInterrupt, EOFError):
        return False

    if choice == "0":
        return False

    if choice == "3" and current:
        clear_api_config()
        print(f"\n  {ui.GREEN}✔ API config removed.{ui.RESET}\n")
        return True

    if choice == "1":
        return _setup_api_wizard(mode, ui)

    if choice == "2":
        return _setup_local_wizard(mode, ui)

    print(f"  {ui.YELLOW}Invalid choice.{ui.RESET}\n")
    return False


def _setup_api_wizard(mode: str, ui) -> bool:
    """Sub-wizard: configure API provider."""
    print()

    # Privacy notice — shown once
    keys_data = _load_api_keys()
    if not keys_data.get("_privacy_notice_shown"):
        print(f"  {ui.YELLOW}━━━ Privacy Notice ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{ui.RESET}")
        print(f"  Your API key will be stored in:")
        print(f"  {ui.GRAY}~/.vernux/api_keys.json{ui.RESET}  (readable only by you, chmod 600)")
        print(f"  It is NEVER sent anywhere except the provider you choose.")
        print(f"  VERNUX is open source — you can verify this yourself.")
        print(f"  To remove your key at any time: {ui.BOLD}vernux ai-setup{ui.RESET}")
        print(f"  {ui.YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{ui.RESET}")
        print()
        if not ui.confirm("Continue with API setup?"):
            return False
        keys_data["_privacy_notice_shown"] = True
        _save_api_keys(keys_data)
        print()

    # Provider list
    providers = list(KNOWN_PROVIDERS.items())
    print(f"  {ui.BOLD}Choose a provider:{ui.RESET}\n")
    for i, (pid, pdata) in enumerate(providers, 1):
        print(f"  [{i}] {pdata['label']}")
        if pdata.get("hint"):
            print(f"      {ui.GRAY}{pdata['hint']}{ui.RESET}")
    print()

    try:
        raw = input(f"  Choose (1-{len(providers)}): ").strip()
        idx = int(raw) - 1
        if not 0 <= idx < len(providers):
            raise ValueError
    except (ValueError, EOFError, KeyboardInterrupt):
        print(f"  {ui.YELLOW}Cancelled.{ui.RESET}\n")
        return False

    provider_id, pdata = providers[idx]
    print()

    # Base URL (pre-filled for known, empty for custom)
    base_url = pdata["base_url"]
    if provider_id == "custom" or not base_url:
        try:
            base_url = input(
                f"  Base URL (e.g. http://localhost:11434/v1): "
            ).strip().rstrip("/")
        except (EOFError, KeyboardInterrupt):
            return False
        if not base_url:
            print(f"  {ui.YELLOW}Cancelled — no URL entered.{ui.RESET}\n")
            return False
    else:
        print(f"  Endpoint: {ui.GRAY}{base_url}{ui.RESET}")

    # API key
    print()
    try:
        api_key = input("  Paste your API key: ").strip()
    except (EOFError, KeyboardInterrupt):
        return False
    if not api_key:
        print(f"  {ui.YELLOW}No key entered. Cancelled.{ui.RESET}\n")
        return False

    # Model name
    default_model = pdata.get("model", "")
    print()
    try:
        model_input = input(
            f"  Model name [{default_model}]: "
        ).strip()
    except (EOFError, KeyboardInterrupt):
        return False
    model = model_input if model_input else default_model
    if not model:
        print(f"  {ui.YELLOW}No model name entered. Cancelled.{ui.RESET}\n")
        return False

    # Save
    set_api_config(provider_id, api_key, base_url, model)

    print()
    print(f"  {ui.GREEN}✔ API configured:{ui.RESET}")
    print(f"     Provider : {pdata['label']}")
    print(f"     Model    : {model}")
    print(f"     Key      : {'*' * (len(api_key) - 4)}{api_key[-4:]}")
    print(f"     Stored in: ~/.vernux/api_keys.json (chmod 600)")
    print()
    if mode == "noob":
        print(f"  {ui.GRAY}AI is now active. Just type what you want to do!{ui.RESET}")
    else:
        print(f"  {ui.GRAY}AI backend active. 'vernux ai-setup' to change.{ui.RESET}")
    print()
    return True


def _setup_local_wizard(mode: str, ui) -> bool:
    """Sub-wizard: set up local model (delegates to existing install-model flow)."""
    binary = find_llama_cpp()
    if not binary:
        print()
        print(f"  {ui.YELLOW}llamdrop is not installed.{ui.RESET}")
        print(f"  Install it first:")
        print(f"  {ui.GRAY}curl -sL https://raw.githubusercontent.com/ypatole035-ai/llamdrop/main/install.sh | bash{ui.RESET}")
        print()
        if mode == "noob":
            print(f"  Once installed, run: {ui.BOLD}vernux ai-setup{ui.RESET}")
        return False

    installed = list_installed_models()
    if installed:
        print()
        print(f"  {ui.GREEN}✔ Local AI ready:{ui.RESET}  {installed[0]['name']}")
        print(f"  {ui.GRAY}To add more models: vernux install-model{ui.RESET}")
        print()

        # Enable llm_enabled if not already set
        from modules.config import set_value
        set_value("llm_enabled", True)
        return True

    print()
    print(f"  {ui.YELLOW}llamdrop binary found but no models downloaded.{ui.RESET}")
    print(f"  Run: {ui.BOLD}vernux install-model{ui.RESET}  to download a model.")
    print()
    return False
