# =============================================================================
# modules/executor.py — Command Runner & Output Handler
# Version: 0.2.0 | Phase 1 — Core Engine
# =============================================================================

import subprocess
import os
import re

# ---------------------------------------------------------------------------
# Error translation map
# Known bash errors → plain English
# ---------------------------------------------------------------------------
ERROR_MAP = [
    # File / path errors
    (r"No such file or directory",           "That file or folder doesn't exist. Check the name and try again."),
    (r"Permission denied",                   "VERNUX doesn't have permission to do that. You may need to check file permissions."),
    (r"Is a directory",                      "That's a folder, not a file. Use a different command for folders."),
    (r"Not a directory",                     "That's a file, not a folder."),
    (r"Directory not empty",                 "That folder isn't empty. Delete its contents first, or use rm -rf."),
    (r"File exists",                         "A file with that name already exists."),
    (r"Too many levels of symbolic links",   "There's a broken shortcut (symlink) in that path."),

    # Command errors
    (r"command not found",                   "That tool isn't installed. Try installing it with pkg install."),
    (r"not found",                           "Command not found. It may not be installed."),
    (r"Syntax error",                        "There's a syntax error in the command."),
    (r"bad interpreter",                     "The script has a bad shebang line or wrong interpreter."),

    # Network errors
    (r"Network is unreachable",              "No internet connection. Check your WiFi or data."),
    (r"Could not resolve host",              "Couldn't reach that address. Check your internet connection."),
    (r"Connection refused",                  "The server refused the connection. It may be down or the address is wrong."),
    (r"Connection timed out",               "The connection timed out. Check your internet or try again."),
    (r"curl: \(6\)",                         "Couldn't resolve the hostname. Check the URL and your internet."),
    (r"wget: unable to resolve",             "Couldn't find that address. Check the URL and your internet."),

    # Package manager errors
    (r"Unable to locate package",            "That package doesn't exist in Termux. Check the exact package name."),
    (r"E: Package .* has no installation candidate", "That package isn't available. Try pkg search to find the right name."),
    (r"dpkg: error",                         "Package install failed. Try running: pkg update, then retry."),
    (r"Segmentation fault",                  "The program crashed unexpectedly. Try reinstalling it."),

    # Git errors
    (r"not a git repository",               "This folder isn't a git project. Run 'git init' first, or go to your project folder."),
    (r"fatal: repository .* not found",      "That GitHub repository doesn't exist or is private."),
    (r"Authentication failed",               "GitHub authentication failed. Check your SSH key or token."),
    (r"Permission denied \(publickey\)",     "SSH key not set up for GitHub. You need to add your SSH key to GitHub first."),
    (r"remote: Repository not found",        "That GitHub repository doesn't exist or you don't have access."),
    (r"Updates were rejected",               "Your local changes conflict with what's on GitHub. Try git pull first."),

    # Storage errors
    (r"No space left on device",             "Your device is out of storage space. Free up some space and try again."),
    (r"Read-only file system",               "That location is read-only and can't be written to."),
    (r"Input/output error",                  "A disk or storage error occurred. Your device storage may have an issue."),

    # Python errors
    (r"ModuleNotFoundError",                 "A required Python package is missing. Install it with pip install."),
    (r"ImportError",                         "Python can't import a required module. You may need to install a package."),
    (r"SyntaxError",                         "There's a Python syntax error in your code."),

    # Kill / process errors
    (r"No such process",                     "That process isn't running anymore."),
    (r"Operation not permitted",             "You don't have permission to do that operation."),
]


def translate_error(stderr: str) -> str:
    """
    Match stderr against known error patterns.
    Returns plain English message, or empty string if unknown.
    """
    if not stderr:
        return ""
    for pattern, message in ERROR_MAP:
        if re.search(pattern, stderr, re.IGNORECASE):
            return message
    return ""


# ---------------------------------------------------------------------------
# Command runner
# ---------------------------------------------------------------------------

def run(command: str, cwd: str = None, timeout: int = 120) -> dict:
    """
    Execute a bash command.
    Returns:
      {
        stdout:           str
        stderr:           str
        exit_code:        int
        translated_error: str   — plain English error (empty if no error)
        timed_out:        bool
      }
    """
    if cwd is None:
        cwd = os.path.expanduser("~")

    result = {
        "stdout":           "",
        "stderr":           "",
        "exit_code":        0,
        "translated_error": "",
        "timed_out":        False,
    }

    try:
        proc = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=timeout,
            env={**os.environ, "TERM": "xterm-256color"},
        )
        result["stdout"]    = proc.stdout
        result["stderr"]    = proc.stderr
        result["exit_code"] = proc.returncode

        if proc.returncode != 0:
            result["translated_error"] = translate_error(proc.stderr)

    except subprocess.TimeoutExpired:
        result["exit_code"]        = -1
        result["stderr"]           = f"Command timed out after {timeout} seconds."
        result["translated_error"] = f"That took too long (over {timeout}s) and was stopped."
        result["timed_out"]        = True
    except Exception as e:
        result["exit_code"]        = -1
        result["stderr"]           = str(e)
        result["translated_error"] = f"Unexpected error: {e}"

    return result


# ---------------------------------------------------------------------------
# CWD tracker — called after cd commands
# ---------------------------------------------------------------------------

def resolve_new_cwd(command: str, current_cwd: str) -> str:
    """
    If the command is a cd, return the new working directory.
    Otherwise return current_cwd unchanged.
    """
    command = command.strip()
    if not command.startswith("cd"):
        return current_cwd

    # Extract the path argument
    parts = command.split(None, 1)
    if len(parts) == 1:
        # plain 'cd' goes home
        return os.path.expanduser("~")

    path = parts[1].strip().strip("'\"")

    # Handle special cases
    if path == "-":
        return current_cwd  # We don't track previous dirs here — no change
    if path == "~" or path == "":
        return os.path.expanduser("~")

    # Resolve relative paths
    if not os.path.isabs(path):
        candidate = os.path.normpath(os.path.join(current_cwd, path))
    else:
        candidate = os.path.normpath(path)

    if os.path.isdir(candidate):
        return candidate
    return current_cwd  # Invalid path — stay put


def fill_params(command: str, params: dict) -> str:
    """
    Replace {param} placeholders in a command template with actual values.
    e.g. fill_params("pkg install {package}", {"package": "python3"}) → "pkg install python3"
    """
    for key, value in params.items():
        command = command.replace(f"{{{key}}}", str(value))
    return command
