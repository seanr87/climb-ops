# sleeper-pipeline

Read-only Sleeper data puller for **The Climb**. A GitHub Action fetches league
data twice a week and commits a Claude-ready digest to `data/`. Your local
clone doubles as the Claude Cowork folder.

## Setup (one time)
1. Create a repo (private is fine) and push these files.
2. Done. No secrets needed — the Sleeper API is public and read-only.
   The script resolves the league from `USERNAME` + `SEASON` + `LEAGUE_NAME`
   at the top of `scripts/pull_sleeper.py`.
3. Test it: **Actions tab → "Pull Sleeper data" → Run workflow**. After it
   finishes, `data/digest.md` should appear in the repo.
4. Clone the repo somewhere and point Claude Cowork at that folder.

## Weekly flow
- **Tue ~9 PM ET**: Action commits fresh digest.
- **Tue before bed**: open Cowork → "pull latest and give me waiver claims" → tap them into Sleeper.
- **Wed 3 AM ET**: waivers clear with your claims already in.
- **Sun ~8 AM ET**: Action commits fresh digest → "pull latest, set my lineup" → tap swaps in.

## How the scheduling works (since it's your first rodeo)
- `on.schedule.cron` uses **UTC**, standard 5-field cron (`min hour dom month dow`).
  `0 1 * * WED` = 01:00 UTC Wednesday = 9 PM Tuesday EDT, a few hours ahead of
  the Wed 3 AM waiver run.
  ⚠️ When DST ends in November, these drift 1 hour earlier ET (the Tue pull
  lands at 8 PM). Either live with it or update the crons to `0 2` / `0 13`
  to hold 9 PM Tue / 8 AM Sun.
- `workflow_dispatch` adds the manual **Run workflow** button in the Actions tab —
  great for testing and for ad-hoc pulls (e.g., before a trade decision).
- Scheduled runs execute on the default branch only, and GitHub may delay them
  a few minutes under load. GitHub also **disables schedules after 60 days of
  repo inactivity** — the bot's own commits count as activity, so this pipeline
  keeps itself alive during the season.
- `permissions: contents: write` + the default `GITHUB_TOKEN` is what lets the
  workflow commit back to the repo. No PAT needed.

## Files
- `scripts/pull_sleeper.py` — stdlib-only (no pip installs), pulls league,
  rosters, week matchups, transactions, 24h trending adds/drops, slim player DB.
- `data/digest.json` — full structured dump for Claude.
- `data/digest.md` — human-readable summary (roster, trending, transactions).
- `data/players_slim.json` — player name/team/injury lookup (~few hundred KB).
