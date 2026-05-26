# =============================================================================
# modules/reality_bridge.py — Reality Gap Scenarios & Android Quirks
# Version: 0.3.0 | Phase 2 — Knowledge Base
# =============================================================================

import json
import os
import re

SCENARIOS_DIR = os.path.join(os.path.dirname(__file__),
                             "../data/universal/reality_bridge")

# ---------------------------------------------------------------------------
# Built-in scenario registry
# All scenarios inline + JSON files from scenarios dir both supported
# ---------------------------------------------------------------------------

SCENARIOS = {

    # ── Storage ─────────────────────────────────────────────────────────────
    "storage_permission": {
        "triggers": ["permission denied sdcard", "cannot access sdcard",
                     "sdcard not found", "no access to storage",
                     "storage not accessible", "cant access phone files",
                     "sdcard empty", "/sdcard permission"],
        "category": "storage",
        "noob": (
            "Termux can't see your phone's files until you give it permission.\n\n"
            "  Fix: run this command and tap Allow when the popup appears:\n"
            "  $ termux-setup-storage\n\n"
            "  After that, your phone files are in ~/storage/downloads/"
        ),
        "learner": (
            "Termux is sandboxed — it can't access /sdcard/ without Android storage permission.\n\n"
            "  Run: termux-setup-storage\n"
            "  Accept the popup. This creates ~/storage/ symlinks:\n"
            "    ~/storage/downloads  →  your Downloads folder\n"
            "    ~/storage/dcim       →  your Camera roll\n"
            "    ~/storage/shared     →  /sdcard/ root\n\n"
            "  After setup, copy files: cp myfile.txt ~/storage/downloads/"
        ),
        "pro": (
            "Run termux-setup-storage. Creates ~/storage symlinks to Android dirs.\n"
            "Or: cp file /sdcard/Download/ directly after permission granted."
        ),
        "auto_check": "storage_permission",
        "brand_notes": {
            "xiaomi":  "MIUI may revoke storage after MIUI optimization — disable it in Developer Settings.",
            "oppo":    "ColorOS: manually grant storage in App Info → Permissions → Files and Media.",
            "vivo":    "VivoUI: may need to manually allow storage in Settings → Apps → Termux.",
        }
    },

    "termux_home_vs_sdcard": {
        "triggers": ["where is my file", "file not found after download",
                     "file disappeared", "downloaded but cant find",
                     "where did file go", "file saved where"],
        "category": "storage",
        "noob": (
            "Termux has its own private home folder (~) that Android's Files app can't see.\n\n"
            "  Where things are:\n"
            "    ~ (home)              → Only Termux can see this\n"
            "    ~/storage/downloads  → Your normal Downloads folder\n"
            "    /sdcard/Download/    → Same Downloads folder\n\n"
            "  To move a file to where your phone can find it:\n"
            "  $ cp myfile.txt ~/storage/downloads/"
        ),
        "learner": (
            "Termux home (~) is at /data/data/com.termux/files/home — invisible to Android.\n"
            "Files saved there won't appear in your Files app.\n\n"
            "  To make files accessible to Android:\n"
            "  $ cp file.txt /sdcard/Download/\n"
            "  Or share directly: termux-share myfile.txt"
        ),
        "pro": (
            "~ = /data/data/com.termux/files/home — not visible to Android.\n"
            "cp to /sdcard/ or termux-share to expose files."
        ),
    },

    # ── Git / GitHub ─────────────────────────────────────────────────────────
    "git_auth_failed": {
        "triggers": ["authentication failed git", "git push password wrong",
                     "git credentials", "github login failed",
                     "support for password authentication was removed",
                     "remote: invalid username or password"],
        "category": "git",
        "noob": (
            "GitHub stopped accepting your account password for git push in 2021.\n\n"
            "  You need a Personal Access Token instead. Here's how:\n"
            "  1. Go to github.com → click your profile picture → Settings\n"
            "  2. Scroll down to 'Developer settings' → Personal access tokens → Tokens (classic)\n"
            "  3. Click 'Generate new token (classic)'\n"
            "  4. Tick the 'repo' checkbox → Generate token → copy it\n\n"
            "  Then set it up in Termux so you never type it again:\n"
            "  $ git remote set-url origin https://YOUR_USERNAME:YOUR_TOKEN@github.com/user/repo.git"
        ),
        "learner": (
            "GitHub removed password auth for git operations in August 2021.\n"
            "Use a Personal Access Token (PAT) or SSH key instead.\n\n"
            "  PAT method (easier):\n"
            "  $ git remote set-url origin https://user:TOKEN@github.com/user/repo.git\n\n"
            "  SSH method (better long-term):\n"
            "  $ ssh-keygen -t ed25519 -C 'your@email.com'\n"
            "  $ cat ~/.ssh/id_ed25519.pub\n"
            "  Add the output to GitHub → Settings → SSH Keys"
        ),
        "pro": (
            "GitHub removed password auth 2021-08-13.\n"
            "PAT: git remote set-url origin https://user:token@github.com/user/repo.git\n"
            "SSH: ssh-keygen -t ed25519 && add pubkey to GitHub."
        ),
    },

    "git_not_initialized": {
        "triggers": ["not a git repository", "fatal not a git repo",
                     "git init first", "git command failed not repo"],
        "category": "git",
        "noob": (
            "This folder isn't set up as a Git project yet.\n\n"
            "  To fix it, run:\n"
            "  $ git init\n\n"
            "  Or if you want to download an existing project from GitHub:\n"
            "  $ git clone https://github.com/username/reponame.git"
        ),
        "learner": (
            "No .git/ folder found in the current directory or its parents.\n\n"
            "  Start a new repo here:\n"
            "  $ git init\n\n"
            "  Or clone an existing one:\n"
            "  $ git clone https://github.com/user/repo.git"
        ),
        "pro": "git init or git clone url. Check cwd with pwd.",
    },

    "git_config_missing": {
        "triggers": ["please tell me who you are", "git config user",
                     "git commit failed identity", "git user email not set"],
        "category": "git",
        "noob": (
            "Git doesn't know your name yet. Run these two commands:\n\n"
            '  $ git config --global user.name "Your Name"\n'
            '  $ git config --global user.email "your@email.com"\n\n'
            "  Use the same email as your GitHub account."
        ),
        "learner": (
            "Git requires user.name and user.email before making commits.\n\n"
            '  $ git config --global user.name "Your Name"\n'
            '  $ git config --global user.email "your@email.com"\n\n'
            "  --global sets it for all repos. Per-repo: omit --global."
        ),
        "pro": (
            "git config --global user.name/user.email not set.\n"
            "git config --global user.name 'name' && git config --global user.email 'email'"
        ),
    },

    "git_single_file_download": {
        "triggers": ["download single file github", "download one file from github",
                     "get raw file github", "github raw download",
                     "download file without cloning"],
        "category": "git",
        "noob": (
            "You don't need to clone the whole project to get one file.\n\n"
            "  1. Go to the file on GitHub in your browser\n"
            "  2. Click the 'Raw' button\n"
            "  3. Copy that URL, then run:\n"
            "  $ wget https://raw.githubusercontent.com/user/repo/main/filename\n\n"
            "  Or use the GitHub API:\n"
            "  $ curl -O https://raw.githubusercontent.com/user/repo/main/filename"
        ),
        "learner": (
            "Use the raw GitHub URL to download a single file:\n\n"
            "  $ wget https://raw.githubusercontent.com/USER/REPO/BRANCH/PATH/FILE\n\n"
            "  Or via curl:\n"
            "  $ curl -O https://raw.githubusercontent.com/USER/REPO/main/file.py"
        ),
        "pro": "wget/curl raw.githubusercontent.com/user/repo/branch/file.",
    },

    # ── Package names ────────────────────────────────────────────────────────
    "package_name_wrong": {
        "triggers": ["package not found", "unable to locate package",
                     "no installation candidate", "package does not exist",
                     "pkg install failed"],
        "category": "packages",
        "noob": (
            "Termux uses different package names from regular Linux.\n\n"
            "  Common fixes:\n"
            "    python  → python3\n"
            "    node    → nodejs\n"
            "    gcc     → clang\n"
            "    mysql   → mariadb\n"
            "    sudo    → tsu\n"
            "    screen  → tmux\n\n"
            "  To search for the right name:\n"
            "  $ pkg search keyword"
        ),
        "learner": (
            "Termux package names differ from Debian/Ubuntu. Key differences:\n\n"
            "  python  → python3      gcc     → clang\n"
            "  node    → nodejs       mysql   → mariadb\n"
            "  sudo    → tsu          screen  → tmux\n"
            "  youtube-dl → yt-dlp   ffmpeg4 → ffmpeg\n\n"
            "  Search: pkg search <keyword>\n"
            "  Update list first: pkg update"
        ),
        "pro": (
            "pkg search. Key: python3, nodejs, clang, mariadb, tsu, yt-dlp.\n"
            "pkg update first if package list is stale."
        ),
    },

    "gui_app_wont_work": {
        "triggers": ["gui app wont work", "display not found",
                     "cannot open display", "no display available",
                     "gtk error", "qt error", "x11 error",
                     "graphical app termux"],
        "category": "packages",
        "noob": (
            "Termux is a text-only terminal — it can't run apps with windows or buttons directly.\n\n"
            "  Options:\n"
            "  • Use the text-based version of the tool if available\n"
            "  • Install Termux:X11 from F-Droid for limited GUI support\n"
            "  • For Android GUI apps, install them normally from Play Store"
        ),
        "learner": (
            "Termux has no display server by default — GUI apps fail with 'no display'.\n\n"
            "  Options:\n"
            "  1. Termux:X11 — X11 display server for Termux (F-Droid)\n"
            "     $ pkg install x11-repo\n"
            "     $ pkg install termux-x11-nightly\n"
            "  2. VNC server (pkg install tigervnc)\n"
            "  3. Use CLI alternatives (htop instead of GUI task manager, etc.)"
        ),
        "pro": (
            "No display. Options: Termux:X11 (pkg install x11-repo then termux-x11-nightly),\n"
            "VNC (pkg install tigervnc), or proot-distro for full Linux."
        ),
    },

    # ── Navigation ───────────────────────────────────────────────────────────
    "frozen_terminal": {
        "triggers": ["terminal frozen", "terminal stuck", "ctrl c not working",
                     "termux not responding", "terminal hangs",
                     "command wont stop"],
        "category": "navigation",
        "noob": (
            "Your terminal is stuck. Try these in order:\n\n"
            "  1. Press Ctrl+C  (stops most running commands)\n"
            "  2. Press Ctrl+Z  (pauses the command)\n"
            "  3. Press q       (exits some programs like less, top, man)\n"
            "  4. Type 'exit'   (closes the current shell)\n"
            "  5. Swipe to close Termux and reopen it (fresh session)"
        ),
        "learner": (
            "Common interrupt keys:\n"
            "  Ctrl+C = SIGINT (stops most commands)\n"
            "  Ctrl+Z = SIGTSTP (pauses, use fg to resume or kill %1)\n"
            "  q      = quit (less, top, htop, man)\n"
            "  :q!    = force quit (vim)\n"
            "  Ctrl+D = EOF (exits python, shells)\n\n"
            "If completely frozen: swipe Termux notification → close."
        ),
        "pro": "Ctrl+C/Z/D. q for pagers. :q! for vim. kill $(pgrep name) from another session.",
    },

    "run_a_script": {
        "triggers": ["how to run script",
        "how do i run a bash script",
        "run bash script",
        "how to execute script", "bash script wont run",
                     "permission denied script", "cannot execute script",
                     "run sh file", "execute bash file", "./script not working"],
        "category": "navigation",
        "noob": (
            "To run a script, you first need to give it permission to run:\n\n"
            "  $ chmod +x myscript.sh\n"
            "  $ ./myscript.sh\n\n"
            "  The ./ at the start means 'this folder'. Don't forget it."
        ),
        "learner": (
            "Scripts need execute permission before they can run.\n\n"
            "  $ chmod +x script.sh    # add execute permission\n"
            "  $ ./script.sh           # run from current dir\n\n"
            "  Or without chmod:\n"
            "  $ bash script.sh        # explicitly call bash\n"
            "  $ python3 script.py     # for Python scripts"
        ),
        "pro": "chmod +x then ./script. Or bash/python3 script directly.",
    },

    # ── Android quirks ───────────────────────────────────────────────────────
    "battery_optimization": {
        "triggers": ["termux killed", "termux stops when screen off",
        "termux stops when screen turns off",
        "screen turns off termux dies",
                     "long command stopped", "download cancelled screen off",
                     "process killed background", "termux closed itself",
                     "background process died"],
        "category": "android",
        "noob": (
            "Android is killing Termux to save battery when your screen turns off.\n\n"
            "  Fix 1 — Disable battery optimization for Termux:\n"
            "  Settings → Apps → Termux → Battery → Unrestricted\n\n"
            "  Fix 2 — Keep wake lock while running long commands:\n"
            "  $ termux-wake-lock\n\n"
            "  Fix 3 — Use tmux so your session survives Termux being closed:\n"
            "  $ pkg install tmux\n"
            "  $ tmux\n"
            "  (then Ctrl+B, D to detach safely)"
        ),
        "learner": (
            "Android aggressively kills background processes to save battery.\n\n"
            "  Solutions:\n"
            "  1. Battery: Settings → Apps → Termux → Battery → Unrestricted (No restrictions)\n"
            "  2. Wake lock: termux-wake-lock (keeps CPU active)\n"
            "  3. tmux: survives Termux being swiped away\n"
            "  4. Termux notification: keep it visible (Android is less likely to kill visible apps)"
        ),
        "pro": (
            "Disable battery optimization + termux-wake-lock + tmux.\n"
            "Notification visibility also helps on aggressive OEMs."
        ),
        "brand_notes": {
            "xiaomi":  "MIUI: Settings → Battery & performance → App battery saver → Termux → No restrictions. Also: Settings → Developer options → Disable MIUI optimization.",
            "oppo":    "ColorOS: Settings → Battery → Battery Optimization → All apps → Termux → Don't optimize.",
            "vivo":    "VivoUI: i Manager → Battery → High background power consumption → Termux → Allow.",
            "realme":  "Realme UI: Settings → Battery → Battery Optimization → Termux → Don't optimize.",
            "samsung": "OneUI: Settings → Apps → Termux → Battery → Unrestricted. Also disable Adaptive battery.",
        }
    },

    "termux_wake_lock_how": {
        "triggers": ["how to use tmux", "tmux keep running",
                     "keep command running", "run in background",
                     "detach session", "long running command background"],
        "category": "android",
        "noob": (
            "To keep a command running even when you close Termux:\n\n"
            "  1. Install tmux:\n"
            "     $ pkg install tmux\n\n"
            "  2. Start a tmux session:\n"
            "     $ tmux\n\n"
            "  3. Run your long command inside tmux\n\n"
            "  4. Detach safely (command keeps running):\n"
            "     Press Ctrl+B, then press D\n\n"
            "  5. Come back later:\n"
            "     $ tmux attach"
        ),
        "learner": (
            "tmux basics:\n"
            "  $ tmux               # new session\n"
            "  $ tmux new -s work   # named session\n"
            "  Ctrl+B d             # detach (session keeps running)\n"
            "  $ tmux attach        # reattach\n"
            "  $ tmux ls            # list sessions\n\n"
            "  Pane splitting:\n"
            "  Ctrl+B %             # split vertical\n"
            "  Ctrl+B \"             # split horizontal\n"
            "  Ctrl+B arrow         # move between panes"
        ),
        "pro": (
            "tmux new -s name. Ctrl+B d to detach. tmux attach -t name.\n"
            "Ctrl+B %/\" split. Ctrl+B x kill pane."
        ),
    },

    # ── Brand-specific ───────────────────────────────────────────────────────
    "miui_storage_bug": {
        "triggers": ["miui storage", "xiaomi storage termux",
                     "termux storage xiaomi", "miui optimization termux"],
        "category": "brands",
        "noob": (
            "Xiaomi's MIUI has a known bug with Termux storage.\n\n"
            "  Fix:\n"
            "  1. Go to Settings → Additional Settings → Developer Options\n"
            "  2. Turn off 'MIUI optimization'\n"
            "  3. Restart your phone\n"
            "  4. Run termux-setup-storage again in Termux"
        ),
        "learner": (
            "MIUI optimization interferes with Termux storage permission.\n\n"
            "  Fix:\n"
            "  Settings → Additional Settings → Developer Options → Disable MIUI optimization → Reboot\n"
            "  Then: termux-setup-storage"
        ),
        "pro": "Developer options → disable MIUI optimization → reboot → termux-setup-storage.",
        "brand_notes": {"xiaomi": "This is a MIUI-specific bug. MIUI 12+ especially affected."},
    },

    "oppo_storage_bug": {
        "triggers": ["oppo storage", "coloros storage termux", "oppo termux permission",
                     "realme storage termux"],
        "category": "brands",
        "noob": (
            "On OPPO/Realme phones, you need to manually grant storage permission.\n\n"
            "  Fix:\n"
            "  1. Settings → Apps → See all apps → Termux\n"
            "  2. Tap Permissions → Files and Media\n"
            "  3. Select 'Allow access to media only' or 'Allow all'\n"
            "  4. Run termux-setup-storage in Termux"
        ),
        "learner": (
            "ColorOS/Realme UI restricts storage differently from stock Android.\n\n"
            "  Settings → Apps → Termux → Permissions → Files and Media → Allow\n"
            "  Then: termux-setup-storage"
        ),
        "pro": "Settings → Apps → Termux → Permissions → Files → Allow. Then termux-setup-storage.",
        "brand_notes": {"oppo": "ColorOS 11+ requires manual permission grant.", "realme": "Realme UI same as ColorOS."},
    },
}


