# Design: Real-Time Runner Detection & Signal Analytics

**No code yet.** System design for two new layers: near-real-time runner detection and historical signal analytics.

---

## Current Project State (Summary)

### What We Have
- **Ingestion**: Multiple source groups/channels; contract-only; claim-before-forward; 24h duplicate window
- **Forward**: Two destinations (small-cap / large-cap) by MC threshold; pair URL in alert
- **Stored per signal**: entry price, liquidity, volume, pair URL, signal link, chain, DEX, token name/symbol, source_group
- **Background checker** (every 5 min): 1h/6h checks, New Day at midnight, daily report at 11:59 PM
- **DB**: `signals` table with status (active/win/loss), 1h/6h snapshots, current_* fields

### What We Don't Have
- Near-real-time momentum detection (runners explode in minutes)
- Historical analytics (patterns, best hours, MC ranges, etc.)
- Outcome classification (failed / neutral / successful / runner)
- Time-to-peak, max price/MC tracking

---

# Part 1: Real-Time Runner Detection

## 1. Architecture

### Option: Short-Interval Polling Loop (Recommended)

**Why not event-driven per token?**
- Would require WebSockets or push; DexScreener has no push API.
- Polling is the only realistic option.

**Why not a separate process?**
- Same DB, same Telegram client; sharing is simpler in one process.
- Runner engine runs as an additional **async task** in the same event loop.

**Design:**
- **Runner watcher**: Separate loop from `background_checker`, runs every **1–2 minutes**.
- **Scope**: Only tokens in **active** status, created **&lt; 1 hour ago** (early momentum window).
- **Coexistence**:
  - **Forward flow**: Unchanged; still claim → fetch → forward → update.
  - **1h/6h reports**: Unchanged; still run at fixed times.
  - **Duplicate prevention**: Unchanged; claim-before-forward only for new signals.
  - **Runner alerts**: Read-only on signals; no forward, only send to REPORT_DESTINATION.

**Flow:**
```
Runner watcher (every 1–2 min)
  → Get signals: status='active', age < 1h, not yet runner_alerted
  → For each: fetch DexScreener (reuse fetch_dexscreener_data)
  → Run detection logic
  → If runner: send alert to REPORT_DESTINATION, mark runner_alerted=1
  → Sleep
```

---

## 2. Detection Strategy (Core Logic)

Goal: **momentum continuation**, not just “price went up”. Reduce pump-and-dump noise.

### Strategy A: Velocity-Based (Price/Time)

**Signal**: Price increase per minute since entry.

- `velocity = (current_price - entry_price) / entry_price / minutes_elapsed`
- Threshold: e.g. &gt; 2% per minute over 3–5 min window.
- **Why runner**: Sustained velocity implies momentum, not a single spike.
- **Pump rejection**: Pumps often spike once then dump; velocity over several minutes filters that.

### Strategy B: Volume Acceleration

**Signal**: 5m or 1h volume rising vs 24h average.

- DexScreener: `volume.h5`, `volume.h1`, `volume.h24`.
- `acceleration = volume_5m * (24/0.083) / volume_24h` (5m annualized vs 24h).
- Threshold: e.g. &gt; 2× (volume in last 5m is &gt; 2× the 24h rate).
- **Why runner**: Real runners show volume pickup; pumps often have one burst then fade.

### Strategy C: Liquidity Expansion Without Dump

**Signal**: Liquidity up, price stable or up.

- `liq_growth = (current_liq - entry_liq) / entry_liq`
- Condition: liq_growth &gt; 20% AND price_change &gt; 0 (or small drawdown &lt; 5%).
- **Why runner**: Liquidity adds without dump = strong buying; dump would show liq up but price down.

### Strategy D: Micro-Pullback Rejection

**Signal**: Brief dip then recovery.

- Track: peak price since entry, current price.
- If price &gt; 1.1× entry and had a pullback &lt; 10% from peak and recovered &gt; peak: continuation.
- **Why runner**: Healthy runners often pull back slightly then extend; straight pumps often dump.

### Strategy E: Breakout After Consolidation

**Signal**: Flat/slow move then sharp move up.

- Compare price change over last 2–3 data points vs earlier window.
- If earlier: &lt; 5% over 5–10 min; recent: &gt; 15% over 2–3 min → breakout.
- **Why runner**: Consolidation then breakout is a classic pattern.

### Recommended Combination

**Phase 1 (minimal):**
- **A (velocity)** + **B (volume acceleration)**.
- Both must pass: e.g. velocity &gt; 1.5%/min AND volume_accel &gt; 1.5×.

**Phase 2 (richer):**
- Add **C (liquidity expansion)** as a booster (optional).
- Add **D (micro-pullback)** to avoid false positives on sharp reversals.

**Phase 3:**
- Add **E** when we have enough historical snapshots (needs price history).

---

## 3. Time Sensitivity

### Detection Latency

- **Target**: 3–8 minutes after first signal.
- **Polling**: Every **1–2 minutes** for tokens in the 0–60 min window.
- **Minimum age**: Do not run detection before **2–3 minutes** after entry (avoid noise).

### Intervals

