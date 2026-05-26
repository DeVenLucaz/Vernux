# =============================================================================
# modules/device.py — Device Profiler & Compatibility Checker
# Version: 0.1.0 | Phase 0 — Foundation
# =============================================================================

import os
import shutil
import subprocess
import json

DEVICE_FILE = os.path.expanduser("~/.vernux/device.json")

# Device tier thresholds (RAM in GB)
TIERS = [
    (2.0, "micro"),
    (3.0, "low"),
    (6.0, "low-mid"),
    (8.0, "mid"),
]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _run(cmd: str) -> str:
    """Run a shell command, return stdout stripped. Empty string on failure."""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=5
        )
        return result.stdout.strip()
    except Exception:
        return ""


def _read_file(path: str) -> str:
    try:
        with open(path, "r") as f:
            return f.read()
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Individual detectors
# ---------------------------------------------------------------------------

def get_ram() -> dict:
    """
    Read /proc/meminfo and return total + available RAM in MB and GB.
    Returns: {total_mb, available_mb, total_gb, available_gb}
    """
    raw = _read_file("/proc/meminfo")
    result = {"total_mb": 0, "available_mb": 0, "total_gb": 0.0, "available_gb": 0.0}

    for line in raw.splitlines():
        if line.startswith("MemTotal:"):
            kb = int(line.split()[1])
            result["total_mb"] = kb // 1024
            result["total_gb"] = round(kb / 1024 / 1024, 2)
        elif line.startswith("MemAvailable:"):
            kb = int(line.split()[1])
            result["available_mb"] = kb // 1024
            result["available_gb"] = round(kb / 1024 / 1024, 2)

    return result


def get_cpu() -> dict:
    """
    Read /proc/cpuinfo. Returns model name, core count, architecture.
    """
    raw    = _read_file("/proc/cpuinfo")
    arch   = _run("uname -m")
    cores  = 0
    model  = "Unknown"

    for line in raw.splitlines():
        if line.startswith("processor"):
            cores += 1
        if line.startswith("Hardware") or line.startswith("model name"):
            parts = line.split(":", 1)
            if len(parts) == 2 and parts[1].strip():
                model = parts[1].strip()

    return {"model": model, "cores": cores, "arch": arch}


def get_storage() -> dict:
    """
    Returns internal (Termux home) and sdcard storage info in GB.
    """
    home = os.path.expanduser("~")
    result = {"internal_free_gb": 0.0, "internal_total_gb": 0.0,
              "sdcard_free_gb": 0.0, "sdcard_available": False}

    try:
        stat = shutil.disk_usage(home)
        result["internal_free_gb"]  = round(stat.free  / 1e9, 2)
        result["internal_total_gb"] = round(stat.total / 1e9, 2)
    except Exception:
        pass

    sdcard = "/sdcard"
    if os.path.exists(sdcard):
        try:
            stat = shutil.disk_usage(sdcard)
            result["sdcard_free_gb"]  = round(stat.free / 1e9, 2)
            result["sdcard_available"] = True
        except Exception:
            result["sdcard_available"] = False

    return result


def get_android_version() -> dict:
    """
    Read Android version and API level via getprop.
    Returns: {version, api_level}
    """
    version   = _run("getprop ro.build.version.release")
    api_level = _run("getprop ro.build.version.sdk")
    return {
        "version":   version   or "Unknown",
        "api_level": api_level or "Unknown"
    }


def get_brand() -> str:
    """
    Read phone brand via getprop. Returns lowercase brand string.
    e.g. 'xiaomi', 'samsung', 'oppo', 'vivo', 'realme', 'oneplus', 'unknown'
    """
    brand = _run("getprop ro.product.brand").lower()
    return brand or "unknown"


def classify_tier(ram_total_gb: float) -> str:
    """
    Classify device tier based on total RAM.
    micro < 2GB, low < 3GB, low-mid < 6GB, mid < 8GB, high 8GB+
    """
    for threshold, tier in TIERS:
        if ram_total_gb < threshold:
            return tier
    return "high"


def check_termux_api() -> bool:
    """Check if termux-api package is available (termux-battery-status as probe)."""
    result = _run("command -v termux-battery-status")
    return bool(result)


# ---------------------------------------------------------------------------
# Main profile builder
# ---------------------------------------------------------------------------

def build_profile() -> dict:
    """
    Build full device profile. Called once on first run.
    Saves result to ~/.vernux/device.json.
    Returns the profile dict.
    """
    ram     = get_ram()
    cpu     = get_cpu()
    storage = get_storage()
    android = get_android_version()
    brand   = get_brand()
    tier    = classify_tier(ram["total_gb"])
    has_api = check_termux_api()

    profile = {
        "ram":           ram,
        "cpu":           cpu,
        "storage":       storage,
        "android":       android,
        "brand":         brand,
        "tier":          tier,
        "termux_api":    has_api,
    }

    # Save to disk
    try:
        config_dir = os.path.expanduser("~/.vernux")
        os.makedirs(config_dir, exist_ok=True)
        with open(DEVICE_FILE, "w") as f:
            json.dump(profile, f, indent=2)
    except IOError:
        pass

    return profile


def load_profile() -> dict:
    """
    Load saved device profile. Builds fresh if not found.
    """
    if os.path.exists(DEVICE_FILE):
        try:
            with open(DEVICE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return build_profile()


def check_task_compat(task_id: str, profile: dict = None) -> dict:
    """
    Pre-task compatibility check.
    Returns: {ok: bool, warnings: [str]}

    Currently covers: heavy_install, llm_run, large_download
    """
    if profile is None:
        profile = load_profile()

    warnings = []
    tier     = profile.get("tier", "low")
    ram_free = profile.get("ram", {}).get("available_gb", 0)
    storage  = profile.get("storage", {}).get("internal_free_gb", 0)

    HEAVY_TASKS = {
        "heavy_install": {
            "min_storage_gb": 0.5,
            "warn_tiers":     ["micro"],
        },
        "llm_run": {
            "min_ram_gb":  1.0,
            "warn_tiers":  ["micro", "low"],
            "min_storage_gb": 1.0,
        },
        "large_download": {
            "min_storage_gb": 1.0,
            "warn_tiers":     [],
        }
    }

    task = HEAVY_TASKS.get(task_id)
    if not task:
        return {"ok": True, "warnings": []}

    if "min_ram_gb" in task and ram_free < task["min_ram_gb"]:
        warnings.append(
            f"Low available RAM ({ram_free:.1f}GB free). This might be slow or crash."
        )
    if "min_storage_gb" in task and storage < task["min_storage_gb"]:
        warnings.append(
            f"Low storage ({storage:.1f}GB free). This operation needs more space."
        )
    if tier in task.get("warn_tiers", []):
        warnings.append(
            f"Your device ({tier} tier) may struggle with this operation."
        )

    return {"ok": len(warnings) == 0, "warnings": warnings}
