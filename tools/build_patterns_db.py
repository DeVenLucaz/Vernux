# =============================================================================
# tools/build_patterns_db.py — Pattern Database Builder
# Version: 0.1.0
# =============================================================================
# Fetches data from two open-source sources and converts them into
# Vernux's patterns.json format, merging with existing handwritten patterns.
#
# Sources:
#   1. NL2Bash (MIT)  — ~9,000 English↔command pairs from StackOverflow
#      https://github.com/TellinaTool/nl2bash
#   2. tldr-pages (CC0) — community cheatsheets, one .md per command
#      https://github.com/tldr-pages/tldr/releases/latest/download/tldr.zip
#
# Output:
#   data/patterns_generated.json  — new patterns from external sources
#   data/patterns.json            — merged: handwritten + generated (no duplicates)
#
# Usage:
#   python tools/build_patterns_db.py              # full build
#   python tools/build_patterns_db.py --nl2bash    # NL2Bash only
#   python tools/build_patterns_db.py --tldr       # tldr-pages only
#   python tools/build_patterns_db.py --dry-run    # show stats, don't write
#   python tools/build_patterns_db.py --limit 200  # cap new patterns at N
#
# Important: generated patterns have source_credit="nl2bash" or "tldr"
# They use description_learner only — noob descriptions need human review.
# Run with --review after to audit generated patterns before shipping.
# =============================================================================

import json
import os
import re
import sys
import time
import argparse
import zipfile
import io
import urllib.request
from pathlib import Path
from collections import defaultdict

ROOT        = Path(__file__).parent.parent
DATA_DIR    = ROOT / "data"
PATTERNS_IN = DATA_DIR / "patterns.json"
PATTERNS_GEN= DATA_DIR / "patterns_generated.json"

# ---------------------------------------------------------------------------
# Termux-relevant command filter
# These are the commands we care about — anything else from NL2Bash is noise
# ---------------------------------------------------------------------------

TERMUX_COMMANDS = {
    # Core navigation & files
    "ls","cd","pwd","mkdir","rm","cp","mv","cat","less","more","head","tail",
    "touch","find","locate","file","stat","tree","ln","readlink","chmod",
    "chown","chgrp","du","df","wc","sort","uniq","cut","tr","tee","xargs",
    # Archives
    "zip","unzip","tar","gzip","gunzip","bzip2","xz","7z","7za",
    # Text processing
    "grep","sed","awk","diff","patch","strings","hexdump","xxd","base64",
    "md5sum","sha256sum","sha1sum","od","split","csplit","col","column",
    "fold","fmt","nl","rev","paste","join","expand","unexpand",
    # Network
    "curl","wget","ssh","scp","rsync","ping","nc","netcat","nmap","netstat",
    "ifconfig","ip","dig","nslookup","host","traceroute","whois","ftp",
    "ssh-keygen","ssh-copy-id","openssl","gpg",
    # Packages
    "pkg","apt","apt-get","pip","pip3","npm","gem","cargo","go",
    # Git
    "git",
    # Processes
    "ps","kill","pkill","killall","top","htop","nice","renice","jobs",
    "fg","bg","nohup","screen","tmux","watch","cron","crontab","at",
    # System info
    "free","uname","uptime","date","cal","who","whoami","id","hostname",
    "lscpu","lsof","lsblk","lspci","lsusb","env","printenv","strace",
    # Editors
    "nano","vim","vi","emacs","micro","nvim",
    # Shell / scripting
    "bash","sh","zsh","fish","echo","printf","read","export","source",
    "alias","unalias","history","clear","reset","sleep","wait","test",
    "expr","bc","dc","eval","exec","true","false","yes",
    # Dev tools
    "python3","python","node","nodejs","ruby","perl","php","java","javac",
    "gcc","clang","make","cmake","ninja","ffmpeg","ffprobe","convert",
    "sqlite3","mysql","redis-cli","mongo","docker","kubectl",
    # Modern utils
    "jq","yq","fzf","rg","ripgrep","fd","bat","tldr","man","info",
    "whatis","apropos","which","whereis","type",
    # Termux-specific
    "termux-setup-storage","termux-wake-lock","termux-wake-unlock",
    "termux-share","termux-clipboard-get","termux-clipboard-set",
    "termux-notification","termux-open","termux-open-url",
    "termux-battery-status","termux-info","termux-camera-photo",
    # File utils
    "ln","mount","umount","dd","sync","fsck",
}

