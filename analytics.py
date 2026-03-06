"""
Signal analytics and performance intelligence for MadApes Forwarder.
Daily insights, outcome classification, pattern discovery.
"""
import logging

from db import get_all_active_signals, save_analytics_daily
from madapes.formatting import safe_float

logger = logging.getLogger(__name__)


def classify_outcome(signal_row):
    """Classify: failed | neutral | successful | runner"""
    original_price = safe_float(signal_row["original_price"])
    runner_alerted = signal_row["runner_alerted"]
    max_price_seen = safe_float(signal_row["max_price_seen"])

    if runner_alerted:
        return "runner"

    if not original_price or original_price <= 0:
        return "neutral"

    effective_max = max_price_seen or original_price
    mult = effective_max / original_price

    if mult < 0.8:
        return "failed"
    if mult <= 1.2:
        return "neutral"
    return "successful"


def compute_daily_analytics(signals):
    """Compute aggregates for the daily report."""
    if not signals:
        return {
            "total": 0, "win_count": 0, "loss_count": 0, "active_count": 0,
            "runner_count": 0, "failed_count": 0, "neutral_count": 0,
            "successful_count": 0, "best_mc_range": None, "best_hour": None,
            "observation": None,
        }

    wins = [s for s in signals if s["status"] == "win"]
    losses = [s for s in signals if s["status"] == "loss"]
    active = [s for s in signals if s["status"] == "active"]

    outcomes = [classify_outcome(s) for s in signals]
    runner_count = outcomes.count("runner")
    failed_count = outcomes.count("failed")
    neutral_count = outcomes.count("neutral")
    successful_count = outcomes.count("successful")

    mc_buckets = {}
    bucket_names = ["0-10K", "10-50K", "50-80K", "80-150K", "150K+"]
    limits = [10_000, 50_000, 80_000, 150_000, float("inf")]

    for s in signals:
        mc = safe_float(s["original_market_cap"])
        if mc is None:
            continue
        for i, lim in enumerate(limits):
            if mc < lim:
                bn = bucket_names[i]
                mc_buckets[bn] = mc_buckets.get(bn, 0) + 1
                break

    best_mc_range = max(mc_buckets, key=mc_buckets.get) if mc_buckets else None

    hour_counts = {}
    for i, s in enumerate(signals):
        hour = s["hour_utc"]
        if hour is not None:
            if outcomes[i] == "runner" or s["status"] == "win":
                hour_counts[hour] = hour_counts.get(hour, 0) + 1
    best_hour = max(hour_counts, key=hour_counts.get) if hour_counts else None

    obs_parts = []
    if runner_count > 0:
        obs_parts.append(f"{runner_count} runner(s) detected")
    if best_mc_range:
        obs_parts.append(f"Best MC: {best_mc_range}")
    if best_hour is not None:
        obs_parts.append(f"Peak hour: {best_hour}:00 UTC")
    observation = " | ".join(obs_parts) if obs_parts else None

    return {
        "total": len(signals), "win_count": len(wins), "loss_count": len(losses),
        "active_count": len(active), "runner_count": runner_count,
        "failed_count": failed_count, "neutral_count": neutral_count,
        "successful_count": successful_count, "best_mc_range": best_mc_range,
        "best_hour": best_hour, "observation": observation,
    }


def build_daily_analytics_block(analytics):
    """Build the analytics block to append to daily report."""
    lines = []
    if analytics["total"] == 0:
        return lines

    lines.append("")
    lines.append("\U0001f4ca <b>Analytics</b>")
    lines.append(f"   Runners: {analytics['runner_count']} | Successful: {analytics['successful_count']} | Neutral: {analytics['neutral_count']} | Failed: {analytics['failed_count']}")

    if analytics.get("best_mc_range"):
        lines.append(f"   Best MC range: {analytics['best_mc_range']}")
    if analytics.get("best_hour") is not None:
        lines.append(f"   Peak hour: {analytics['best_hour']}:00 UTC")
    if analytics.get("observation"):
        lines.append(f"   \U0001f4a1 {analytics['observation']}")

    return lines


def run_daily_analytics(report_date):
    """Compute and persist daily analytics."""
    signals = get_all_active_signals()
    analytics = compute_daily_analytics(signals)
    save_analytics_daily(
        report_date=report_date,
        total_signals=analytics["total"],
        win_count=analytics["win_count"],
        loss_count=analytics["loss_count"],
        active_count=analytics["active_count"],
        runner_count=analytics["runner_count"],
        best_mc_range=analytics.get("best_mc_range"),
        best_hour=analytics.get("best_hour"),
        observation=analytics.get("observation"),
    )
    return analytics
