# logic_patcher/core.py

import os
import re
import struct
import warnings
from .utils import read_binary, write_binary, copy_file, logger, safe_decode

# Java DataOutputStream.writeUTF() stores each string as a 2-byte big-endian unsigned short
# (the UTF-8 byte count) followed by the UTF-8 bytes.  In the .logic binary the layout is:
#
#   [high_byte=\x00] [low_byte=length] [content...] [suffix] [next_high_byte=\x00]
#
# The leading literal \x00 in the pattern asserts high byte == 0 (strings < 256 bytes).
# Group 1 is the low byte of the 2-byte length header.
# Group 2 is the content (the name+roll string itself).
# Group 3 is the Java serialization type suffix (sr, q, or xsr).
# Group 4 is the \x00 that begins the next string's 2-byte length header.
PATTERN = rb"\x00([\x05-\xff])([A-Za-z][^\x00]{2,245}?[Bb][Tt]\d{2}[A-Za-z]{2}\d{3})((?:x)?(?:sr|q))(\x00)"


def process_folder(name, roll, folder, log_callback=None, progress_callback=None):
    out_folder = os.path.join(folder, "replaced_output")
    os.makedirs(out_folder, exist_ok=True)

    new_content = (name + " " + roll).encode()
    new_len = len(new_content)

    if new_len > 65535:
        raise ValueError(
            f"name+roll encodes to {new_len} bytes, which exceeds the Java "
            f"writeUTF maximum of 65535 bytes."
        )
    if new_len > 255:
        warnings.warn(
            f"name+roll encodes to {new_len} bytes (> 255). The 2-byte Java length "
            f"header will have a non-zero high byte; PATTERN will not re-match on a "
            f"subsequent run.",
            UserWarning,
            stacklevel=2,
        )

    # struct.pack(">H", n) produces the same bytes as b"\x00" + bytes([n]) for n < 256,
    # but is explicit about the 2-byte big-endian Java writeUTF format and safe for n up to 65535.
    replacement_prefix = struct.pack(">H", new_len) + new_content

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

        def rep(m):
            found.append(m.group(2))
            return replacement_prefix + m.group(3) + m.group(4)

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