| Age range     | Poll interval | Rationale                      |
|---------------|---------------|--------------------------------|
| 2–15 min      | 1 min         | Highest momentum probability   |
| 15–45 min     | 2 min         | Still relevant, fewer checks   |
| 45–60 min     | 3 min         | Hand-off to 1h report          |
| &gt; 60 min    | None          | 1h/6h handle from here         |

### API Usage

- DexScreener: **300 req/min** for token endpoint.
- With ~20 active signals in first hour, 1 min polling ≈ 20 req/min.
- Stagger requests (e.g. 1–2 sec between tokens) to avoid bursts.
- Cache per-token result for 60–90 sec to avoid duplicate calls if logic reuses.

---

## 4. Data Sources

### DexScreener Fields (per pair)

| Field                  | Use                          |
|------------------------|-------------------------------|
| `priceUsd`             | Velocity, pullback           |
| `priceChange.h5/h1/h24`| Momentum confirmation        |
| `volume.h5/h1/h24`     | Volume acceleration          |
| `liquidity.usd`        | Liquidity expansion          |
| `fdv`                  | MC context                    |
| `dexId`                | Pair type (pump vs Raydium)  |
| `pairCreatedAt`        | Pair age                      |
| `txns` (buys/sells)    | Optional: buy/sell ratio     |

### Single vs Multiple Pairs

- **Use primary pair only** (highest liquidity), same as today.
- Pair can change (pump → Raydium); we already pick best pair per fetch.
- No need to track multiple pairs for runner detection; keep it simple.

---

## 5. Output Behavior

### Where

- **Only** REPORT_DESTINATION. No change to destination groups.

### Message Type

- **“Runner detected”** or **“Momentum continuation”** — one clear label.
- Avoid “second alert” (confusing; not a new signal).

### Message Content

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔥 RUNNER DETECTED

🟣 SOLANA · Token ($SYM)
📍 CA (tap to copy): <code>full_address</code>

Entry: 4:24 PM | $0.000198 | MC $50K
Now:   $0.000312 | MC $78K

📈 +57.6% in 8 min | 7.2%/min velocity
💹 Vol 5m: 2.3× 24h rate

🔗 Signal Link | 📊 DexScreener
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

- Entry vs current (price, MC)
- Key metrics (e.g. % change, velocity, volume acceleration)
- Signal Link + DexScreener (reuse stored links)

---

## 6. State & Safety

### One Runner Alert per Token

- New column: `runner_alerted` (0/1) or `runner_alerted_at` (timestamp).
- Once set, never alert again for that signal.
- Query for runner check: `runner_alerted = 0` (or `runner_alerted_at IS NULL`).

### No Spam

- One alert per token.
- Optional: min time between runner alerts globally (e.g. 30 sec) to avoid bursts.

### No Flapping

- Require **two consecutive** detections before alerting (e.g. 1 min apart).
- Or use a short cooldown: if detected, wait 60 sec and re-check; if still positive, alert.
- Hysteresis: “confirmed” only after N successive passes.

### DB Changes

```sql
-- Add to signals
runner_alerted INTEGER DEFAULT 0
runner_alerted_at TEXT
runner_score REAL  -- optional: store composite score for analytics
```

---

## 7. Project Evolution

### Current Layout

```
main.py
  - forward_message, message_handler, edited_message_handler
  - background_checker (1h, 6h, New Day, daily report)
  - fetch_dexscreener_data, DB helpers
  - All in one module
```

### After Runner Engine

```
main.py (orchestration)
  - message handlers (unchanged)
  - background_checker (unchanged)
  - runner_watcher() — NEW async task
  - asyncio.create_task(runner_watcher()) at startup

runner.py (new module, optional)
  - get_signals_for_runner_check()
  - detect_runner(signal_row, current_data) -> bool
  - build_runner_alert_message()
  - send_runner_alert()
```

### Unchanged

- Forward flow, claim/save, routing
- 1h/6h checks, daily report, New Day
- Duplicate prevention

### Modular

- Runner logic in its own module.
- Detection thresholds in config (e.g. `RUNNER_VELOCITY_MIN`, `RUNNER_VOL_ACCEL_MIN`).

---

# Part 2: Signal Analytics & Performance Intelligence

## 1. Time-Based Analysis

### Stored at Signal Time

- `original_timestamp` (already have)
- Add: `hour_utc`, `day_of_week`, `session` (asia/eu/us) — computed once at save.

### Session Definition

- Asia: 00–08 UTC
- EU: 08–16 UTC
- US: 16–24 UTC

### Derived Later

- Time from entry → breakout (when price &gt; 1.2× entry)
- Time from entry → peak (max price)
- Duration of run (peak → first -20% from peak)

### Aggregation

- By hour: count signals, count runners, win rate.
- By day: weekend vs weekday.
- By session: which session has most runners.

---

## 2. Market-State at Signal Time

### Already Stored

- `original_market_cap`, `original_liquidity`, `original_volume`
- `source_group`, `chain`
- DEX is in pair/exchange; need to persist: add `original_dex_id` at save.

### Add at Save

- `original_dex_id` (pump vs raydium/etc.)
- `destination_type` ('under_80k' | 'over_80k') — which destination we sent to

