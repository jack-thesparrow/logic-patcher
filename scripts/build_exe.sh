#!/usr/bin/env bash
# Build Windows EXEs via PyInstaller (run from project root on Windows or Wine)
set -euo pipefail

APP="logic-patcher"

echo "Installing dependencies..."
pip install pyinstaller --quiet
pip install -e . --quiet

echo "Building GUI executable..."
pyinstaller \
    --onefile \
    --windowed \
    --name "${APP}-gui" \
    --icon assets/icon.ico \
    --add-data "assets/icon.ico;assets" \
    logic_patcher/gui.py

echo "Building CLI executable..."
pyinstaller \
    --onefile \
    --console \
    --name "${APP}" \
    logic_patcher/cli.py

echo "Done. Outputs in dist/"
ls -lh dist/
