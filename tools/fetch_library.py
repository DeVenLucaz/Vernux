# =============================================================================
# tools/fetch_library.py — Linux Command Library Data Fetcher
# Version: 0.1.0 | Phase 1 — Library Enrichment
# =============================================================================
# DEV TOOL — run once (or on update) to build data/library.json
#
# Fetches command data from linuxcommandlibrary.com and converts it into
# Vernux's offline library format. Requires internet during build only.
# The output (data/library.json) ships with Vernux and works 100% offline.
#
# Usage:
#   python tools/fetch_library.py               # full fetch (~500 priority cmds)
#   python tools/fetch_library.py --quick       # Termux-relevant subset only
#   python tools/fetch_library.py --cmd grep    # single command test
#
# Data source:   https://linuxcommandlibrary.com  (Apache 2.0)
# Credits:       Simon Schubert / LinuxCommandLibrary contributors
# =============================================================================

import json
import os
import sys
import re
import time
import argparse
import urllib.request
import urllib.error
from pathlib import Path
from html.parser import HTMLParser

ROOT     = Path(__file__).parent.parent
DATA_DIR = ROOT / "data"
OUT_FILE = DATA_DIR / "library.json"

# ---------------------------------------------------------------------------
# Priority command list — Termux-relevant, fetched first
# Covers what users actually type in Termux day-to-day
# ---------------------------------------------------------------------------

TERMUX_PRIORITY = [
    # Navigation & files
    "ls", "cd", "pwd", "mkdir", "rm", "cp", "mv", "cat", "less", "more",
    "touch", "find", "locate", "file", "stat", "tree", "ln", "realpath",
    "basename", "dirname", "readlink",
    # Text processing
    "grep", "sed", "awk", "cut", "sort", "uniq", "wc", "head", "tail",
    "tr", "diff", "patch", "xargs", "tee", "column", "fmt", "fold",
    # Archives
    "zip", "unzip", "tar", "gzip", "gunzip", "bzip2", "xz", "7z",
    # Network
    "curl", "wget", "ssh", "scp", "rsync", "ping", "nmap", "netstat",
    "ifconfig", "ip", "nc", "telnet", "dig", "nslookup", "host",
    "traceroute", "whois", "httpie",
    # Packages
    "pkg", "apt", "pip", "pip3", "npm", "gem", "cargo", "go",
    # Git
    "git",
    # Processes
    "ps", "kill", "pkill", "top", "htop", "nice", "renice", "jobs",
    "fg", "bg", "nohup", "screen", "tmux",
    # System info
    "df", "du", "free", "uname", "uptime", "date", "cal", "who",
    "whoami", "id", "hostname", "lscpu", "lsof", "lsblk",
    # Permissions
    "chmod", "chown", "chgrp", "umask", "sudo", "su",
    # Editors
    "nano", "vim", "vi", "emacs", "micro",
    # Shell
    "echo", "printf", "read", "export", "source", "alias", "unalias",
    "history", "clear", "reset", "env", "set", "unset", "declare",
    "eval", "exec", "exit", "logout", "sleep", "wait", "watch",
    # Scripting
    "bash", "sh", "zsh", "fish", "test", "expr", "bc", "dc",
    # Dev tools
    "python3", "python", "node", "ruby", "perl", "php", "java",
    "gcc", "clang", "make", "cmake", "ninja",
    "ffmpeg", "ffprobe", "imagemagick", "convert",
    # Termux-specific
    "termux-setup-storage", "termux-wake-lock", "termux-wake-unlock",
    "termux-share", "termux-clipboard-get", "termux-clipboard-set",
    "termux-notification", "termux-open", "termux-open-url",
    "termux-battery-status", "termux-info",
    # Misc utils
    "jq", "yq", "fzf", "rg", "ripgrep", "fd", "bat",
    "tldr", "man", "info", "whatis", "apropos",
    "cron", "crontab", "at", "awk", "sed",
    "base64", "md5sum", "sha256sum", "xxd", "hexdump",
    "strings", "od", "split", "csplit",
    "strace", "ltrace", "ldd",
    "ssh-keygen", "ssh-copy-id", "ssh-agent", "ssh-add",
    "gpg", "openssl",
    "mysql", "sqlite3", "redis-cli", "mongo",
    "docker", "kubectl",
    "vim", "nvim", "code",
]

# ---------------------------------------------------------------------------
# HTML parser to extract LCL man page content
# ---------------------------------------------------------------------------