# Commands that are dangerous, system-destructive, or irrelevant to Termux
BLOCKLIST_COMMANDS = {
    "sudo","su","systemctl","service","init","reboot","shutdown","halt",
    "fdisk","parted","mkfs","format","apt-key","dpkg-reconfigure",
    "useradd","userdel","usermod","groupadd","passwd","visudo",
    "iptables","ufw","firewalld","semanage","chroot","debootstrap",
    "docker-compose",  # too complex for patterns
}

# NL descriptions that indicate the pair is too complex/system-specific
BLOCKLIST_NL_PATTERNS = [
    r"centos|ubuntu|debian|fedora|redhat|arch linux|gentoo",  # distro-specific
    r"systemd|systemctl|service\s+\w+\s+start",
    r"root\s+user|as\s+root|with\s+sudo",
    r"cron\s+job|crontab",  # complex
    r"ssl\s+cert|openssl\s+req|certificate",  # complex
    r"compile\s+from\s+source|build\s+from\s+source",
    r"docker\s+run|docker\s+build|dockerfile",
    r"kernel\s+module|modprobe|insmod",
    r"mount\s+partition|disk\s+partition|fdisk",
    r"iptables|firewall\s+rule",
    r"add\s+user|create\s+user|user\s+account",
    r"\bldap\b|\bsamba\b|\bnfs\b|\bsmb\b",
]

# ---------------------------------------------------------------------------
# Category inference from command
# ---------------------------------------------------------------------------

CMD_TO_CATEGORY = {
    # navigation / files
    **{c: "files" for c in ["ls","cd","pwd","mkdir","rm","cp","mv","cat",
                             "less","more","head","tail","touch","find",
                             "locate","file","stat","tree","ln","readlink",
                             "du","df","chmod","chown","chgrp","dd","sync"]},
    # archives
    **{c: "archives" for c in ["zip","unzip","tar","gzip","gunzip","bzip2",
                                "xz","7z","7za"]},
    # text
    **{c: "files" for c in ["grep","sed","awk","wc","sort","uniq","cut","tr",
                             "tee","xargs","diff","patch","strings","hexdump",
                             "xxd","base64","md5sum","sha256sum","sha1sum",
                             "od","split","csplit","col","column","fold","fmt",
                             "nl","rev","paste","join","jq","yq"]},
    # network
    **{c: "network" for c in ["curl","wget","ssh","scp","rsync","ping","nc",
                               "netcat","nmap","netstat","ifconfig","ip","dig",
                               "nslookup","host","traceroute","whois","ftp",
                               "ssh-keygen","ssh-copy-id","openssl","gpg"]},
    # packages
    **{c: "packages" for c in ["pkg","apt","apt-get","pip","pip3","npm",
                                "gem","cargo","go"]},
    # git
    "git": "git",
    # processes
    **{c: "processes" for c in ["ps","kill","pkill","killall","top","htop",
                                 "nice","renice","jobs","fg","bg","nohup",
                                 "screen","tmux","watch","cron","crontab","at"]},
    # system
    **{c: "system" for c in ["free","uname","uptime","date","cal","who",
                              "whoami","id","hostname","lscpu","lsof","lsblk",
                              "lspci","lsusb","env","printenv","strace"]},
    # editors
    **{c: "editors" for c in ["nano","vim","vi","emacs","micro","nvim"]},
    # shell
    **{c: "shell" for c in ["bash","sh","zsh","fish","echo","printf","read",
                             "export","source","alias","unalias","history",
                             "clear","reset","sleep","wait","test","expr",
                             "bc","dc","eval","exec"]},
    # programming
    **{c: "programming" for c in ["python3","python","node","nodejs","ruby",
                                   "perl","php","java","javac","gcc","clang",
                                   "make","cmake","ninja","ffmpeg","ffprobe",
                                   "convert","sqlite3","mysql","redis-cli",
                                   "mongo","docker","kubectl"]},
    # termux
    **{c: "android" for c in ["termux-setup-storage","termux-wake-lock",
                               "termux-wake-unlock","termux-share",
                               "termux-clipboard-get","termux-clipboard-set",
                               "termux-notification","termux-open",
                               "termux-open-url","termux-battery-status",
                               "termux-info","termux-camera-photo"]},
    # utils
    **{c: "navigation" for c in ["which","whereis","type","whatis","apropos",
                                  "man","info","tldr","fzf","rg","ripgrep",
                                  "fd","bat"]},
}

