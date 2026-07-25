<#
.SYNOPSIS
  One-time seed: copies your real, already-logged-in Chrome profile into
  scraper/browser_profile/ so the scraper starts "warm" - already trusted
  by Reddit/X - instead of hitting fresh-device verification flows that
  don't reliably work under browser automation (X's Prelude fraud-check
  SDK fails to initialize in a Playwright-driven browser, breaking the
  "Confirm your account" step server-side).

.IMPORTANT
  Close ALL Chrome windows before running this - Chrome locks its profile
  folder while running, and a locked/in-use copy can end up corrupted.

.USAGE
  From the project root or scraper/ folder:
    powershell -ExecutionPolicy Bypass -File .\scraper\seed-profile-from-chrome.ps1
#>

$ErrorActionPreference = 'Stop'

$scriptDir     = Split-Path -Parent $MyInvocation.MyCommand.Path
$destProfile   = Join-Path $scriptDir 'browser_profile'
$sourceRoot    = Join-Path $env:LOCALAPPDATA 'Google\Chrome\User Data'
$sourceProfile = Join-Path $sourceRoot 'Default'   # check chrome://version if you use a different profile

if (-not (Test-Path $sourceProfile)) {
    Write-Host "Couldn't find $sourceProfile." -ForegroundColor Red
    Write-Host "If you use a non-default Chrome profile, open chrome://version in Chrome, find 'Profile Path', and update `$sourceProfile` at the top of this script to match." -ForegroundColor Yellow
    exit 1
}

if (Get-Process chrome -ErrorAction SilentlyContinue) {
    Write-Host "Chrome is currently running - close ALL Chrome windows first, then re-run this script." -ForegroundColor Red
    exit 1
}

if (Test-Path $destProfile) {
    Write-Host "Removing existing $destProfile ..."
    Remove-Item -Recurse -Force $destProfile
}

New-Item -ItemType Directory -Path $destProfile | Out-Null
New-Item -ItemType Directory -Path (Join-Path $destProfile 'Default') | Out-Null

Write-Host "Copying Local State (holds the key cookies/saved passwords are decrypted with)..."
Copy-Item (Join-Path $sourceRoot 'Local State') $destProfile

Write-Host "Copying profile data (skipping cache folders - can take a minute)..."
robocopy $sourceProfile (Join-Path $destProfile 'Default') /E /XD "Cache" "Code Cache" "GPUCache" "Service Worker" "blob_storage" "Crashpad" | Out-Null

Write-Host "`nDone - scraper/browser_profile/ now starts from your real logged-in Chrome session." -ForegroundColor Green
Write-Host "Run: python run_scraper.py"
Write-Host "`nNote: this copied your real cookies (incl. other logged-in sites) and, if saved, stored passwords into scraper/browser_profile/. It's already gitignored, but it's sensitive - treat that folder like a copy of your login credentials." -ForegroundColor Yellow
