# =============================================================================
# modules/ui.py — Terminal Display & User Interaction
# Version: 0.2.0 | Phase 1 — Core Engine
# =============================================================================

import sys
import time
import threading

# ---------------------------------------------------------------------------
# ANSI color constants
# ---------------------------------------------------------------------------
RESET  = "\033[0m"
BOLD   = "\033[1m"
DIM    = "\033[2m"

GREEN  = "\033[32m"
YELLOW = "\033[33m"
RED    = "\033[31m"
CYAN   = "\033[36m"
WHITE  = "\033[37m"
GRAY   = "\033[90m"

BG_RED    = "\033[41m"
BG_YELLOW = "\033[43m"

SAFETY_COLORS = {
    "green":  GREEN,
    "yellow": YELLOW,
    "red":    RED,
    "skull":  RED + BOLD,
}

SAFETY_ICONS = {
    "green":  "🟢",
    "yellow": "🟡",
    "red":    "🔴",
    "skull":  "☠️ ",
}

MODE_COLORS = {
    "noob":    GREEN,
    "learner": YELLOW,
    "pro":     RED,
}

MODE_ICONS = {
    "noob":    "🟢",
    "learner": "🟡",
    "pro":     "🔴",
}


def _c(color: str, text: str) -> str:
    """Wrap text in a color code."""
    return f"{color}{text}{RESET}"


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

def get_prompt(mode: str) -> str:
    icon  = MODE_ICONS.get(mode, "●")
    color = MODE_COLORS.get(mode, WHITE)
    return f"{color}{BOLD}VERNUX {icon} >{RESET} "


# ---------------------------------------------------------------------------
# Safety warnings
# ---------------------------------------------------------------------------

def print_safety_warning(level: str, description: str, reason: str = ""):
    """Print a mode-appropriate safety warning block."""
    icon  = SAFETY_ICONS.get(level, "⚠️")
    color = SAFETY_COLORS.get(level, YELLOW)

    if level in ("red", "skull"):
        print()
        print(f"{color}{BOLD}{'━' * 44}{RESET}")
        print(f"{color}{BOLD}  {icon}  WARNING — {level.upper()}{RESET}")
        print(f"{color}{'━' * 44}{RESET}")
        print(f"{color}  {description}{RESET}")
        if reason:
            print(f"{GRAY}  Reason: {reason}{RESET}")
        if level == "skull":
            print(f"{RED}{BOLD}  This CANNOT be undone.{RESET}")
        print(f"{color}{'━' * 44}{RESET}")
        print()
    elif level == "yellow":
        print()
        print(f"{YELLOW}  {icon}  Heads up: {description}{RESET}")
        if reason:
            print(f"{GRAY}  ({reason}){RESET}")
        print()
    # green: no warning printed


# ---------------------------------------------------------------------------
# Confirmations
# ---------------------------------------------------------------------------