def infer_category(command: str) -> str:
    first = command.strip().split()[0] if command.strip() else ""
    return CMD_TO_CATEGORY.get(first, "system")

# ---------------------------------------------------------------------------
# Safety inference — conservative heuristic
# ---------------------------------------------------------------------------

def infer_safety(command: str) -> str:
    cmd = command.lower()
    if re.search(r'\brm\s+-rf?\b|\brm\s+.*-f\b', cmd):
        return "skull"
    if re.search(r'\brm\b|\bdd\b|\bmkfs\b|\bformat\b', cmd):
        return "caution"
    if re.search(r'\bchmod\s+777\b|\bchown\b|\bkill\b|\bpkill\b', cmd):
        return "caution"
    if re.search(r'\bssh\b|\bwget\b|\bcurl\b.*\|\s*bash', cmd):
        return "caution"
    return "green"

# ---------------------------------------------------------------------------
# ID generation
# ---------------------------------------------------------------------------

def make_id(command: str, source: str, idx: int) -> str:
    first = re.sub(r'[^a-z0-9]', '_', command.strip().split()[0].lower())
    return f"{source}_{first}_{idx:04d}"

# ---------------------------------------------------------------------------
# NL2Bash fetcher + converter
# ---------------------------------------------------------------------------

NL2BASH_NL_URL = "https://raw.githubusercontent.com/TellinaTool/nl2bash/master/data/bash/all.nl"
NL2BASH_CM_URL = "https://raw.githubusercontent.com/TellinaTool/nl2bash/master/data/bash/all.cm"

def _fetch_text(url: str) -> str | None:
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Vernux/0.7.2 pattern builder"}
        )
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"  ✗ fetch failed: {url}\n    {e}")
        return None

def _nl_is_blocked(nl: str) -> bool:
    nl_low = nl.lower()
    for pat in BLOCKLIST_NL_PATTERNS:
        if re.search(pat, nl_low):
            return True
    return False

def _extract_first_command(cmd_line: str) -> str:
    """Extract the first word (binary name) from a command string."""
    stripped = cmd_line.strip().lstrip("$").strip()
    parts = stripped.split()
    return parts[0] if parts else ""

def _nl_to_triggers(nl: str) -> list[str]:
    """
    Convert a NL2Bash description into 1-3 trigger phrases.
    The NL is programmer-style — we clean it up but keep it as-is mostly.
    e.g. "Find all .py files modified in the last 7 days"
         → ["find all py files modified in last 7 days",
            "find python files modified recently"]
    """
    # Lowercase, strip trailing period
    t = nl.strip().rstrip(".")
    t = re.sub(r'\s+', ' ', t).lower()
    # Remove common preamble phrases
    t = re.sub(r'^(find\s+and\s+|search\s+for\s+and\s+)', '', t)
    # Remove quoted strings (they're usually file/path placeholders)
    t = re.sub(r"'[^']{1,30}'", '', t)
    t = re.sub(r'"[^"]{1,30}"', '', t)
    # Remove path-like segments  /home/xxx /var/www etc
    t = re.sub(r'/\S+', '', t)
    # Normalize whitespace again
    t = re.sub(r'\s+', ' ', t).strip()
    if not t or len(t) < 8:
        return []
    return [t]

