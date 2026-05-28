#!/usr/bin/env bash
# =============================================================================
# install.sh — VERNUX Installer
# Version: 0.5.0 | Phase 4 — Local AI
# =============================================================================
# Usage: bash install.sh
# One-line: curl -fsSL https://raw.githubusercontent.com/DeVenLucaz/Vernux/main/install.sh | bash
# =============================================================================

set -e

VERNUX_DIR="$HOME/.vernux"
VERNUX_REPO="https://github.com/DeVenLucaz/Vernux"
MODELS_DIR="$VERNUX_DIR/models"
MIN_PYTHON_MAJOR=3
MIN_PYTHON_MINOR=8

# Colors
RED='\033[0;31m'; YELLOW='\033[0;33m'; GREEN='\033[0;32m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

info()    { echo -e "${CYAN}  ℹ  $1${RESET}"; }
success() { echo -e "${GREEN}  ✔  $1${RESET}"; }
warn()    { echo -e "${YELLOW}  ⚠  $1${RESET}"; }
error()   { echo -e "${RED}  ✗  $1${RESET}"; }
die()     { error "$1"; exit 1; }

# ---------------------------------------------------------------------------
# Banner
# ---------------------------------------------------------------------------
echo ""
echo -e "${CYAN}${BOLD}╔════════════════════════════════════════╗${RESET}"
echo -e "${CYAN}${BOLD}║         VERNUX Installer               ║${RESET}"
echo -e "${CYAN}${BOLD}║  Natural Language for Termux — v0.7.6  ║${RESET}"
echo -e "${CYAN}${BOLD}╚════════════════════════════════════════╝${RESET}"
echo ""

# ---------------------------------------------------------------------------
# Step 1: Check Termux / Android
# ---------------------------------------------------------------------------
info "Checking environment..."

if [ ! -d "/data/data/com.termux" ]; then
    warn "This doesn't look like Termux. VERNUX is designed for Termux on Android."
    warn "Continuing anyway — some features may not work."
fi

# ---------------------------------------------------------------------------
# Step 2: Check Python
# ---------------------------------------------------------------------------
if ! command -v python3 &>/dev/null; then
    warn "Python 3 not found. Installing..."
    pkg install python3 -y || die "Failed to install Python 3. Run: pkg install python3"
fi

PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PY_MAJOR=$(echo $PY_VER | cut -d. -f1)
PY_MINOR=$(echo $PY_VER | cut -d. -f2)

if [ "$PY_MAJOR" -lt "$MIN_PYTHON_MAJOR" ] || \
   ([ "$PY_MAJOR" -eq "$MIN_PYTHON_MAJOR" ] && [ "$PY_MINOR" -lt "$MIN_PYTHON_MINOR" ]); then
    die "Python $MIN_PYTHON_MAJOR.$MIN_PYTHON_MINOR+ required. You have $PY_VER. Run: pkg install python3"
fi
success "Python $PY_VER"

# ---------------------------------------------------------------------------
# Step 3: Check git
# ---------------------------------------------------------------------------
if ! command -v git &>/dev/null; then
    info "Installing git..."
    pkg install git -y || die "Failed to install git"
fi
success "git $(git --version | awk '{print $3}')"

# ---------------------------------------------------------------------------
# Step 4: Check storage space
# ---------------------------------------------------------------------------
FREE_MB=$(df "$HOME" | tail -1 | awk '{print int($4/1024)}')
if [ "$FREE_MB" -lt 50 ]; then
    die "Less than 50MB free storage. Free up space and try again."
elif [ "$FREE_MB" -lt 200 ]; then
    warn "Low storage (${FREE_MB}MB free). Installation will proceed but model download may fail."
else
    success "Storage: ${FREE_MB}MB free"
fi

# ---------------------------------------------------------------------------
# Step 5: Create VERNUX directories
# ---------------------------------------------------------------------------
mkdir -p "$VERNUX_DIR" "$MODELS_DIR"
success "Created $VERNUX_DIR"

