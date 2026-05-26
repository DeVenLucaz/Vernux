# =============================================================================
# modules/safety.py — Context-Aware Risk Classifier
# Version: 0.2.0 | Phase 1 — Core Engine
# =============================================================================

import re

# ---------------------------------------------------------------------------
# Protected paths — never auto-run danger commands on these
# ---------------------------------------------------------------------------
PROTECTED_PATHS = [
    "/sdcard/",
    "/storage/",
    "~/.ssh/",
    "/data/data/com.termux/files/usr/",
    "/system/",
    "/proc/",
    "/dev/",
]

# ---------------------------------------------------------------------------
# Hard-stop patterns — NEVER run, regardless of mode or context
# ---------------------------------------------------------------------------
HARD_STOP_PATTERNS = [
    r"rm\s+-rf\s+/\s*$",          # rm -rf /
    r"rm\s+-rf\s+/\s+",           # rm -rf / with trailing stuff
    r"rm\s+--no-preserve-root",   # rm --no-preserve-root
    r":\(\)\{.*\};",               # fork bomb
    r">\s*/dev/sda",              # overwrite disk
    r"dd\s+.*of=/dev/[a-z]+\b",  # dd to raw device
    r"mkfs\.",                     # format filesystem
    r"chmod\s+-R\s+777\s+/",     # chmod 777 root
]

# ---------------------------------------------------------------------------
# Pattern-based classification
# ---------------------------------------------------------------------------

# (regex_pattern, safety_level, reversible)
DANGER_RULES = [
    # Hard danger — irreversible data loss
    (r"\brm\b.*-[rf]+.*(/sdcard|/storage|~/|~\s*$)", "red",    False),
    (r"\brm\s+-rf\b",                                  "red",    False),
    (r"\bdd\b.*\bif=",                                 "red",    False),
    (r"\bshred\b",                                     "red",    False),
    (r"\btruncate\b",                                  "red",    False),

    # Caution — potentially risky but often routine
    (r"\bgit\s+push\b",                                "yellow", False),
    (r"\brm\b",                                        "yellow", False),
    (r"\bmv\b",                                        "yellow", True),
    (r"\bchmod\b",                                     "yellow", True),
    (r"\bchown\b",                                     "yellow", True),
    (r"\bkill\b",                                      "yellow", False),
    (r"\bpkill\b",                                     "yellow", False),
    (r"\bpkg\s+(uninstall|remove)\b",                  "yellow", True),
    (r"\bssh-keygen\b",                                "yellow", True),
    (r"\bcurl\b.*\|\s*bash",                           "yellow", False),
    (r"\bwget\b.*\|\s*bash",                           "yellow", False),
]

# Commands that are always safe regardless
SAFE_COMMANDS = {
    "ls", "pwd", "cd", "cat", "echo", "grep", "find", "which",
    "whoami", "uname", "date", "cal", "free", "df", "du",
    "ping", "curl", "wget", "git", "pkg", "pip", "python3",
    "node", "npm", "zip", "unzip", "tar", "clear", "history",
    "ps", "top", "htop", "man", "help", "nano", "vim",
}

# Dev-workflow commands that should have reduced risk in project context
DEV_WORKFLOW_PATTERNS = [
    r"\brm\s+-rf\s+\./build\b",
    r"\brm\s+-rf\s+\./dist\b",
    r"\brm\s+-rf\s+\./node_modules\b",
    r"\brm\s+-rf\s+\./__pycache__\b",
    r"\brm\s+-rf\s+\./\.pytest_cache\b",
]


# ---------------------------------------------------------------------------
# Core classification logic
# ---------------------------------------------------------------------------

def _is_hard_stop(command: str) -> bool:
    for pattern in HARD_STOP_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            return True
    return False


def _hits_protected_path(command: str) -> bool:
    for path in PROTECTED_PATHS:
        if path in command:
            return True
    return False


def _is_dev_workflow(command: str) -> bool:
    for pattern in DEV_WORKFLOW_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            return True
    return False


def _base_classify(command: str) -> tuple[str, bool]:
    """
    Returns (safety_level, reversible) based on pattern rules.
    """
    for pattern, level, reversible in DANGER_RULES:
        if re.search(pattern, command, re.IGNORECASE):
            return level, reversible
    return "green", True


def classify(command: str, context: dict = None) -> dict:
    """
    Context-aware safety classification.

    context keys (all optional):
      vernux_created_files: set of paths VERNUX created this session
      cwd: current working directory

    Returns:
      {
        level:      "green" | "yellow" | "red" | "skull"
        reversible: bool
        reason:     str  — plain English explanation
        hard_stop:  bool — True means we refuse to run, no override
      }
    """
    if context is None:
        context = {}

    # --- Hard stop check first (no override possible) ---
    if _is_hard_stop(command):
        return {
            "level":      "skull",
            "reversible": False,
            "reason":     "This command could permanently destroy your system. It will not run.",
            "hard_stop":  True,
        }

    # --- Base classification from patterns ---
    level, reversible = _base_classify(command)

    # --- Context adjustments ---

    # Dev workflow: rm -rf ./build etc → downgrade from red to yellow
    if level == "red" and _is_dev_workflow(command):
        level = "yellow"
        reason = "Removing a build/cache folder — standard dev workflow."
    elif level == "red" and _hits_protected_path(command):
        # Hitting protected path + red = skull
        level = "skull"
        reversible = False
        reason = f"This would permanently delete files from a protected location."
    elif level == "red":
        reason = "This permanently deletes files. There is no undo."
    elif level == "yellow" and _hits_protected_path(command):
        # Caution command on protected path → escalate to red
        level = "red"
        reversible = False
        reason = f"This affects a protected location on your device."
    elif level == "yellow":
        reason = "This command modifies or removes something. Double-check before running."
    else:
        reason = ""

    # VERNUX-created file check: if the file was created by VERNUX, lower risk
    created = context.get("vernux_created_files", set())
    if created and level in ("red", "yellow"):
        for f in created:
            if f in command:
                level = "yellow" if level == "red" else "green"
                reason += " (VERNUX created this file.)"
                break

    return {
        "level":      level,
        "reversible": reversible,
        "reason":     reason,
        "hard_stop":  False,
    }


def requires_confirmation(level: str, mode: str) -> bool:
    """
    Decide if the user must confirm before running.
    """
    if mode == "noob":
        return level in ("green", "yellow", "red", "skull")  # always confirm
    elif mode == "learner":
        return level in ("yellow", "red", "skull")
    else:  # pro
        return level in ("red", "skull")


def requires_explicit_yes(level: str) -> bool:
    """Skull-level ops require typing 'yes' explicitly."""
    return level == "skull"
