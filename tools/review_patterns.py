# =============================================================================
# tools/review_patterns.py — Generated Pattern Review Tool
# Version: 0.1.0
# =============================================================================
# After running build_patterns_db.py, use this tool to audit the generated
# patterns and fill in description_noob fields before shipping.
#
# Usage:
#   python tools/review_patterns.py               # review all missing noob descs
#   python tools/review_patterns.py --source nl2bash  # review one source only
#   python tools/review_patterns.py --stats       # show coverage stats only
#   python tools/review_patterns.py --auto-noob   # auto-generate simple noob descs
#
# The --auto-noob flag generates basic noob descriptions from description_learner.
# They won't be as good as handwritten ones, but are better than empty.
# =============================================================================

import json
import re
import argparse
from pathlib import Path

ROOT        = Path(__file__).parent.parent
DATA_DIR    = ROOT / "data"
PATTERNS_IN = DATA_DIR / "patterns.json"
PATTERNS_GEN= DATA_DIR / "patterns_generated.json"

# ---------------------------------------------------------------------------
# Auto-noob description generator
# Converts programmer-style learner descriptions into simpler noob language
# ---------------------------------------------------------------------------

# Verb mappings — programmer verbs → plain language
VERB_MAP = {
    "search for":       "look for",
    "execute":          "run",
    "display":          "show",
    "print":            "show",
    "output":           "show",
    "list":             "show",
    "enumerate":        "list",
    "concatenate":      "combine",
    "compress":         "shrink",
    "decompress":       "unpack",
    "extract":          "unpack",
    "archive":          "bundle up",
    "recursively":      "",   # strip
    "recursion":        "",
    "traverse":         "go through",
    "iterate":          "go through",
    "directory":        "folder",
    "directories":      "folders",
    "file system":      "storage",
    "stdout":           "screen",
    "stdin":            "keyboard input",
    "stderr":           "error messages",
    "stream":           "data",
    "regex":            "search pattern",
    "regular expression":"search pattern",
    "pattern":          "search text",
    "argument":         "value",
    "parameter":        "setting",
    "flag":             "option",
    "repository":       "project folder",
    "commit":           "save point",
    "branch":           "version",
    "remote":           "GitHub copy",
    "merge":            "combine",
    "checksum":         "fingerprint",
    "hash":             "fingerprint",
    "symlink":          "shortcut",
    "symbolic link":    "shortcut",
    "process":          "running program",
    "daemon":           "background program",
    "socket":           "connection",
    "port":             "connection point",
    "interface":        "network card",
    "stdin":            "input",
}

def auto_noob_desc(command: str, learner_desc: str, category: str) -> str:
    """
    Generate a basic noob description from the learner description.
    Not as good as handwritten, but fills the gap.
    """
    if not learner_desc:
        first = command.strip().split()[0]
        return f"Runs the '{first}' command."

    desc = learner_desc.strip().rstrip(".")

    # Apply verb/term mappings
    desc_lower = desc.lower()
    for tech_term, plain_term in VERB_MAP.items():
        if tech_term in desc_lower:
            if plain_term:
                desc = re.sub(re.escape(tech_term), plain_term,
                              desc, flags=re.IGNORECASE, count=1)
            else:
                desc = re.sub(r'\b' + re.escape(tech_term) + r'\b', '',
                              desc, flags=re.IGNORECASE)

    # Clean up double spaces
    desc = re.sub(r'\s+', ' ', desc).strip()

    # Add Termux context for certain categories
    if category == "git":
        desc = f"Git version control: {desc.lower()}"
    elif category == "network":
        desc = f"Network: {desc.lower()}"
    elif category == "packages":
        desc = f"Package manager: {desc.lower()}"

    # Cap length
    if len(desc) > 120:
        desc = desc[:117] + "..."

    return desc.strip().rstrip(".")