# ---------------------------------------------------------------------------
# Matching logic
# ---------------------------------------------------------------------------

def _load_json_scenarios() -> dict:
    """Load additional scenario JSON files from the scenarios directory."""
    extra = {}
    if not os.path.exists(SCENARIOS_DIR):
        return extra
    for f in os.listdir(SCENARIOS_DIR):
        if f.endswith(".json"):
            try:
                with open(os.path.join(SCENARIOS_DIR, f)) as fp:
                    data = json.load(fp)
                    if isinstance(data, dict):
                        extra.update(data)
            except Exception:
                continue
    return extra


def _all_scenarios() -> dict:
    """Return merged built-in + JSON scenarios."""
    merged = dict(SCENARIOS)
    merged.update(_load_json_scenarios())
    return merged


def match_scenario(user_input: str, context: dict = None) -> dict | None:
    """
    Match user input / error to a reality gap scenario.
    Returns the scenario dict or None.
    """
    text     = user_input.lower()
    all_scen = _all_scenarios()

    best      = None
    best_score = 0

    for scen_id, scen in all_scen.items():
        triggers = scen.get("triggers", [])
        for trigger in triggers:
            if trigger in text:
                # Longer trigger = more specific = better match
                score = len(trigger)
                if score > best_score:
                    best_score = score
                    best = scen

    return best


def get_response(scenario: dict, mode: str, brand: str = "") -> str:
    """
    Format scenario response for the given mode and device brand.
    """
    text = scenario.get(mode, scenario.get("learner", ""))

    # Append brand-specific note if available
    brand_notes = scenario.get("brand_notes", {})
    brand_key   = brand.lower()
    if brand_key in brand_notes:
        text += f"\n\n  📱 {brand.capitalize()} note: {brand_notes[brand_key]}"

    return text


def explain_scenario(user_input: str, mode: str, brand: str = "") -> str | None:
    """
    Top-level function: match scenario and return formatted response.
    Returns None if no scenario matched.
    """
    scenario = match_scenario(user_input)
    if scenario is None:
        return None
    return get_response(scenario, mode, brand)
