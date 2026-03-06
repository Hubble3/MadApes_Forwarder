# MadApes Forwarder — How to Use & Verify Everything Works

This guide explains **every feature** in the project and **how to verify** each one is working.

---

## Table of Contents

1. [Setup](#1-setup)
2. [Feature List](#2-feature-list)
3. [How to Verify Each Feature](#3-how-to-verify-each-feature)
4. [Troubleshooting](#4-troubleshooting)

---

## 1. Setup

### Prerequisites

- Python 3.11+
- Telegram account (userbot, not a bot)
- API credentials from [my.telegram.org/apps](https://my.telegram.org/apps)

### Installation

```bash
cd MadApes_Forwarder
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your values
```

### Get User IDs (for groups only)

For **groups**, only messages from `ALLOWED_USER_IDS` are forwarded. Channels forward all messages.

```bash
python get_user_ids.py
```

This lists every member in your source groups with their IDs. Add the IDs of users you want to allow to `ALLOWED_USER_IDS` in `.env`.

### Run the Bot

```bash
python main.py
```

First run: enter the code Telegram sends you (and 2FA password if enabled).

**⚠️ Important: Run only ONE instance** — If you run the bot in two places (e.g. local + host), you will get duplicate forwards, duplicate 1h/6h reports, and duplicate daily alerts. Use one instance only, or stop one before starting the other.

---

## 2. Feature List

| # | Feature | What It Does |
|---|---------|--------------|
| 1 | **Signal forwarding** | Monitors source groups/channels, detects contract addresses, enriches with DexScreener data, forwards to destination |
| 2 | **Market cap routing** | Routes signals to small-cap or large-cap destination based on MC |
| 3 | **Contract-only filtering** | Ignores messages without a contract address (ticker-only) |
| 4 | **Edited message catch** | Re-checks edits for ~30s when someone adds a contract after posting |
| 5 | **Duplicate protection** | One forward per token per 24h across all sources |
| 6 | **1h performance updates** | Sends winner updates to report group 1 hour after signal |
| 7 | **6h performance updates** | Sends winner updates to report group 6 hours after signal (only for 1h winners) |
| 8 | **Daily report** | End-of-day summary (winners, losers, active) sent at 11:55 PM in display timezone |
| 9 | **New Day message** | Sends "NEW DAY" at midnight to both destinations + report group |
| 10 | **Runner detection** | Near-real-time momentum alerts for fast movers |
| 11 | **Analytics** | Outcome classification, best MC range, daily insights in report |
| 12 | **DexScreener pair links** | Uses pair URL so the link matches the stats shown |
| 13 | **Signal links in reports** | 1h/6h/daily reports include "DexScreener" + "Our alert message" links |

---

## 3. How to Verify Each Feature

### Feature 1: Signal Forwarding

**What it does:** When a message with a contract address is posted in a source group/channel, it forwards the original message + an info block to a destination.

**How to verify:**

1. In a **source channel** (e.g. DD): Post a message with a real contract address (e.g. Solana: `GshtxEQsr4CSE1Q9BfDMvc3mf3QK2AnX3EQxGwptpump` or EVM: `0xebecb4e1e3cf94b450d20e9abf50d85cb5579b07`).
2. In a **source group** (e.g. MadApes): Same test, but the message must be from a user in `ALLOWED_USER_IDS`.

**Expected:** Within a few seconds you see in the destination:
- The original forwarded message
- A "TRADING ALERT" block with token name, address, price, MC, volume, DEX, links

**Logs to look for:**
```
✅ Claimed signal X for ...
✅ Got DexScreener data for ...
📤 Delivery destination: ...
✅ Delivered source msg ...
```

---

### Feature 2: Market Cap Routing

**What it does:** MC < threshold → small-cap destination; MC ≥ threshold → large-cap destination.

**How to verify:**

1. Post a token with MC < $90K (or your `MC_THRESHOLD`) → should go to `DESTINATION_UNDER_80K`.
2. Post a token with MC ≥ $90K → should go to `DESTINATION_80K_OR_MORE`.

**Logs to look for:**
```
📊 MC $65,553 < $90,000 → Routing to UNDER_THRESHOLD destination
📤 Delivery destination: Solana_Signals <90k mc
```
or
```
📊 MC $266,971 ≥ $90,000 → Routing to OVER_THRESHOLD destination
📤 Delivery destination: Solana_Signls ≥90k mc
```

---

### Feature 3: Contract-Only Filtering

**What it does:** Messages with only tickers (e.g. `$PEPE`) and no contract address are ignored.

**How to verify:**

1. Post: `Check out $PEPE!` (no contract) in a source.
2. **Expected:** Message is skipped.

**Logs to look for:**
```
⏳ Pending edit watch for message X: no contract yet (will re-check edits for ~30s)
⏭️  Skipping message X: No contract address detected (ticker-only signals are ignored)
```

---

### Feature 4: Edited Message Catch

**What it does:** If a message is posted without a contract, then edited within ~30s to add one, it gets processed.

**How to verify:**

1. Post: `New token!` (no contract).
2. Within ~30 seconds, edit it to add a contract address at the end.
3. **Expected:** The edited message is forwarded.

**Logs to look for:**
```
✏️  Edited message X in MadApes: contract detected, re-processing
✅ Edited message X: forwarded after contract was added
```

---

### Feature 5: Duplicate Protection

**What it does:** Same token is never forwarded twice within 24h, even if posted in multiple sources or edited.

**How to verify:**

1. Forward a signal for token X.
2. Post the same token (or same address) in another source group, or send a duplicate message.
3. **Expected:** Second message is skipped.

**Logs to look for:**
```
⏭️  Skipping message X: Claim failed (duplicate or race)
```
or
```
⏭️  Skipping message X: Same token forwarded recently (channel+discussion dedup)
```
or
```
⏭️  Skipping message X: Already processed (duplicate event)
```

---

### Feature 6: 1h Performance Updates

**What it does:** 1 hour after a signal is forwarded, the bot checks the price. If it's a winner (price up), it sends an update to `REPORT_DESTINATION`.

**How to verify:**

1. Forward a signal.
2. Wait 1 hour (or adjust timing in code for testing).
3. If the token is up, you should receive a "PERFORMANCE UPDATE (1h)" in the report group.

**Logs to look for:**
```
🔍 Checking X signals for 1h update...
✅ Updated signal X - WINNER (+X.XX%)
```

**Report group:** Look for a message like:
```
📊 PERFORMANCE UPDATE (1h)
🟣 SOLANA · Token Name ($SYMBOL)
📍 CA (tap to copy): ...
🟢 WINNER: +X.XX% (X.XXx)
📊 DexScreener | 🔗 Our alert message
```

---

### Feature 7: 6h Performance Updates

**What it does:** 6 hours after a signal, the bot re-checks 1h winners. If still up, it sends a 6h update to the report group.

**How to verify:**

1. Have a signal that was a 1h winner.
2. Wait 6 hours from the original forward.
3. If still up, you should receive a "PERFORMANCE UPDATE (6h)" in the report group.

**Logs to look for:**
```
🔍 Checking X signals for 6h update...
✅ Updated signal X - Still WINNER (+X.XX%)
```

---

### Feature 8: Daily Report

**What it does:** At **11:55 PM** in your `DISPLAY_TIMEZONE` (e.g. Maryland), sends a daily summary to `REPORT_DESTINATION` with winners, losers, active signals, and analytics.

**How to verify:**

1. Have at least one signal in the DB.
2. Wait until 11:55 PM in the display timezone, or run the bot at that time.

**Logs to look for:**
```
📊 Daily report started (Maryland 11:59 PM)
✅ Daily report sent for ...
```

**Report group:** Long message with sections like:
```
📊 DAILY REPORT — January 31, 2026
...
🟢 WINNERS (X)
...
🔴 LOSERS (X)
...
⚪ ACTIVE (X)
...
```

---

### Feature 9: New Day Message

**What it does:** At **midnight** in your display timezone, sends "NEW DAY — Day, Date" to both destinations and the report group.

**How to verify:**

1. Run the bot at or past midnight (display timezone).
2. **Expected:** All three destinations receive:
   ```
   🌅 NEW DAY — Tuesday, January 28, 2026
   ```

**Logs to look for:**
```
🌅 NEW DAY sent to ...
✅ NEW DAY broadcast to 3 destination(s)
```

---

### Feature 10: Runner Detection

**What it does:** In the first ~hour after a signal, polls DexScreener every `RUNNER_POLL_INTERVAL` (default 90s). If a token shows strong momentum (velocity + volume acceleration), sends a "Runner detected" alert to the report group.

**How to verify:**

1. Forward a signal for a token that pumps quickly (e.g. +50% in 10 minutes).
2. Within 3–30 minutes, if it meets runner thresholds, you should get an alert in the report group.

**Logs to look for:**
```
🏃 Runner watcher started
```
(No specific "runner detected" log unless one triggers — check report group for the alert.)

**Report group:** Look for:
```
🔥 RUNNER DETECTED
🟣 SOLANA · Token Name
...
```

**Tuning:** If runners are missed, lower `RUNNER_VELOCITY_MIN` or `RUNNER_VOL_ACCEL_MIN` in `.env`. If you get too many false positives, raise them.

---

### Feature 11: Analytics

**What it does:** Classifies outcomes (failed, neutral, successful, runner), computes best MC range, best hour, and appends insights to the daily report.

**How to verify:**

1. Run for a full day with multiple signals.
2. Check the **daily report** — at the bottom you should see an analytics block, e.g.:
   ```
   📈 Analytics
   Outcomes: X failed | X neutral | X successful | X runners
   Best MC range: ...
   Best hour: ...
   ```

---

### Feature 12: DexScreener Pair Links

**What it does:** Uses the **pair URL** (not token URL) so the DexScreener link matches the exact pair used for stats (avoids pump vs Raydium confusion).

**How to verify:**

1. Forward a Solana token that has graduated from pump.fun.
2. Click the DexScreener link in the alert.
3. **Expected:** You land on the same pair whose stats are shown (e.g. Raydium), not the pump pair.

---

### Feature 13: Signal Links in Reports

**What it does:** 1h, 6h, and daily reports include:
- **📊 DexScreener** — link to the chart
- **🔗 Our alert message** — link to the original alert in your destination

**How to verify:**

1. Get a 1h or 6h winner update.
2. Check that both links are present and clickable.
3. **Expected:** DexScreener opens the chart; "Our alert message" opens the original alert in Telegram.

---

## 4. Troubleshooting

### Bot doesn't forward

- **Channels:** All messages are forwarded. Check you're in the channel and the message has a contract.
- **Groups:** Only messages from `ALLOWED_USER_IDS` are forwarded. Run `get_user_ids.py` and add IDs to `.env`.
- Check logs for `⏭️  Skipping` or `Claim failed`.

### No 1h/6h updates

- Ensure `REPORT_DESTINATION` is set and resolvable.
- 1h checks run every 5 minutes; signals are checked 1h after forward.
- Losers are not reported — only winners get updates.

### Daily report not sent

- Runs at **11:55 PM** in `DISPLAY_TIMEZONE`.
- Needs at least one signal in the DB.
- Check `REPORT_DESTINATION` is valid.

### Duplicate forwards or duplicate reports

- **Running two instances?** If the bot runs in two places (local + host, two terminals, etc.), you will get duplicate alerts. Stop one instance and use only one.
- Otherwise, duplicates are prevented by claim + idempotency. Check logs for skip reasons.

### Reset everything

```bash
python reset_local_state.py
```

Removes `signals.db` and session files. You’ll need to log in again on next run.

---

## Quick Reference: Log Messages

| Log | Meaning |
|-----|---------|
| `✅ Claimed signal X` | Token reserved, about to forward |
| `📤 Delivery destination: ...` | Where the alert is being sent |
| `✅ Delivered source msg` | Forward completed |
| `⏭️  Skipping message: No contract` | Ticker-only, ignored |
| `⏭️  Skipping: Claim failed` | Duplicate token |
| `⏭️  Skipping: Already processed` | Same (chat, msg) already handled |
| `⏭️  Skipping: Same token forwarded recently` | Channel+discussion dedup |
| `🔍 Checking X signals for 1h update` | Background checker running |
| `📊 Daily report started` | End-of-day report triggered |
| `🌅 NEW DAY sent to` | Midnight broadcast sent |
