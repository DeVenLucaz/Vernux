# =============================================================================
# modules/packages.py — Package Intelligence
# Version: 0.3.0 | Phase 2 — Knowledge Base
# =============================================================================

import json
import os
import subprocess

PKG_CACHE_FILE = os.path.join(os.path.dirname(__file__), "../data/pkg_cache.json")

# ---------------------------------------------------------------------------
# Name resolution map — common/wrong name → real Termux package name
# ---------------------------------------------------------------------------
NAME_MAP = {
    # Python
    "python":       "python3",
    "py":           "python3",
    "py3":          "python3",
    "python2":      "python",     # Termux has python2 as 'python'

    # Node / JS
    "node":         "nodejs",
    "node.js":      "nodejs",
    "npm":          "nodejs",     # npm comes with nodejs

    # Editors
    "vi":           "vim",
    "neovim":       "neovim",
    "nvim":         "neovim",
    "emacs":        "emacs",
    "code":         None,         # VSCode not available in Termux

    # Media
    "ffmpeg4":      "ffmpeg",
    "ffmpeg5":      "ffmpeg",
    "youtube-dl":   "yt-dlp",    # youtube-dl deprecated, use yt-dlp
    "youtubedl":    "yt-dlp",
    "yt_dlp":       "yt-dlp",
    "imagemagick":  "imagemagick",
    "convert":      "imagemagick",
    "mogrify":      "imagemagick",

    # Compilers / build
    "gcc":          "clang",      # Termux uses clang, not gcc
    "g++":          "clang",
    "cc":           "clang",
    "c++":          "clang",
    "javac":        "openjdk-21",
    "java":         "openjdk-21",

    # Network
    "ncat":         "nmap",
    "nc":           "ncat",
    "netcat":       "ncat",
    "speedtest":    "speedtest-cli",

    # Database
    "mysql":        "mariadb",
    "mysqld":       "mariadb",
    "psql":         "postgresql",
    "postgres":     "postgresql",
    "mongo":        "mongodb",    # Note: may not be available
    "redis":        "redis",

    # Web servers
    "apache":       "apache2",
    "httpd":        "apache2",

    # Shell
    "zsh":          "zsh",
    "fish":         "fish",
    "bash":         "bash",       # Already installed

    # System tools
    "sudo":         "tsu",        # tsu is the Termux sudo equivalent
    "su":           "tsu",
    "htop":         "htop",
    "btop":         "btop",
    "screen":       "tmux",       # screen isn't in Termux, use tmux

    # Compression
    "7z":           "p7zip",
    "7zip":         "p7zip",
    "rar":          "unrar",
    "gzip":         "gzip",       # usually pre-installed
    "bzip2":        "bzip2",

    # Misc
    "git":          "git",
    "curl":         "curl",
    "wget":         "wget",
    "ssh":          "openssh",
    "sshd":         "openssh",
    "sftp":         "openssh",
    "rsync":        "rsync",
    "zip":          "zip",
    "unzip":        "unzip",
    "tar":          "tar",        # pre-installed
    "nano":         "nano",
    "tmux":         "tmux",
    "figlet":       "figlet",
    "cowsay":       "cowsay",
    "lolcat":       "lolcat",
    "toilet":       "toilet",
    "nmap":         "nmap",
    "termux-api":   "termux-api",
    "ping":         "inetutils",  # ping may need inetutils
}

# ---------------------------------------------------------------------------
# Lighter alternatives map
# ---------------------------------------------------------------------------
ALTERNATIVES = {
    "mariadb":    [{"name": "sqlite", "reason": "Lightweight DB, no server needed. Great for small projects."}],
    "postgresql": [{"name": "sqlite", "reason": "Simpler, file-based. No server setup required."}],
    "openjdk-21": [{"name": "openjdk-17", "reason": "Smaller footprint, still LTS."}],
    "rust":       [{"name": "clang", "reason": "C/C++ compiler, much smaller. Use Rust only if you specifically need it."}],
    "mongodb":    [{"name": "sqlite", "reason": "Much lighter. MongoDB needs ~500MB+ RAM."}],
    "apache2":    [{"name": "nginx", "reason": "Lower memory usage, simpler config for most use cases."}],
}

_PKG_CACHE = None


def _load_cache() -> dict:
    """Load pkg_cache.json into memory. Cached after first load."""
    global _PKG_CACHE
    if _PKG_CACHE is not None:
        return _PKG_CACHE

    path = os.path.abspath(PKG_CACHE_FILE)
    if not os.path.exists(path):
        _PKG_CACHE = {"packages": []}
        return _PKG_CACHE

    try:
        with open(path) as f:
            data = json.load(f)
        # Index by name for fast lookup
        _PKG_CACHE = {p["name"]: p for p in data.get("packages", [])}
    except Exception:
        _PKG_CACHE = {}

    return _PKG_CACHE


