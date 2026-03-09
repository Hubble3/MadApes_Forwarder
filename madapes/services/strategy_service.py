"""Trading strategy engine - evaluates signals against 7 trading strategies.

Each strategy defines entry criteria, position sizing, and exit rules.
Strategies are evaluated independently; a signal can match multiple strategies.
"""
import logging
from datetime import datetime
from typing import Optional

from madapes.formatting import safe_float
from madapes.services.caller_service import get_caller
from madapes.services.portfolio_service import get_portfolio_by_chain

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Dangerous patterns that disqualify signals from certain strategies
# ---------------------------------------------------------------------------
DANGEROUS_PATTERNS = {"pump_and_dump", "possible_wash_trading", "liquidity_drain"}

# ---------------------------------------------------------------------------
# Strategy definitions (metadata for API listing)
# ---------------------------------------------------------------------------
STRATEGY_DEFINITIONS = [
    {
        "name": "convergence_sniper",
        "description": "Multi-caller convergence with high confidence and safety.",
        "criteria": (
            "Multi-caller count >= 2, at least one caller composite_score >= 50, "
            "confidence >= 60, safety >= 50, MC $30K-$2M, liquidity >= $10K."
        ),
        "position_size": 175,
    },
    {
        "name": "elite_caller",
        "description": "High-conviction trades from proven elite callers.",
        "criteria": (
            "Caller composite_score >= 70, total_signals >= 10, win_rate >= 50%, "
            "safety >= 30. Position scales with caller score."
        ),
        "position_size": "120-200 (scales with score)",
    },
    {
        "name": "micro_cap_scalp",
        "description": "Quick scalps on very early micro-cap tokens.",
        "criteria": (
            "MC < $80K, liquidity >= $5K, safety >= 40, chain is solana or base."
        ),
        "position_size": 50,
    },
    {
        "name": "safety_first",
        "description": "Conservative entries on high-safety tokens with no dangerous patterns.",
        "criteria": (
            "Safety >= 80, MC $100K-$10M, liquidity >= $25K, confidence >= 45, "
            "no pump_and_dump / wash_trading / liquidity_drain patterns."
        ),
        "position_size": 100,
    },
    {
        "name": "momentum_rider",
        "description": "Add to runners already showing strong momentum.",
        "criteria": (
            "Runner already alerted, velocity >= 3.0, vol_accel >= 2.0, "
            "price change from entry >= 50%, MC < $5M, safety >= 40."
        ),
        "position_size": 75,
    },
    {
        "name": "chain_rotation",
        "description": "Rotate into hot chains based on 7-day performance.",
        "criteria": (
            "Hot chain (win_rate > 55%, avg_return > 15%): confidence >= 40. "
            "Neutral: confidence >= 55. Cold: confidence >= 70."
        ),
        "position_size": "70-130 (varies by chain heat)",
    },
    {
        "name": "time_decay",
        "description": "Adjust entry criteria based on time-of-day liquidity patterns.",
        "criteria": (
            "Peak 13-21 UTC: confidence >= 40, safety >= 35. "
            "Decent 8-13/21-23 UTC: confidence >= 55, safety >= 50. "
            "Off-peak 0-8 UTC: confidence >= 75, multi-caller >= 2, caller_score >= 60."
        ),
        "position_size": "80-120 (varies by time window)",
    },
]


# ---------------------------------------------------------------------------
# Helper: extract common values from input dicts
# ---------------------------------------------------------------------------

def _extract_values(signal_data: dict, enrichment_data: dict, caller_data: dict, safety_result: dict):
    """Extract commonly used values from the input dictionaries."""
    mc = safe_float(enrichment_data.get("fdv") or enrichment_data.get("market_cap"))
    liquidity = safe_float(enrichment_data.get("liquidity"))
    chain = (enrichment_data.get("chain") or signal_data.get("chain") or "").lower()
    confidence = safe_float(signal_data.get("confidence_score"), 0)
    safety = safe_float(safety_result.get("safety_score"), 0) if safety_result else 0
    return mc, liquidity, chain, confidence, safety


# ---------------------------------------------------------------------------
# Individual strategy evaluators
# ---------------------------------------------------------------------------

