<#
.SYNOPSIS
  Checks logs/scraper.log for the "real Chrome not found" fallback warning
  from run_scraper.py, installs Playwright's Chrome channel if needed, and
  clears the (possibly bot-flagged) persistent browser profile so the next
  scraper run starts clean.

.USAGE
  From the project root:
    powershell -ExecutionPolicy Bypass -File .\scraper\fix-chrome-detection.ps1
#>

$ErrorActionPreference = 'Stop'

$scriptDir   = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptDir
$logPath     = Join-Path $projectRoot 'logs\scraper.log'
$profilePath = Join-Path $scriptDir 'browser_profile'

# --- 1. Check the log for the Chrome-not-found warning -----------------
Write-Host "Checking $logPath for a Chrome-not-found warning..."

$needsChromeInstall = $false
if (Test-Path $logPath) {
    if (Select-String -Path $logPath -Pattern 'Real Chrome not available' -Quiet) {
        Write-Host "Found it - run_scraper.py fell back to bundled Chromium last time." -ForegroundColor Yellow
        $needsChromeInstall = $true
    } else {
        Write-Host "No warning found - real Chrome was already being used (or wasn't needed yet)."
    }
} else {
    Write-Host "No logs/scraper.log yet - installing Chrome anyway to be safe."
    $needsChromeInstall = $true
}

# --- 2. Install Playwright's Chrome channel if needed -------------------
if ($needsChromeInstall) {
    Write-Host "`nInstalling Chrome for Playwright (python -m playwright install chrome)..."
    python -m playwright install chrome
    if ($LASTEXITCODE -ne 0) {
        Write-Host "playwright install chrome failed (exit code $LASTEXITCODE) - see output above." -ForegroundColor Red
        exit 1
    }
    Write-Host "Chrome installed." -ForegroundColor Green
}

# --- 3. Delete the (possibly bot-flagged) persistent browser profile ---
if (Test-Path $profilePath) {
    Write-Host "`nDeleting $profilePath ..."
    Remove-Item -Recurse -Force $profilePath
    Write-Host "Deleted. You'll need to log into Reddit and X again on the next run." -ForegroundColor Green
} else {
    Write-Host "`nNo browser_profile directory found - nothing to delete."
}

Write-Host "`nDone. Run: python scraper\run_scraper.py"
