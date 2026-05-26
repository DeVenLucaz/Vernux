# =============================================================================
# modules/doctor.py — Full Health Checker
# Version: 0.6.0 | Phase 5 — Polish & Release
# =============================================================================

import os
import sys
import subprocess
import json
import shutil

CONFIG_DIR   = os.path.expanduser("~/.vernux")
INSTALL_DIR  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR     = os.path.join(INSTALL_DIR, "data")

AGGRESSIVE_BRANDS = {"xiaomi", "redmi", "oppo", "realme", "vivo", "iqoo"}


def _run(cmd: str) -> tuple[str, int]:
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=6)
        return r.stdout.strip(), r.returncode
    except Exception:
        return "", 1


def _chk(name: str, status: str, msg: str, fix: str = "") -> dict:
    return {"name": name, "status": status, "message": msg, "fix": fix}


# ── Python & runtime ──────────────────────────────────────────────────────────

def check_python_version() -> dict:
    v = sys.version_info
    s = f"{v.major}.{v.minor}.{v.micro}"
    if v >= (3, 8):
        return _chk("Python version", "ok", s)
    return _chk("Python version", "fail", f"{s} — need 3.8+", "pkg install python3")


def check_python_deps() -> dict:
    """Check all stdlib modules VERNUX uses."""
    required = ["json", "os", "re", "subprocess", "shutil",
                "hashlib", "threading", "difflib"]
    missing  = []
    for mod in required:
        try:
            __import__(mod)
        except ImportError:
            missing.append(mod)
    if missing:
        return _chk("Python stdlib", "fail", f"Missing: {', '.join(missing)}")
    return _chk("Python stdlib", "ok", "All modules available")


# ── Storage ───────────────────────────────────────────────────────────────────

def check_storage_permission() -> dict:
    sdcard = "/sdcard"
    if os.path.exists(sdcard) and os.access(sdcard, os.R_OK):
        # Check write too
        if os.access(sdcard, os.W_OK):
            return _chk("Storage permission", "ok", "/sdcard readable + writable")
        return _chk("Storage permission", "warn", "/sdcard readable but not writable",
                    "Run: termux-setup-storage")
    return _chk("Storage permission", "warn", "/sdcard not accessible",
                "Run: termux-setup-storage  (then Allow the popup)")


def check_storage_space() -> dict:
    try:
        usage   = shutil.disk_usage(os.path.expanduser("~"))
        free_gb = usage.free / 1e9
        used_pct = int(usage.used / usage.total * 100)
        if free_gb < 0.2:
            return _chk("Storage space", "fail",
                        f"{free_gb:.2f}GB free ({used_pct}% used) — critically low",
                        "Free space: pkg autoclean && rm unneeded files")
        if free_gb < 1.0:
            return _chk("Storage space", "warn",
                        f"{free_gb:.1f}GB free ({used_pct}% used)",
                        "Consider: pkg autoclean to free cached packages")
        return _chk("Storage space", "ok", f"{free_gb:.1f}GB free ({used_pct}% used)")
    except Exception:
        return _chk("Storage space", "warn", "Could not check")


def check_sdcard_storage() -> dict:
    sdcard = "/sdcard"
    if not os.path.exists(sdcard):
        return _chk("SD card / internal", "warn", "Not mounted",
                    "Run: termux-setup-storage")
    try:
        usage = shutil.disk_usage(sdcard)
        free_gb = usage.free / 1e9
        if free_gb < 0.5:
            return _chk("SD card / internal", "warn", f"{free_gb:.1f}GB free — low")
        return _chk("SD card / internal", "ok", f"{free_gb:.1f}GB free")
    except Exception:
        return _chk("SD card / internal", "warn", "Could not read SD card usage")


# ── RAM ───────────────────────────────────────────────────────────────────────

def check_ram() -> dict:
    try:
        with open("/proc/meminfo") as f:
            lines = f.readlines()
        total_kb = avail_kb = 0
        for l in lines:
            if l.startswith("MemTotal:"):
                total_kb = int(l.split()[1])
            elif l.startswith("MemAvailable:"):
                avail_kb = int(l.split()[1])
        total_gb = total_kb / 1024 / 1024
        avail_gb = avail_kb / 1024 / 1024
        used_pct = int((total_kb - avail_kb) / total_kb * 100) if total_kb else 0
        if avail_gb < 0.2:
            return _chk("RAM available", "warn",
                        f"{avail_gb:.2f}GB free of {total_gb:.1f}GB ({used_pct}% used) — low")
        return _chk("RAM available", "ok",
                    f"{avail_gb:.2f}GB free of {total_gb:.1f}GB ({used_pct}% used)")
    except Exception:
        return _chk("RAM available", "warn", "Could not read /proc/meminfo")


# ── Network ───────────────────────────────────────────────────────────────────

