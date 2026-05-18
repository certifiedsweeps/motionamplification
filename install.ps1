# ═══════════════════════════════════════════════════════════════
#  Motion Amplifier — Windows Installer (PowerShell)
#
#  Run from PowerShell (as normal user — no admin needed):
#    Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
#    .\install.ps1
#
#  What it does:
#    1. Checks for Python 3.8+
#    2. Creates a virtual environment in %USERPROFILE%\motion-amplifier\
#    3. Installs dependencies
#    4. Downloads the two app scripts
#    5. Creates .bat launcher shortcuts on your Desktop
# ═══════════════════════════════════════════════════════════════

# ── CONFIG — update these URLs after you push to GitHub/Gist ──
$WebcamUrl  = "https://raw.githubusercontent.com/YOUR_USER/YOUR_REPO/main/motion_amplifier.py"
$AppUrl     = "https://raw.githubusercontent.com/YOUR_USER/YOUR_REPO/main/motion_amplifier_app.py"
$InstallDir = "$env:USERPROFILE\motion-amplifier"
$Desktop    = [Environment]::GetFolderPath("Desktop")

function Write-OK    { param($msg) Write-Host "[OK] $msg" -ForegroundColor Green }
function Write-Warn  { param($msg) Write-Host "[!]  $msg" -ForegroundColor Yellow }
function Write-Fail  { param($msg) Write-Host "[X]  $msg" -ForegroundColor Red; exit 1 }

Write-Host ""
Write-Host "  Magnifier Motion Amplifier - Windows Installer" -ForegroundColor Cyan
Write-Host "  -----------------------------------------------" -ForegroundColor Cyan
Write-Host ""

# ── 1. Python check ───────────────────────────────────────────
$pythonCmd = $null
foreach ($cmd in @("python", "python3", "py")) {
    try {
        $ver = & $cmd --version 2>&1
        if ($ver -match "Python (\d+)\.(\d+)") {
            $major = [int]$Matches[1]
            $minor = [int]$Matches[2]
            if ($major -ge 3 -and $minor -ge 8) {
                $pythonCmd = $cmd
                Write-OK "Python $major.$minor found ('$cmd')."
                break
            }
        }
    } catch {}
}

if (-not $pythonCmd) {
    Write-Fail ("Python 3.8+ not found.`n" +
                "Download from https://python.org/downloads/`n" +
                "Make sure to check 'Add Python to PATH' during install.")
}

# ── 2. Create install directory ───────────────────────────────
New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
Write-OK "Install directory: $InstallDir"

# ── 3. Virtual environment ────────────────────────────────────
$VenvDir = "$InstallDir\.venv"
if (-not (Test-Path $VenvDir)) {
    Write-Host "[..] Creating virtual environment..." -NoNewline
    & $pythonCmd -m venv $VenvDir
    Write-OK "Virtual environment created."
} else {
    Write-OK "Virtual environment already exists."
}

$Pip    = "$VenvDir\Scripts\pip.exe"
$Python = "$VenvDir\Scripts\python.exe"
$Streamlit = "$VenvDir\Scripts\streamlit.exe"

# ── 4. Install dependencies ───────────────────────────────────
Write-Host "[..] Installing dependencies (this may take a minute)..." -NoNewline
& $Pip install --quiet --upgrade pip 2>&1 | Out-Null
& $Pip install --quiet opencv-python numpy streamlit 2>&1 | Out-Null
Write-OK "Dependencies installed."

# ── 5. Download scripts ───────────────────────────────────────
function Download-File {
    param($Url, $Dest, $Name)
    try {
        Invoke-WebRequest -Uri $Url -OutFile $Dest -UseBasicParsing -ErrorAction Stop
        Write-OK "Downloaded $Name."
    } catch {
        Write-Warn "Could not download $Name. Copy it manually to $Dest"
    }
}

Download-File $WebcamUrl "$InstallDir\motion_amplifier.py"     "motion_amplifier.py"
Download-File $AppUrl    "$InstallDir\motion_amplifier_app.py" "motion_amplifier_app.py"

# ── 6. Desktop shortcuts (.bat) ───────────────────────────────

# Webcam launcher
$WebcamBat = @"
@echo off
title Motion Amplifier - Webcam
"$Python" "$InstallDir\motion_amplifier.py" %*
pause
"@
Set-Content -Path "$Desktop\Motion Amplifier (Webcam).bat" -Value $WebcamBat
Write-OK "Desktop shortcut created: 'Motion Amplifier (Webcam).bat'"

# Web app launcher
$AppBat = @"
@echo off
title Motion Amplifier - Web App
echo.
echo   Opening Motion Amplifier web app...
echo   Your browser will open at http://localhost:8501
echo   Close this window to stop the server.
echo.
start "" http://localhost:8501
"$Streamlit" run "$InstallDir\motion_amplifier_app.py"
pause
"@
Set-Content -Path "$Desktop\Motion Amplifier (Web App).bat" -Value $AppBat
Write-OK "Desktop shortcut created: 'Motion Amplifier (Web App).bat'"

# ── Done ──────────────────────────────────────────────────────
Write-Host ""
Write-Host "  Installation complete!" -ForegroundColor Green
Write-Host ""
Write-Host "  Two shortcuts are on your Desktop:"
Write-Host ""
Write-Host "    Motion Amplifier (Webcam).bat"
Write-Host "      Real-time webcam view with live sliders."
Write-Host ""
Write-Host "    Motion Amplifier (Web App).bat"
Write-Host "      Opens a browser — upload a video clip and download the result."
Write-Host ""