def fetch_nl2bash(limit: int = 0) -> list[dict]:
    """
    Fetch NL2Bash corpus and convert to Vernux pattern dicts.
    Returns list of pattern dicts (source_credit='nl2bash').
    """
    print("\n  Fetching NL2Bash corpus...")
    nl_text = _fetch_text(NL2BASH_NL_URL)
    cm_text = _fetch_text(NL2BASH_CM_URL)
    if not nl_text or not cm_text:
        print("  ✗ Could not fetch NL2Bash data.")
        return []

    nl_lines = [l.strip() for l in nl_text.splitlines()]
    cm_lines = [l.strip() for l in cm_text.splitlines()]
    total_raw = min(len(nl_lines), len(cm_lines))
    print(f"  Raw pairs: {total_raw}")

    # Group by command — same command can have many NL descriptions
    # We merge them: multiple NL → multiple triggers, one pattern
    by_command: dict[str, dict] = {}

    skipped_blocklist = 0
    skipped_complex   = 0
    skipped_irrelevant= 0

    for i in range(total_raw):
        nl  = nl_lines[i].strip()
        cmd = cm_lines[i].strip()
        if not nl or not cmd:
            continue

        first = _extract_first_command(cmd)
        if not first:
            continue

        # Filter: must be a Termux-relevant command
        if first not in TERMUX_COMMANDS:
            skipped_irrelevant += 1
            continue

        # Filter: must not be in blocklist
        if first in BLOCKLIST_COMMANDS:
            skipped_blocklist += 1
            continue

        # Filter: NL must not describe blocked scenarios
        if _nl_is_blocked(nl):
            skipped_blocklist += 1
            continue

        # Filter: skip overly complex commands (pipes > 2, subshells, etc.)
        pipe_count = cmd.count("|")
        if pipe_count > 2:
            skipped_complex += 1
            continue
        if cmd.count("$(") > 1 or cmd.count("`") > 2:
            skipped_complex += 1
            continue
        if len(cmd) > 200:
            skipped_complex += 1
            continue

        triggers = _nl_to_triggers(nl)
        if not triggers:
            continue

        if cmd not in by_command:
            by_command[cmd] = {
                "command":  cmd,
                "triggers": [],
                "nl_descs": [],  # raw NL descriptions for description_learner
                "first":    first,
            }

        # Add trigger if not already present (dedup)
        for t in triggers:
            if t not in by_command[cmd]["triggers"]:
                by_command[cmd]["triggers"].append(t)

        by_command[cmd]["nl_descs"].append(nl)

    print(f"  Skipped irrelevant: {skipped_irrelevant}")
    print(f"  Skipped blocklist:  {skipped_blocklist}")
    print(f"  Skipped complex:    {skipped_complex}")
    print(f"  Unique commands:    {len(by_command)}")

    # Convert grouped data to pattern dicts
    patterns = []
    for idx, (cmd, data) in enumerate(by_command.items()):
        if limit and len(patterns) >= limit:
            break

        # Use the first NL description as description_learner (most concise)
        desc_learner = data["nl_descs"][0] if data["nl_descs"] else ""
        # Cap triggers at 6 per pattern
        triggers = data["triggers"][:6]
        if not triggers:
            continue

        first = data["first"]
        pattern = {
            "id":                make_id(cmd, "nl2bash", idx),
            "triggers":          triggers,
            "command":           cmd,
            "description_noob":  "",   # intentionally blank — needs human review
            "description_learner": desc_learner,
            "description_pro":   cmd,
            "example":           cmd,
            "safety":            infer_safety(cmd),
            "reversible":        False,
            "undo":              "",
            "requires":          [first] if first else [],
            "category":          infer_category(cmd),
            "source_credit":     "nl2bash",
        }
        patterns.append(pattern)

    print(f"  → {len(patterns)} patterns generated from NL2Bash")
    return patterns