def _eval_convergence_sniper(
    signal_data: dict,
    enrichment_data: dict,
    caller_data: dict,
    safety_result: dict,
    patterns: list,
    multi_caller_count: int,
) -> dict:
    """Strategy 1: Convergence Sniper - multi-caller convergence."""
    mc, liquidity, chain, confidence, safety = _extract_values(
        signal_data, enrichment_data, caller_data, safety_result
    )

    if multi_caller_count < 2:
        return _fail("convergence_sniper", "Multi-caller count < 2")

    # Check if at least one caller has composite_score >= 50
    caller_score = safe_float(caller_data.get("composite_score"), 0)
    if caller_score < 50:
        return _fail("convergence_sniper", f"Caller score {caller_score:.0f} < 50")

    if confidence < 60:
        return _fail("convergence_sniper", f"Confidence {confidence:.0f} < 60")

    if safety < 50:
        return _fail("convergence_sniper", f"Safety {safety:.0f} < 50")

    if mc is None or not (30_000 <= mc <= 2_000_000):
        return _fail("convergence_sniper", f"MC {mc} outside $30K-$2M range")

    if liquidity is None or liquidity < 10_000:
        return _fail("convergence_sniper", f"Liquidity {liquidity} < $10K")

    return {
        "eligible": True,
        "position_size": 175.0,
        "strategy": "convergence_sniper",
        "exit_rules": {
            "take_profit_pct": 100,
            "stop_loss_pct": -25,
            "trailing_stop_pct": 15,
            "max_hold_hours": 24,
        },
        "reason": f"Multi-caller ({multi_caller_count}x), confidence {confidence:.0f}, safety {safety:.0f}",
    }


def _eval_elite_caller(
    signal_data: dict,
    enrichment_data: dict,
    caller_data: dict,
    safety_result: dict,
    patterns: list,
    multi_caller_count: int,
) -> dict:
    """Strategy 2: Elite Caller - proven callers with strong track records."""
    _, _, _, _, safety = _extract_values(
        signal_data, enrichment_data, caller_data, safety_result
    )

    caller_score = safe_float(caller_data.get("composite_score"), 0)
    total_signals = int(caller_data.get("total_signals", 0))
    win_count = int(caller_data.get("win_count", 0))
    loss_count = int(caller_data.get("loss_count", 0))
    checked = win_count + loss_count
    win_rate = (win_count / checked * 100) if checked > 0 else 0

    if caller_score < 70:
        return _fail("elite_caller", f"Caller score {caller_score:.0f} < 70")

    if total_signals < 10:
        return _fail("elite_caller", f"Total signals {total_signals} < 10")

    if win_rate < 50:
        return _fail("elite_caller", f"Win rate {win_rate:.0f}% < 50%")

    if safety < 30:
        return _fail("elite_caller", f"Safety {safety:.0f} < 30")

    # Position size scales with caller score
    if caller_score >= 90:
        position = 200.0
    elif caller_score >= 80:
        position = 150.0
    else:
        position = 120.0

    return {
        "eligible": True,
        "position_size": position,
        "strategy": "elite_caller",
        "exit_rules": {
            "take_profit_pct": 150,
            "stop_loss_pct": -20,
            "trailing_stop_pct": 20,
            "max_hold_hours": 48,
        },
        "reason": f"Elite caller score {caller_score:.0f}, win rate {win_rate:.0f}%, {total_signals} signals",
    }


def _eval_micro_cap_scalp(
    signal_data: dict,
    enrichment_data: dict,
    caller_data: dict,
    safety_result: dict,
    patterns: list,
    multi_caller_count: int,
) -> dict:
    """Strategy 3: Micro Cap Scalp - quick scalps on very early tokens."""
    mc, liquidity, chain, _, safety = _extract_values(
        signal_data, enrichment_data, caller_data, safety_result
    )

    if mc is None or mc >= 80_000:
        return _fail("micro_cap_scalp", f"MC {mc} >= $80K")

    if liquidity is None or liquidity < 5_000:
        return _fail("micro_cap_scalp", f"Liquidity {liquidity} < $5K")

    if safety < 40:
        return _fail("micro_cap_scalp", f"Safety {safety:.0f} < 40")

    if chain not in ("solana", "base"):
        return _fail("micro_cap_scalp", f"Chain '{chain}' not solana or base")

    return {
        "eligible": True,
        "position_size": 50.0,
        "strategy": "micro_cap_scalp",
        "exit_rules": {
            "take_profit_pct": 50,
            "stop_loss_pct": -30,
            "trailing_stop_pct": 10,
            "max_hold_hours": 6,
        },
        "reason": f"Micro cap ${mc:,.0f}, chain={chain}, safety {safety:.0f}",
    }


