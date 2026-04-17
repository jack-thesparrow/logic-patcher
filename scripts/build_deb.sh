#!/usr/bin/env bash
# Build a Debian .deb package for logic-patcher (run from project root)
set -euo pipefail

VERSION="1.0.0"
PKG="logic-patcher"
ARCH="all"
BUILD_DIR="build/deb"
PKG_DIR="${BUILD_DIR}/${PKG}_${VERSION}_${ARCH}"

echo "Cleaning previous build..."
rm -rf "$BUILD_DIR"

echo "Creating package directory structure..."
mkdir -p "${PKG_DIR}/DEBIAN"
mkdir -p "${PKG_DIR}/usr/bin"
mkdir -p "${PKG_DIR}/usr/lib/python3/dist-packages"
mkdir -p "${PKG_DIR}/usr/share/applications"
mkdir -p "${PKG_DIR}/usr/share/pixmaps"

echo "Installing Python package files..."
pip3 install . --target "${PKG_DIR}/usr/lib/python3/dist-packages" --quiet

cat > "${PKG_DIR}/usr/bin/logic-patcher" <<'EOF'
#!/usr/bin/env python3
from logic_patcher.cli import main
main()
EOF
chmod +x "${PKG_DIR}/usr/bin/logic-patcher"

cat > "${PKG_DIR}/usr/bin/logic-patcher-gui" <<'EOF'
#!/usr/bin/env python3
from logic_patcher.gui import launch_gui
launch_gui()
EOF
chmod +x "${PKG_DIR}/usr/bin/logic-patcher-gui"

cp assets/icon.png "${PKG_DIR}/usr/share/pixmaps/logic-patcher.png"

cat > "${PKG_DIR}/usr/share/applications/logic-patcher.desktop" <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=Logic Patcher
Comment=Patch .logic binary files with name and roll number
Exec=logic-patcher-gui
Icon=logic-patcher
Categories=Utility;
Terminal=false
EOF

PKG_SIZE=$(du -sk "${PKG_DIR}/usr" | cut -f1)
cat > "${PKG_DIR}/DEBIAN/control" <<EOF
Package: ${PKG}
Version: ${VERSION}
Section: utils
Priority: optional
Architecture: ${ARCH}
Installed-Size: ${PKG_SIZE}
Depends: python3 (>= 3.8), python3-tk
Maintainer: Rahul Tudu <rahultudu4705@gmail.com>
Description: Logic Patcher
 A utility to patch .logic binary files by replacing encoded
 name and roll number fields.
EOF

echo "Building .deb..."
dpkg-deb --build "$PKG_DIR"

echo "Done: ${BUILD_DIR}/${PKG}_${VERSION}_${ARCH}.deb"
ls -lh "${BUILD_DIR}/"*.deb
