"""Statistical insights endpoints — win rates by caller, chain, MC bucket, time, tier."""
from fastapi import APIRouter, Depends

from api.auth import verify_api_key
from db import get_connection

router = APIRouter()


@router.get("/")
async def get_insights(api_key: str = Depends(verify_api_key)):
    """Comprehensive statistical insights from historical signal data."""
    with get_connection() as conn:
        # ── Data readiness ──
        total = conn.execute("SELECT COUNT(*) as cnt FROM signals").fetchone()["cnt"]
        checked = conn.execute(
            "SELECT COUNT(*) as cnt FROM signals WHERE status IN ('win','loss')"
        ).fetchone()["cnt"]
        with_6h = conn.execute(
            "SELECT COUNT(*) as cnt FROM signals WHERE price_6h IS NOT NULL"
        ).fetchone()["cnt"]
        runners = conn.execute(
            "SELECT COUNT(*) as cnt FROM signals WHERE runner_alerted = 1"
        ).fetchone()["cnt"]

        data_readiness = {
            "total_signals": total,
            "checked_signals": checked,
            "signals_with_6h": with_6h,
            "runners_detected": runners,
            "ml_ready": checked >= 20,
            "ml_min_samples": 20,
            "ml_recommended": 200,
            "progress_pct": min(100, round(checked / 200 * 100, 1)) if checked > 0 else 0,
        }

        # ── Win rate by caller (callers with 3+ checked signals) ──
        caller_rows = conn.execute("""
            SELECT
                s.sender_name,
                s.sender_id,
                COUNT(*) as total,
                SUM(CASE WHEN s.status = 'win' THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN s.status = 'loss' THEN 1 ELSE 0 END) as losses,
                ROUND(AVG(s.price_change_percent), 1) as avg_return,
                SUM(CASE WHEN s.runner_alerted = 1 THEN 1 ELSE 0 END) as runners,
                COALESCE(c.composite_score, 0) as score
            FROM signals s
            LEFT JOIN callers c ON s.sender_id = c.sender_id
            WHERE s.status IN ('win', 'loss')
            GROUP BY s.sender_id
            HAVING total >= 2
            ORDER BY wins * 1.0 / total DESC
        """).fetchall()

        by_caller = []
        for r in caller_rows:
            t = r["total"]
            w = r["wins"]
            by_caller.append({
                "sender_name": r["sender_name"],
                "sender_id": r["sender_id"],
                "total": t,
                "wins": w,
                "losses": r["losses"],
                "win_rate": round(w / t * 100, 1) if t > 0 else 0,
                "avg_return": r["avg_return"] or 0,
                "runners": r["runners"],
                "score": round(r["score"], 1),
            })

        # ── Win rate by chain ──
        chain_rows = conn.execute("""
            SELECT
                chain,
                COUNT(*) as total,
                SUM(CASE WHEN status = 'win' THEN 1 ELSE 0 END) as wins,
                ROUND(AVG(price_change_percent), 1) as avg_return,
                SUM(CASE WHEN runner_alerted = 1 THEN 1 ELSE 0 END) as runners
            FROM signals
            WHERE status IN ('win', 'loss') AND chain IS NOT NULL
            GROUP BY chain
            ORDER BY total DESC
        """).fetchall()

        by_chain = []
        for r in chain_rows:
            t = r["total"]
            w = r["wins"]
            by_chain.append({
                "chain": r["chain"],
                "total": t,
                "wins": w,
                "win_rate": round(w / t * 100, 1) if t > 0 else 0,
                "avg_return": r["avg_return"] or 0,
                "runners": r["runners"],
            })

        # ── Win rate by market cap bucket ──
        mc_rows = conn.execute("""
            SELECT
                CASE
                    WHEN original_market_cap < 50000 THEN 'Under $50K'
                    WHEN original_market_cap < 100000 THEN '$50K - $100K'
                    WHEN original_market_cap < 300000 THEN '$100K - $300K'
                    WHEN original_market_cap < 500000 THEN '$300K - $500K'
                    WHEN original_market_cap < 1000000 THEN '$500K - $1M'
                    ELSE '$1M+'
                END as mc_bucket,
                COUNT(*) as total,
                SUM(CASE WHEN status = 'win' THEN 1 ELSE 0 END) as wins,
                ROUND(AVG(price_change_percent), 1) as avg_return,
                SUM(CASE WHEN runner_alerted = 1 THEN 1 ELSE 0 END) as runners,
                ROUND(AVG(original_market_cap), 0) as avg_mc
            FROM signals
            WHERE status IN ('win', 'loss') AND original_market_cap IS NOT NULL
            GROUP BY mc_bucket
            ORDER BY avg_mc ASC
        """).fetchall()

        by_mc = []
        for r in mc_rows:
            t = r["total"]
            w = r["wins"]
            by_mc.append({
                "bucket": r["mc_bucket"],
                "total": t,
                "wins": w,
                "win_rate": round(w / t * 100, 1) if t > 0 else 0,
                "avg_return": r["avg_return"] or 0,
                "runners": r["runners"],
            })

        # ── Win rate by hour (UTC) ──
        hour_rows = conn.execute("""
            SELECT
                hour_utc,
                COUNT(*) as total,
                SUM(CASE WHEN status = 'win' THEN 1 ELSE 0 END) as wins,
                ROUND(AVG(price_change_percent), 1) as avg_return
            FROM signals
            WHERE status IN ('win', 'loss') AND hour_utc IS NOT NULL
            GROUP BY hour_utc
            ORDER BY hour_utc
        """).fetchall()

        by_hour = []
        for r in hour_rows:
            t = r["total"]
            w = r["wins"]
            by_hour.append({
                "hour": r["hour_utc"],
                "total": t,
                "wins": w,
                "win_rate": round(w / t * 100, 1) if t > 0 else 0,
                "avg_return": r["avg_return"] or 0,
            })

        # ── Win rate by tier (gold/silver/bronze) ──
        tier_rows = conn.execute("""
            SELECT
                signal_tier,
                COUNT(*) as total,
                SUM(CASE WHEN status = 'win' THEN 1 ELSE 0 END) as wins,
                ROUND(AVG(price_change_percent), 1) as avg_return,
                SUM(CASE WHEN runner_alerted = 1 THEN 1 ELSE 0 END) as runners
            FROM signals
            WHERE status IN ('win', 'loss') AND signal_tier IS NOT NULL
            GROUP BY signal_tier
            ORDER BY
                CASE signal_tier
                    WHEN 'gold' THEN 1
                    WHEN 'silver' THEN 2
                    WHEN 'bronze' THEN 3
                    ELSE 4
                END
        """).fetchall()

        by_tier = []
        for r in tier_rows:
            t = r["total"]
            w = r["wins"]
            by_tier.append({
                "tier": r["signal_tier"],
                "total": t,
                "wins": w,
                "win_rate": round(w / t * 100, 1) if t > 0 else 0,
                "avg_return": r["avg_return"] or 0,
                "runners": r["runners"],
            })

        # ── Win rate by session (Asia/EU/US) ──
        session_rows = conn.execute("""
            SELECT
                session,
                COUNT(*) as total,
                SUM(CASE WHEN status = 'win' THEN 1 ELSE 0 END) as wins,
                ROUND(AVG(price_change_percent), 1) as avg_return
            FROM signals
            WHERE status IN ('win', 'loss') AND session IS NOT NULL AND session != ''
            GROUP BY session
            ORDER BY total DESC
        """).fetchall()

        by_session = []
        for r in session_rows:
            t = r["total"]
            w = r["wins"]
            by_session.append({
                "session": r["session"],
                "total": t,
                "wins": w,
                "win_rate": round(w / t * 100, 1) if t > 0 else 0,
                "avg_return": r["avg_return"] or 0,
            })

        # ── Top performing signals (best returns) ──
        top_rows = conn.execute("""
            SELECT
                id, token_name, token_symbol, chain, signal_tier,
                original_market_cap, price_change_percent, multiplier,
                runner_alerted, sender_name
            FROM signals
            WHERE status IN ('win', 'loss') AND price_change_percent IS NOT NULL
            ORDER BY price_change_percent DESC
            LIMIT 5
        """).fetchall()

        top_signals = []
        for r in top_rows:
            top_signals.append({
                "id": r["id"],
                "token": r["token_symbol"] or r["token_name"] or "Unknown",
                "chain": r["chain"],
                "tier": r["signal_tier"],
                "mc": r["original_market_cap"],
                "return_pct": r["price_change_percent"],
                "multiplier": r["multiplier"],
                "is_runner": bool(r["runner_alerted"]),
                "caller": r["sender_name"],
            })

        # ── Key takeaways (auto-generated insights) ──
        takeaways = _generate_takeaways(by_caller, by_chain, by_mc, by_hour, by_tier, by_session, data_readiness)

    return {
        "data_readiness": data_readiness,
        "by_caller": by_caller,
        "by_chain": by_chain,
        "by_mc": by_mc,
        "by_hour": by_hour,
        "by_tier": by_tier,
        "by_session": by_session,
        "top_signals": top_signals,
        "takeaways": takeaways,
    }