# ---------------------------------------------------------------------------
# Step 6: Clone or update repo
# ---------------------------------------------------------------------------
INSTALL_DIR="$HOME/vernux"

if [ -d "$INSTALL_DIR/.git" ]; then
    info "Updating existing VERNUX installation..."
    cd "$INSTALL_DIR"
    git pull --quiet
    success "Updated VERNUX"
else
    info "Downloading VERNUX..."
    if [ -d "$INSTALL_DIR" ]; then
        rm -rf "$INSTALL_DIR"
    fi
    git clone --quiet "$VERNUX_REPO.git" "$INSTALL_DIR" || \
        die "Failed to clone VERNUX. Check your internet connection."
    success "Downloaded VERNUX to $INSTALL_DIR"
fi

# ---------------------------------------------------------------------------
# Step 7: Build data files
# ---------------------------------------------------------------------------
info "Building pattern and package databases..."
cd "$INSTALL_DIR"
python3 tools/build_db.py > /dev/null 2>&1 && success "Data files built" || \
    warn "Data build had warnings — VERNUX will still work"

# ---------------------------------------------------------------------------
# Step 7b: Build offline command library (tldr-pages + LinuxCommandLibrary)
# ---------------------------------------------------------------------------
info "Building offline command library (710+ commands)..."
info "Downloading tldr-pages (~5MB, CC0 public domain)..."
if python3 tools/build_library_tldr.py --quiet 2>/dev/null; then
    success "Command library built (710+ commands offline)"
else
    warn "Library build failed — run manually: python3 tools/build_library_tldr.py"
    warn "VERNUX will still work, but explain/search will have fewer commands"
fi

# ---------------------------------------------------------------------------
# Step 8: Device profile
# ---------------------------------------------------------------------------
info "Profiling your device..."
RAM_GB=$(python3 -c 'import re; lines=open("/proc/meminfo").readlines(); kb=[int(l.split()[1]) for l in lines if l.startswith("MemTotal:")]; print(round(kb[0]/1024/1024,1)) if kb else print(2.0)' 2>/dev/null || echo "2.0")

BRAND=$(getprop ro.product.brand 2>/dev/null | tr '[:upper:]' '[:lower:]' || echo "unknown")
ANDROID=$(getprop ro.build.version.release 2>/dev/null || echo "unknown")
success "Device: ${RAM_GB}GB RAM, ${BRAND}, Android ${ANDROID}"

# Low-RAM warning
AGGRESSIVE_BRANDS="xiaomi redmi oppo realme vivo iqoo"
if echo "$AGGRESSIVE_BRANDS" | grep -qw "$BRAND"; then
    warn "Your device brand ($BRAND) may kill background processes."
    warn "Disable battery optimization for Termux before long tasks."
fi

# ---------------------------------------------------------------------------
# Step 9: Make vernux runnable
# ---------------------------------------------------------------------------
# Use $PREFIX/bin (standard Termux bin path) with hardcoded fallback
VERNUX_BIN="${PREFIX:-/data/data/com.termux/files/usr}/bin/vernux"
cat > "$VERNUX_BIN" << BINEOF
#!/usr/bin/env bash
cd "$INSTALL_DIR" && python3 vernux.py "\$@"
BINEOF

if chmod +x "$VERNUX_BIN" 2>/dev/null; then
    success "vernux command installed to $VERNUX_BIN"
else
    warn "Could not set permissions on $VERNUX_BIN — adding alias fallback"
fi

# Always add alias as a reliable fallback (harmless if binary works too)
if ! grep -q "alias vernux=" "$HOME/.bashrc" 2>/dev/null; then
    echo "alias vernux='cd $INSTALL_DIR && python3 vernux.py'" >> "$HOME/.bashrc"
    warn "Added 'vernux' alias to ~/.bashrc — run: source ~/.bashrc"
fi