def check_internet() -> dict:
    out, code = _run("ping -c 1 -W 3 8.8.8.8 2>/dev/null")
    if code == 0:
        # Parse RTT
        m = __import__("re").search(r"time=([\d.]+)", out)
        rtt = f" ({m.group(1)}ms)" if m else ""
        return _chk("Internet", "ok", f"Connected{rtt}")
    # Try curl as fallback
    _, code2 = _run("curl -s --max-time 5 https://8.8.8.8 2>/dev/null || true")
    _, code3 = _run("curl -s --max-time 5 https://github.com 2>/dev/null || true")
    if code3 == 0:
        return _chk("Internet", "ok", "Connected (GitHub reachable)")
    return _chk("Internet", "warn", "No response — check WiFi or mobile data")


# ── Packages ──────────────────────────────────────────────────────────────────

def check_package(pkg: str, display: str = None) -> dict:
    name = display or pkg
    out, code = _run(f"command -v {pkg}")
    if code == 0 and out:
        version_out, _ = _run(f"{pkg} --version 2>/dev/null | head -1")
        ver = version_out.split("\n")[0][:40] if version_out else "installed"
        return _chk(name, "ok", ver)
    # dpkg fallback
    out2, code2 = _run(f"dpkg -l {pkg} 2>/dev/null | grep '^ii' | head -1")
    if code2 == 0 and out2:
        return _chk(name, "ok", "installed")
    return _chk(name, "warn", "Not installed", f"pkg install {pkg}")


def check_termux_api() -> dict:
    out, code = _run("command -v termux-battery-status")
    if code == 0:
        return _chk("termux-api", "ok", "Installed")
    return _chk("termux-api", "warn", "Not installed",
                "pkg install termux-api  (+ install Termux:API app from F-Droid)")


# ── Git config ────────────────────────────────────────────────────────────────

def check_git_config() -> dict:
    name,  _ = _run("git config --global user.name")
    email, _ = _run("git config --global user.email")
    branch, _ = _run("git config --global init.defaultBranch")
    missing = []
    if not name:  missing.append("user.name")
    if not email: missing.append("user.email")
    if not missing:
        br_note = "" if branch == "main" else f" (defaultBranch={branch or 'master'})"
        return _chk("git config", "ok", f"{name} <{email}>{br_note}")
    fix = " && ".join([
        f'git config --global user.name "Your Name"' if "user.name" in missing else "",
        f'git config --global user.email "you@email.com"' if "user.email" in missing else "",
    ]).strip(" && ")
    return _chk("git config", "warn", f"Missing: {', '.join(missing)}", fix)


# ── VERNUX data ───────────────────────────────────────────────────────────────

def check_vernux_data() -> dict:
    checks = {
        "patterns.json": ("patterns", 100),
        "pkg_cache.json": ("packages", 30),
        "recipes.json":   ("recipes",  5),
    }
    issues = []
    for fname, (key, min_count) in checks.items():
        fpath = os.path.join(DATA_DIR, fname)
        if not os.path.exists(fpath):
            issues.append(f"{fname} missing")
            continue
        try:
            with open(fpath) as f:
                d = json.load(f)
            count = len(d.get(key, []))
            if count < min_count:
                issues.append(f"{fname}: {count} {key} (expected ≥{min_count})")
        except Exception:
            issues.append(f"{fname}: corrupted")

    if issues:
        return _chk("VERNUX data files", "fail",
                    "; ".join(issues), "Run: python tools/build_db.py")
    return _chk("VERNUX data files", "ok", "patterns + packages + recipes OK")


def check_models_json() -> dict:
    path = os.path.join(INSTALL_DIR, "models.json")
    if not os.path.exists(path):
        return _chk("models.json", "warn", "Not found",
                    "Re-download from GitHub")
    try:
        with open(path) as f:
            d = json.load(f)
        count = len(d.get("models", []))
        return _chk("models.json", "ok", f"{count} model definitions")
    except Exception:
        return _chk("models.json", "warn", "Corrupted")


def check_device_profile() -> dict:
    path = os.path.join(CONFIG_DIR, "device.json")
    if not os.path.exists(path):
        return _chk("Device profile", "warn", "Not built yet",
                    "Run vernux once to build it")
    try:
        with open(path) as f:
            d = json.load(f)
        tier  = d.get("tier", "?")
        brand = d.get("brand", "?")
        ram   = d.get("ram", {}).get("total_gb", 0)
        return _chk("Device profile", "ok",
                    f"{brand.capitalize()}, {ram:.1f}GB RAM, {tier} tier")
    except Exception:
        return _chk("Device profile", "warn", "Corrupted — will rebuild on next run")


def check_vernux_config() -> dict:
    path = os.path.join(CONFIG_DIR, "config.json")
    if not os.path.exists(path):
        return _chk("VERNUX config", "warn", "Not created yet — run vernux first")
    try:
        with open(path) as f:
            d = json.load(f)
        mode    = d.get("mode", "noob")
        llm_en  = d.get("llm_enabled", False)
        return _chk("VERNUX config", "ok",
                    f"mode={mode}, llm_enabled={llm_en}")
    except Exception:
        return _chk("VERNUX config", "warn", "Corrupted",
                    f"Delete {path} and run vernux to recreate")


# ── LLM / AI ──────────────────────────────────────────────────────────────────

