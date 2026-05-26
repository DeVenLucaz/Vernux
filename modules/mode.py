# =============================================================================
# modules/mode.py — Mode Logic & Output Filtering
# Version: 0.2.0 | Phase 1 — Core Engine
# =============================================================================

from modules.config import get as config_get


def get_mode() -> str:
    """Read current mode from config. Defaults to noob."""
    return config_get("mode", "noob")


def get_description(entry: dict, mode: str) -> str:
    """
    Return the right description field from a knowledge base entry
    based on the current mode.
    Falls back to description_learner then description_pro if field is empty.
    """
    key = f"description_{mode}"
    desc = entry.get(key, "").strip()
    if desc:
        return desc
    # Fallback chain
    for fallback in ("description_learner", "description_noob", "description_pro"):
        desc = entry.get(fallback, "").strip()
        if desc:
            return desc
    return entry.get("command", "")


def should_show_command(mode: str, safety_level: str) -> bool:
    """
    Determine if the raw command should be displayed to the user.
    Noob: never.
    Learner: always (educational).
    Pro: always.
    """
    if mode == "noob":
        return False
    return True


def requires_confirmation(mode: str, safety_level: str) -> bool:
    """
    Decide if user confirmation is needed before running.
    Noob confirms everything.
    Learner confirms yellow and above.
    Pro confirms red and above.
    """
    if mode == "noob":
        return True
    elif mode == "learner":
        return safety_level in ("yellow", "red", "skull")
    else:  # pro
        return safety_level in ("red", "skull")


def format_pre_run(entry: dict, mode: str, params: dict = None) -> dict:
    """
    Build the full pre-run display payload for a matched entry.

    Returns:
      {
        description: str   — what VERNUX will do
        show_command: bool — whether to display the raw command
        command_parts: list — [{token, meaning}] for learner breakdown (empty for others)
      }
    """
    desc         = get_description(entry, mode)
    show_command = should_show_command(mode, entry.get("safety", "green"))

    # Substitute params into description if present
    if params:
        for key, value in params.items():
            desc = desc.replace(f"{{{key}}}", str(value))

    # Learner mode: build command breakdown
    command_parts = []
    if mode == "learner" and show_command:
        command_parts = _build_command_parts(entry.get("command", ""))

    return {
        "description":   desc,
        "show_command":  show_command,
        "command_parts": command_parts,
    }


def _build_command_parts(command: str) -> list[dict]:
    """
    Very simple command breakdown for learner mode.
    Splits on spaces and flags, returns [{token, meaning}].
    Only covers common tokens — extended in Phase 2.
    """
    KNOWN_TOKENS = {
        "pkg":       "Termux package manager",
        "install":   "install a package",
        "uninstall": "remove an installed package",
        "update":    "refresh package list from server",
        "upgrade":   "install newer versions of everything",
        "-y":        "auto-confirm (don't ask for permission)",
        "-r":        "recursive (include subfolders)",
        "-rf":       "recursive + force (no confirmation)",
        "-h":        "human-readable output",
        "-la":       "long format + all files (including hidden)",
        "-a":        "include hidden files",
        "-l":        "long format listing",
        "rm":        "permanently delete a file or folder",
        "mv":        "move or rename a file",
        "cp":        "copy a file",
        "ls":        "list files in the current directory",
        "cd":        "change to a different directory",
        "mkdir":     "create a new folder",
        "-p":        "create parent folders if needed",
        "chmod":     "change file permissions",
        "+x":        "add execute permission (makes it runnable)",
        "git":       "git version control tool",
        "clone":     "download a repository",
        "status":    "show what has changed",
        "commit":    "save a snapshot of your changes",
        "-m":        "include a message",
        "push":      "upload changes to GitHub",
        "pull":      "download latest changes from GitHub",
        "wget":      "download a file from the internet",
        "curl":      "make an HTTP request",
        "-O":        "save output to a file",
        "python3":   "run a Python 3 script",
        "pip":       "Python package manager",
        "zip":       "create a zip archive",
        "unzip":     "extract a zip archive",
        "df":        "show disk/storage usage",
        "free":      "show RAM usage",
        "ping":      "test network connection",
        "-c":        "limit to N packets",
        "ps":        "show running processes",
        "kill":      "stop a running process",
        "clear":     "clear the terminal screen",
        "cat":       "display file contents",
        "grep":      "search for text inside files",
        "find":      "search for files by name or type",
        "pwd":       "print current directory path",
        "&&":        "run next command only if this one succeeded",
        "||":        "run next command only if this one failed",
        "|":         "pipe: send output of this to next command",
        ">":         "redirect output to a file (overwrites)",
        ">>":        "redirect output to a file (appends)",
    }

    tokens = command.split()
    parts  = []
    for token in tokens:
        meaning = KNOWN_TOKENS.get(token, "")
        if meaning:
            parts.append({"token": token, "meaning": meaning})

    return parts


def format_result(result: dict, mode: str) -> dict:
    """
    Post-run: determine how to display the result based on mode.
    Returns dict with display decisions for ui.py to act on.
    """
    success = result["exit_code"] == 0

    return {
        "success":          success,
        "show_raw_output":  mode in ("learner", "pro"),
        "show_raw_error":   mode in ("learner", "pro"),
        "use_translation":  mode == "noob" or not success,
    }