# ---------------------------------------------------------------------------
# Step 10: Optional — AI model download
# ---------------------------------------------------------------------------
echo ""
echo -e "${YELLOW}${BOLD}  Optional: Local AI Model${RESET}"
echo -e "${YELLOW}  VERNUX works without a model (151 patterns cover most tasks).${RESET}"
echo -e "${YELLOW}  A model lets VERNUX handle anything you can throw at it.${RESET}"
echo ""

# Select appropriate model based on RAM
if python3 -c "import sys; sys.exit(0 if float('$RAM_GB') >= 2.5 else 1)" 2>/dev/null; then
    MODEL_NAME="Qwen2.5-Coder 1.5B Q4"
    MODEL_SIZE="~1GB"
    MODEL_FILE="qwen2.5-coder-1.5b-instruct-q4_k_m.gguf"
    MODEL_URL="https://huggingface.co/Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF/resolve/main/qwen2.5-coder-1.5b-instruct-q4_k_m.gguf"
else
    MODEL_NAME="Qwen2.5-Coder 1.5B Q4 (micro)"
    MODEL_SIZE="~1GB"
    MODEL_FILE="qwen2.5-coder-1.5b-instruct-q4_k_m.gguf"
    MODEL_URL="https://huggingface.co/Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF/resolve/main/qwen2.5-coder-1.5b-instruct-q4_k_m.gguf"
    warn "Low RAM device (${RAM_GB}GB). AI responses will be slow (10-60s per query)."
fi

echo -e "  Recommended: ${CYAN}${MODEL_NAME}${RESET} (${MODEL_SIZE})"
echo ""
read -p "  Download AI model? [y/N] " DOWNLOAD_MODEL

if echo "$DOWNLOAD_MODEL" | grep -qiE "^y(es)?$"; then
    # Check llama.cpp
    if ! command -v llama-cli &>/dev/null && ! command -v llama.cpp &>/dev/null; then
        info "llama.cpp not found. Installing from Termux packages..."
        pkg install llama-cpp -y 2>/dev/null || {
            warn "llama.cpp not available in pkg. Trying to build from source..."
            warn "This requires clang and make. Run: pkg install clang make"
            warn "Then: pkg install llama-cpp"
            warn "Skipping model download for now."
            DOWNLOAD_MODEL="n"
        }
    fi

    if echo "$DOWNLOAD_MODEL" | grep -qiE "^y(es)?$"; then
        MODEL_PATH="$MODELS_DIR/$MODEL_FILE"
        if [ -f "$MODEL_PATH" ]; then
            success "Model already downloaded: $MODEL_FILE"
        else
            info "Downloading $MODEL_NAME ($MODEL_SIZE)..."
            warn "Keep Termux open during download. Use tmux for safety."
            wget --show-progress -O "$MODEL_PATH" "$MODEL_URL" && {
                success "Model downloaded: $MODEL_FILE"
                # Enable LLM in config
                python3 -c "
import json, os
cfg_file = os.path.expanduser('~/.vernux/config.json')
cfg = {}
if os.path.exists(cfg_file):
    with open(cfg_file) as f: cfg = json.load(f)
cfg['llm_enabled'] = True
cfg['llm_model']   = '$MODEL_FILE'
with open(cfg_file, 'w') as f: json.dump(cfg, f, indent=2)
print('LLM enabled in config')
"
            } || {
                error "Download failed. Try again later with: vernux install-model"
                rm -f "$MODEL_PATH"
            }
        fi
    fi
else
    info "Skipping model download. You can add it later with: vernux install-model"
fi

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
echo ""
echo -e "${GREEN}${BOLD}╔════════════════════════════════════════╗${RESET}"
echo -e "${GREEN}${BOLD}║       VERNUX installed!                ║${RESET}"
echo -e "${GREEN}${BOLD}╚════════════════════════════════════════╝${RESET}"
echo ""
echo -e "  Start VERNUX: ${CYAN}vernux${RESET}"
echo -e "  Or:           ${CYAN}cd $INSTALL_DIR && python3 vernux.py${RESET}"
echo ""
echo -e "  Run ${CYAN}vernux doctor${RESET} to check everything is set up correctly."
echo ""
