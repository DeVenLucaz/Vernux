# =============================================================================
# tools/build_db.py — Data Ingestion & Build Pipeline
# Version: 0.1.0 | Phase 0 — Foundation
# =============================================================================
# DEV TOOL — not shipped to users. Run once during development.
# Usage: python tools/build_db.py
#
# Reads raw data source repos from tools/sources/ (git clone them there first).
# Outputs clean unified JSONs to data/ directories.
# =============================================================================

import json
import os
import sys
import re
from pathlib import Path

# Project root = one level up from tools/
ROOT      = Path(__file__).parent.parent
DATA_DIR  = ROOT / "data"
SRC_DIR   = Path(__file__).parent / "sources"

LAYERS = ["noob", "learner", "pro", "universal"]

# ---------------------------------------------------------------------------
# Unified entry schema
# ---------------------------------------------------------------------------
# {
#   "id":                  str   unique snake_case
#   "triggers":            list  phrases that activate this entry
#   "command":             str   bash command with {param} placeholders
#   "description_noob":    str   plain English for beginners
#   "description_learner": str   educational breakdown
#   "description_pro":     str   one-line / raw
#   "example":             str   real example invocation
#   "safety":              str   "green" | "yellow" | "red" | "skull"
#   "reversible":          bool
#   "undo":                str | null
#   "requires":            list  package names
#   "category":            str   e.g. "archives", "git", "network"
#   "source_credit":       str   original data source name
# }

ENTRY_SCHEMA_KEYS = [
    "id", "triggers", "command",
    "description_noob", "description_learner", "description_pro",
    "example", "safety", "reversible", "undo",
    "requires", "category", "source_credit"
]

ENTRY_DEFAULTS = {
    "triggers":            [],
    "command":             "",
    "description_noob":    "",
    "description_learner": "",
    "description_pro":     "",
    "example":             "",
    "safety":              "green",
    "reversible":          True,
    "undo":                None,
    "requires":            [],
    "category":            "general",
    "source_credit":       "unknown"
}


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_entry(entry: dict) -> tuple[bool, list]:
    """
    Validate a unified entry against the schema.
    Returns (is_valid, list_of_errors).
    """
    errors = []

    if not entry.get("id"):
        errors.append("Missing or empty 'id'")

    if not entry.get("command"):
        errors.append("Missing or empty 'command'")

    if not isinstance(entry.get("triggers"), list) or len(entry["triggers"]) == 0:
        errors.append("'triggers' must be a non-empty list")

    valid_safety = {"green", "yellow", "red", "skull"}
    if entry.get("safety") not in valid_safety:
        errors.append(f"'safety' must be one of {valid_safety}")

    if not isinstance(entry.get("requires"), list):
        errors.append("'requires' must be a list")

    return len(errors) == 0, errors


def make_id(text: str) -> str:
    """Convert a human-readable string to a snake_case id."""
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\s_]", "", text)
    text = re.sub(r"\s+", "_", text)
    return text[:64]


# ---------------------------------------------------------------------------
# Output writers
# ---------------------------------------------------------------------------

def write_layer(layer: str, entries: list, filename: str = "entries.json"):
    """Write a list of entries to data/<layer>/<filename>."""
    out_dir = DATA_DIR / layer
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / filename

    with open(out_path, "w") as f:
        json.dump({"entries": entries}, f, indent=2, ensure_ascii=False)

    print(f"  ✔  Wrote {len(entries)} entries → {out_path.relative_to(ROOT)}")


def write_patterns(patterns: list):
    """Write patterns.json to data/."""
    out_path = DATA_DIR / "patterns.json"
    payload = {
        "_comment": "VERNUX Pattern Library — built by tools/build_db.py",
        "_version": "0.1.0",
        "patterns":  patterns
    }
    with open(out_path, "w") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(f"  ✔  Wrote {len(patterns)} patterns → data/patterns.json")