# ---------------------------------------------------------------------------
# tldr-pages fetcher + converter
# ---------------------------------------------------------------------------

TLDR_ZIP_URL = "https://github.com/tldr-pages/tldr/releases/latest/download/tldr.zip"

# Platforms to pull from — ordered by priority
TLDR_PLATFORMS = ["android", "linux", "common"]

def _parse_tldr_md(content: str, cmd_name: str) -> dict | None:
    """
    Parse a tldr markdown page into structured data.

    tldr format:
      # command
      > Short description sentence.
      > More information: url
      - Example description:
        `command {{arg}}`
      - Another example:
        `command --flag`
    """
    lines = content.splitlines()
    description = ""
    examples    = []   # list of (description, command_template)
    current_ex  = None

    for line in lines:
        line = line.rstrip()
        # Description line
        if line.startswith("> ") and not description:
            desc = line[2:].strip()
            # Skip "More information:" lines
            if not desc.lower().startswith("more information"):
                description = desc
        # Example description
        elif line.startswith("- "):
            current_ex = line[2:].rstrip(":").strip()
        # Example command (indented with spaces before backtick)
        elif line.strip().startswith("`") and line.strip().endswith("`") and current_ex:
            raw_cmd = line.strip()[1:-1].strip()
            # Remove {{placeholder}} syntax → replace with generic placeholder
            clean_cmd = re.sub(r'\{\{[^}]+\}\}', '{arg}', raw_cmd)
            # Remove longform/shortform selector {{[-s|--long]}} → --long
            clean_cmd = re.sub(r'\{\[([^\]]+)\]\}', lambda m: m.group(1).split('|')[-1], clean_cmd)
            examples.append((current_ex, clean_cmd))
            current_ex = None

    if not description and not examples:
        return None

    return {
        "name":        cmd_name,
        "description": description,
        "examples":    examples[:6],  # cap at 6
    }


def _tldr_example_to_triggers(ex_desc: str) -> list[str]:
    """
    Convert a tldr example description to trigger phrases.
    e.g. "Search for a pattern in a file" → ["search for pattern in file",
                                              "find pattern in file"]
    """
    t = ex_desc.strip().rstrip(".")
    t = re.sub(r'\s+', ' ', t).lower()
    # Remove file/path placeholders
    t = re.sub(r'\bpath/to/\S+', '', t)
    t = re.sub(r'\bfile/to/\S+', '', t)
    t = re.sub(r'\s+', ' ', t).strip()
    if not t or len(t) < 8:
        return []
    return [t]