def confirm(prompt: str, require_yes: bool = False) -> bool:
    """
    Ask user to confirm an action.
    require_yes=True: user must type exactly "yes" (for skull-level ops).
    Returns True if confirmed.
    """
    if require_yes:
        print(f"{RED}{BOLD}  Type 'yes' to proceed, anything else cancels:{RESET}")
        try:
            response = input(f"  {BOLD}> {RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            return False
        return response.lower() == "yes"
    else:
        print(f"{YELLOW}  {prompt} [y/N]{RESET} ", end="")
        try:
            response = input().strip().lower()
        except (KeyboardInterrupt, EOFError):
            return False
        return response in ("y", "yes")


# ---------------------------------------------------------------------------
# Command display (mode-aware)
# ---------------------------------------------------------------------------

def print_command(command: str, mode: str):
    """Show the resolved command — only in learner and pro modes."""
    if mode == "noob":
        return  # Noob never sees raw commands
    if mode == "learner":
        print(f"{CYAN}  $ {command}{RESET}")
    elif mode == "pro":
        print(f"{DIM}  $ {command}{RESET}")


def print_command_parts(command: str, parts: list[dict]):
    """
    Learner mode: break down each command token.
    parts = [{token: str, meaning: str}]
    """
    print(f"{CYAN}  $ {command}{RESET}")
    for part in parts:
        print(f"{GRAY}    {BOLD}{part['token']}{RESET}{GRAY} — {part['meaning']}{RESET}")
    print()


# ---------------------------------------------------------------------------
# Result display
# ---------------------------------------------------------------------------

def _translate_stdout_noob(stdout: str, command: str) -> str:
    """
    Convert raw command output to plain English for Noob mode.
    Only handles common commands — everything else gets a generic summary.
    """
    lines = stdout.strip().splitlines()
    cmd = command.strip().split()[0] if command.strip() else ""

    # ls / ls -la output
    if cmd == "ls":
        entries = [l for l in lines if l.strip() and not l.startswith("total")]
        dirs    = [l for l in entries if l.startswith("d")]
        files   = [l for l in entries if not l.startswith("d")]
        hidden  = [l for l in entries if " ." in l or l.split()[-1].startswith(".")]
        parts   = []
        if files:
            parts.append(f"📄 {len(files)} file(s)")
        if dirs:
            parts.append(f"📁 {len(dirs)} folder(s)")
        if hidden:
            parts.append(f"👁  {len(hidden)} hidden item(s)")
        if not parts:
            return "  The folder is empty."
        names = [l.split()[-1] for l in entries[:8]]
        return "  " + ", ".join(parts) + "\n  Items: " + ", ".join(names) + (
            f"  … and {len(entries)-8} more" if len(entries) > 8 else ""
        )

    # df output (storage check)
    if cmd == "df":
        for line in lines:
            parts = line.split()
            if len(parts) >= 5 and "%" in parts[-2]:
                used_pct = parts[-2]
                avail    = parts[3] if len(parts) > 3 else "?"
                return f"  Storage: {used_pct} used. About {avail}K free."
        return "  " + "\n  ".join(lines[:3])

    # free output (RAM)
    if cmd == "free":
        for line in lines:
            if line.lower().startswith("mem"):
                parts = line.split()
                if len(parts) >= 3:
                    total = int(parts[1]) // 1024
                    used  = int(parts[2]) // 1024
                    return f"  RAM: {used}MB used out of {total}MB total."
        return "  " + "\n  ".join(lines[:2])

    # ping output
    if cmd == "ping":
        if "0% packet loss" in stdout or "0 received" not in stdout:
            return "  ✅ Internet is working."
        return "  ❌ No internet connection detected."

    # git status
    if cmd == "git" and "status" in command:
        if "nothing to commit" in stdout:
            return "  ✅ Everything is saved. Nothing new to commit."
        if "Untracked files" in stdout or "Changes not staged" in stdout:
            return "  📝 You have unsaved changes. Run 'save my work' to commit them."
        return "  " + "\n  ".join(lines[:4])

    # Default: show first 5 lines with indent, note if truncated
    if len(lines) <= 6:
        return "\n".join(f"  {l}" for l in lines)
    return "\n".join(f"  {l}" for l in lines[:5]) + f"\n  … ({len(lines)-5} more lines)"


def print_result(stdout: str, stderr: str, exit_code: int, mode: str,
                 translated_error: str = "", command: str = ""):
    """Display command output in a mode-appropriate way."""
    if exit_code == 0:
        if stdout.strip():
            if mode == "pro":
                print(stdout)
            elif mode == "noob":
                print()
                print(_translate_stdout_noob(stdout, command))
                print()
            else:  # learner
                print()
                for line in stdout.strip().splitlines():
                    print(f"  {line}")
                print()
    else:
        # Error path
        if mode == "noob":
            msg = translated_error or "Something went wrong. Try again or ask for help."
            print(f"\n{RED}  ✗ {msg}{RESET}\n")
        elif mode == "learner":
            msg = translated_error or stderr.strip() or "Command failed."
            print(f"\n{RED}  ✗ {msg}{RESET}")
            if stderr.strip() and translated_error:
                print(f"{GRAY}  Raw: {stderr.strip()[:120]}{RESET}")
            print()
        else:  # pro
            if stderr.strip():
                print(f"{RED}{stderr.strip()}{RESET}")
            else:
                print(f"{RED}Exit code {exit_code}{RESET}")


def print_success(message: str, mode: str):
    """Print a success message (mode-aware verbosity)."""
    if mode == "pro":
        print(f"{GREEN}✔{RESET}  {message}")
    else:
        print(f"\n{GREEN}  ✔  {message}{RESET}\n")


def print_info(message: str):
    """Print a neutral info line."""
    print(f"{GRAY}  ℹ  {message}{RESET}")


def print_error(message: str):
    """Print a plain error line."""
    print(f"{RED}  ✗  {message}{RESET}")


# ---------------------------------------------------------------------------
# Device card (first run)
# ---------------------------------------------------------------------------

def print_device_card(profile: dict):
    """Display a friendly device summary card on first run."""
    ram     = profile.get("ram", {})
    storage = profile.get("storage", {})
    android = profile.get("android", {})
    brand   = profile.get("brand", "unknown").capitalize()
    tier    = profile.get("tier", "unknown")
    has_api = profile.get("termux_api", False)

    tier_colors = {
        "micro":   RED,
        "low":     YELLOW,
        "low-mid": YELLOW,
        "mid":     GREEN,
        "high":    GREEN,
    }
    tc = tier_colors.get(tier, WHITE)

    print()
    print(f"{CYAN}{BOLD}  ┌─ Your Device ─────────────────────────┐{RESET}")
    print(f"{CYAN}{BOLD}  │{RESET}  RAM      : {ram.get('total_gb', 0):.1f} GB  {tc}({tier} tier){RESET}")
    print(f"{CYAN}{BOLD}  │{RESET}  Free RAM : {ram.get('available_gb', 0):.1f} GB")
    print(f"{CYAN}{BOLD}  │{RESET}  Storage  : {storage.get('internal_free_gb', 0):.1f} GB free")
    print(f"{CYAN}{BOLD}  │{RESET}  Brand    : {brand}")
    print(f"{CYAN}{BOLD}  │{RESET}  Android  : {android.get('version', 'Unknown')}")
    print(f"{CYAN}{BOLD}  │{RESET}  Termux-API: {'✔ installed' if has_api else '✗ not found'}")
    print(f"{CYAN}{BOLD}  └───────────────────────────────────────┘{RESET}")
    print()


# ---------------------------------------------------------------------------
# Spinner (for LLM calls — Phase 4, stub here)
# ---------------------------------------------------------------------------

class Spinner:
    """Context manager that shows a spinning indicator during long ops."""
    def __init__(self, message: str = "Thinking"):
        self.message  = message
        self._stop    = threading.Event()
        self._thread  = None

    def _spin(self):
        chars = ["⠋", "⠙", "⠸", "⠴", "⠦", "⠇"]
        i = 0
        while not self._stop.is_set():
            sys.stdout.write(f"\r{CYAN}  {chars[i % len(chars)]}  {self.message}...{RESET}")
            sys.stdout.flush()
            time.sleep(0.1)
            i += 1
        sys.stdout.write("\r" + " " * (len(self.message) + 12) + "\r")
        sys.stdout.flush()

    def __enter__(self):
        self._thread = threading.Thread(target=self._spin, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *_):
        self._stop.set()
        if self._thread:
            self._thread.join()


# ---------------------------------------------------------------------------
# "Did you mean?" display
# ---------------------------------------------------------------------------

def print_did_you_mean(candidates: list[dict]):
    """Show top pattern candidates when confidence is below threshold."""
    print(f"\n{YELLOW}  Not sure what you mean. Did you mean:{RESET}")
    for i, c in enumerate(candidates[:3], 1):
        print(f"{YELLOW}    {i}. {c['id'].replace('_', ' ')}{RESET}"
              f"{GRAY} — {c.get('description_noob', '')[:60]}{RESET}")
    print(f"{GRAY}  Or try rephrasing what you want to do.{RESET}\n")


# ---------------------------------------------------------------------------
# Doctor output
# ---------------------------------------------------------------------------

def print_doctor_report(checks: list[dict]):
    """
    Render a vernux doctor health report.
    Each check: {name: str, status: 'ok'|'warn'|'fail', message: str, fix: str}
    """
    icons = {"ok": f"{GREEN}✔{RESET}", "warn": f"{YELLOW}⚠{RESET}", "fail": f"{RED}✗{RESET}"}
    print(f"\n{BOLD}  VERNUX Doctor — Health Report{RESET}")
    print(f"{GRAY}  {'─' * 40}{RESET}")
    for check in checks:
        icon = icons.get(check["status"], "?")
        print(f"  {icon}  {check['name']:<28} {GRAY}{check['message']}{RESET}")
        if check.get("fix") and check["status"] != "ok":
            print(f"{YELLOW}     Fix: {check['fix']}{RESET}")
    print(f"{GRAY}  {'─' * 40}{RESET}\n")
