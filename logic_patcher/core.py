import os, re

PATTERN = rb"\x00([\x05-\x50])([A-Za-z][^\x00]{2,60}?[Bb][Tt]\d{2}[A-Za-z]{2}\d{3})((?:x)?(?:sr|q))(\x00)"


def process_folder(name, roll, folder, log_callback=None):
    out_folder = os.path.join(folder, "replaced_output")
    os.makedirs(out_folder, exist_ok=True)

    new_content = (name + " " + roll).encode()
    new_len = len(new_content)

    total_replacements = 0
    changed_files = 0

    for root_dir, _, files in os.walk(folder):
        for fname in files:
            src = os.path.join(root_dir, fname)
            rel = os.path.relpath(src, folder)
            dst = os.path.join(out_folder, rel)

            os.makedirs(os.path.dirname(dst), exist_ok=True)

            if not fname.endswith(".logic"):
                with open(src, "rb") as f:
                    data = f.read()
                with open(dst, "wb") as f:
                    f.write(data)
                continue

            with open(src, "rb") as f:
                data = f.read()

            found = []

            def rep(m):
                found.append(m.group(2).decode(errors="replace"))
                return (
                    b"\x00" + bytes([new_len]) + new_content + m.group(3) + m.group(4)
                )

            new_data, n = re.subn(PATTERN, rep, data)

            with open(dst, "wb") as f:
                f.write(new_data)

            if n > 0:
                changed_files += 1
                total_replacements += n
                if log_callback:
                    log_callback(f"[OK] {rel} ({n} replacements)")
                    for old in found:
                        log_callback(f"   replaced: {old}")
            else:
                if log_callback:
                    log_callback(f"[--] {rel} (no match)")

    return changed_files, total_replacements, out_folder
