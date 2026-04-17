# logic_patcher/utils.py

import os
import shutil


def ensure_dir(path):
    """Create directory if it doesn't exist."""
    if path:
        os.makedirs(path, exist_ok=True)


def read_binary(path):
    """Read file as binary."""
    with open(path, "rb") as f:
        return f.read()


def write_binary(path, data):
    """Write binary data to file."""
    ensure_dir(os.path.dirname(path))
    with open(path, "wb") as f:
        f.write(data)


def copy_file(src, dst):
    """Copy file preserving metadata."""
    ensure_dir(os.path.dirname(dst))
    shutil.copy2(src, dst)


def safe_decode(data):
    """Safely decode bytes to string."""
    try:
        return data.decode("utf-8")
    except Exception:
        return data.decode(errors="replace")


def logger(callback, message):
    """Unified logging (CLI + GUI compatible)."""
    if callback:
        callback(message)