def write_pkg_cache(packages: list):
    """Write pkg_cache.json to data/."""
    out_path = DATA_DIR / "pkg_cache.json"
    payload = {
        "_comment": "VERNUX Package Cache — built by tools/build_db.py",
        "_version": "0.1.0",
        "packages":  packages
    }
    with open(out_path, "w") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(f"  ✔  Wrote {len(packages)} packages → data/pkg_cache.json")


# ---------------------------------------------------------------------------
# Source ingestors
# ---------------------------------------------------------------------------
# Each ingestor reads one source repo and returns raw dicts.
# Normalizer converts raw dicts to unified schema.

def ingest_101_commands(src_path: Path) -> list:
    """
    Ingest bobbyiliev/101-linux-commands-ebook.
    Expects markdown files in the source directory.
    Returns list of raw dicts: {name, description, example, category}
    """
    raw = []
    if not src_path.exists():
        print(f"  ⚠  Source not found: {src_path} — skipping")
        return raw

    for md_file in sorted(src_path.rglob("*.md")):
        text = md_file.read_text(errors="ignore")
        # Extract command name from filename or first heading
        name_match = re.search(r"^#\s+(.+)", text, re.MULTILINE)
        cmd_match  = re.search(r"```(?:bash|sh)?\n(.+?)\n```", text, re.DOTALL)

        if name_match and cmd_match:
            raw.append({
                "name":        name_match.group(1).strip(),
                "description": text[:300],   # First 300 chars as rough description
                "command":     cmd_match.group(1).strip().splitlines()[0],
                "category":    "general",
                "source":      "101_linux_commands"
            })

    return raw


def ingest_linux_cmdlib(src_path: Path) -> list:
    """
    Ingest SimonSchubert/LinuxCommandLibrary JSON data.
    Expects a commands.json or similar in the source directory.
    """
    raw = []
    if not src_path.exists():
        print(f"  ⚠  Source not found: {src_path} — skipping")
        return raw

    # LinuxCommandLibrary stores data as individual JSON files or one big JSON
    for json_file in sorted(src_path.rglob("*.json")):
        try:
            data = json.loads(json_file.read_text())
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and "name" in item:
                        raw.append({**item, "source": "linux_cmdlib"})
            elif isinstance(data, dict) and "name" in data:
                raw.append({**data, "source": "linux_cmdlib"})
        except Exception:
            continue

    return raw


def normalize_entry(raw: dict, layer: str) -> dict | None:
    """
    Convert a raw ingested dict to the unified VERNUX entry schema.
    Returns None if the entry is too minimal to be useful.
    """
    name    = raw.get("name", "").strip()
    command = raw.get("command", raw.get("cmd", "")).strip()

    if not name or not command:
        return None

    entry = dict(ENTRY_DEFAULTS)
    entry["id"]                  = make_id(name)
    entry["command"]             = command
    entry["triggers"]            = [name.lower()]
    entry["description_noob"]    = raw.get("description", "")[:200]
    entry["description_learner"] = raw.get("description", "")[:300]
    entry["description_pro"]     = command
    entry["example"]             = raw.get("example", command)
    entry["category"]            = raw.get("category", "general")
    entry["source_credit"]       = raw.get("source", "unknown")

    # Heuristic safety classification
    danger_patterns = ["rm -rf", "dd if=", "mkfs", "> /dev/", "chmod 777"]
    caution_patterns = ["rm ", "mv ", "chmod", "chown", "kill", "pkill"]

    for p in danger_patterns:
        if p in command:
            entry["safety"] = "red"
            entry["reversible"] = False
            break
    else:
        for p in caution_patterns:
            if p in command:
                entry["safety"] = "yellow"
                break

    return entry


# ---------------------------------------------------------------------------
# Seed patterns (hand-curated, Phase 0 minimum viable set)
# ---------------------------------------------------------------------------