def _generate_takeaways(by_caller, by_chain, by_mc, by_hour, by_tier, by_session, readiness) -> list:
    """Generate human-readable insight takeaways from the data."""
    tips = []

    if readiness["checked_signals"] < 10:
        tips.append({
            "type": "info",
            "text": f"Only {readiness['checked_signals']} signals checked so far. Insights will become more reliable with more data.",
        })
        return tips

    # Best caller
    if by_caller:
        best = max(by_caller, key=lambda x: x["win_rate"]) if by_caller else None
        if best and best["total"] >= 3:
            tips.append({
                "type": "success",
                "text": f"Best caller: {best['sender_name']} with {best['win_rate']}% win rate across {best['total']} signals.",
            })

    # Best chain
    if by_chain:
        best_chain = max(by_chain, key=lambda x: x["win_rate"]) if by_chain else None
        if best_chain and best_chain["total"] >= 3:
            tips.append({
                "type": "success",
                "text": f"Best chain: {best_chain['chain'].upper()} with {best_chain['win_rate']}% win rate ({best_chain['total']} signals).",
            })

    # Best MC range
    if by_mc:
        best_mc = max(by_mc, key=lambda x: x["avg_return"])
        if best_mc["total"] >= 2:
            tips.append({
                "type": "success",
                "text": f"Best MC range: {best_mc['bucket']} with {best_mc['avg_return']:+.1f}% avg return.",
            })

    # Tier accuracy
    if by_tier and len(by_tier) >= 2:
        gold = next((t for t in by_tier if t["tier"] == "gold"), None)
        bronze = next((t for t in by_tier if t["tier"] == "bronze"), None)
        if gold and bronze:
            if gold["win_rate"] > bronze["win_rate"]:
                tips.append({
                    "type": "success",
                    "text": f"Tier system is working: GOLD ({gold['win_rate']}% WR) outperforms BRONZE ({bronze['win_rate']}% WR).",
                })
            else:
                tips.append({
                    "type": "warning",
                    "text": f"Tier system needs tuning: GOLD ({gold['win_rate']}% WR) not outperforming BRONZE ({bronze['win_rate']}% WR).",
                })

    # Best hour
    if by_hour and len(by_hour) >= 3:
        best_hour = max(by_hour, key=lambda x: x["win_rate"])
        if best_hour["total"] >= 2:
            tips.append({
                "type": "info",
                "text": f"Best hour: {best_hour['hour']}:00 UTC with {best_hour['win_rate']}% win rate.",
            })

    # ML readiness
    if readiness["ml_ready"]:
        tips.append({
            "type": "info",
            "text": f"ML training available ({readiness['checked_signals']} samples). Recommended: {readiness['ml_recommended']}+ for reliable predictions.",
        })
    else:
        remaining = readiness["ml_min_samples"] - readiness["checked_signals"]
        tips.append({
            "type": "warning",
            "text": f"Need {remaining} more checked signals before ML training can begin.",
        })

    return tips
