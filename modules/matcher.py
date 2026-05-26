# =============================================================================
# modules/matcher.py — Natural Language Pattern Matching Engine
# Version: 0.2.0 | Phase 1 — Core Engine
# =============================================================================

import json
import os
import re
from difflib import SequenceMatcher

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
PATTERNS_FILE      = os.path.join(os.path.dirname(__file__), "../data/patterns.json")
CONFIDENCE_THRESHOLD = 0.42   # Below this → "did you mean?" instead of match
FUZZY_BOOST          = 0.15   # Bonus for fuzzy token overlap

# Noise words — stripped before matching
STOP_WORDS = {
    "i", "want", "to", "can", "you", "please", "help", "me", "my",
    "how", "do", "a", "an", "the", "in", "on", "for", "get", "make",
    "need", "would", "like", "could", "should", "is", "are", "it",
    "this", "that", "with", "from", "just", "now", "up", "and", "let",
    "show", "give", "tell", "find", "put", "set",
    # Question words — prevent "what is grep" matching pattern commands
    "what", "which", "who", "does", "explain", "mean", "why", "when",
}

# ---------------------------------------------------------------------------
# Pattern loader
# ---------------------------------------------------------------------------
_PATTERNS_CACHE: list[dict] | None = None


def load_patterns(force_reload: bool = False) -> list[dict]:
    """
    Load patterns from data/patterns.json.
    Cached in memory after first load.
    """
    global _PATTERNS_CACHE
    if _PATTERNS_CACHE is not None and not force_reload:
        return _PATTERNS_CACHE

    path = os.path.abspath(PATTERNS_FILE)
    if not os.path.exists(path):
        _PATTERNS_CACHE = []
        return _PATTERNS_CACHE

    try:
        with open(path, "r") as f:
            data = json.load(f)
        _PATTERNS_CACHE = data.get("patterns", [])
    except (json.JSONDecodeError, IOError):
        _PATTERNS_CACHE = []

    return _PATTERNS_CACHE


# ---------------------------------------------------------------------------
# Keyword extraction
# ---------------------------------------------------------------------------

def extract_keywords(user_input: str) -> list[str]:
    """
    Extract meaningful keywords from user input.
    Lowercases, strips punctuation, removes stop words.
    Returns list of tokens.
    """
    text   = user_input.lower().strip()
    text   = re.sub(r"[^\w\s]", " ", text)
    tokens = text.split()
    return [t for t in tokens if t not in STOP_WORDS and len(t) > 1]


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def _token_overlap_score(keywords: list[str], trigger: str) -> float:
    """
    Score how well user keywords match a trigger phrase.
    Uses exact overlap + fuzzy matching for partial hits.
    """
    trigger_tokens = [t for t in trigger.lower().split() if t not in STOP_WORDS]
    if not trigger_tokens or not keywords:
        return 0.0

    matched = 0.0
    for kw in keywords:
        # Exact match in trigger tokens
        if kw in trigger_tokens:
            matched += 1.0
            continue
        # Fuzzy: does any trigger token closely resemble this keyword?
        best_fuzzy = max(
            (SequenceMatcher(None, kw, tt).ratio() for tt in trigger_tokens),
            default=0.0
        )
        if best_fuzzy >= 0.8:
            matched += best_fuzzy * 0.8   # Partial credit for fuzzy hit

    # Normalize against the longer of the two token sets
    denominator = max(len(trigger_tokens), len(keywords))
    return matched / denominator


def score_pattern(keywords: list[str], pattern: dict) -> float:
    """
    Score a pattern against extracted keywords.
    Checks all triggers and returns the best score.
    """
    if not keywords:
        return 0.0

    triggers = pattern.get("triggers", [])
    best     = 0.0
    for trigger in triggers:
        s = _token_overlap_score(keywords, trigger)
        if s > best:
            best = s

    # Bonus: if the pattern ID itself overlaps with keywords
    pid_tokens = pattern.get("id", "").replace("_", " ").split()
    id_score   = _token_overlap_score(keywords, " ".join(pid_tokens))
    best       = max(best, id_score * 0.9)

    return round(best, 3)


# ---------------------------------------------------------------------------
# Parameter extraction
# ---------------------------------------------------------------------------

def extract_params(user_input: str, pattern: dict) -> dict:
    """
    Try to extract {placeholder} values from the user's input.
    Simple heuristic: last meaningful token fills the first placeholder.
    Extended in Phase 2 with smarter NER.
    """
    command  = pattern.get("command", "")
    params   = {}
    placeholders = re.findall(r"\{(\w+)\}", command)

    if not placeholders:
        return params

    # Connector words that appear between verb and argument — never the argument itself
    CONNECTOR_WORDS = {
        "called", "named", "name", "for", "of", "about", "at", "as",
        "into", "inside", "under", "using", "via", "out", "all", "new",
    }

    # Preserve filenames with extensions before lowercasing/splitting
    # e.g. "delete file test.txt" → keep "test.txt" as one token
    preserved = re.findall(r'\S+\.\w+', user_input)

    keywords = extract_keywords(user_input)

    # Remove trigger words from keywords to isolate the "argument"
    trigger_words = set()
    for t in pattern.get("triggers", []):
        trigger_words.update(t.lower().split())

    args = [k for k in keywords if k not in trigger_words and k not in CONNECTOR_WORDS]

    # Re-inject preserved filenames at their correct position
    # Replace split fragments (e.g. ["test", "txt"]) with the full token
    for fname in preserved:
        base, ext = fname.rsplit(".", 1)
        if base in args and ext in args:
            idx = args.index(base)
            args[idx] = fname
            if ext in args:
                args.remove(ext)

    for i, placeholder in enumerate(placeholders):
        if i < len(args):
            params[placeholder] = args[i]
        else:
            # For multi-placeholder commands, use last arg for remaining slots
            params[placeholder] = args[-1] if args else f"<{placeholder}>"

    return params


# ---------------------------------------------------------------------------
# Main match function
# ---------------------------------------------------------------------------

def match(user_input: str) -> dict:
    """
    Match user input against all loaded patterns.

    Returns:
      {
        found:      bool
        pattern:    dict | None   — the matched pattern entry
        confidence: float
        params:     dict          — extracted {placeholder} values
        candidates: list[dict]    — top 3 near-misses (for "did you mean?")
      }
    """
    patterns = load_patterns()
    keywords = extract_keywords(user_input)

    if not patterns or not keywords:
        return {
            "found": False, "pattern": None,
            "confidence": 0.0, "params": {},
            "candidates": []
        }

    # Score all patterns
    scored = []
    for p in patterns:
        s = score_pattern(keywords, p)
        if s > 0:
            scored.append((s, p))

    # Sort descending
    scored.sort(key=lambda x: x[0], reverse=True)

    if not scored:
        return {
            "found": False, "pattern": None,
            "confidence": 0.0, "params": {},
            "candidates": []
        }

    best_score, best_pattern = scored[0]
    candidates = [p for _, p in scored[1:4]]  # Top 3 near-misses

    if best_score >= CONFIDENCE_THRESHOLD:
        params = extract_params(user_input, best_pattern)
        return {
            "found":      True,
            "pattern":    best_pattern,
            "confidence": best_score,
            "params":     params,
            "candidates": candidates,
        }
    else:
        return {
            "found":      False,
            "pattern":    None,
            "confidence": best_score,
            "params":     {},
            "candidates": [p for _, p in scored[:3]],
        }