def resolve_name(common_name: str) -> tuple[str | None, bool]:
    """
    Resolve a common/wrong package name to the real Termux package name.
    Returns (real_name, was_remapped).
    Returns (None, False) if the package is known to be unavailable.
    """
    key = common_name.lower().strip()
    if key in NAME_MAP:
        real = NAME_MAP[key]
        was_remapped = (real != key)
        return real, was_remapped
    # No mapping needed — use as-is
    return common_name, False


def is_installed(pkg_name: str) -> bool:
    """Check if a package is currently installed."""
    try:
        result = subprocess.run(
            f"dpkg -l {pkg_name} 2>/dev/null | grep '^ii'",
            shell=True, capture_output=True, text=True, timeout=5
        )
        return bool(result.stdout.strip())
    except Exception:
        return False


def get_cache_entry(pkg_name: str) -> dict:
    """Get cached package metadata."""
    cache = _load_cache()
    return cache.get(pkg_name, {})


def get_size_estimate(pkg_name: str) -> str:
    """Return human-readable size estimate from cache."""
    entry = get_cache_entry(pkg_name)
    mb = entry.get("size_estimate_mb", 0)
    if mb == 0:
        return "unknown size"
    if mb >= 1000:
        return f"~{mb/1000:.1f} GB"
    return f"~{mb} MB"


def get_alternatives(pkg_name: str) -> list[dict]:
    """Return lighter alternatives for a package."""
    return ALTERNATIVES.get(pkg_name, [])


def get_install_advice(pkg_name: str, mode: str,
                       ram_gb: float = 4.0) -> dict:
    """
    Full pre-install intelligence check.

    Returns:
      {
        real_name:    str   — resolved Termux package name
        remapped:     bool  — was the name corrected?
        unavailable:  bool  — is this package unavailable in Termux?
        installed:    bool  — already installed?
        size:         str   — size estimate
        ram_warning:  str   — warning if RAM is too low (or empty)
        alternatives: list  — lighter alternatives
        install_cmd:  str   — the correct install command
      }
    """
    real_name, remapped = resolve_name(pkg_name)

    if real_name is None:
        return {
            "real_name": pkg_name, "remapped": False,
            "unavailable": True, "installed": False,
            "size": "", "ram_warning": "",
            "alternatives": [], "install_cmd": "",
        }

    installed  = is_installed(real_name)
    size       = get_size_estimate(real_name)
    alts       = get_alternatives(real_name)
    entry      = get_cache_entry(real_name)
    size_mb    = entry.get("size_estimate_mb", 0)

    # RAM warning for heavy packages on low-RAM devices
    ram_warning = ""
    HEAVY = {"mariadb": 1.0, "postgresql": 0.8, "openjdk-21": 0.5,
              "rust": 1.0, "clang": 0.5, "mongodb": 1.5}
    min_ram = HEAVY.get(real_name, 0)
    if min_ram and ram_gb < min_ram:
        ram_warning = (f"{real_name} needs ~{min_ram:.0f}GB RAM to run well. "
                       f"Your device has {ram_gb:.1f}GB available.")

    return {
        "real_name":    real_name,
        "remapped":     remapped,
        "unavailable":  False,
        "installed":    installed,
        "size":         size,
        "ram_warning":  ram_warning,
        "alternatives": alts,
        "install_cmd":  f"pkg install {real_name} -y",
    }


def format_install_advice(advice: dict, mode: str) -> str:
    """Format install advice into a user-facing message."""
    lines = []

    if advice["unavailable"]:
        return f"  ✗  '{advice['real_name']}' isn't available in Termux."

    if advice["remapped"]:
        if mode == "noob":
            lines.append(f"  ℹ  In Termux, that's called '{advice['real_name']}'.")
        elif mode == "learner":
            lines.append(f"  ℹ  Package name corrected: → '{advice['real_name']}'")
        # pro: silent remap

    if advice["installed"]:
        if mode == "noob":
            lines.append(f"  ✔  Already installed! You're good to go.")
        elif mode == "learner":
            lines.append(f"  ✔  '{advice['real_name']}' is already installed.")
        # pro: silent

    if advice["ram_warning"] and mode != "pro":
        lines.append(f"  ⚠  {advice['ram_warning']}")

    if advice["alternatives"] and mode != "pro":
        alt = advice["alternatives"][0]
        lines.append(f"  💡 Lighter alternative: {alt['name']} — {alt['reason']}")

    return "\n".join(lines)
