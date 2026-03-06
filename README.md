# MadApes Forwarder

Telegram **userbot** that monitors groups/channels, detects **token contract addresses**, enriches with **DexScreener** data, routes by **market cap**, and tracks performance with **1h / 6h updates** plus a **daily report**.

## What it does

- **Sources**: multiple groups + channels (`SOURCE_GROUPS`)
- **Contract-only**: ignores ticker-only messages
- **Edited-message catch**: re-checks edits for ~30s when a contract is added after posting
- **Duplicate protection**: one forward per token per 24h across all sources (claim-before-forward)
- **Routing**:
  - MC < `MC_THRESHOLD` → `DESTINATION_UNDER_80K`
  - MC ≥ `MC_THRESHOLD` → `DESTINATION_80K_OR_MORE`
  - No MC → under-threshold
- **DexScreener link**: uses **pair URL** (not token URL) so the alert link matches the pair used for stats
- **Reporting**:
  - 1h/6h winner updates → `REPORT_DESTINATION` (includes Signal Link + DexScreener)
  - Daily report (11:59 PM display timezone) → `REPORT_DESTINATION` (includes analytics)
  - **New Day** message (midnight display timezone) → both destinations + report group
- **Runner detection**: near-real-time momentum alerts (velocity + volume acceleration) → `REPORT_DESTINATION`
- **Analytics**: outcome classification, best MC range, peak hour, daily insights in report

## Requirements

- Python 3.11+
- Telegram user account (userbot, not a bot)

```bash
pip install -r requirements.txt
```

## Configuration

Copy `.env.example` → `.env` and set values.

| Variable | Description |
|----------|-------------|
| `API_ID`, `API_HASH` | [my.telegram.org/apps](https://my.telegram.org/apps) |
| `PHONE_NUMBER` | With country code |
| `SESSION_NAME` | Session file prefix; use different for local vs host |
| `SOURCE_GROUPS` | Comma-separated groups/channels to watch |
| `ALLOWED_USER_IDS` | Comma-separated; who can trigger forwards (groups only) |
| `DESTINATION_UNDER_80K` | Small-cap destination |
| `DESTINATION_80K_OR_MORE` | Large-cap destination |
| `MC_THRESHOLD` | Market-cap cutoff (default 80000) |
| `REPORT_DESTINATION` | **Required** for reports and 1h/6h updates |
| `MAX_SIGNALS` | Max signals to keep (default 100) |
| `FORWARD_DELAY` | Seconds between forwards (default 1; 0 = no delay) |
| `DISPLAY_TIMEZONE` | e.g. `America/New_York` for alerts and reports |
| `RUNNER_VELOCITY_MIN` | % per minute for runner detection (default 1.5) |
| `RUNNER_VOL_ACCEL_MIN` | 5m vol vs 24h rate for runner (default 1.5) |
| `RUNNER_POLL_INTERVAL` | Runner watcher interval in seconds (default 90) |

Use `get_user_ids.py` to find user IDs for `ALLOWED_USER_IDS`.

## Run

```bash
python main.py
```

First run: Telegram login code (and 2FA if enabled).

**Run only one instance** — Running locally and on a host at the same time causes duplicate forwards and reports. Use one or the other.

## Session files (AuthKeyDuplicatedError)

Using the **same** session from two IPs at once (e.g. local + host) revokes it.

- Local: `SESSION_NAME=madapes_local`
- Host: `SESSION_NAME=madapes_host`

Create a host session:

1. Stop the bot everywhere.
2. Set `SESSION_NAME=madapes_host` in `.env`, run `python main.py`, log in once, then stop.
3. Deploy with `madapes_host.session` and `SESSION_NAME=madapes_host`.
4. Set local `.env` back to `SESSION_NAME=madapes_local`.

## Reset local state

Removes `signals.db` and all `*.session` files:

```bash
python reset_local_state.py
```

## Deploy (e.g. JustRunMy.App)

**ZIP**: `main.py`, `config.py`, `db.py`, `dexscreener.py`, `runner.py`, `analytics.py`, `utils.py`, `requirements.txt`, host session file. **No** `.env`; set env vars in the platform.

**Start**: `python -u main.py`  
**Env**: same keys as `.env` (including `SESSION_NAME`, `REPORT_DESTINATION`).

## Project structure

| File | Role |
|------|------|
| `main.py` | Entry point, Telegram handlers, orchestration |
| `config.py` | Configuration from `.env` |
| `db.py` | Database layer (signals, analytics) |
| `dexscreener.py` | DexScreener API client |
| `runner.py` | Real-time runner detection |
| `analytics.py` | Daily analytics and outcome classification |
| `utils.py` | Shared utilities |

## Notes

- Run only one instance (two = duplicate alerts).
- You need admin + “Post messages” on destination channels.
- Reports, 1h/6h updates, and runner alerts go only to `REPORT_DESTINATION`.
- New Day is sent to both destinations and the report group.