def get_stats(patterns: list[dict]) -> dict:
    total      = len(patterns)
    by_source  = {}
    has_noob   = 0
    missing    = []

    for p in patterns:
        src = p.get("source_credit", "vernux")
        by_source[src] = by_source.get(src, 0) + 1
        if p.get("description_noob", "").strip():
            has_noob += 1
        else:
            missing.append(p)

    return {
        "total":      total,
        "has_noob":   has_noob,
        "missing":    len(missing),
        "by_source":  by_source,
        "missing_patterns": missing,
    }


def main():
    ap = argparse.ArgumentParser(
        description="Review and fill noob descriptions on generated patterns"
    )
    ap.add_argument("--source",    type=str, default=None,
                    help="Filter to one source: nl2bash, tldr, vernux")
    ap.add_argument("--stats",     action="store_true",
                    help="Show coverage stats only, don't modify")
    ap.add_argument("--auto-noob", action="store_true",
                    help="Auto-fill missing noob descriptions from learner desc")
    ap.add_argument("--category",  type=str, default=None,
                    help="Filter to one category")
    ap.add_argument("--limit",     type=int, default=0,
                    help="Limit how many to auto-fill")
    args = ap.parse_args()

    if not PATTERNS_IN.exists():
        print(f"  ✗ {PATTERNS_IN} not found. Run build_patterns_db.py first.")
        return

    with open(PATTERNS_IN) as f:
        data = json.load(f)
    patterns = data.get("patterns", [])

    # Filter
    if args.source:
        filtered = [p for p in patterns if p.get("source_credit") == args.source]
    elif args.category:
        filtered = [p for p in patterns if p.get("category") == args.category]
    else:
        filtered = patterns

    stats = get_stats(filtered)

    print("\n" + "="*60)
    print("  Pattern Review Stats")
    print("="*60)
    print(f"  Total patterns:        {stats['total']}")
    print(f"  Has noob description:  {stats['has_noob']}")
    print(f"  Missing noob desc:     {stats['missing']}")
    print(f"\n  By source:")
    for src, count in sorted(stats["by_source"].items()):
        print(f"    {src:<16} {count:4d} patterns")

    # Category breakdown of missing
    missing = stats["missing_patterns"]
    if missing:
        by_cat = {}
        for p in missing:
            cat = p.get("category", "other")
            by_cat[cat] = by_cat.get(cat, 0) + 1
        print(f"\n  Missing by category:")
        for cat, cnt in sorted(by_cat.items(), key=lambda x: -x[1]):
            print(f"    {cat:<16} {cnt:4d}")

    if args.stats:
        print()
        return

    # Auto-fill noob descriptions
    if args.auto_noob:
        filled   = 0
        to_fill  = [p for p in patterns if not p.get("description_noob","").strip()]

        if args.source:
            to_fill = [p for p in to_fill if p.get("source_credit") == args.source]
        if args.category:
            to_fill = [p for p in to_fill if p.get("category") == args.category]
        if args.limit:
            to_fill = to_fill[:args.limit]

        print(f"\n  Auto-filling {len(to_fill)} noob descriptions...")

        for p in to_fill:
            noob = auto_noob_desc(
                p.get("command", ""),
                p.get("description_learner", ""),
                p.get("category", "")
            )
            p["description_noob"] = noob
            filled += 1

        # Save back
        data["patterns"] = patterns
        with open(PATTERNS_IN, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        print(f"  ✓ Filled {filled} noob descriptions")
        print(f"  ✓ Saved → {PATTERNS_IN}")
        print()
        print("  NOTE: auto-generated noob descriptions are approximate.")
        print("  Review them and rewrite Termux-specific ones by hand.")
        return

    # Show first 10 missing patterns for inspection
    if missing:
        print(f"\n  First {min(10, len(missing))} patterns missing noob description:\n")
        for p in missing[:10]:
            print(f"  [{p.get('source_credit','?')}] [{p.get('category','?')}]")
            print(f"  triggers: {p['triggers'][:2]}")
            print(f"  command:  {p['command'][:80]}")
            print(f"  learner:  {p.get('description_learner','')[:80]}")
            print()

    print("  Run with --auto-noob to auto-fill, or edit patterns.json manually.")
    print()


if __name__ == "__main__":
    main()