class LCLParser(HTMLParser):
    """
    Extracts structured data from linuxcommandlibrary.com man pages.
    The page structure:
      - <h1> or <title> → command name
      - description paragraphs
      - example code blocks  ($ prefix)
      - flags/options table
    """

    def __init__(self):
        super().__init__()
        self.reset_state()

    def reset_state(self):
        self.title       = ""
        self.description = []
        self.examples    = []
        self.synopsis    = ""
        self.flags       = []   # list of (flag, description)
        self._current    = None
        self._buf        = ""
        self._in_code    = False
        self._in_pre     = False
        self._depth      = 0
        self._tag_stack  = []

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        self._tag_stack.append(tag)
        self._buf = ""

        if tag in ("code", "pre"):
            self._in_code = True
        if tag == "pre":
            self._in_pre = True

    def handle_endtag(self, tag):
        if self._tag_stack and self._tag_stack[-1] == tag:
            self._tag_stack.pop()

        text = self._buf.strip()

        if tag in ("code", "pre"):
            self._in_code = False
            if tag == "pre":
                self._in_pre = False
            if text:
                # Extract examples — lines starting with $
                for line in text.splitlines():
                    line = line.strip()
                    if line.startswith("$"):
                        ex = line[1:].strip()
                        if ex and ex not in self.examples:
                            self.examples.append(ex)
                # Grab synopsis from first code block if it looks like one
                if not self.synopsis and re.search(r'\[.*\]', text):
                    self.synopsis = text.splitlines()[0].strip()[:120]

        if tag == "p" and text and not self._in_pre:
            # Skip nav/UI paragraphs
            skip_patterns = [
                "linux command library", "search for", "linuxcommandlibrary",
                "cookie", "privacy", "©", "github", "install", "powered by"
            ]
            tl = text.lower()
            if not any(p in tl for p in skip_patterns):
                if len(text) > 30:
                    self.description.append(text)

        if tag in ("h1", "h2", "title") and text:
            if not self.title and len(text) < 60:
                # "grep man | Linux Command Library" → extract "grep"
                m = re.match(r'^(\S+)\s+(?:man|linux)', text.lower())
                if m:
                    self.title = m.group(1)
                elif "|" in text:
                    self.title = text.split("|")[0].strip().split()[0]

        self._buf = ""

    def handle_data(self, data):
        self._buf += data


