#!/usr/bin/env bash
# Build a self-contained Debian .deb via PyInstaller (run from project root).
# All dependencies — including Python and PySide6 — are bundled into the binary.
set -euo pipefail

VERSION="1.0.0"
PKG="logic-patcher"
ARCH="$(dpkg --print-architecture)"
BUILD_DIR="build/deb"
PKG_DIR="${BUILD_DIR}/${PKG}_${VERSION}_${ARCH}"

echo "Installing build tools..."
pip install "pyinstaller>=6.0" --quiet
pip install -e ".[gui]" --quiet

echo "Generating entry-point stubs..."
cat > _gui_entry.py <<'EOF'
from logic_patcher.gui import launch_gui
launch_gui()
EOF

cat > _cli_entry.py <<'EOF'
from logic_patcher.cli import main
main()
EOF

# Needed on headless build hosts so PySide6 can be imported during analysis
export QT_QPA_PLATFORM=offscreen

echo "Building GUI binary..."
pyinstaller \
    --onefile \
    --noconsole \
    --name "${PKG}-gui" \
    --collect-all logic_patcher \
    --collect-all PySide6 \
    --add-data "assets/icon.svg:assets" \
    _gui_entry.py

echo "Building CLI binary..."
pyinstaller \
    --onefile \
    --console \
    --name "${PKG}" \
    --collect-all logic_patcher \
    _cli_entry.py

rm -f _gui_entry.py _cli_entry.py

echo "Assembling .deb package structure..."
rm -rf "$BUILD_DIR"
mkdir -p "${PKG_DIR}/DEBIAN"
mkdir -p "${PKG_DIR}/usr/bin"
mkdir -p "${PKG_DIR}/usr/share/applications"
mkdir -p "${PKG_DIR}/usr/share/icons/hicolor/scalable/apps"

install -m 755 "dist/${PKG}-gui" "${PKG_DIR}/usr/bin/${PKG}-gui"
install -m 755 "dist/${PKG}"     "${PKG_DIR}/usr/bin/${PKG}"
cp assets/icon.svg "${PKG_DIR}/usr/share/icons/hicolor/scalable/apps/${PKG}.svg"

cat > "${PKG_DIR}/usr/share/applications/${PKG}.desktop" <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=Logic Patcher
Comment=Patch .logic binary files with name and roll number
Exec=${PKG}-gui
Icon=${PKG}
Categories=Utility;
Terminal=false
StartupWMClass=logic-patcher
EOF

PKG_SIZE=$(du -sk "${PKG_DIR}/usr" | cut -f1)
cat > "${PKG_DIR}/DEBIAN/control" <<EOF
Package: ${PKG}
Version: ${VERSION}
Section: utils
Priority: optional
Architecture: ${ARCH}
Installed-Size: ${PKG_SIZE}
Depends: libc6
Maintainer: Rahul Tudu <rahultudu4705@gmail.com>
Description: Logic Patcher
 Patch .logic binary files with student name and roll number.
 Python runtime and all GUI libraries are bundled — no separate
 Python or Qt installation required.
EOF

echo "Building .deb..."
dpkg-deb --build "$PKG_DIR"

echo ""
echo "Done: ${BUILD_DIR}/${PKG}_${VERSION}_${ARCH}.deb"
ls -lh "${BUILD_DIR}/"*.deb