def fetch_tldr(limit: int = 0) -> list[dict]:
    """
    Download the tldr zip and convert pages to Vernux patterns.
    Focuses on android/, linux/, common/ platforms in that order.
    Returns list of pattern dicts (source_credit='tldr').
    """
    print("\n  Downloading tldr-pages zip (~5MB)...")
    raw = _fetch_text(TLDR_ZIP_URL)
    if not raw:
        # Try binary fetch
        try:
            req = urllib.request.Request(
                TLDR_ZIP_URL,
                headers={"User-Agent": "Vernux/0.7.2 pattern builder"}
            )
            with urllib.request.urlopen(req, timeout=60) as r:
                raw_bytes = r.read()
        except Exception as e:
            print(f"  ✗ Could not download tldr zip: {e}")
            return []
    else:
        raw_bytes = raw.encode("latin-1")

    try:
        zf = zipfile.ZipFile(io.BytesIO(raw_bytes))
    except Exception as e:
        print(f"  ✗ Could not open tldr zip: {e}")
        return []

    # Index all .md files by command name, preferring android > linux > common
    # tldr zip structure: pages/linux/grep.md  pages/common/grep.md etc
    cmd_pages: dict[str, str] = {}  # cmd_name → content

    for platform in reversed(TLDR_PLATFORMS):  # reversed so android wins
        prefix = f"pages/{platform}/"
        for name in zf.namelist():
            if name.startswith(prefix) and name.endswith(".md"):
                cmd_name = Path(name).stem  # e.g. "grep", "git-checkout"
                try:
                    content = zf.read(name).decode("utf-8", errors="replace")
                    cmd_pages[cmd_name] = content
                except Exception:
                    pass

    print(f"  Pages found across {TLDR_PLATFORMS}: {len(cmd_pages)}")

    # Filter to Termux-relevant commands
    relevant = {}
    for cmd_name, content in cmd_pages.items():
        # Normalize: "git-checkout" → first word is "git"
        first = cmd_name.split("-")[0]
        if first in TERMUX_COMMANDS or cmd_name in TERMUX_COMMANDS:
            relevant[cmd_name] = content

    print(f"  Termux-relevant pages: {len(relevant)}")

    # Convert to patterns
    patterns = []
    for idx, (cmd_name, content) in enumerate(relevant.items()):
        if limit and len(patterns) >= limit:
            break

        parsed = _parse_tldr_md(content, cmd_name)
        if not parsed:
            continue

        # Build one pattern per example description (richer trigger variety)
        # Group all into one pattern per command
        all_triggers = []
        all_examples = []

        # The top-level description is the best description_learner
        desc_learner = parsed["description"]

        for ex_desc, ex_cmd in parsed["examples"]:
            triggers = _tldr_example_to_triggers(ex_desc)
            all_triggers.extend(triggers)
            # Use the real command (with {arg} placeholders cleaned)
            if ex_cmd and ex_cmd not in all_examples:
                all_examples.append(ex_cmd)

        # Also add the command name itself as a trigger
        if cmd_name not in all_triggers:
            all_triggers.insert(0, cmd_name)

        # Deduplicate and cap
        seen = set()
        unique_triggers = []
        for t in all_triggers:
            if t not in seen and len(t) > 3:
                seen.add(t)
                unique_triggers.append(t)
        unique_triggers = unique_triggers[:8]

        if not unique_triggers:
            continue

        # Use the first real example command, fall back to cmd_name
        real_cmd = all_examples[0] if all_examples else cmd_name
        # Restore {arg} → proper Vernux param syntax if needed
        real_cmd = real_cmd.replace("{arg}", "{filename}")
        first_word = cmd_name.split("-")[0]

        pattern = {
            "id":                  make_id(cmd_name, "tldr", idx),
            "triggers":            unique_triggers,
            "command":             real_cmd,
            "description_noob":    "",    # blank — needs human review
            "description_learner": desc_learner,
            "description_pro":     real_cmd,
            "example":             real_cmd,
            "safety":              infer_safety(real_cmd),
            "reversible":          False,
            "undo":                "",
            "requires":            [first_word],
            "category":            infer_category(real_cmd),
            "source_credit":       "tldr",
        }
        patterns.append(pattern)

    print(f"  → {len(patterns)} patterns generated from tldr-pages")
    return patterns

# ---------------------------------------------------------------------------
# Merge logic
# ---------------------------------------------------------------------------

def _normalize_trigger(t: str) -> str:
    return re.sub(r'\s+', ' ', t.lower().strip())

def _normalize_command(c: str) -> str:
    return re.sub(r'\s+', ' ', c.strip())