def _fetch_url(url: str, timeout: int = 15) -> str | None:
    """Fetch a URL, return text content or None on failure."""
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Vernux/0.7.0 (command library builder; https://github.com/DeVenLucaz/Vernux)"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        return None


def fetch_command(cmd: str) -> dict | None:
    """
    Fetch a single command's page from LCL and return a structured dict.
    Returns None if fetch or parse fails.
    """
    url = f"https://linuxcommandlibrary.com/man/{cmd}"
    html = _fetch_url(url)
    if not html:
        return None

    parser = LCLParser()
    try:
        parser.feed(html)
    except Exception:
        pass

    desc_parts = parser.description
    if not desc_parts and not parser.examples:
        return None

    # Build a clean description by taking the most useful paragraph
    # (skip very short ones, take up to 2 substantive paragraphs)
    clean_desc = []
    for p in desc_parts:
        p = p.strip()
        # Remove HTML remnants
        p = re.sub(r'<[^>]+>', '', p)
        # Normalize whitespace
        p = re.sub(r'\s+', ' ', p)
        if len(p) > 50 and len(clean_desc) < 2:
            clean_desc.append(p)

    full_desc = " ".join(clean_desc)[:800]

    # First sentence as short description
    short_desc = re.split(r'(?<=[.!?])\s', full_desc)[0][:200] if full_desc else ""

    examples = parser.examples[:8]   # cap at 8 examples

    if not short_desc and not examples:
        return None

    return {
        "name":        cmd,
        "synopsis":    parser.synopsis or cmd,
        "description": full_desc,
        "short":       short_desc,
        "examples":    examples,
        "source":      "LinuxCommandLibrary",
    }


# ---------------------------------------------------------------------------
# Category mapping — group commands for library browsing
# ---------------------------------------------------------------------------

CATEGORIES = {
    "files":      ["ls","cd","pwd","mkdir","rm","cp","mv","cat","less","more",
                   "touch","find","locate","file","stat","tree","ln","realpath",
                   "basename","dirname","readlink","chmod","chown","chgrp","umask"],
    "text":       ["grep","sed","awk","cut","sort","uniq","wc","head","tail",
                   "tr","diff","patch","xargs","tee","column","fmt","fold",
                   "jq","yq","base64","md5sum","sha256sum","xxd","hexdump",
                   "strings","od","split","csplit"],
    "archives":   ["zip","unzip","tar","gzip","gunzip","bzip2","xz","7z"],
    "network":    ["curl","wget","ssh","scp","rsync","ping","nmap","netstat",
                   "ifconfig","ip","nc","telnet","dig","nslookup","host",
                   "traceroute","whois","httpie"],
    "packages":   ["pkg","apt","pip","pip3","npm","gem","cargo","go"],
    "git":        ["git"],
    "processes":  ["ps","kill","pkill","top","htop","nice","renice","jobs",
                   "fg","bg","nohup","screen","tmux","watch","cron","crontab"],
    "system":     ["df","du","free","uname","uptime","date","cal","who",
                   "whoami","id","hostname","lscpu","lsof","lsblk","sudo","su"],
    "editors":    ["nano","vim","vi","emacs","micro","nvim"],
    "shell":      ["bash","sh","zsh","fish","echo","printf","read","export",
                   "source","alias","unalias","history","clear","reset","env",
                   "set","unset","declare","eval","exec","exit","sleep","wait",
                   "test","expr","bc","dc"],
    "dev":        ["python3","python","node","ruby","perl","php","java",
                   "gcc","clang","make","cmake","ninja","ffmpeg","ffprobe",
                   "sqlite3","mysql","redis-cli","docker","kubectl",
                   "ssh-keygen","ssh-copy-id","gpg","openssl"],
    "termux":     ["termux-setup-storage","termux-wake-lock","termux-wake-unlock",
                   "termux-share","termux-clipboard-get","termux-clipboard-set",
                   "termux-notification","termux-open","termux-open-url",
                   "termux-battery-status","termux-info"],
    "utils":      ["fzf","rg","ripgrep","fd","bat","tldr","man","info",
                   "whatis","apropos","strace","ltrace","ldd"],
}

def _get_category(cmd: str) -> str:
    for cat, cmds in CATEGORIES.items():
        if cmd in cmds:
            return cat
    return "other"


# ---------------------------------------------------------------------------
# Main build logic
# ---------------------------------------------------------------------------

def build_library(commands: list[str], quiet: bool = False) -> dict:
    """Fetch all commands and return the full library dict."""
    library = {
        "meta": {
            "version":      "0.1.0",
            "source":       "LinuxCommandLibrary (linuxcommandlibrary.com)",
            "license":      "Apache 2.0 — Simon Schubert & contributors",
            "credits_url":  "https://github.com/SimonSchubert/LinuxCommandLibrary",
            "command_count": 0,
            "build_note":   "Built by Vernux tools/fetch_library.py"
        },
        "commands": {}
    }

    total   = len(commands)
    success = 0
    failed  = []

    for i, cmd in enumerate(commands, 1):
        if not quiet:
            print(f"  [{i:3d}/{total}] {cmd:<30}", end="", flush=True)

        data = fetch_command(cmd)

        if data:
            data["category"] = _get_category(cmd)
            library["commands"][cmd] = data
            success += 1
            if not quiet:
                print(f"✓  {len(data['description'])} chars, {len(data['examples'])} examples")
        else:
            failed.append(cmd)
            if not quiet:
                print("✗  (not found or parse failed)")

        # Polite rate limiting — don't hammer the server
        time.sleep(0.4)

    library["meta"]["command_count"] = success

    if not quiet:
        print(f"\n  Done: {success}/{total} commands fetched")
        if failed:
            print(f"  Failed ({len(failed)}): {', '.join(failed[:10])}")
            if len(failed) > 10:
                print(f"         ... and {len(failed) - 10} more")

    return library


def merge_with_existing(new_data: dict, existing_path: Path) -> dict:
    """
    Merge new fetch results into existing library.json.
    New data overwrites old entries for the same command.
    Keeps entries that weren't re-fetched.
    """
    if not existing_path.exists():
        return new_data

    with open(existing_path) as f:
        existing = json.load(f)

    existing_cmds = existing.get("commands", {})
    new_cmds      = new_data.get("commands", {})
    merged        = {**existing_cmds, **new_cmds}

    result = dict(new_data)
    result["commands"]                   = merged
    result["meta"]["command_count"]      = len(merged)
    result["meta"]["merged_from_existing"] = True

    return result


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(
        description="Fetch Linux Command Library data → data/library.json"
    )
    ap.add_argument("--quick",  action="store_true",
                    help="Fetch only the 60 most common Termux commands")
    ap.add_argument("--cmd",    type=str, default=None,
                    help="Fetch and print a single command (debug)")
    ap.add_argument("--merge",  action="store_true",
                    help="Merge into existing library.json (keep old entries)")
    ap.add_argument("--quiet",  action="store_true",
                    help="Suppress per-command output")
    args = ap.parse_args()

    # Single command debug mode
    if args.cmd:
        print(f"\nFetching: {args.cmd}")
        data = fetch_command(args.cmd)
        if data:
            print(json.dumps(data, indent=2))
        else:
            print("Failed to fetch.")
        return

    # Choose command list
    if args.quick:
        commands = TERMUX_PRIORITY[:60]
        print(f"\n  Quick mode: fetching {len(commands)} priority commands")
    else:
        commands = TERMUX_PRIORITY
        print(f"\n  Full mode: fetching {len(commands)} commands")

    print(f"  Output: {OUT_FILE}")
    print(f"  Source: linuxcommandlibrary.com (Apache 2.0)\n")

    library = build_library(commands, quiet=args.quiet)

    if args.merge:
        library = merge_with_existing(library, OUT_FILE)

    DATA_DIR.mkdir(exist_ok=True)
    with open(OUT_FILE, "w") as f:
        json.dump(library, f, indent=2, ensure_ascii=False)

    print(f"\n  ✓ Saved {library['meta']['command_count']} commands → {OUT_FILE}")
    print(f"  File size: {OUT_FILE.stat().st_size // 1024}KB\n")


if __name__ == "__main__":
    main()
