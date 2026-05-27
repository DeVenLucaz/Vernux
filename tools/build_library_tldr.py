# =============================================================================
# tools/build_library_tldr.py — tldr-pages → VERNUX library builder
# Version: 0.1.0 | Phase 6 — Database Expansion
# =============================================================================
#
# Fetches tldr-pages (CC0 public domain) and converts them into VERNUX's
# offline library format, merging with the existing data/library.json.
#
# tldr-pages covers 600+ commands with plain English descriptions and
# real usage examples. This fills gaps that LinuxCommandLibrary misses.
#
# Usage:
#   python tools/build_library_tldr.py               # full build, merge
#   python tools/build_library_tldr.py --overwrite    # replace, don't merge
#   python tools/build_library_tldr.py --cmd grep     # test single command
#   python tools/build_library_tldr.py --quick        # android+common only
#
# Data source:  https://github.com/tldr-pages/tldr
# License:      Creative Commons CC0 1.0 Universal (public domain)
# Credits:      tldr-pages contributors — https://github.com/tldr-pages/tldr/graphs/contributors
# =============================================================================

import json
import os
import sys
import re
import io
import zipfile
import argparse
import urllib.request
import urllib.error
from pathlib import Path

ROOT     = Path(__file__).parent.parent
DATA_DIR = ROOT / "data"
OUT_FILE = DATA_DIR / "library.json"

TLDR_ZIP_URL = "https://github.com/tldr-pages/tldr/releases/latest/download/tldr.zip"

# Platforms in priority order — android wins over linux wins over common
TLDR_PLATFORMS = ["android", "linux", "common"]

# ---------------------------------------------------------------------------
# Termux-relevant command list — same as build_patterns_db.py for consistency
# ---------------------------------------------------------------------------

TERMUX_COMMANDS = {
    # Navigation & files
    "ls", "cd", "pwd", "mkdir", "rm", "cp", "mv", "cat", "less", "more",
    "touch", "find", "locate", "file", "stat", "tree", "ln", "realpath",
    "basename", "dirname", "readlink", "chmod", "chown", "chgrp", "umask",
    # Text processing
    "grep", "sed", "awk", "cut", "sort", "uniq", "wc", "head", "tail",
    "tr", "diff", "patch", "xargs", "tee", "column", "fmt", "fold",
    "jq", "yq", "base64", "md5sum", "sha256sum", "xxd", "hexdump",
    "strings", "od", "split", "csplit",
    # Archives
    "zip", "unzip", "tar", "gzip", "gunzip", "bzip2", "xz", "7z",
    # Network
    "curl", "wget", "ssh", "scp", "rsync", "ping", "nmap", "netstat",
    "ifconfig", "ip", "nc", "telnet", "dig", "nslookup", "host",
    "traceroute", "whois",
    # Packages
    "pkg", "apt", "pip", "pip3", "npm", "gem", "cargo", "go",
    # Git
    "git", "git-clone", "git-commit", "git-push", "git-pull",
    "git-checkout", "git-branch", "git-log", "git-status", "git-diff",
    "git-merge", "git-rebase", "git-stash", "git-reset", "git-add",
    "git-init", "git-remote", "git-fetch", "git-tag",
    # Processes
    "ps", "kill", "pkill", "top", "htop", "nice", "renice", "jobs",
    "fg", "bg", "nohup", "screen", "tmux", "watch",
    "cron", "crontab", "at",
    # System info
    "df", "du", "free", "uname", "uptime", "date", "cal", "who",
    "whoami", "id", "hostname", "lscpu", "lsof", "lsblk",
    "sudo", "su", "tsu",
    # Editors
    "nano", "vim", "vi", "emacs", "micro", "nvim",
    # Shell
    "bash", "sh", "zsh", "fish", "echo", "printf", "read", "export",
    "source", "alias", "unalias", "history", "clear", "reset", "env",
    "set", "unset", "declare", "eval", "exec", "exit", "sleep", "wait",
    "test", "expr", "bc", "dc",
    # Dev tools
    "python3", "python", "node", "ruby", "perl", "php", "java",
    "gcc", "clang", "make", "cmake", "ninja",
    "ffmpeg", "ffprobe", "convert", "imagemagick",
    "sqlite3", "mysql", "redis-cli",
    "docker", "kubectl",
    "ssh-keygen", "ssh-copy-id", "ssh-agent", "ssh-add",
    "gpg", "openssl",
    # Termux-specific
    "termux-setup-storage", "termux-wake-lock", "termux-wake-unlock",
    "termux-share", "termux-clipboard-get", "termux-clipboard-set",
    "termux-notification", "termux-open", "termux-open-url",
    "termux-battery-status", "termux-info",
    # Modern utils
    "fzf", "rg", "ripgrep", "fd", "bat", "tldr", "man", "info",
    "whatis", "apropos", "strace", "ltrace", "ldd",
    "http", "httpie",
}