def _eval_safety_first(
    signal_data: dict,
    enrichment_data: dict,
    caller_data: dict,
    safety_result: dict,
    patterns: list,
    multi_caller_count: int,
) -> dict:
    """Strategy 4: Safety First - conservative entries on high-safety tokens."""
    mc, liquidity, _, confidence, safety = _extract_values(
        signal_data, enrichment_data, caller_data, safety_result
    )

    if safety < 80:
        return _fail("safety_first", f"Safety {safety:.0f} < 80")

    if mc is None or not (100_000 <= mc <= 10_000_000):
        return _fail("safety_first", f"MC {mc} outside $100K-$10M range")

    if liquidity is None or liquidity < 25_000:
        return _fail("safety_first", f"Liquidity {liquidity} < $25K")

    if confidence < 45:
        return _fail("safety_first", f"Confidence {confidence:.0f} < 45")

    # Check for dangerous patterns
    if patterns:
        dangerous_found = DANGEROUS_PATTERNS.intersection(set(patterns))
        if dangerous_found:
            return _fail("safety_first", f"Dangerous patterns: {', '.join(dangerous_found)}")

    return {
        "eligible": True,
        "position_size": 100.0,
        "strategy": "safety_first",
        "exit_rules": {
            "take_profit_pct": 80,
            "stop_loss_pct": -15,
            "trailing_stop_pct": 12,
            "max_hold_hours": 72,
        },
        "reason": f"High safety {safety:.0f}, MC ${mc:,.0f}, confidence {confidence:.0f}",
    }


def _eval_momentum_rider(
    signal_data: dict,
    enrichment_data: dict,
    caller_data: dict,
    safety_result: dict,
    patterns: list,
    multi_caller_count: int,
) -> dict:
    """Strategy 5: Momentum Rider - add to runners showing strong momentum."""
    mc, _, _, _, safety = _extract_values(
        signal_data, enrichment_data, caller_data, safety_result
    )

    runner_alerted = int(signal_data.get("runner_alerted", 0))
    if not runner_alerted:
        return _fail("momentum_rider", "Not a runner-alerted signal")

    velocity = safe_float(signal_data.get("velocity"), 0)
    vol_accel = safe_float(signal_data.get("vol_accel"), 0)
    price_change = safe_float(signal_data.get("price_change_percent"), 0)

    if velocity < 3.0:
        return _fail("momentum_rider", f"Velocity {velocity:.1f} < 3.0")

    if vol_accel < 2.0:
        return _fail("momentum_rider", f"Vol accel {vol_accel:.1f} < 2.0")

    if price_change < 50:
        return _fail("momentum_rider", f"Price change {price_change:.0f}% < 50%")

    if mc is not None and mc >= 5_000_000:
        return _fail("momentum_rider", f"MC ${mc:,.0f} >= $5M")

    if safety < 40:
        return _fail("momentum_rider", f"Safety {safety:.0f} < 40")

    return {
        "eligible": True,
        "position_size": 75.0,
        "strategy": "momentum_rider",
        "exit_rules": {
            "take_profit_pct": 200,
            "stop_loss_pct": -20,
            "trailing_stop_pct": 25,
            "max_hold_hours": 12,
        },
        "reason": f"Runner velocity {velocity:.1f}, vol_accel {vol_accel:.1f}, +{price_change:.0f}%",
    }


def _eval_chain_rotation(
    signal_data: dict,
    enrichment_data: dict,
    caller_data: dict,
    safety_result: dict,
    patterns: list,
    multi_caller_count: int,
) -> dict:
    """Strategy 6: Chain Rotation - rotate into hot chains based on 7-day performance."""
    _, _, chain, confidence, _ = _extract_values(
        signal_data, enrichment_data, caller_data, safety_result
    )

    if not chain:
        return _fail("chain_rotation", "No chain data")

    # Query portfolio for chain performance
    chain_perf = get_portfolio_by_chain()
    chain_data = chain_perf.get(chain)

    if chain_data and chain_data.get("closed", 0) > 0:
        chain_wr = chain_data.get("win_rate", 0)
        chain_realized = chain_data.get("total_realized", 0)
        chain_closed = chain_data.get("closed", 1)
        chain_avg_return = chain_realized / chain_closed if chain_closed > 0 else 0
    else:
        # No data for this chain - treat as neutral
        chain_wr = 50
        chain_avg_return = 0

    # Determine chain heat
    if chain_wr > 55 and chain_avg_return > 15:
        heat = "hot"
        min_confidence = 40
        position = 130.0
    elif chain_wr >= 40:
        heat = "neutral"
        min_confidence = 55
        position = 100.0
    else:
        heat = "cold"
        min_confidence = 70
        position = 70.0

    if confidence < min_confidence:
        return _fail(
            "chain_rotation",
            f"Chain '{chain}' is {heat} (WR {chain_wr:.0f}%), confidence {confidence:.0f} < {min_confidence}",
        )

    return {
        "eligible": True,
        "position_size": position,
        "strategy": "chain_rotation",
        "exit_rules": {
            "take_profit_pct": 100,
            "stop_loss_pct": -20,
            "trailing_stop_pct": 15,
            "max_hold_hours": 36,
        },
        "reason": f"Chain '{chain}' is {heat} (WR {chain_wr:.0f}%, avg return ${chain_avg_return:.0f}), confidence {confidence:.0f}",
    }


