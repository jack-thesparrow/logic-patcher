#!/usr/bin/env bash
# Build Windows EXEs via PyInstaller (run from project root on Windows or in CI)
set -euo pipefail

APP="logic-patcher"

echo "Installing dependencies..."
pip install pyinstaller --quiet
pip install -e . --quiet

# PyInstaller cannot use files with relative imports as entry points.
# These wrappers use absolute imports after the package is installed above.
cat > _gui_entry.py <<'EOF'
from logic_patcher.gui import launch_gui
launch_gui()
EOF

cat > _cli_entry.py <<'EOF'
from logic_patcher.cli import main
main()
EOF

echo "Building GUI executable (windowed, no console)..."
pyinstaller \
    --onefile \
    --windowed \
    --name "${APP}-gui" \
    --icon assets/icon.ico \
    --collect-all logic_patcher \
    _gui_entry.py

echo "Building CLI executable..."
pyinstaller \
    --onefile \
    --console \
    --name "${APP}" \
    --collect-all logic_patcher \
    _cli_entry.py

rm -f _gui_entry.py _cli_entry.py

echo "Done. Outputs in dist/"
ls dist/
