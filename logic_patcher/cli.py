import argparse
from .core import process_folder


def main():
    parser = argparse.ArgumentParser(description="Logic File Replacer")
    parser.add_argument("name", help="Full Name")
    parser.add_argument("roll", help="Roll Number")
    parser.add_argument("folder", help="Target Folder")

    args = parser.parse_args()

    def log(msg):
        print(msg)

    changed, total, out = process_folder(args.name, args.roll, args.folder, log)

    print("\n===== SUMMARY =====")
    print(f"Files changed: {changed}")
    print(f"Total replacements: {total}")
    print(f"Output folder: {out}")


if __name__ == "__main__":
    main()
