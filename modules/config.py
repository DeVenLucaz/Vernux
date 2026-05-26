# =============================================================================
# modules/config.py — User Configuration Manager
# Version: 0.1.0 | Phase 0 — Foundation
# =============================================================================

import json
import os

CONFIG_DIR  = os.path.expanduser("~/.vernux")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")

DEFAULTS = {
    "mode":         "noob",
    "first_run":    True,
    "ssh_key_done": False,
    "llm_enabled":  False,
    "llm_model":    None,
    "lang":         "en",
    "version":      "0.1.0"
}


def load_config() -> dict:
    """Read config file. Return defaults merged with any saved values."""
    if not os.path.exists(CONFIG_FILE):
        return dict(DEFAULTS)
    try:
        with open(CONFIG_FILE, "r") as f:
            saved = json.load(f)
        # Merge: defaults first, then saved values on top
        merged = dict(DEFAULTS)
        merged.update(saved)
        return merged
    except (json.JSONDecodeError, IOError):
        return dict(DEFAULTS)


def save_config(cfg: dict) -> bool:
    """Write the full config dict to disk. Returns True on success."""
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(CONFIG_FILE, "w") as f:
            json.dump(cfg, f, indent=2)
        return True
    except IOError:
        return False


def get(key: str, default=None):
    """Safe single-key getter. Reads fresh from disk each time."""
    cfg = load_config()
    return cfg.get(key, default)


def set_value(key: str, value) -> bool:
    """Set a single config key and save."""
    cfg = load_config()
    cfg[key] = value
    return save_config(cfg)


def reset_config() -> bool:
    """Wipe config and restore defaults."""
    return save_config(dict(DEFAULTS))