def build_seed_patterns() -> list:
    """
    Hand-curated seed patterns for Phase 0.
    These 30 patterns cover the most common Termux beginner tasks.
    Expanded to 150+ in Phase 2.
    """
    return [
        {
            "id": "update_packages",
            "triggers": ["update packages", "update termux", "update everything", "pkg update"],
            "command": "pkg update && pkg upgrade -y",
            "description_noob": "I'll update all your installed apps and tools to their latest versions.",
            "description_learner": "pkg update = refresh package list, pkg upgrade = install newer versions of everything installed.",
            "description_pro": "pkg update && pkg upgrade -y",
            "example": "pkg update && pkg upgrade -y",
            "safety": "green", "reversible": False, "undo": None,
            "requires": [], "category": "packages", "source_credit": "vernux"
        },
        {
            "id": "install_python",
            "triggers": ["install python", "get python", "i need python", "setup python"],
            "command": "pkg install python3 -y",
            "description_noob": "I'll install Python 3 — the most popular coding language. Takes about 30 seconds.",
            "description_learner": "In Termux the package is called python3, not python. pkg install fetches and installs it.",
            "description_pro": "pkg install python3 -y",
            "example": "pkg install python3 -y",
            "safety": "green", "reversible": True, "undo": "pkg uninstall python3",
            "requires": [], "category": "packages", "source_credit": "vernux"
        },
        {
            "id": "install_git",
            "triggers": ["install git", "get git", "i need git", "setup git"],
            "command": "pkg install git -y",
            "description_noob": "I'll install Git — the tool you need to work with GitHub and save your project history.",
            "description_learner": "Git is version control. After install, you'll need to configure your name and email before committing.",
            "description_pro": "pkg install git -y",
            "example": "pkg install git -y",
            "safety": "green", "reversible": True, "undo": "pkg uninstall git",
            "requires": [], "category": "packages", "source_credit": "vernux"
        },
        {
            "id": "install_nodejs",
            "triggers": ["install nodejs", "install node", "get nodejs", "i need node", "setup nodejs"],
            "command": "pkg install nodejs -y",
            "description_noob": "I'll install Node.js — used for JavaScript projects and web servers.",
            "description_learner": "Termux package is 'nodejs' not 'node'. Includes npm automatically.",
            "description_pro": "pkg install nodejs -y",
            "example": "pkg install nodejs -y",
            "safety": "green", "reversible": True, "undo": "pkg uninstall nodejs",
            "requires": [], "category": "packages", "source_credit": "vernux"
        },
        {
            "id": "setup_storage",
            "triggers": ["setup storage", "access phone storage", "access sdcard", "termux storage", "setup sdcard", "grant storage permission"],
            "command": "termux-setup-storage",
            "description_noob": "I'll ask Android for permission to access your phone's storage (Downloads, Pictures, etc). A popup will appear — tap Allow.",
            "description_learner": "termux-setup-storage creates a ~/storage symlink to Android storage locations. Must be run once. Accept the popup.",
            "description_pro": "termux-setup-storage",
            "example": "termux-setup-storage",
            "safety": "green", "reversible": False, "undo": None,
            "requires": [], "category": "storage", "source_credit": "vernux"
        },
        {
            "id": "copy_to_downloads",
            "triggers": ["copy to downloads", "save to phone", "move to sdcard", "share file to phone", "copy to sdcard"],
            "command": "cp {file} /sdcard/Download/",
            "description_noob": "I'll copy your file to the Downloads folder on your phone — where you can find it in the Files app.",
            "description_learner": "Termux home is sandboxed. /sdcard/Download/ is your phone's Downloads folder accessible to Android apps.",
            "description_pro": "cp {file} /sdcard/Download/",
            "example": "cp myfile.txt /sdcard/Download/",
            "safety": "green", "reversible": True, "undo": "rm /sdcard/Download/{file}",
            "requires": [], "category": "storage", "source_credit": "vernux"
        },
        {
            "id": "show_current_directory",
            "triggers": ["where am i", "current directory", "what folder am i in", "show path", "pwd"],
            "command": "pwd",
            "description_noob": "I'll show you exactly where you are in the file system — like checking which room you're in.",
            "description_learner": "pwd = print working directory. Shows your full current path.",
            "description_pro": "pwd",
            "example": "pwd",
            "safety": "green", "reversible": True, "undo": None,
            "requires": [], "category": "navigation", "source_credit": "vernux"
        },
        {
            "id": "list_files",
            "triggers": ["list files", "show files", "what's here", "show folder contents", "ls"],
            "command": "ls -la",
            "description_noob": "I'll show you all the files and folders here, including hidden ones.",
            "description_learner": "ls -l = detailed list, -a = include hidden files (starting with dot).",
            "description_pro": "ls -la",
            "example": "ls -la",
            "safety": "green", "reversible": True, "undo": None,
            "requires": [], "category": "navigation", "source_credit": "vernux"
        },
        {
            "id": "make_folder",
            "triggers": ["make folder", "create folder", "new directory", "mkdir", "create directory"],
            "command": "mkdir -p {folder_name}",
            "description_noob": "I'll create a new folder for you.",
            "description_learner": "mkdir -p creates the folder and any missing parent folders. Safe to run even if it already exists.",
            "description_pro": "mkdir -p {folder_name}",
            "example": "mkdir -p myproject",
            "safety": "green", "reversible": True, "undo": "rmdir {folder_name}",
            "requires": [], "category": "files", "source_credit": "vernux"
        },
        {
            "id": "delete_file",
            "triggers": ["delete file", "remove file", "rm file"],
            "command": "rm {filename}",
            "description_noob": "I'll permanently delete that file. This cannot be undone — there is no Recycle Bin.",
            "description_learner": "rm removes a single file permanently. Use rm -r for folders. No undo.",
            "description_pro": "rm {filename}",
            "example": "rm oldfile.txt",
            "safety": "yellow", "reversible": False, "undo": None,
            "requires": [], "category": "files", "source_credit": "vernux"
        },
        {
            "id": "zip_folder",
            "triggers": ["compress folder", "zip folder", "archive directory", "zip files", "make zip"],
            "command": "zip -r {output}.zip {folder}/",
            "description_noob": "I'll bundle your folder into a single compressed zip file.",
            "description_learner": "zip -r = recursive (includes subfolders). Output is a .zip archive you can share.",
            "description_pro": "zip -r {output}.zip {folder}/",
            "example": "zip -r myproject.zip myproject/",
            "safety": "green", "reversible": True, "undo": "rm {output}.zip",
            "requires": ["zip"], "category": "archives", "source_credit": "vernux"
        },
        {
            "id": "unzip_file",
            "triggers": ["unzip file", "extract zip", "extract archive", "unzip"],
            "command": "unzip {file}.zip",
            "description_noob": "I'll unpack the zip file and put all the files into a folder.",
            "description_learner": "unzip extracts to current directory. Use -d folder to extract to a specific location.",
            "description_pro": "unzip {file}.zip",
            "example": "unzip archive.zip",
            "safety": "green", "reversible": True, "undo": None,
            "requires": ["unzip"], "category": "archives", "source_credit": "vernux"
        },
        {
            "id": "check_storage",
            "triggers": ["check storage", "how much storage", "disk space", "storage left", "why is storage full"],
            "command": "df -h ~",
            "description_noob": "I'll show how much storage space is left on your device.",
            "description_learner": "df -h = disk free, human readable. ~ = your Termux home directory.",
            "description_pro": "df -h ~",
            "example": "df -h ~",
            "safety": "green", "reversible": True, "undo": None,
            "requires": [], "category": "system", "source_credit": "vernux"
        },
        {
            "id": "check_ram",
            "triggers": ["check ram", "how much ram", "memory usage", "ram left", "free memory"],
            "command": "free -h",
            "description_noob": "I'll show how much memory (RAM) your device has and how much is currently being used.",
            "description_learner": "free -h shows total, used, and available RAM in human-readable format.",
            "description_pro": "free -h",
            "example": "free -h",
            "safety": "green", "reversible": True, "undo": None,
            "requires": [], "category": "system", "source_credit": "vernux"
        },
        {
            "id": "install_package",
            "triggers": ["install {package}", "get {package}", "i need {package}", "download {package}"],
            "command": "pkg install {package} -y",
            "description_noob": "I'll install {package} for you. This might take a minute depending on your connection.",
            "description_learner": "pkg install is Termux's package manager. -y auto-confirms. Package name must be the exact Termux name.",
            "description_pro": "pkg install {package} -y",
            "example": "pkg install curl -y",
            "safety": "green", "reversible": True, "undo": "pkg uninstall {package}",
            "requires": [], "category": "packages", "source_credit": "vernux"
        },
        {
            "id": "clone_repo",
            "triggers": ["clone repo", "download repo", "git clone", "clone from github", "clone repository"],
            "command": "git clone {url}",
            "description_noob": "I'll download the entire project from GitHub to your Termux.",
            "description_learner": "git clone downloads a repository. Creates a folder with the project name. Requires git installed.",
            "description_pro": "git clone {url}",
            "example": "git clone https://github.com/user/repo.git",
            "safety": "green", "reversible": True, "undo": "rm -rf {repo_name}",
            "requires": ["git"], "category": "git", "source_credit": "vernux"
        },
        {
            "id": "git_status",
            "triggers": ["git status", "what changed", "show changes", "check git status"],
            "command": "git status",
            "description_noob": "I'll show you which files have changed since your last save.",
            "description_learner": "git status shows tracked/untracked changes. Run this before committing.",
            "description_pro": "git status",
            "example": "git status",
            "safety": "green", "reversible": True, "undo": None,
            "requires": ["git"], "category": "git", "source_credit": "vernux"
        },
        {
            "id": "download_file",
            "triggers": ["download file", "download url", "wget", "curl download", "get file from url"],
            "command": "wget {url}",
            "description_noob": "I'll download that file from the internet to your current folder.",
            "description_learner": "wget downloads a file from a URL. Use -O filename.ext to save with a specific name.",
            "description_pro": "wget {url}",
            "example": "wget https://example.com/file.zip",
            "safety": "green", "reversible": True, "undo": None,
            "requires": ["wget"], "category": "network", "source_credit": "vernux"
        },
        {
            "id": "run_python_script",
            "triggers": ["run python script", "run python file", "execute python", "python script"],
            "command": "python3 {script}.py",
            "description_noob": "I'll run your Python script.",
            "description_learner": "python3 executes a .py file. Make sure you're in the right directory first.",
            "description_pro": "python3 {script}.py",
            "example": "python3 main.py",
            "safety": "green", "reversible": True, "undo": None,
            "requires": ["python3"], "category": "programming", "source_credit": "vernux"
        },
        {
            "id": "install_pip_package",
            "triggers": ["pip install", "install pip package", "install python package"],
            "command": "pip install {package}",
            "description_noob": "I'll add a Python library that you can use in your scripts.",
            "description_learner": "pip is Python's package manager. Installs libraries from PyPI. Use pip3 if pip isn't found.",
            "description_pro": "pip install {package}",
            "example": "pip install requests",
            "safety": "green", "reversible": True, "undo": "pip uninstall {package}",
            "requires": ["python3"], "category": "programming", "source_credit": "vernux"
        },
        {
            "id": "clear_terminal",
            "triggers": ["clear screen", "clear terminal", "cls", "clean screen"],
            "command": "clear",
            "description_noob": "I'll clean up the screen so it's blank again.",
            "description_learner": "clear scrolls the terminal. Your history is still accessible by scrolling up.",
            "description_pro": "clear",
            "example": "clear",
            "safety": "green", "reversible": True, "undo": None,
            "requires": [], "category": "terminal", "source_credit": "vernux"
        },
        {
            "id": "show_running_processes",
            "triggers": ["show processes", "what's running", "running apps", "ps", "process list"],
            "command": "ps aux",
            "description_noob": "I'll show you all the programs running right now in Termux.",
            "description_learner": "ps aux = process snapshot. a=all users, u=user-friendly, x=include background processes.",
            "description_pro": "ps aux",
            "example": "ps aux",
            "safety": "green", "reversible": True, "undo": None,
            "requires": [], "category": "system", "source_credit": "vernux"
        },
        {
            "id": "kill_process",
            "triggers": ["kill process", "stop process", "kill program", "force stop"],
            "command": "kill {pid}",
            "description_noob": "I'll stop that running program. You'll need the process ID number — use 'show processes' first to find it.",
            "description_learner": "kill sends SIGTERM to a process by PID. Use kill -9 if it doesn't respond.",
            "description_pro": "kill {pid}",
            "example": "kill 1234",
            "safety": "yellow", "reversible": False, "undo": None,
            "requires": [], "category": "system", "source_credit": "vernux"
        },
        {
            "id": "change_directory",
            "triggers": ["go to folder", "change directory", "navigate to", "open folder", "cd"],
            "command": "cd {path}",
            "description_noob": "I'll move you into that folder.",
            "description_learner": "cd = change directory. Use cd ~ to go home, cd .. to go up one level, cd - to go back.",
            "description_pro": "cd {path}",
            "example": "cd myproject",
            "safety": "green", "reversible": True, "undo": "cd -",
            "requires": [], "category": "navigation", "source_credit": "vernux"
        },
        {
            "id": "show_file_content",
            "triggers": ["show file", "read file", "cat file", "display file", "print file"],
            "command": "cat {filename}",
            "description_noob": "I'll display the contents of that file right here in the terminal.",
            "description_learner": "cat prints file contents to stdout. Use less {file} for long files you can scroll.",
            "description_pro": "cat {filename}",
            "example": "cat readme.txt",
            "safety": "green", "reversible": True, "undo": None,
            "requires": [], "category": "files", "source_credit": "vernux"
        },
        {
            "id": "check_internet",
            "triggers": ["check internet", "test connection", "am i online", "ping test", "internet connection"],
            "command": "ping -c 4 8.8.8.8",
            "description_noob": "I'll check if your internet connection is working.",
            "description_learner": "ping sends 4 packets to Google's DNS (8.8.8.8). If you see replies, internet is working.",
            "description_pro": "ping -c 4 8.8.8.8",
            "example": "ping -c 4 8.8.8.8",
            "safety": "green", "reversible": True, "undo": None,
            "requires": [], "category": "network", "source_credit": "vernux"
        },
        {
            "id": "make_script_executable",
            "triggers": ["make executable", "run script", "chmod script", "permission denied script"],
            "command": "chmod +x {script}",
            "description_noob": "I'll give that script permission to run.",
            "description_learner": "chmod +x adds execute permission. Then run it with ./{script}",
            "description_pro": "chmod +x {script}",
            "example": "chmod +x setup.sh",
            "safety": "yellow", "reversible": True, "undo": "chmod -x {script}",
            "requires": [], "category": "files", "source_credit": "vernux"
        },
        {
            "id": "install_nano",
            "triggers": ["install nano", "get text editor", "install text editor", "text editor termux"],
            "command": "pkg install nano -y",
            "description_noob": "I'll install Nano — a simple text editor you can use right inside Termux.",
            "description_learner": "nano is the most beginner-friendly terminal text editor. Open a file: nano filename.txt. Ctrl+X to exit.",
            "description_pro": "pkg install nano -y",
            "example": "pkg install nano -y",
            "safety": "green", "reversible": True, "undo": "pkg uninstall nano",
            "requires": [], "category": "packages", "source_credit": "vernux"
        },
        {
            "id": "search_package",
            "triggers": ["search package", "find package", "is package available", "pkg search"],
            "command": "pkg search {query}",
            "description_noob": "I'll search for available packages that match what you're looking for.",
            "description_learner": "pkg search queries the Termux package index. Shows all matching package names.",
            "description_pro": "pkg search {query}",
            "example": "pkg search ffmpeg",
            "safety": "green", "reversible": True, "undo": None,
            "requires": [], "category": "packages", "source_credit": "vernux"
        },
        {
            "id": "install_ffmpeg",
            "triggers": ["install ffmpeg", "get ffmpeg", "convert video", "video tool"],
            "command": "pkg install ffmpeg -y",
            "description_noob": "I'll install FFmpeg — a powerful tool for working with video and audio files.",
            "description_learner": "Termux package is 'ffmpeg' not 'ffmpeg4'. Includes full codec support.",
            "description_pro": "pkg install ffmpeg -y",
            "example": "pkg install ffmpeg -y",
            "safety": "green", "reversible": True, "undo": "pkg uninstall ffmpeg",
            "requires": [], "category": "packages", "source_credit": "vernux"
        },
    ]


