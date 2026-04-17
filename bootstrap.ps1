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
        # Refresh PATH for this session
        $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH", "Machine") + ";" +
                    [System.Environment]::GetEnvironmentVariable("PATH", "User")
        $PYTHON = "python"
        Success "Python installed via winget"
    } else {
        Fail "winget not available. Install Python 3.8+ from https://python.org and re-run."
    }
}

# ── 2. Verify tkinter (bundled with python.org installer) ─────────────────────
Step "Verifying tkinter"

try {
    & $PYTHON -c "import tkinter" 2>&1 | Out-Null
    Success "tkinter is available"
} catch {
    Fail "tkinter not found. Re-install Python from https://python.org and make sure 'tcl/tk and IDLE' is checked during setup."
}

# ── 3. Create virtual environment ─────────────────────────────────────────────
Step "Setting up virtual environment"

if (Test-Path $VENV) {
    Warn ".venv already exists — skipping creation"
} else {
    & $PYTHON -m venv $VENV
    Success "Created $VENV"
}

$pip    = ".\$VENV\Scripts\pip.exe"
$python = ".\$VENV\Scripts\python.exe"

# ── 4. Install package ────────────────────────────────────────────────────────
Step "Installing logic-patcher (editable)"

& $pip install --upgrade pip --quiet
& $pip install -e . --quiet
Success "Package installed"

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

# ── 7. Detect GitHub username from remote ────────────────────────────────────
$githubUser = "<your-github-username>"
try {
    $remoteUrl = git remote get-url origin 2>$null
    if ($remoteUrl -match "github\.com[:/]([^/]+)/") { $githubUser = $Matches[1] }
} catch { }

# ── 8. Print next steps ───────────────────────────────────────────────────────
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
    logic-patcher "Full Name BT21CS001" "BT21CS001" C:\path\to\folder

  Build .exe (run from project root):
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

  4. Enable branch protection on main:
       GitHub → Settings → Branches → Add rule for "main"
       ✓ Require status checks to pass → select "CI / test"
       ✓ Require branches to be up to date before merging

── Publishing a release ─────────────────────────────────

  Tag a version and push — the release workflow builds
  logic-patcher-gui.exe (Windows) + logic-patcher_*.deb (Linux)
  and attaches them to a GitHub Release automatically:

    git tag v1.0.0
    git push origin v1.0.0

  Before that works, set up PyPI trusted publishing:
    PyPI → Your project → Publishing → Add GitHub publisher
    Owner:    $githubUser
    Repo:     logic-patcher
    Workflow: release.yml
    Environment: pypi

════════════════════════════════════════════════════════

"@ -ForegroundColor White