# Category mapping
CATEGORIES = {
    "files":     {"ls","cd","pwd","mkdir","rm","cp","mv","cat","less","more",
                  "touch","find","locate","file","stat","tree","ln","realpath",
                  "basename","dirname","readlink","chmod","chown","chgrp","umask"},
    "text":      {"grep","sed","awk","cut","sort","uniq","wc","head","tail",
                  "tr","diff","patch","xargs","tee","column","fmt","fold",
                  "jq","yq","base64","md5sum","sha256sum","xxd","hexdump",
                  "strings","od","split","csplit"},
    "archives":  {"zip","unzip","tar","gzip","gunzip","bzip2","xz","7z"},
    "network":   {"curl","wget","ssh","scp","rsync","ping","nmap","netstat",
                  "ifconfig","ip","nc","telnet","dig","nslookup","host",
                  "traceroute","whois","http","httpie"},
    "packages":  {"pkg","apt","pip","pip3","npm","gem","cargo","go"},
    "git":       {"git","git-clone","git-commit","git-push","git-pull",
                  "git-checkout","git-branch","git-log","git-status","git-diff",
                  "git-merge","git-rebase","git-stash","git-reset","git-add",
                  "git-init","git-remote","git-fetch","git-tag"},
    "processes": {"ps","kill","pkill","top","htop","nice","renice","jobs",
                  "fg","bg","nohup","screen","tmux","watch","cron","crontab","at"},
    "system":    {"df","du","free","uname","uptime","date","cal","who",
                  "whoami","id","hostname","lscpu","lsof","lsblk","sudo","su","tsu"},
    "editors":   {"nano","vim","vi","emacs","micro","nvim"},
    "shell":     {"bash","sh","zsh","fish","echo","printf","read","export",
                  "source","alias","unalias","history","clear","reset","env",
                  "set","unset","declare","eval","exec","exit","sleep","wait",
                  "test","expr","bc","dc"},
    "dev":       {"python3","python","node","ruby","perl","php","java",
                  "gcc","clang","make","cmake","ninja","ffmpeg","ffprobe",
                  "convert","sqlite3","mysql","redis-cli","docker","kubectl",
                  "ssh-keygen","ssh-copy-id","gpg","openssl"},
    "termux":    {"termux-setup-storage","termux-wake-lock","termux-wake-unlock",
                  "termux-share","termux-clipboard-get","termux-clipboard-set",
                  "termux-notification","termux-open","termux-open-url",
                  "termux-battery-status","termux-info"},
    "utils":     {"fzf","rg","ripgrep","fd","bat","tldr","man","info",
                  "whatis","apropos","strace","ltrace","ldd"},
}


def _get_category(cmd: str) -> str:
    base = cmd.split("-")[0]  # git-checkout → git
    for cat, cmds in CATEGORIES.items():
        if cmd in cmds or base in cmds:
            return cat
    return "other"


# ---------------------------------------------------------------------------
# tldr markdown parser
# ---------------------------------------------------------------------------

def _parse_tldr_md(content: str, cmd_name: str) -> dict | None:
    """
    Parse a tldr markdown page.

    Format:
      # command
      > Short description.
      > More information: url
      - Example description:
        `the actual command`
    """
    lines       = content.splitlines()
    description = ""
    more_url    = ""
    examples    = []   # list of (desc_str, cmd_str)
    current_ex  = None

    for line in lines:
        line = line.rstrip()

        if line.startswith("> "):
            text = line[2:].strip()
            if text.lower().startswith("more information"):
                # Extract URL
                m = re.search(r'https?://\S+', text)
                if m:
                    more_url = m.group(0).rstrip(">.")
            elif not description:
                description = text

        elif line.startswith("- "):
            current_ex = line[2:].rstrip(":").strip()

        elif line.strip().startswith("`") and line.strip().endswith("`") and current_ex:
            raw_cmd = line.strip()[1:-1].strip()
            # Replace {{placeholder}} with <arg>
            clean_cmd = re.sub(r'\{\{[^}]+\}\}', '<arg>', raw_cmd)
            examples.append((current_ex, clean_cmd))
            current_ex = None

    if not description and not examples:
        return None

    return {
        "name":        cmd_name,
        "description": description,
        "examples":    examples[:8],
        "more_url":    more_url,
    }


