# logic_patcher/core.py

import os
import re
from .utils import read_binary, write_binary, copy_file, logger, safe_decode

PATTERN = rb"\x00([\x05-\x50])([A-Za-z][^\x00]{2,60}?[Bb][Tt]\d{2}[A-Za-z]{2}\d{3})((?:x)?(?:sr|q))(\x00)"


def process_folder(name, roll, folder, log_callback=None, progress_callback=None):
    out_folder = os.path.join(folder, "replaced_output")
    os.makedirs(out_folder, exist_ok=True)

    new_content = (name + " " + roll).encode()
    new_len = len(new_content)

    total_replacements = 0
    changed_files = 0

    # Collect all files first, skipping the output directory
    all_files = []
    for root_dir, dirs, files in os.walk(folder):
        # Prevent walking into the output folder on re-runs
        dirs[:] = [d for d in dirs if os.path.join(root_dir, d) != out_folder]
        for fname in files:
            all_files.append((root_dir, fname))

    total_files = len(all_files)

    for i, (root_dir, fname) in enumerate(all_files):
        src = os.path.join(root_dir, fname)
        rel = os.path.relpath(src, folder)
        dst = os.path.join(out_folder, rel)

        if progress_callback:
            progress_callback(i + 1, total_files)

        if not fname.endswith(".logic"):
            copy_file(src, dst)
            continue

        data = read_binary(src)

        found = []

        def rep(m, _found=found):
            _found.append(m.group(2))
            return b"\x00" + bytes([new_len]) + new_content + m.group(3) + m.group(4)

        new_data, n = re.subn(PATTERN, rep, data)

        write_binary(dst, new_data)

        if n > 0:
            changed_files += 1
            total_replacements += n
            logger(log_callback, f"[OK] {rel} ({n} replacements)")
            for old in found:
                logger(log_callback, f"   replaced: {safe_decode(old)}")
        else:
            logger(log_callback, f"[--] {rel} (no match)")

    return changed_files, total_replacements, out_folder
