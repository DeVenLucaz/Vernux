# =============================================================================
# modules/updater.py — Self-Update & Package Cache Refresh
# Version: 0.6.0 | Phase 5 — Polish & Release
# =============================================================================

import os
import json
import subprocess
import re
import sys

VERNUX_DIR   = os.path.expanduser("~/.vernux")
INSTALL_DIR  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GITHUB_API   = "https://api.github.com/repos/DeVenLucaz/Vernux/releases/latest"
RAW_BASE     = "https://raw.githubusercontent.com/DeVenLucaz/Vernux/main"
PKG_CACHE_URL = f"{RAW_BASE}/data/pkg_cache.json"
PATTERNS_URL  = f"{RAW_BASE}/data/patterns.json"
RECIPES_URL   = f"{RAW_BASE}/data/recipes.json"


def _run(cmd: str, capture: bool = True) -> tuple[str, int]:
    try:
        r = subprocess.run(
            cmd, shell=True, capture_output=capture,
            text=True, timeout=30
        )
        return r.stdout.strip(), r.returncode
    except subprocess.TimeoutExpired:
        return "", -1
    except Exception as e:
        return str(e), -1


def _fetch_json(url: str) -> dict | None:
    """Fetch JSON from a URL via curl."""
    out, code = _run(f"curl -s --max-time 15 '{url}'")
    if code != 0 or not out:
        return None
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return None


def _fetch_raw(url: str) -> str | None:
    """Fetch raw content from a URL."""
    out, code = _run(f"curl -s --max-time 30 '{url}'")
    return out if code == 0 and out else None


def get_current_version() -> str:
    try:
        from modules import VERSION
        return VERSION
    except Exception:
        return "0.0.0"


def compare_versions(current: str, latest: str) -> bool:
    """Returns True if latest > current."""
    def parse(v: str) -> tuple:
        v = v.lstrip("v")
        parts = v.split(".")
        try:
            return tuple(int(p) for p in parts)
        except ValueError:
            return (0, 0, 0)
    return parse(latest) > parse(current)


def check_for_update() -> dict:
    """
    Check GitHub releases API for a newer version.
    Returns {available: bool, latest_version: str, current_version: str, url: str}
    """
    current = get_current_version()
    data    = _fetch_json(GITHUB_API)

    if not data:
        return {
            "available":       False,
            "latest_version":  current,
            "current_version": current,
            "url":             "",
            "error":           "Could not reach GitHub — check your internet."
        }

    latest = data.get("tag_name", "").lstrip("v")
    url    = data.get("html_url", "")

    return {
        "available":       compare_versions(current, latest),
        "latest_version":  latest,
        "current_version": current,
        "url":             url,
        "error":           "",
    }


def do_code_update() -> dict:
    """
    Pull latest code from GitHub via git pull.
    Returns {ok: bool, message: str}
    """
    # Check git available
    _, code = _run("command -v git")
    if code != 0:
        return {"ok": False, "message": "git not found. Run: pkg install git"}

    # Check if we're in a git repo
    _, git_code = _run(f"git -C '{INSTALL_DIR}' rev-parse --git-dir")
    if git_code != 0:
        return {"ok": False, "message": "VERNUX directory is not a git repo. Re-install with install.sh"}

    # Pull
    out, code = _run(f"git -C '{INSTALL_DIR}' pull --ff-only")
    if code == 0:
        if "Already up to date" in out:
            return {"ok": True, "message": "Already up to date."}
        return {"ok": True, "message": f"Updated successfully.\n{out[:200]}"}
    else:
        return {"ok": False, "message": f"git pull failed: {out[:200]}"}


def refresh_pkg_cache() -> dict:
    """
    Fetch latest pkg_cache.json from GitHub.
    Returns {ok: bool, count: int, message: str}
    """
    raw = _fetch_raw(PKG_CACHE_URL)
    if not raw:
        return {"ok": False, "count": 0, "message": "Could not fetch package cache from GitHub."}

    try:
        data = json.loads(raw)
        packages = data.get("packages", [])
        if len(packages) == 0:
            return {"ok": False, "count": 0, "message": "Fetched empty package cache."}

        cache_path = os.path.join(INSTALL_DIR, "data", "pkg_cache.json")
        with open(cache_path, "w") as f:
            json.dump(data, f, indent=2)

        # Reload in-memory cache
        try:
            import modules.packages as pkg_module
            pkg_module._PKG_CACHE = None
        except Exception:
            pass

        return {"ok": True, "count": len(packages), "message": f"Package cache updated: {len(packages)} packages."}
    except Exception as e:
        return {"ok": False, "count": 0, "message": f"Failed to parse package cache: {e}"}


def refresh_patterns() -> dict:
    """Fetch latest patterns.json from GitHub."""
    raw = _fetch_raw(PATTERNS_URL)
    if not raw:
        return {"ok": False, "count": 0, "message": "Could not fetch patterns."}
    try:
        data     = json.loads(raw)
        patterns = data.get("patterns", [])
        if not patterns:
            return {"ok": False, "count": 0, "message": "Empty patterns received."}
        path = os.path.join(INSTALL_DIR, "data", "patterns.json")
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        # Reload matcher cache
        try:
            import modules.matcher as matcher
            matcher._PATTERNS_CACHE = None
        except Exception:
            pass
        return {"ok": True, "count": len(patterns), "message": f"Patterns updated: {len(patterns)}."}
    except Exception as e:
        return {"ok": False, "count": 0, "message": f"Failed: {e}"}


def refresh_recipes() -> dict:
    """Fetch latest recipes.json from GitHub."""
    raw = _fetch_raw(RECIPES_URL)
    if not raw:
        return {"ok": False, "count": 0, "message": "Could not fetch recipes."}
    try:
        data    = json.loads(raw)
        recipes = data.get("recipes", [])
        if not recipes:
            return {"ok": False, "count": 0, "message": "Empty recipes received."}
        path = os.path.join(INSTALL_DIR, "data", "recipes.json")
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        # Reload recipe cache
        try:
            import modules.recipes as rec
            rec._RECIPES_CACHE = None
        except Exception:
            pass
        return {"ok": True, "count": len(recipes), "message": f"Recipes updated: {len(recipes)}."}
    except Exception as e:
        return {"ok": False, "count": 0, "message": f"Failed: {e}"}


def run_full_update(verbose: bool = True) -> dict:
    """
    Full update pipeline:
      1. Check for new code version
      2. Pull if available
      3. Refresh pkg_cache, patterns, recipes regardless
    Returns summary dict.
    """
    results = {
        "code_update":   None,
        "pkg_cache":     None,
        "patterns":      None,
        "recipes":       None,
        "version_check": None,
    }

    # Version check
    ver_info = check_for_update()
    results["version_check"] = ver_info

    # Code update
    if ver_info.get("available"):
        results["code_update"] = do_code_update()
    else:
        results["code_update"] = {
            "ok": True,
            "message": f"Code up to date (v{ver_info['current_version']})"
        }

    # Always refresh data files
    results["pkg_cache"] = refresh_pkg_cache()
    results["patterns"]  = refresh_patterns()
    results["recipes"]   = refresh_recipes()

    return results
