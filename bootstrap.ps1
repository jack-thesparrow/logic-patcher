# Bootstrap script for Windows — sets up the full development environment.
# Run once after cloning:  .\bootstrap.ps1
# If blocked by execution policy, run:  powershell -ExecutionPolicy Bypass -File bootstrap.ps1
#Requires -Version 5.1
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$VENV = ".venv"

# ── Colours ───────────────────────────────────────────────────────────────────
function Info    { Write-Host "[•] $args" -ForegroundColor Cyan }
function Success { Write-Host "[✓] $args" -ForegroundColor Green }
function Warn    { Write-Host "[!] $args" -ForegroundColor Yellow }
function Step    { Write-Host "`n── $args ──" -ForegroundColor White }
function Fail    { Write-Host "[✗] $args" -ForegroundColor Red; exit 1 }

# ── 1. Locate Python ──────────────────────────────────────────────────────────
Step "Checking Python"

$PYTHON = $null
foreach ($candidate in @("python", "python3", "py")) {
    try {
        $ver = & $candidate --version 2>&1
        if ($ver -match "Python (\d+)\.(\d+)") {
            $major = [int]$Matches[1]; $minor = [int]$Matches[2]
            if ($major -ge 3 -and $minor -ge 8) {
                $PYTHON = $candidate
                Success "Found $candidate ($($ver.ToString().Trim()))"
                break
            }
        }
    } catch { }
}

if (-not $PYTHON) {
    Warn "Python 3.8+ not found — attempting install via winget..."
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        winget install --id Python.Python.3.12 --source winget --silent --accept-package-agreements --accept-source-agreements
        $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH", "Machine") + ";" +
                    [System.Environment]::GetEnvironmentVariable("PATH", "User")
        $PYTHON = "python"
        Success "Python installed via winget"
    } else {
        Fail "winget not available. Install Python 3.8+ from https://python.org and re-run."
    }
}

# ── 2. Create virtual environment ─────────────────────────────────────────────
Step "Setting up virtual environment"

if (Test-Path $VENV) {
    Warn ".venv already exists — skipping creation"
} else {
    & $PYTHON -m venv $VENV
    Success "Created $VENV"
}

$pip    = ".\$VENV\Scripts\pip.exe"
$python = ".\$VENV\Scripts\python.exe"

# ── 3. Install package + GUI dependencies ─────────────────────────────────────
Step "Installing logic-patcher with GUI dependencies (PySide6)"

& $pip install --upgrade pip --quiet
& $pip install -e ".[gui]" --quiet
Success "Package and PySide6 installed"

# ── 4. Verify PySide6 ─────────────────────────────────────────────────────────
Step "Verifying PySide6"

try {
    & $python -c "import PySide6.QtWidgets" 2>&1 | Out-Null
    Success "PySide6 is available"
} catch {
    Fail "PySide6 import failed. Try: pip install PySide6"
}

# ── 5. Run tests ──────────────────────────────────────────────────────────────
Step "Running test suite"

& $python -m unittest tests.test_core -v
if ($LASTEXITCODE -ne 0) { Fail "Tests failed" }
Success "All tests passed"

# ── 6. Check Git ──────────────────────────────────────────────────────────────
$currentBranch = ""
$aheadCount    = "unknown"
if (Get-Command git -ErrorAction SilentlyContinue) {
    $currentBranch = git branch --show-current 2>$null
    try { $aheadCount = git rev-list --count "origin/${currentBranch}..HEAD" 2>$null } catch { }
}

$githubUser = "<your-github-username>"
try {
    $remoteUrl = git remote get-url origin 2>$null
    if ($remoteUrl -match "github\.com[:/]([^/]+)/") { $githubUser = $Matches[1] }
} catch { }

# ── 7. Print next steps ───────────────────────────────────────────────────────
Write-Host @"

════════════════════════════════════════════════════════
  Development environment ready!
════════════════════════════════════════════════════════

Activate the venv in any new terminal:
  .\.venv\Scripts\activate

── Day-to-day commands ──────────────────────────────────

  Run tests:
    python -m unittest tests.test_core -v

  Launch GUI:
    logic-patcher-gui

  Run CLI:
    logic-patcher "Full Name" "BT21CS001" C:\path\to\folder

  Build self-contained .exe (from project root):
    bash scripts\build_exe.sh
    # output → dist\logic-patcher-gui.exe
    #          dist\logic-patcher.exe

  Note: .deb builds are Linux-only. Use GitHub CI for that.

── Git workflow ─────────────────────────────────────────

  Current branch : $currentBranch
  Commits ahead  : $aheadCount

  1. Push the current branch:
       git push -u origin $currentBranch

  2. Open a Pull Request on GitHub and watch the CI run.

  3. Once CI is green, merge to main.

── Publishing a release ─────────────────────────────────

  Tag a version and push — the release workflow builds
  logic-patcher-gui.exe (Windows) + logic-patcher_*.deb (Linux)
  and attaches them to a GitHub Release automatically:

    git tag v1.0.0
    git push origin v1.0.0

════════════════════════════════════════════════════════

"@ -ForegroundColor White