# ---------------------------------------------------------------------------
# Seed package cache
# ---------------------------------------------------------------------------

def build_seed_pkg_cache() -> list:
    """
    Minimal seed package cache for Phase 0.
    Contains the most important Termux packages with common-name → real-name mapping.
    Expanded by tools/refresh_pkg_cache.py (Phase 5) with full termux-packages list.
    """
    return [
        {"name": "python3",   "common_names": ["python", "py", "python3"], "category": "programming", "size_estimate_mb": 65},
        {"name": "nodejs",    "common_names": ["node", "nodejs", "npm"],    "category": "programming", "size_estimate_mb": 80},
        {"name": "git",       "common_names": ["git"],                      "category": "development", "size_estimate_mb": 20},
        {"name": "ffmpeg",    "common_names": ["ffmpeg", "ffmpeg4"],        "category": "media",       "size_estimate_mb": 90},
        {"name": "wget",      "common_names": ["wget"],                     "category": "network",     "size_estimate_mb": 2},
        {"name": "curl",      "common_names": ["curl"],                     "category": "network",     "size_estimate_mb": 3},
        {"name": "nano",      "common_names": ["nano", "text editor"],      "category": "editors",     "size_estimate_mb": 4},
        {"name": "vim",       "common_names": ["vim", "vi"],                "category": "editors",     "size_estimate_mb": 10},
        {"name": "zip",       "common_names": ["zip"],                      "category": "archives",    "size_estimate_mb": 1},
        {"name": "unzip",     "common_names": ["unzip"],                    "category": "archives",    "size_estimate_mb": 1},
        {"name": "openssh",   "common_names": ["ssh", "openssh", "sshd"],   "category": "network",     "size_estimate_mb": 8},
        {"name": "tmux",      "common_names": ["tmux", "screen"],           "category": "terminal",    "size_estimate_mb": 5},
        {"name": "zsh",       "common_names": ["zsh", "zshell"],            "category": "shell",       "size_estimate_mb": 8},
        {"name": "clang",     "common_names": ["gcc", "cc", "clang", "c compiler"], "category": "development", "size_estimate_mb": 200},
        {"name": "make",      "common_names": ["make"],                     "category": "development", "size_estimate_mb": 3},
        {"name": "rust",      "common_names": ["rust", "rustc", "cargo"],   "category": "programming", "size_estimate_mb": 500},
        {"name": "golang",    "common_names": ["go", "golang"],             "category": "programming", "size_estimate_mb": 300},
        {"name": "php",       "common_names": ["php"],                      "category": "programming", "size_estimate_mb": 40},
        {"name": "ruby",      "common_names": ["ruby", "gem"],              "category": "programming", "size_estimate_mb": 50},
        {"name": "perl",      "common_names": ["perl"],                     "category": "programming", "size_estimate_mb": 30},
        {"name": "htop",      "common_names": ["htop", "top", "task manager"], "category": "system",  "size_estimate_mb": 1},
        {"name": "nmap",      "common_names": ["nmap", "network scanner"],  "category": "network",     "size_estimate_mb": 15},
        {"name": "termux-api","common_names": ["termux-api", "termux api"], "category": "android",     "size_estimate_mb": 2},
        {"name": "tsu",       "common_names": ["sudo", "tsu", "superuser"], "category": "system",      "size_estimate_mb": 1},
        {"name": "sqlite",    "common_names": ["sqlite", "sqlite3"],        "category": "database",    "size_estimate_mb": 5},
        {"name": "mariadb",   "common_names": ["mysql", "mariadb"],        "category": "database",    "size_estimate_mb": 150},
        {"name": "nginx",     "common_names": ["nginx", "web server"],      "category": "server",      "size_estimate_mb": 10},
        {"name": "apache2",   "common_names": ["apache", "apache2", "httpd"],"category": "server",    "size_estimate_mb": 15},
        {"name": "yt-dlp",    "common_names": ["yt-dlp", "youtube-dl", "youtube downloader"], "category": "media", "size_estimate_mb": 10},
        {"name": "imagemagick","common_names": ["imagemagick", "convert", "image editing"], "category": "media", "size_estimate_mb": 30},
    ]


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