### MC Buckets for Analysis

- 0–10K, 10–50K, 50–80K, 80–150K, 150K+

---

## 3. Outcome Classification

### Post-Hoc (Computed at 1h, 6h, or Daily)

| Outcome  | Definition (example)                          |
|----------|-----------------------------------------------|
| Failed   | Price &lt; 0.8× entry at 1h                    |
| Neutral  | 0.8× ≤ price ≤ 1.2× at 1h                    |
| Successful | Price &gt; 1.2× at 1h, not runner           |
| Runner   | Price &gt; 1.5× within 30 min, or runner_alerted |

### Data Needed

- `max_price_seen`, `max_price_seen_at` (from runner watcher + 1h/6h)
- `max_market_cap_seen`, `max_market_cap_seen_at`
- At 1h/6h we already have snapshots; extend to track max.

### Classification Logic

- Runner: `runner_alerted = 1` OR (max_price &gt; 1.5× entry AND time_to_peak &lt; 45 min)
- Successful: max &gt; 1.2×, not runner
- Neutral: max between 0.8× and 1.2×
- Failed: max &lt; 0.8× (or never recovered)

---

## 4. Pattern Discovery

### Rule-Based (No ML)

- **MC + session**: e.g. “Runners: 60% in 10–50K MC, US session”
- **DEX**: “Raydium pairs: 2× runner rate vs pump”
- **Liquidity growth**: “Runners avg +80% liq in first 15 min”
- **Source**: “Source X: 35% runner rate vs 15% avg”

### Implementation

- SQL aggregations + Python summaries.
- Store aggregates in `analytics_daily`, `analytics_weekly`, `analytics_monthly`.

---

## 5. Reporting Structure

### Daily (with Daily Report)

- Total signals, winners, losers, runners
- Best/worst performer
- One observation: e.g. “6/8 runners in US session” or “Best MC: 20–40K”

### Weekly (New)

- Best time windows (hour + day)
- Best MC ranges
- Runner frequency vs prior week
- Top DEXs by outcome
- Performance trend (up/down vs last week)

### Monthly (New)

- Summary counts
- Structural insights (what works)
- What got worse vs last month
- What improved

---

## 6. Analytics Architecture

### Storage

**At signal time (extend `signals`):**
- `original_dex_id`, `destination_type`
- `hour_utc`, `day_of_week`, `session`

**Over time (from checks):**
- `max_price_seen`, `max_price_seen_at`
- `max_market_cap_seen`, `max_market_cap_seen_at`
- `outcome` (computed: failed/neutral/successful/runner)

**New tables:**
- `signal_snapshots` (optional): time-series of price/vol/liq for pattern mining
- `analytics_daily`: date, metrics (counts, best MC range, best hour, etc.)
- `analytics_weekly`: week, aggregates
- `analytics_monthly`: month, aggregates

### Computation

| When      | What                                  |
|-----------|----------------------------------------|
| Incremental | On 1h/6h update: refresh max_* fields |
| Daily     | After daily report: compute daily analytics, classify outcomes |
| Weekly    | After last day of week: compute weekly rollup |
| Monthly   | After last day of month: compute monthly rollup |

### Modularity

- `analytics.py`: compute functions, aggregation logic
- `report_analytics()`: build daily/weekly/monthly blocks
- Called from `generate_daily_report` (daily) and from new scheduled jobs (weekly/monthly)
- Non-blocking: run after main report send; failures only log.

---

## 7. Output

- All analytics → **REPORT_DESTINATION only**.
- No change to alert routing.
- Structured blocks, minimal noise.

---

## Implementation Order (Suggested)

1. **Runner detection** (standalone value):
   - Add `runner_alerted`, `runner_alerted_at`
   - Implement runner watcher loop (1–2 min)
   - Velocity + volume acceleration detection
   - Runner alert message to report group

2. **Max tracking** (enables outcomes):
   - Add `max_price_seen`, `max_price_seen_at`, `max_market_cap_seen`, `max_market_cap_seen_at`
   - Update in runner watcher and 1h/6h checks

3. **Outcome classification**:
   - Add `outcome` column
   - Compute in daily report or dedicated job

4. **Analytics schema**:
   - Add `original_dex_id`, `destination_type`, `hour_utc`, `day_of_week`, `session` at save
   - Create `analytics_daily` table

5. **Daily analytics block**:
   - Compute and append to daily report

6. **Weekly/monthly**:
   - New tables, scheduled jobs, separate report messages

---

## Summary

| Component          | Approach                                      |
|--------------------|-----------------------------------------------|
| Runner architecture| Short-interval polling loop, same process     |
| Detection          | Velocity + volume acceleration, then liquidity |
| Intervals          | 1–2 min for first hour only                   |
| Data source        | DexScreener, primary pair                     |
| Output             | Report group only, “Runner detected”          |
| State              | `runner_alerted` flag, optional confirmation  |
| Analytics          | New columns at save, new tables for rollups   |
| Computation        | Incremental (max), daily/weekly/monthly batch |
| Integration        | Modular; forward flow and reports unchanged   |