def merge_patterns(existing: list[dict], new_patterns: list[dict]) -> tuple[list[dict], dict]:
    """
    Merge new_patterns into existing, avoiding duplicates.
    Duplicate detection: same normalized command OR overlapping triggers.
    Returns (merged_list, stats).
    """
    # Build indexes on existing
    existing_commands = {_normalize_command(p["command"]) for p in existing}
    existing_triggers = set()
    for p in existing:
        for t in p.get("triggers", []):
            existing_triggers.add(_normalize_trigger(t))

    added      = []
    skipped_cmd= 0
    skipped_trg= 0

    for p in new_patterns:
        cmd_norm = _normalize_command(p["command"])
        # Skip if exact same command already exists
        if cmd_norm in existing_commands:
            skipped_cmd += 1
            continue
        # Skip if majority of triggers already exist
        p_triggers = [_normalize_trigger(t) for t in p.get("triggers", [])]
        overlap = sum(1 for t in p_triggers if t in existing_triggers)
        if p_triggers and overlap / len(p_triggers) > 0.5:
            skipped_trg += 1
            continue
        added.append(p)
        existing_commands.add(cmd_norm)
        for t in p_triggers:
            existing_triggers.add(t)

    merged = existing + added
    stats  = {
        "existing":     len(existing),
        "new_total":    len(new_patterns),
        "added":        len(added),
        "skipped_cmd":  skipped_cmd,
        "skipped_trg":  skipped_trg,
        "final_total":  len(merged),
    }
    return merged, stats

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(
        description="Build Vernux patterns.json from open-source NL→command data"
    )
    ap.add_argument("--nl2bash",  action="store_true", help="NL2Bash source only")
    ap.add_argument("--tldr",     action="store_true", help="tldr-pages source only")
    ap.add_argument("--dry-run",  action="store_true", help="Show stats without writing")
    ap.add_argument("--limit",    type=int, default=0,  help="Cap new patterns per source")
    ap.add_argument("--no-merge", action="store_true",  help="Don't merge with patterns.json")
    args = ap.parse_args()

    do_nl2bash = args.nl2bash or (not args.nl2bash and not args.tldr)
    do_tldr    = args.tldr    or (not args.nl2bash and not args.tldr)

    print("\n" + "="*60)
    print("  Vernux Pattern Database Builder")
    print("="*60)

    # Load existing patterns
    existing = []
    if PATTERNS_IN.exists() and not args.no_merge:
        with open(PATTERNS_IN) as f:
            d = json.load(f)
        existing = d.get("patterns", [])
        print(f"\n  Existing patterns: {len(existing)}")

    # Fetch from sources
    generated = []
    if do_nl2bash:
        nl2bash_pats = fetch_nl2bash(limit=args.limit)
        generated.extend(nl2bash_pats)

    if do_tldr:
        tldr_pats = fetch_tldr(limit=args.limit)
        generated.extend(tldr_pats)

    print(f"\n  Total generated: {len(generated)}")

    if not generated:
        print("  Nothing to add. Exiting.")
        return

    # Save generated patterns separately (for inspection)
    if not args.dry_run:
        DATA_DIR.mkdir(exist_ok=True)
        with open(PATTERNS_GEN, "w") as f:
            json.dump({"patterns": generated}, f, indent=2, ensure_ascii=False)
        print(f"\n  ✓ Saved generated → {PATTERNS_GEN}")
        print(f"    ({PATTERNS_GEN.stat().st_size // 1024}KB, {len(generated)} patterns)")

    # Merge
    if not args.no_merge and existing:
        merged, stats = merge_patterns(existing, generated)
        print(f"\n  Merge stats:")
        print(f"    Existing:         {stats['existing']}")
        print(f"    Generated:        {stats['new_total']}")
        print(f"    Added (new):      {stats['added']}")
        print(f"    Skipped (dup cmd):{stats['skipped_cmd']}")
        print(f"    Skipped (dup trg):{stats['skipped_trg']}")
        print(f"    Final total:      {stats['final_total']}")

        if not args.dry_run:
            output = {"patterns": merged}
            with open(PATTERNS_IN, "w") as f:
                json.dump(output, f, indent=2, ensure_ascii=False)
            print(f"\n  ✓ Merged → {PATTERNS_IN}")
            print(f"    ({PATTERNS_IN.stat().st_size // 1024}KB, {len(merged)} patterns)")
    elif args.dry_run:
        print("\n  [dry-run] No files written.")
    else:
        # no-merge: just write generated to patterns.json
        if not args.dry_run:
            with open(PATTERNS_GEN, "w") as f:
                json.dump({"patterns": generated}, f, indent=2, ensure_ascii=False)

    print("\n  IMPORTANT: generated patterns have empty description_noob fields.")
    print("  Review data/patterns_generated.json and fill in noob descriptions")
    print("  before shipping to users. Run: python tools/review_patterns.py")
    print()


if __name__ == "__main__":
    main()