# ---------------------------------------------------------------------------
# Mode-aware text builder
# ---------------------------------------------------------------------------

def _build_noob(parsed: dict) -> str:
    """Plain English explanation for beginners."""
    desc = parsed["description"]
    lines = [desc]
    if parsed["examples"]:
        ex_desc, ex_cmd = parsed["examples"][0]
        lines.append(f"\nFor example, to {ex_desc.lower().rstrip('.')}:")
        lines.append(f"  {ex_cmd}")
    return "\n".join(lines)


def _build_learner(parsed: dict) -> str:
    """Description + up to 3 examples with context."""
    desc = parsed["description"]
    lines = [desc]
    if parsed["examples"]:
        lines.append("\nExamples:")
        for ex_desc, ex_cmd in parsed["examples"][:3]:
            lines.append(f"  # {ex_desc}")
            lines.append(f"  {ex_cmd}")
    return "\n".join(lines)


def _build_pro(parsed: dict) -> str:
    """One-line summary only."""
    return parsed["description"]


# ---------------------------------------------------------------------------
# Download + convert
# ---------------------------------------------------------------------------

def download_tldr_zip(quiet: bool = False) -> bytes | None:
    """Download the tldr-pages zip. Returns raw bytes or None."""
    if not quiet:
        print("  Downloading tldr-pages zip (~5MB)...")
    try:
        req = urllib.request.Request(
            TLDR_ZIP_URL,
            headers={"User-Agent": "Vernux/0.7.5 (library builder; https://github.com/DeVenLucaz/Vernux)"}
        )
        with urllib.request.urlopen(req, timeout=60) as r:
            data = r.read()
        if not quiet:
            print(f"  Downloaded: {len(data) // 1024}KB")
        return data
    except Exception as e:
        print(f"  ✗ Download failed: {e}")
        return None


def build_library_from_tldr(zip_bytes: bytes, quick: bool = False, quiet: bool = False) -> dict:
    """
    Parse the tldr zip and build a library dict in VERNUX format.
    quick=True uses android+common only (smaller, faster).
    """
    try:
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    except Exception as e:
        print(f"  ✗ Could not open zip: {e}")
        return {}

    platforms = ["android", "common"] if quick else TLDR_PLATFORMS

    # Index pages — android wins over linux wins over common
    cmd_pages: dict[str, tuple[str, str]] = {}  # cmd → (content, platform)
    for platform in reversed(platforms):
        prefix = f"pages/{platform}/"
        for name in zf.namelist():
            if name.startswith(prefix) and name.endswith(".md"):
                cmd_name = Path(name).stem
                try:
                    content = zf.read(name).decode("utf-8", errors="replace")
                    cmd_pages[cmd_name] = (content, platform)
                except Exception:
                    pass

    if not quiet:
        print(f"  Pages found ({', '.join(platforms)}): {len(cmd_pages)}")

    # Filter to Termux-relevant
    relevant = {
        cmd: (content, plat)
        for cmd, (content, plat) in cmd_pages.items()
        if cmd in TERMUX_COMMANDS or cmd.split("-")[0] in TERMUX_COMMANDS
    }

    if not quiet:
        print(f"  Termux-relevant: {len(relevant)}")

    library = {}
    for cmd_name, (content, platform) in sorted(relevant.items()):
        parsed = _parse_tldr_md(content, cmd_name)
        if not parsed:
            continue

        entry = {
            "name":        cmd_name,
            "synopsis":    cmd_name,
            "description": parsed["description"],
            "short":       parsed["description"][:120],
            "noob":        _build_noob(parsed),
            "learner":     _build_learner(parsed),
            "pro":         _build_pro(parsed),
            "examples":    [cmd for _, cmd in parsed["examples"]],
            "category":    _get_category(cmd_name),
            "source":      "tldr-pages",
            "platform":    platform,
        }
        if parsed.get("more_url"):
            entry["more_url"] = parsed["more_url"]

        library[cmd_name] = entry

    if not quiet:
        print(f"  Converted: {len(library)} entries")

    return library


