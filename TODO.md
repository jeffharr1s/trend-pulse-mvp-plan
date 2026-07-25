# TrendPulse TODO

Last updated: 2026-07-25

## Next time, in order

1. Terminal (project root): `Ctrl+C` to stop `vercel dev` if it's still running, then `npm run dev:local` again to pick up the latest `vercel.json` fix.
2. Reload `http://localhost:3000/` in the browser. If it's still blank, run:
   ```
   curl -s -w "\nHTTP %{http_code}\n" http://localhost:3000/api/trends
   ```
   and check what comes back, that pinpoints whether the dashboard issue is fixed or what's still broken.
3. Fix `TELEGRAM_CHANNELS` in `.env`, still has placeholder `channel1,channel2` as of last check. Replace with real public channel usernames (no `@`).
4. To run the scraper (Reddit + X + Telegram), two terminals in `scraper/`:
   - Terminal A: `.\launch-chrome-debug.ps1`, log into Reddit and X in the window that opens, leave it open
   - Terminal B: `python run_scraper.py`, press Enter once logged in

## Status as of today

**Fixed:**
- PowerShell scripts crashing from em dashes under legacy `powershell.exe`
- `vercel.json` invalid `runtime` string
- Locked `node_modules/.vite/deps` cache
- Locked `.vercel/cache` (Python venv setup)
- `vercel.json` invalid `maxDuration` field (local dev builder doesn't accept it)
- X's Prelude fraud-check SDK blocking account verification (fixed via CDP-attach to a manually-launched real Chrome instead of a Playwright-launched one)
- Scraper now recovers automatically if the browser crashes/closes mid-run, instead of failing every cycle forever until manually restarted

**Working:**
- Reddit scraping (confirmed)
- Telegram scraping mechanism (tested against a real public channel, just needs real channel names in `.env`)

**Not yet confirmed:**
- Dashboard actually rendering in the browser (was still blank as of the last test, fix applied but not re-tested)
- X scraping via the new CDP-attach flow (built and reasoned through, not yet confirmed working end-to-end)

**Deferred feature (paused mid-planning):**
- Source auto-discovery: scan scraped text for mentions of other candidate sources (e.g. `t.me/<channel>` links) and queue them for manual approval rather than auto-adding, to avoid pulling in scam/spam channels. Picks back up once the dashboard is confirmed working.

## Git

22 commits ahead of GitHub as of today. Run `npm run release` to bump the version, commit, and push whenever ready to publish.