def _eval_time_decay(
    signal_data: dict,
    enrichment_data: dict,
    caller_data: dict,
    safety_result: dict,
    patterns: list,
    multi_caller_count: int,
) -> dict:
    """Strategy 7: Time Decay - adjust criteria based on UTC hour."""
    _, _, _, confidence, safety = _extract_values(
        signal_data, enrichment_data, caller_data, safety_result
    )

    # Determine current UTC hour
    ts = signal_data.get("original_timestamp")
    if ts:
        try:
            dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
            hour_utc = dt.hour
        except Exception:
            hour_utc = datetime.utcnow().hour
    else:
        hour_utc = datetime.utcnow().hour

    # Peak: 13-21 UTC
    if 13 <= hour_utc <= 21:
        window = "peak"
        min_confidence = 40
        min_safety = 35
        position = 120.0
        extra_checks = True  # no extra checks needed
    # Decent: 8-13, 21-23 UTC
    elif (8 <= hour_utc < 13) or (21 < hour_utc <= 23):
        window = "decent"
        min_confidence = 55
        min_safety = 50
        position = 100.0
        extra_checks = True
    # Off-peak: 0-8 UTC
    else:
        window = "off-peak"
        min_confidence = 75
        min_safety = 0  # checked separately
        position = 80.0
        extra_checks = False

    if confidence < min_confidence:
        return _fail("time_decay", f"{window} window ({hour_utc}h UTC), confidence {confidence:.0f} < {min_confidence}")

    if min_safety > 0 and safety < min_safety:
        return _fail("time_decay", f"{window} window ({hour_utc}h UTC), safety {safety:.0f} < {min_safety}")

    # Off-peak extra requirements
    if not extra_checks:
        if multi_caller_count < 2:
            return _fail("time_decay", f"Off-peak requires multi-caller >= 2, got {multi_caller_count}")
        caller_score = safe_float(caller_data.get("composite_score"), 0)
        if caller_score < 60:
            return _fail("time_decay", f"Off-peak requires caller score >= 60, got {caller_score:.0f}")

    return {
        "eligible": True,
        "position_size": position,
        "strategy": "time_decay",
        "exit_rules": {
            "take_profit_pct": 80,
            "stop_loss_pct": -20,
            "trailing_stop_pct": 15,
            "max_hold_hours": 24,
        },
        "reason": f"{window} window ({hour_utc}h UTC), confidence {confidence:.0f}, safety {safety:.0f}",
    }


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _fail(strategy: str, reason: str) -> dict:
    """Return a non-eligible result."""
    return {
        "eligible": False,
        "position_size": 0.0,
        "strategy": strategy,
        "exit_rules": {},
        "reason": reason,
    }


# ---------------------------------------------------------------------------
# Main evaluation functions
# ---------------------------------------------------------------------------

_EVALUATORS = [
    _eval_convergence_sniper,
    _eval_elite_caller,
    _eval_micro_cap_scalp,
    _eval_safety_first,
    _eval_momentum_rider,
    _eval_chain_rotation,
    _eval_time_decay,
]


def evaluate_strategies(
    signal_data: dict,
    enrichment_data: dict,
    caller_data: dict,
    safety_result: dict,
    patterns: list,
    multi_caller_count: int,
) -> list[dict]:
    """Evaluate ALL strategies against a signal.

    Returns a list of matching (eligible) strategy results,
    sorted by position_size descending (highest conviction first).
    """
    results = []
    for evaluator in _EVALUATORS:
        try:
            result = evaluator(
                signal_data, enrichment_data, caller_data, safety_result,
                patterns, multi_caller_count,
            )
            if result.get("eligible"):
                results.append(result)
        except Exception as e:
            logger.error(f"Error evaluating strategy {evaluator.__name__}: {e}")

    # Sort by position_size descending
    results.sort(key=lambda r: r["position_size"], reverse=True)
    return results


def get_best_strategy(
    signal_data: dict,
    enrichment_data: dict,
    caller_data: dict,
    safety_result: dict,
    patterns: list,
    multi_caller_count: int,
) -> dict | None:
    """Return the single best (highest position_size) strategy, or None."""
    results = evaluate_strategies(
        signal_data, enrichment_data, caller_data, safety_result,
        patterns, multi_caller_count,
    )
    return results[0] if results else None


def get_strategy_definitions() -> list[dict]:
    """Return metadata for all strategies (for API listing)."""
    return STRATEGY_DEFINITIONS