# ---------------------------------------------------------------------------
# Merge logic
# ---------------------------------------------------------------------------

def merge_into_library(tldr_data: dict, existing_path: Path, overwrite: bool = False) -> dict:
    """
    Merge tldr data into existing library.json.

    Priority:
      - If overwrite=False: existing entries WIN (LCL data is richer, keep it)
    - New tldr entries fill gaps where LCL has nothing
    - If overwrite=True: tldr entries overwrite existing ones
    """
    existing = {}
    meta     = {}

    if existing_path.exists():
        try:
            with open(existing_path) as f:
                raw = json.load(f)
            existing = raw.get("commands", {})
            meta     = raw.get("meta", {})
        except Exception:
            pass

    if overwrite:
        merged = {**existing, **tldr_data}
    else:
        # tldr fills gaps only
        merged = {**tldr_data, **existing}

    # Update meta
    meta.update({
        "command_count":   len(merged),
        "tldr_entries":    len(tldr_data),
        "lcl_entries":     len(existing),
        "sources":         ["LinuxCommandLibrary (Apache 2.0)", "tldr-pages (CC0 1.0)"],
        "tldr_credits":    "https://github.com/tldr-pages/tldr — CC0 1.0 Universal",
        "lcl_credits":     "https://github.com/SimonSchubert/LinuxCommandLibrary — Apache 2.0",
        "build_note":      "Built by Vernux tools/build_library_tldr.py + tools/fetch_library.py",
    })

    return {"meta": meta, "commands": merged}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(
        description="Build/update data/library.json from tldr-pages (CC0)"
    )
    ap.add_argument("--overwrite", action="store_true",
                    help="Overwrite existing entries (default: fill gaps only)")
    ap.add_argument("--quick",     action="store_true",
                    help="Android + common platforms only (faster, smaller)")
    ap.add_argument("--quiet",     action="store_true",
                    help="Suppress progress output")
    ap.add_argument("--cmd",       type=str, default=None,
                    help="Test parse a single command name")
    args = ap.parse_args()

    print("\n  VERNUX — tldr-pages Library Builder")
    print("  Source: tldr-pages (CC0 1.0) — github.com/tldr-pages/tldr\n")

    zip_bytes = download_tldr_zip(quiet=args.quiet)
    if not zip_bytes:
        sys.exit(1)

    # Single command test mode
    if args.cmd:
        try:
            zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
        except Exception as e:
            print(f"  ✗ {e}")
            sys.exit(1)
        for platform in TLDR_PLATFORMS:
            name = f"pages/{platform}/{args.cmd}.md"
            if name in zf.namelist():
                content = zf.read(name).decode("utf-8", errors="replace")
                parsed  = _parse_tldr_md(content, args.cmd)
                if parsed:
                    entry = {
                        "noob":    _build_noob(parsed),
                        "learner": _build_learner(parsed),
                        "pro":     _build_pro(parsed),
                    }
                    print(json.dumps(entry, indent=2))
                    return
        print(f"  '{args.cmd}' not found in tldr-pages")
        return

    tldr_data = build_library_from_tldr(zip_bytes, quick=args.quick, quiet=args.quiet)

    if not tldr_data:
        print("  ✗ No data built. Exiting.")
        sys.exit(1)

    result = merge_into_library(tldr_data, OUT_FILE, overwrite=args.overwrite)

    DATA_DIR.mkdir(exist_ok=True)
    with open(OUT_FILE, "w") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    total = result["meta"]["command_count"]
    tldr  = result["meta"].get("tldr_entries", 0)
    lcl   = result["meta"].get("lcl_entries", 0)
    size  = OUT_FILE.stat().st_size // 1024

    print(f"\n  ✓ library.json saved")
    print(f"    Total commands : {total}")
    print(f"    LCL entries    : {lcl}")
    print(f"    tldr entries   : {tldr}")
    print(f"    File size      : {size}KB")
    print(f"    Output         : {OUT_FILE}\n")


if __name__ == "__main__":
    main()
