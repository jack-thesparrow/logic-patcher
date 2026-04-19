#!/usr/bin/env bash
# Build self-contained Windows EXEs via PyInstaller (run from project root on Windows or in CI).
# Python runtime and PySide6 are fully bundled — no separate install required on the target machine.
set -euo pipefail

APP="logic-patcher"

echo "Installing build tools..."
pip install "pyinstaller>=6.0" --quiet
pip install -e ".[gui]" --quiet
pip install "Pillow>=9.0" --quiet

echo "Generating icon.ico from icon.svg..."
export QT_QPA_PLATFORM=offscreen
python - <<'PYEOF'
import sys
from PySide6.QtCore import QSize
from PySide6.QtGui import QIcon, QImage
from PySide6.QtWidgets import QApplication
from PIL import Image

app = QApplication.instance() or QApplication(sys.argv)
icon = QIcon("assets/icon.svg")

sizes = [16, 32, 48, 64, 128, 256]
imgs = []
for s in sizes:
    pm = icon.pixmap(QSize(s, s))
    img = pm.toImage().convertToFormat(QImage.Format.Format_RGBA8888)
    pil = Image.frombytes("RGBA", (s, s), bytes(img.constBits()))
    imgs.append(pil)

imgs[0].save("assets/icon.ico", format="ICO",
             sizes=[(s, s) for s in sizes], append_images=imgs[1:])
print("icon.ico generated")
PYEOF

cat > _gui_entry.py <<'EOF'
from logic_patcher.gui import launch_gui
launch_gui()
EOF

cat > _cli_entry.py <<'EOF'
from logic_patcher.cli import main
main()
EOF

echo "Building GUI executable (no console window)..."
pyinstaller \
    --onefile \
    --windowed \
    --name "${APP}-gui" \
    --icon assets/icon.ico \
    --collect-all logic_patcher \
    --collect-all PySide6 \
    --add-data "assets/icon.svg;assets" \
    _gui_entry.py

echo "Building CLI executable..."
pyinstaller \
    --onefile \
    --console \
    --name "${APP}" \
    --collect-all logic_patcher \
    _cli_entry.py

rm -f _gui_entry.py _cli_entry.py

echo ""
echo "Done. Outputs in dist/"
ls dist/
