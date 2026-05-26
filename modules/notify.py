# =============================================================================
# modules/notify.py — Long Task Notifications & Session Kill Warnings
# Version: 0.4.0 | Phase 3 — Recipes
# =============================================================================

import os

# ---------------------------------------------------------------------------
# Operation profiles — what type of task is this?
# ---------------------------------------------------------------------------

# (regex_fragment, operation_type, safe_to_minimize, estimated_seconds)
OPERATION_PROFILES = [
    # Package installs
    ("pkg install",         "package_install",   False, 60),
    ("pkg upgrade",         "package_upgrade",   False, 120),
    ("pkg update",          "package_update",    True,  15),

    # Python
    ("pip install",         "pip_install",       False, 45),
    ("pip install -r",      "pip_install_bulk",  False, 90),

    # Downloads
    ("wget ",               "download",          False, None),
    ("curl -O",             "download",          False, None),
    ("git clone",           "git_clone",         False, 60),
    ("yt-dlp",              "media_download",    False, None),

    # Compilation
    ("make ",               "compilation",       False, 300),
    ("cmake ",              "compilation",       False, 120),
    ("cargo build",         "compilation",       False, 600),
    ("go build",            "compilation",       False, 60),
    ("npm install",         "npm_install",       False, 60),

    # Backups / archives
    ("tar -czf",            "archive_create",    True,  30),
    ("tar -xzf",            "archive_extract",   True,  15),
    ("zip -r",              "archive_create",    True,  20),

    # Git operations
    ("git push",            "git_push",          True,  15),
    ("git pull",            "git_pull",          True,  15),

    # SSH keygen
    ("ssh-keygen",          "keygen",            True,  5),

    # DB setup
    ("mysql_install_db",    "db_setup",          False, 30),
    ("initdb",              "db_setup",          False, 20),
]

# Brands known to aggressively kill background processes
AGGRESSIVE_BRANDS = {
    "xiaomi":  "MIUI aggressively kills background processes. Disable battery optimization: Settings → Apps → Termux → Battery → No restrictions.",
    "redmi":   "MIUI aggressively kills background processes. Disable battery optimization: Settings → Apps → Termux → Battery → No restrictions.",
    "oppo":    "ColorOS may kill long tasks. Settings → Battery → Battery Optimization → Termux → Don't optimize.",
    "realme":  "Realme UI may kill long tasks. Settings → Battery → Battery Optimization → Termux → Don't optimize.",
    "vivo":    "VivoUI may kill long tasks. i Manager → Battery → High background power → Termux → Allow.",
    "samsung": "OneUI: Settings → Apps → Termux → Battery → Unrestricted. Also disable Adaptive battery.",
    "iqoo":    "VivoUI/iQOO: disable battery optimization for Termux before long tasks.",
}

# These operations NEED tmux if the brand is aggressive
NEEDS_TMUX_OPS = {
    "package_install", "package_upgrade", "pip_install", "pip_install_bulk",
    "download", "media_download", "compilation", "npm_install", "db_setup",
    "git_clone",
}


def classify_operation(command: str) -> dict:
    """
    Classify a command as a long-running operation or not.

    Returns:
      {
        is_long:           bool
        operation_type:    str
        safe_to_minimize:  bool   — False = MUST keep Termux open
        estimated_seconds: int | None
      }
    """
    cmd_lower = command.lower().strip()

    for fragment, op_type, safe, secs in OPERATION_PROFILES:
        if fragment in cmd_lower:
            return {
                "is_long":          True,
                "operation_type":   op_type,
                "safe_to_minimize": safe,
                "estimated_seconds": secs,
            }

    return {
        "is_long":          False,
        "operation_type":   "quick",
        "safe_to_minimize": True,
        "estimated_seconds": None,
    }


def format_duration(seconds: int | None) -> str:
    if seconds is None:
        return "a while (depends on your connection)"
    if seconds < 60:
        return f"~{seconds}s"
    return f"~{seconds // 60} min"


def get_brand_warning(brand: str) -> str | None:
    """Return brand-specific battery optimization warning, or None."""
    return AGGRESSIVE_BRANDS.get(brand.lower())


def should_suggest_tmux(operation_type: str, brand: str) -> bool:
    """Suggest tmux if the task is risky to interrupt on this brand."""
    return (
        operation_type in NEEDS_TMUX_OPS and
        brand.lower() in AGGRESSIVE_BRANDS
    )


def build_pre_task_notice(command: str, brand: str = "", mode: str = "noob") -> str | None:
    """
    Build a pre-task notice string for long operations.
    Returns None if the operation is quick (no notice needed).
    """
    info = classify_operation(command)
    if not info["is_long"]:
        return None

    lines = []
    duration = format_duration(info["estimated_seconds"])

    if info["safe_to_minimize"]:
        lines.append(f"  ⏳ This will take {duration}.  ✅ Safe to minimize Termux.")
    else:
        lines.append(f"  ⏳ This will take {duration}.  ⚠️  Keep Termux open — closing it will stop this.")

    brand_warn = get_brand_warning(brand)
    if brand_warn and not info["safe_to_minimize"]:
        lines.append(f"  📱 {brand_warn}")

    if should_suggest_tmux(info["operation_type"], brand) and mode != "pro":
        lines.append(
            "  💡 Tip: run 'pkg install tmux && tmux' first so this survives "
            "if Termux gets closed."
        )

    return "\n".join(lines)
