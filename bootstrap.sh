#!/usr/bin/env bash
# Bootstrap script — sets up the full development environment from scratch.
# Run once after cloning: bash bootstrap.sh
set -euo pipefail

VENV=".venv"
PYTHON=""

# ── Colours ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

info()    { echo -e "${CYAN}[•]${RESET} $*"; }
success() { echo -e "${GREEN}[✓]${RESET} $*"; }
warn()    { echo -e "${YELLOW}[!]${RESET} $*"; }
error()   { echo -e "${RED}[✗]${RESET} $*"; exit 1; }
step()    { echo -e "\n${BOLD}── $* ──${RESET}"; }

# ── 1. Detect OS and install system packages ──────────────────────────────────
step "Detecting OS and installing system dependencies"

install_apt() {
    info "Detected Debian/Ubuntu — using apt"
    sudo apt-get update -qq
    sudo apt-get install -y python3 python3-venv python3-pip dpkg \
        libegl1 libgl1 libglib2.0-0
}

install_dnf() {
    info "Detected Fedora/RHEL — using dnf"
    sudo dnf install -y python3 python3-virtualenv python3-pip dpkg \
        mesa-libGL mesa-libEGL
}

install_pacman() {
    info "Detected Arch — using pacman"
    sudo pacman -Sy --noconfirm python python-virtualenv dpkg \
        mesa libgl
}

install_brew() {
    info "Detected macOS — using brew"
    if ! command -v brew &>/dev/null; then
        error "Homebrew not found. Install it from https://brew.sh then re-run."
    fi
    brew install python
}

if [[ "$OSTYPE" == "darwin"* ]]; then
    install_brew
elif command -v apt-get &>/dev/null; then
    install_apt
elif command -v dnf &>/dev/null; then
    install_dnf
elif command -v pacman &>/dev/null; then
    install_pacman
else
    warn "Unknown package manager — skipping system dependency install."
    warn "Make sure python3 and python3-venv are installed."
fi

# ── 2. Verify Python version ──────────────────────────────────────────────────
step "Checking Python version"

for candidate in python3.12 python3.11 python3.10 python3.9 python3.8 python3 python; do
    if command -v "$candidate" &>/dev/null; then
        PYTHON="$candidate"
        break
    fi
done

[[ -z "$PYTHON" ]] && error "No Python 3 interpreter found."

PY_VERSION=$("$PYTHON" -c 'import sys; print("%d.%d" % sys.version_info[:2])')
PY_MAJOR=$("$PYTHON" -c 'import sys; print(sys.version_info.major)')
PY_MINOR=$("$PYTHON" -c 'import sys; print(sys.version_info.minor)')

[[ "$PY_MAJOR" -lt 3 || ( "$PY_MAJOR" -eq 3 && "$PY_MINOR" -lt 8 ) ]] && \
    error "Python 3.8+ required, found $PY_VERSION"

success "Using $PYTHON ($PY_VERSION)"

# ── 3. Create virtual environment ─────────────────────────────────────────────
step "Setting up virtual environment"

if [[ -d "$VENV" ]]; then
    warn ".venv already exists — skipping creation"
else
    "$PYTHON" -m venv "$VENV"
    success "Created $VENV"
fi

# shellcheck disable=SC1091
source "$VENV/bin/activate"

# ── 4. Install package + GUI dependencies ─────────────────────────────────────
step "Installing logic-patcher with GUI dependencies"

pip install --upgrade pip --quiet
pip install -e ".[gui]" --quiet
success "Package and PySide6 installed"

# ── 5. Verify PySide6 ─────────────────────────────────────────────────────────
step "Verifying PySide6"

if python -c "import PySide6.QtWidgets" 2>/dev/null; then
    success "PySide6 is available"
else
    error "PySide6 import failed. Try: pip install PySide6"
fi

# ── 6. Install desktop entry and icon (for GNOME Activities / app switcher) ───
step "Installing desktop entry"

ICON_DIR="$HOME/.local/share/icons/hicolor/scalable/apps"
DESKTOP_DIR="$HOME/.local/share/applications"
ICON_SRC="$(pwd)/assets/icon.svg"
DESKTOP_FILE="$DESKTOP_DIR/logic-patcher.desktop"
GUI_BIN="$(pwd)/.venv/bin/logic-patcher-gui"

mkdir -p "$ICON_DIR" "$DESKTOP_DIR"
cp "$ICON_SRC" "$ICON_DIR/logic-patcher.svg"

cat > "$DESKTOP_FILE" <<DEOF
[Desktop Entry]
Version=1.0
Type=Application
Name=Logic Patcher
Comment=Patch .logic binary files with name and roll number
Exec=${GUI_BIN}
Icon=logic-patcher
Categories=Utility;
Terminal=false
StartupWMClass=logic-patcher
DEOF

# Refresh icon cache and desktop database
gtk-update-icon-cache -f -t "$HOME/.local/share/icons/hicolor" 2>/dev/null || true
touch "$HOME/.local/share/icons/hicolor"
update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true
success "Desktop entry installed"

# ── 7. Run tests ──────────────────────────────────────────────────────────────
step "Running test suite"

python -m unittest tests.test_core -v
success "All tests passed"

# ── 7. Print next steps ───────────────────────────────────────────────────────
cat <<EOF


${BOLD}════════════════════════════════════════════════════════${RESET}
${GREEN}  Development environment ready!${RESET}
${BOLD}════════════════════════════════════════════════════════${RESET}

${BOLD}Activate the venv in any new terminal:${RESET}
  source .venv/bin/activate

${BOLD}── Day-to-day commands ──────────────────────────────────${RESET}

  Run tests:
    python -m unittest tests.test_core -v

  Launch GUI:
    logic-patcher-gui

  Run CLI:
    logic-patcher "Full Name" "BT21CS001" /path/to/folder

  Build self-contained .deb (Linux only):
    bash scripts/build_deb.sh
    # output → build/deb/logic-patcher_1.0.0_<arch>.deb

  Build self-contained .exe (Windows only — or use GitHub CI):
    bash scripts/build_exe.sh

${BOLD}── Git workflow ─────────────────────────────────────────${RESET}

  You are on branch: $(git branch --show-current 2>/dev/null || echo "(unknown)")
  Commits ahead of origin: $(git rev-list --count origin/$(git branch --show-current 2>/dev/null)..HEAD 2>/dev/null || echo "unknown")

  1. Push the current branch:
       git push -u origin $(git branch --show-current 2>/dev/null || echo "<branch>")

  2. Open a Pull Request on GitHub and watch the CI run.

  3. Once CI is green, merge to main.

${BOLD}── Publishing a release ─────────────────────────────────${RESET}

  Tag a version and push — the release workflow builds
  logic-patcher-gui.exe (Windows) + logic-patcher_*.deb (Linux)
  and attaches them to a GitHub Release automatically:

    git tag v1.0.0
    git push origin v1.0.0

${BOLD}════════════════════════════════════════════════════════${RESET}

EOF