def main():
    print("\n🔧 VERNUX Data Build Pipeline — v0.1.0")
    print("=" * 50)

    stats = {"processed": 0, "skipped": 0, "errors": 0}

    # --- Seed patterns (hand-curated Phase 0 set) ---
    print("\n📋 Building patterns.json...")
    patterns = build_seed_patterns()
    write_patterns(patterns)
    stats["processed"] += len(patterns)

    # --- Seed package cache ---
    print("\n📦 Building pkg_cache.json...")
    packages = build_seed_pkg_cache()
    write_pkg_cache(packages)
    stats["processed"] += len(packages)

    # --- External source ingestion (only if sources/ exists) ---
    if SRC_DIR.exists():
        print(f"\n📥 Ingesting external sources from {SRC_DIR}...")

        # 101 Linux Commands → noob layer
        src = SRC_DIR / "101_linux_commands"
        raw = ingest_101_commands(src)
        entries = []
        for r in raw:
            entry = normalize_entry(r, "noob")
            ok, errs = validate_entry(entry) if entry else (False, ["None returned"])
            if ok:
                entries.append(entry)
                stats["processed"] += 1
            else:
                stats["skipped"] += 1
        if entries:
            write_layer("noob", entries, "101_commands.json")

        # Linux Command Library → learner layer
        src = SRC_DIR / "linux_cmdlib"
        raw = ingest_linux_cmdlib(src)
        entries = []
        for r in raw:
            entry = normalize_entry(r, "learner")
            ok, errs = validate_entry(entry) if entry else (False, ["None returned"])
            if ok:
                entries.append(entry)
                stats["processed"] += 1
            else:
                stats["skipped"] += 1
        if entries:
            write_layer("learner", entries, "linux_cmdlib.json")
    else:
        print(f"\n  ℹ  No external sources found at {SRC_DIR}")
        print("     To ingest external data: clone source repos into tools/sources/")
        print("     then re-run this script.")

    # --- Summary ---
    print("\n" + "=" * 50)
    print(f"✅ Build complete.")
    print(f"   Processed : {stats['processed']}")
    print(f"   Skipped   : {stats['skipped']}")
    print(f"   Errors    : {stats['errors']}")
    print()


if __name__ == "__main__":
    main()
