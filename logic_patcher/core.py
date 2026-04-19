# logic_patcher/core.py

import os
import threading
from concurrent.futures import ThreadPoolExecutor
from .utils import read_binary, write_binary, logger

# Unique 20-byte sequence that immediately precedes the TC_STRING in every .logic file.
ANCHOR = bytes.fromhex('7371007e001fffffffffffffffff707070707070')

# I/O-bound work benefits from more threads than CPU count.
_MAX_WORKERS = min(32, (os.cpu_count() or 4) * 4)


def _read_student_string(data):
    """
    Locate the anchor, then parse the Java TC_STRING (tag 0x74) that follows.
    Returns (raw_str, tag_off) or (None, None).
    """
    idx = data.find(ANCHOR)
    if idx == -1:
        return None, None

    tag_off = idx + len(ANCHOR)
    if tag_off + 3 > len(data):
        return None, None
    if data[tag_off] != 0x74:
        return None, None

    length = int.from_bytes(data[tag_off + 1:tag_off + 3], 'big')
    end = tag_off + 3 + length
    if end > len(data):
        return None, None

    raw = data[tag_off + 3:end].decode('utf-8', errors='replace')
    return raw, tag_off


def _patch(data, tag_off, old_raw, new_raw):
    """
    Overwrite the TC_STRING in-place, updating the 2-byte big-endian length field.
    Returns the patched bytearray, or None on mismatch.
    """
    buf = bytearray(data)
    old_bytes = old_raw.encode('utf-8')
    new_bytes = new_raw.encode('utf-8')

    str_off = tag_off + 3
    if buf[str_off:str_off + len(old_bytes)] != old_bytes:
        return None

    new_len = len(new_bytes)
    buf[tag_off + 1] = (new_len >> 8) & 0xff
    buf[tag_off + 2] = new_len & 0xff
    buf[str_off:str_off + len(old_bytes)] = new_bytes
    return bytes(buf)


def _patch_one(src, dst, new_raw, label, log_callback):
    """Read, patch, and write a single .logic file. Returns (changed, reps)."""
    data = read_binary(src)
    raw, tag_off = _read_student_string(data)

    if raw is None:
        write_binary(dst, data)
        logger(log_callback, f"[--] {label} (anchor not found)")
        return 0, 0

    patched = _patch(data, tag_off, raw, new_raw)

    if patched is None:
        write_binary(dst, data)
        logger(log_callback, f"[!!] {label} (patch mismatch — skipped)")
        return 0, 0

    write_binary(dst, patched)
    logger(log_callback, f"[OK] {label}")
    logger(log_callback, f"   replaced: {repr(raw)}")
    return 1, 1


def process_folder(name, roll, folder, log_callback=None, progress_callback=None):
    out_folder = os.path.join(folder, "replaced_output")
    os.makedirs(out_folder, exist_ok=True)

    new_raw = name + " " + roll
    new_len = len(new_raw.encode('utf-8'))
    if new_len > 65535:
        raise ValueError(
            f"name+roll encodes to {new_len} bytes, exceeding Java writeUTF max of 65535."
        )

    all_files = []
    for root_dir, dirs, files in os.walk(folder):
        dirs[:] = [d for d in dirs if os.path.join(root_dir, d) != out_folder]
        for fname in files:
            if fname.endswith(".logic"):
                all_files.append((root_dir, fname))

    total = len(all_files)
    lock = threading.Lock()
    done_count = [0]
    changed_files = [0]
    total_replacements = [0]

    def process_one(args):
        root_dir, fname = args
        src = os.path.join(root_dir, fname)
        rel = os.path.relpath(src, folder)
        dst = os.path.join(out_folder, rel)

        changed, reps = _patch_one(src, dst, new_raw, rel, log_callback)

        with lock:
            done_count[0] += 1
            changed_files[0] += changed
            total_replacements[0] += reps
            current = done_count[0]

        if progress_callback:
            progress_callback(current, total)

    with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as pool:
        list(pool.map(process_one, all_files))

    return changed_files[0], total_replacements[0], out_folder


def _unique_dst(out_folder, fname):
    """Return a collision-free destination path, appending _1, _2 … as needed."""
    dst = os.path.join(out_folder, fname)
    if not os.path.exists(dst):
        return dst
    stem, ext = os.path.splitext(fname)
    i = 1
    while True:
        dst = os.path.join(out_folder, f"{stem}_{i}{ext}")
        if not os.path.exists(dst):
            return dst
        i += 1


def process_files(name, roll, file_paths, out_folder, log_callback=None, progress_callback=None):
    """Process an explicit list of .logic file paths, writing output to out_folder."""
    os.makedirs(out_folder, exist_ok=True)

    new_raw = name + " " + roll
    if len(new_raw.encode('utf-8')) > 65535:
        raise ValueError("name+roll exceeds Java writeUTF max of 65535 bytes.")

    logic_files = [p for p in file_paths if p.endswith('.logic')]
    total = len(logic_files)
    lock = threading.Lock()
    done_count = [0]
    changed_files = [0]
    total_replacements = [0]

    # Pre-allocate destinations to avoid races in _unique_dst
    dst_map = {}
    for src in logic_files:
        fname = os.path.basename(src)
        dst_map[src] = _unique_dst(out_folder, fname)

    def process_one(src):
        fname = os.path.basename(src)
        dst   = dst_map[src]
        changed, reps = _patch_one(src, dst, new_raw, fname, log_callback)

        with lock:
            done_count[0] += 1
            changed_files[0] += changed
            total_replacements[0] += reps
            current = done_count[0]

        if progress_callback:
            progress_callback(current, total)

    with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as pool:
        list(pool.map(process_one, logic_files))

    return changed_files[0], total_replacements[0], out_folder
