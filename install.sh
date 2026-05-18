#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
#  Motion Amplifier — Mac / Linux Installer
#
#  Usage:
#    chmod +x install.sh && ./install.sh
#
#  What it does:
#    1. Checks for Python 3.8+
#    2. Creates a virtual environment in ~/motion-amplifier/
#    3. Installs dependencies
#    4. Downloads the two app scripts
#    5. Writes launcher shortcuts in the install folder
# ═══════════════════════════════════════════════════════════════

set -e

# ── CONFIG — update these URLs after you push to GitHub/Gist ──
WEBCAM_URL="https://raw.githubusercontent.com/YOUR_USER/YOUR_REPO/main/motion_amplifier.py"
APP_URL="https://raw.githubusercontent.com/YOUR_USER/YOUR_REPO/main/motion_amplifier_app.py"
INSTALL_DIR="$HOME/motion-amplifier"

# ── Colours ───────────────────────────────────────────────────
GREEN="\033[0;32m"; YELLOW="\033[1;33m"; RED="\033[0;31m"; NC="\033[0m"
info()  { echo -e "${GREEN}[✓]${NC} $*"; }
warn()  { echo -e "${YELLOW}[!]${NC} $*"; }
error() { echo -e "${RED}[✗]${NC} $*"; exit 1; }

echo ""
echo "  🔬  Motion Amplifier Installer"
echo "  ─────────────────────────────"
echo ""

# ── 1. Python check ───────────────────────────────────────────
if command -v python3 &>/dev/null; then
    PYTHON=python3
elif command -v python &>/dev/null; then
    PYTHON=python
else
    error "Python not found. Install Python 3.8+ from https://python.org and re-run."
fi

PY_VERSION=$($PYTHON -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PY_MAJOR=$($PYTHON -c "import sys; print(sys.version_info.major)")
PY_MINOR=$($PYTHON -c "import sys; print(sys.version_info.minor)")

if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 8 ]; }; then
    error "Python 3.8+ required (found $PY_VERSION). Please upgrade."
fi
info "Python $PY_VERSION found."

# ── 2. Create install directory ───────────────────────────────
mkdir -p "$INSTALL_DIR"
info "Install directory: $INSTALL_DIR"

# ── 3. Virtual environment ────────────────────────────────────
VENV="$INSTALL_DIR/.venv"
if [ ! -d "$VENV" ]; then
    info "Creating virtual environment…"
    $PYTHON -m venv "$VENV"
else
    info "Virtual environment already exists."
fi

PIP="$VENV/bin/pip"
PYTHON_VENV="$VENV/bin/python"

# ── 4. Install dependencies ───────────────────────────────────
info "Installing dependencies (opencv-python, numpy, streamlit)…"
$PIP install --quiet --upgrade pip
$PIP install --quiet opencv-python numpy streamlit

info "Dependencies installed."

# ── 5. Download scripts ───────────────────────────────────────
download_file() {
    local url="$1"
    local dest="$2"
    local name="$3"

    if command -v curl &>/dev/null; then
        curl -fsSL "$url" -o "$dest" && info "Downloaded $name." || {
            warn "Download failed for $name. Copy the file manually to $dest"
        }
    elif command -v wget &>/dev/null; then
        wget -q "$url" -O "$dest" && info "Downloaded $name." || {
            warn "Download failed for $name. Copy the file manually to $dest"
        }
    else
        warn "Neither curl nor wget found. Copy $name manually to $dest"
    fi
}

download_file "$WEBCAM_URL" "$INSTALL_DIR/motion_amplifier.py"     "motion_amplifier.py"
download_file "$APP_URL"    "$INSTALL_DIR/motion_amplifier_app.py" "motion_amplifier_app.py"

# ── 6. Write launchers ────────────────────────────────────────

# Webcam launcher
cat > "$INSTALL_DIR/run_webcam.sh" << 'EOF'
#!/usr/bin/env bash
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
"$DIR/.venv/bin/python" "$DIR/motion_amplifier.py" "$@"
EOF
chmod +x "$INSTALL_DIR/run_webcam.sh"

# Web app launcher
cat > "$INSTALL_DIR/run_webapp.sh" << 'EOF'
#!/usr/bin/env bash
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo ""
echo "  Opening Motion Amplifier web app…"
echo "  Visit http://localhost:8501 in your browser."
echo "  Press Ctrl+C to stop."
echo ""
"$DIR/.venv/bin/streamlit" run "$DIR/motion_amplifier_app.py"
EOF
chmod +x "$INSTALL_DIR/run_webapp.sh"

info "Launchers written."

# ── Done ──────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}  ✅  Installation complete!${NC}"
echo ""
echo "  To run:"
echo ""
echo "    Webcam (real-time):"
echo "      $INSTALL_DIR/run_webcam.sh"
echo ""
echo "    Web app (upload a clip):"
echo "      $INSTALL_DIR/run_webapp.sh"
echo "      then open http://localhost:8501"
echo ""
