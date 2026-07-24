# TrendPulse MVP - Phase 1 Refactor Instructions

## Quick Apply (Windows PowerShell)

```powershell
cd D:\dev\trendpulse-mvp

# 1. Backup originals
mkdir backup 2>$null
cp api/trends.py backup/trends_old.py
cp api/trends_new.py backup/trends_new_old.py
cp src/App.jsx backup/App_old.jsx
cp requirements.txt backup/requirements_old.txt

# 2. Apply clean versions
mv api/trends_clean.py api/trends.py -Force
mv src/App_clean.jsx src/App.jsx -Force
mv requirements_clean.txt requirements.txt -Force

# 3. Remove duplicates
rm api/trends_new.py

# 4. Optional: Remove dev-only files from repo
# rm test_twitter.py  # Keep if you use it for testing
```

## What Changed

### api/trends.py (was trends_new.py)
- Consolidated from 2 files to 1
- Cleaner variable naming
- Removed dead code
- Same functionality: Stocktwits + Twitter via trends24.in

### src/App.jsx
- Removed "Reddit" filter (no Reddit data yet)
- Added "Multi-Source" filter for tickers trending on multiple platforms
- Cleaner source badges (ST, X, Multi)
- Same functionality otherwise

### requirements.txt  
- Removed `praw` (not approved yet)
- Only: requests + beautifulsoup4

## Vercel Deploy

```bash
# From project root
vercel --prod

# Or if not installed:
npm i -g vercel
vercel login
vercel --prod
```

## Environment Variables (Vercel Dashboard)

Required for alerts:
- `DISCORD_WEBHOOK_URL` - Your Discord webhook
- `RESEND_API_KEY` - Resend.com API key
- `ALERT_EMAIL` - Email to receive alerts

## Test Locally

```bash
# Frontend
npm run dev

# API (separate terminal)
python api/trends.py
```

## File Count After Cleanup

| Before | After |
|--------|-------|
| api/trends.py | ✗ Deleted |
| api/trends_new.py | → api/trends.py |
| api/alert.py | ✓ Unchanged |
| src/App.jsx | ✓ Cleaned |
| requirements.txt | ✓ Slimmed |

Total: ~750 lines (down from ~900)
