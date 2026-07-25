<#
.SYNOPSIS
  Launches a real, non-automated Chrome with remote debugging enabled,
  pointed at scraper/browser_profile/. Run this FIRST, log into Reddit
  and X normally in the window it opens, THEN run run_scraper.py — it
  attaches to this browser instead of launching its own.

.WHY
  Any Playwright-launched Chrome sets navigator.webdriver=true. X's
  Prelude fraud-check SDK fails to initialize when that's set ("core
  worker could not be instantiated"), leaving account verification stuck
  in a broken server-side session no matter what you type — this held
  true even with real Chrome, hidden automation flags, and a profile
  seeded from an already-logged-in session. A normally-launched Chrome
  never sets that flag, so verification works like it would for any
  regular user.

.USAGE
  From the scraper/ folder:
    powershell -ExecutionPolicy Bypass -File .\launch-chrome-debug.ps1

  Leave the window open. Run the scraper in a separate terminal once
  you're logged in.
#>

$ErrorActionPreference = 'Stop'

$scriptDir  = Split-Path -Parent $MyInvocation.MyCommand.Path
$profileDir = Join-Path $scriptDir 'browser_profile'

$chromeCandidates = @(
    "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
    "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
    "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe"
)
$chromePath = $chromeCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1

if (-not $chromePath) {
    Write-Host "Couldn't find chrome.exe in the usual install locations:" -ForegroundColor Red
    $chromeCandidates | ForEach-Object { Write-Host "  $_" }
    Write-Host "Edit `$chromeCandidates at the top of this script to add your actual Chrome path." -ForegroundColor Yellow
    exit 1
}

if (Get-Process chrome -ErrorAction SilentlyContinue) {
    Write-Host "Chrome is already running elsewhere. That's fine as long as it's not using" -ForegroundColor Yellow
    Write-Host "the same profile folder ($profileDir) — this launches a separate instance." -ForegroundColor Yellow
}

if (-not (Test-Path $profileDir)) {
    New-Item -ItemType Directory -Path $profileDir | Out-Null
}

Write-Host "Launching Chrome (remote debugging on port 9222)"
Write-Host "Profile: $profileDir"
Write-Host ""
Write-Host "Log into Reddit and X normally in the window that opens." -ForegroundColor Green
Write-Host "Then, in a separate terminal, run: python run_scraper.py" -ForegroundColor Green

Start-Process -FilePath $chromePath -ArgumentList @(
    "--remote-debugging-port=9222",
    "--user-data-dir=$profileDir",
    "--no-first-run",
    "--no-default-browser-check"
)
