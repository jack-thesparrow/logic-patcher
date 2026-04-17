# Logic Patcher

A utility to patch `.logic` binary files by finding and replacing encoded name and roll number fields. Ships with both a GUI and a CLI.

## Features

- Scans a folder (recursively) for `.logic` files and replaces the encoded name + roll number
- Non-`.logic` files are copied through unchanged
- Live log output and progress bar in the GUI
- Output written to a `replaced_output/` subfolder — originals are never modified
- Zero external dependencies (pure Python stdlib)

## Installation

### Prerequisites

| Platform | Command |
|---|---|
| Ubuntu / Debian | `sudo apt install python3 python3-venv python3-tk` |
| Fedora / RHEL | `sudo dnf install python3 python3-virtualenv python3-tkinter` |
| Arch | `sudo pacman -S python tk` |
| Windows / macOS | Install Python 3.8+ from [python.org](https://python.org) — tkinter is bundled |

### Quick setup (recommended)

```bash
# Linux / macOS
bash bootstrap.sh

# Windows (PowerShell)
.\bootstrap.ps1
```

The bootstrap script installs system dependencies, creates a `.venv`, installs the package, runs the tests, and prints everything you need to know next.

### Manual setup

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .\.venv\Scripts\activate
pip install -e .
```

## Usage

### GUI

```bash
logic-patcher-gui
```

1. Enter your **Full Name** and **Roll Number**
2. Browse to the target folder
3. Click **Start** — output appears in `replaced_output/` inside the chosen folder

### CLI

```bash
logic-patcher "Full Name" "ROLLNUMBER" /path/to/folder
```

Example:

```bash
logic-patcher "Jane Doe BT21CS001" "BT21CS001" ~/Downloads/exam-files
```

Output:

```
[OK] session1.logic (1 replacements)
   replaced: Old Name BT21CS001
[--] notes.logic (no match)

===== SUMMARY =====
Files changed: 1
Total replacements: 1
Output folder: ~/Downloads/exam-files/replaced_output
```

## Development

### Run tests

```bash
python -m unittest tests.test_core -v
```

### Build a Debian package (Linux)

```bash
bash scripts/build_deb.sh
# → build/deb/logic-patcher_1.0.0_all.deb
```

### Build Windows executables

```bash
bash scripts/build_exe.sh        # run on Windows or in CI
# → dist/logic-patcher-gui.exe
# → dist/logic-patcher.exe
```

## CI / CD

| Workflow | Trigger | What it does |
|---|---|---|
| `ci.yml` | Push / PR to `main` | Runs tests on Python 3.8, 3.10, 3.12 |
| `release.yml` | Push a `v*` tag | Builds `.exe` + `.deb`, publishes to PyPI, creates GitHub Release |

### Publishing a release

```bash
git tag v1.0.0
git push origin v1.0.0
```

The release workflow attaches `logic-patcher-gui.exe` (Windows) and `logic-patcher_1.0.0_all.deb` (Linux) to the GitHub Release automatically.

## Project structure

```
logic-patcher/
├── logic_patcher/
│   ├── core.py       # binary pattern matching and replacement
│   ├── cli.py        # argparse CLI entry point
│   ├── gui.py        # tkinter GUI entry point
│   └── utils.py      # shared file I/O and logging helpers
├── tests/
│   └── test_core.py
├── scripts/
│   ├── build_exe.sh  # PyInstaller — Windows EXEs
│   └── build_deb.sh  # dpkg — Debian package
├── assets/
│   ├── icon.ico
│   └── icon.png
├── bootstrap.sh      # Linux/macOS dev environment setup
├── bootstrap.ps1     # Windows dev environment setup
└── pyproject.toml
```

## License

MIT — see [LICENSE](LICENSE).