def check_llama_cpp() -> dict:
    for binary in ["llama-cli", "llama.cpp"]:
        out, code = _run(f"command -v {binary}")
        if code == 0 and out:
            ver_out, _ = _run(f"{binary} --version 2>&1 | head -1")
            return _chk("llama.cpp", "ok",
                        f"{binary} — {ver_out[:50] if ver_out else 'available'}")
    return _chk("llama.cpp", "warn", "Not installed (optional)",
                "pkg install llama-cpp  (or type 'install-model' in VERNUX)")


def check_llm_models() -> dict:
    models_dir = os.path.join(CONFIG_DIR, "models")
    if not os.path.exists(models_dir):
        return _chk("Local AI model", "warn", "No models directory — not installed yet",
                    "Type 'install-model' inside VERNUX")
    gguf_files = [f for f in os.listdir(models_dir) if f.endswith(".gguf")]
    if not gguf_files:
        return _chk("Local AI model", "warn", "No models downloaded (optional)",
                    "Type 'install-model' inside VERNUX")
    sizes = []
    for f in gguf_files:
        size_mb = os.path.getsize(os.path.join(models_dir, f)) // (1024*1024)
        sizes.append(f"{f[:35]} ({size_mb}MB)")
    return _chk("Local AI model", "ok", "; ".join(sizes[:2]))


# ── Android / Brand quirks ────────────────────────────────────────────────────

def check_brand_quirks() -> dict:
    brand_out, _ = _run("getprop ro.product.brand 2>/dev/null")
    brand = brand_out.lower().strip()
    if not brand or brand == "unknown":
        return _chk("Brand quirks", "ok", "Brand not detected or no known issues")

    QUIRK_MAP = {
        "xiaomi": "MIUI may kill background processes. Disable battery optimization for Termux.",
        "redmi":  "MIUI may kill background processes. Disable battery optimization for Termux.",
        "oppo":   "ColorOS may restrict storage. Settings → Apps → Termux → Permissions → Files.",
        "realme": "Realme UI may restrict background. Disable battery optimization.",
        "vivo":   "VivoUI may kill background. i Manager → Battery → Termux → Allow.",
        "iqoo":   "VivoUI may kill background. Check battery optimization settings.",
    }
    if brand in QUIRK_MAP:
        return _chk("Brand quirks", "warn",
                    f"{brand.capitalize()}: {QUIRK_MAP[brand]}")
    return _chk("Brand quirks", "ok", f"Brand: {brand.capitalize()} — no known issues")


def check_battery_optimization() -> dict:
    """Heuristic: check if termux-wake-lock works (needs termux-api)."""
    out, code = _run("command -v termux-battery-status")
    if code != 0:
        return _chk("Wake lock available", "warn",
                    "termux-api not installed — can't check",
                    "pkg install termux-api")
    return _chk("Wake lock available", "ok",
                "termux-wake-lock available (prevents background kill)")


# ── Git repo health ───────────────────────────────────────────────────────────

def check_git_repo() -> dict:
    out, code = _run(f"git -C '{INSTALL_DIR}' status --short 2>/dev/null | head -5")
    if code != 0:
        return _chk("VERNUX git repo", "warn",
                    "Not a git repo (can't auto-update)",
                    "Re-install with install.sh for auto-updates")
    branch_out, _ = _run(f"git -C '{INSTALL_DIR}' branch --show-current 2>/dev/null")
    branch = branch_out.strip() or "main"
    return _chk("VERNUX git repo", "ok", f"Clean, branch: {branch}")


# ── VERNUX version ────────────────────────────────────────────────────────────

def check_vernux_version() -> dict:
    try:
        from modules import VERSION, PHASE_NAME
        return _chk("VERNUX version", "ok", f"v{VERSION} ({PHASE_NAME})")
    except Exception:
        return _chk("VERNUX version", "warn", "Could not read version")


# ── run_all_checks ────────────────────────────────────────────────────────────

def run_all_checks() -> list[dict]:
    """Run all 20 health checks. Returns list of check result dicts."""
    return [
        # Runtime
        check_vernux_version(),
        check_python_version(),
        check_python_deps(),
        # Storage
        check_storage_space(),
        check_sdcard_storage(),
        check_storage_permission(),
        # RAM
        check_ram(),
        # Network
        check_internet(),
        # Core packages
        check_package("git",  "git"),
        check_package("curl", "curl"),
        check_package("wget", "wget"),
        check_package("zip",  "zip"),
        check_git_config(),
        check_termux_api(),
        # VERNUX data
        check_vernux_data(),
        check_models_json(),
        check_device_profile(),
        check_vernux_config(),
        check_git_repo(),
        # AI
        check_llama_cpp(),
        check_llm_models(),
        # Android
        check_brand_quirks(),
        check_battery_optimization(),
    ]


def run_quick_checks() -> list[dict]:
    """Faster subset — skip network and brand checks."""
    return [
        check_vernux_version(),
        check_python_version(),
        check_storage_space(),
        check_ram(),
        check_vernux_data(),
        check_vernux_config(),
        check_llm_models(),
    ]
