# SEO Agent Runner — Setup

Phase 1 MVP: 4 Claude Code subagents orchestrated via the Agent SDK, results pinged to Telegram `@SEO_mirai_bot`.

## What's here

```
.claude/agents/seo/
  gsc-analyst.md        Pulls GSC data (striking-distance KWs, decliners, new queries)
  site-crawler.md       Inventories MDX content (orphans, thin, missing FAQ, hubs)
  cluster-architect.md  Plans topic clusters around a pillar
  seo-auditor.md        On-page QA for a single MDX (pass/warn/fail)

scripts/
  notify.py             Telegram helper (reads TELEGRAM_BOT_TOKEN/CHAT_ID)
  seo/morning_brief.py  Orchestrator: runs gsc-analyst + site-crawler, writes digest, pings Telegram
```

## One-time install (on any host — laptop or Mac Mini)

macOS Homebrew Python is PEP 668 managed, so we install the SDK into a
repo-local venv (`.venv-seo/`, gitignored).

```bash
cd ~/satellite-websites

# 1. Create the venv and install claude-agent-sdk
python3 -m venv .venv-seo
.venv-seo/bin/pip install -q claude-agent-sdk

# 2. Claude Code CLI (skip if `claude --version` works)
#    Otherwise: https://docs.claude.com/claude-code

# 3. Log the CLI into your subscription (once per host)
claude /login

# 4. Confirm env vars are in .env (copied from laptop)
grep -E '^TELEGRAM_(BOT_TOKEN|CHAT_ID)=' .env && echo "telegram ok"

# 5. Make sure GSC token exists
ls -l ~/.config/gsc-token.json
```

## Manual test

```bash
cd ~/satellite-websites

# Dry run — skip the Telegram ping
.venv-seo/bin/python scripts/seo/morning_brief.py --skip-telegram

# Single site
.venv-seo/bin/python scripts/seo/morning_brief.py --site glow-coded

# Full brief (writes report + sends Telegram)
.venv-seo/bin/python scripts/seo/morning_brief.py
```

Output lands in `scripts/seo/reports/YYYY-MM-DD-morning.md`.

## Cron entry (Mac Mini)

Add to `crontab -e`:

```cron
# SEO morning brief — 07:00 local daily
0 7 * * * cd /Users/david/satellite-websites && ./.venv-seo/bin/python scripts/seo/morning_brief.py >> scripts/seo/reports/cron.log 2>&1
```

Adjust the path if the repo lives elsewhere. Env vars for Telegram are loaded from `.env` by the script itself, so cron doesn't need them exported.

## Troubleshooting

- **`ModuleNotFoundError: claude_agent_sdk`** → re-create the venv: `python3 -m venv .venv-seo && .venv-seo/bin/pip install claude-agent-sdk`
- **`claude` not found in cron** → cron has a minimal PATH. Either use absolute path (`/usr/local/bin/claude`) or add `PATH=/usr/local/bin:/usr/bin:/bin:$HOME/.local/bin` at the top of crontab.
- **Agents error: "unknown subagent seo-gsc-analyst"** → the runner passes `setting_sources=["project"]` and `cwd` to the repo root, so it must be run from the repo root or with `cd` first.
- **Telegram silent** → check `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` in `.env`, then `python3 scripts/notify.py "test ping"`.
- **GSC 401** → the refresh token in `~/.config/gsc-token.json` is expired; re-run the GSC OAuth flow on the laptop and copy the updated file across.

## Next phases

- **Phase 2**: add `seo-indexer` (IndexNow + Bing + GSC sitemap resubmit) and `seo-ahrefs-researcher` (KW volume / backlink checks).
- **Phase 3**: writer subagents per persona (ava-chen, mina-park, nadia-okafor, james-reeves, …) orchestrated from `cluster-architect` briefs.
- **Phase 4**: PR-gate workflow — writers open a draft PR, `seo-auditor` reviews, only passing articles auto-merge.

## Mac Mini auto-sync (installed 2026-04-28)

Mac Mini at `david@davids-mac-mini.local` (user `agentdavid`) holds the repo
at `/Users/agentdavid/mirai-seo/satellite-websites` and auto-pulls from
`origin/main` every 30 minutes via launchd.

**What's installed:**
- `/Users/agentdavid/mirai-seo/sync-satellite.sh` — pulls + resets platform-
  specific package-lock drift
- `~/Library/LaunchAgents/com.satellite-websites.sync.plist` — runs the
  sync every 1800 s, logs to `~/mirai/logs/satellite-sync.log`

**To verify it's running:**
```bash
ssh david@davids-mac-mini.local "launchctl list | grep satellite"
ssh david@davids-mac-mini.local "tail -20 ~/mirai/logs/satellite-sync.log"
```

**To manually sync now:**
```bash
ssh david@davids-mac-mini.local "bash /Users/agentdavid/mirai-seo/sync-satellite.sh"
```

**Note:** The Mac Mini does NOT run satellite-websites cron jobs. All daily
article publishing happens via GitHub Actions (`daily-publish.yml`). The
Mac Mini just keeps a fresh checkout for ad-hoc local work.

