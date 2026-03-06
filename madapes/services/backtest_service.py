"""Backtesting engine - simulate strategies against historical signal data."""
import logging
from typing import Optional

from db import get_connection
from madapes.formatting import safe_float

logger = logging.getLogger(__name__)

DEFAULT_POSITION_SIZE = 100.0


def run_backtest(
    strategy: str = "all",
    min_mc: Optional[float] = None,
    max_mc: Optional[float] = None,
    chains: Optional[list] = None,
    min_caller_score: Optional[float] = None,
    position_size: float = DEFAULT_POSITION_SIZE,
) -> dict:
    """Run a backtest against historical signals.

    strategy: "all" (every signal), "winners_only" (only high-confidence), etc.
    Returns backtest results dict.
    """
    with get_connection() as conn:
        query = """SELECT * FROM signals
                   WHERE status IN ('win', 'loss')
                   AND original_price IS NOT NULL
                   AND price_change_percent IS NOT NULL
                   ORDER BY original_timestamp"""
        rows = conn.execute(query).fetchall()

    if not rows:
        return {"error": "No historical data", "trades": 0}

    # Filter signals based on strategy parameters
    filtered = []
    for row in rows:
        mc = safe_float(row["original_market_cap"])

        if min_mc is not None and mc is not None and mc < min_mc:
            continue
        if max_mc is not None and mc is not None and mc > max_mc:
            continue
        if chains and (row["chain"] or "").lower() not in [c.lower() for c in chains]:
            continue

        filtered.append(row)

    if not filtered:
        return {"error": "No signals match filter criteria", "trades": 0}

    # Simulate trades
    total_pnl = 0.0
    wins = 0
    losses = 0
    returns = []
    peak_equity = 0.0
    max_drawdown = 0.0
    equity = 0.0

    for row in filtered:
        pct = safe_float(row["price_change_percent"], 0)
        pnl = position_size * (pct / 100)

        total_pnl += pnl
        equity += pnl
        returns.append(pct)

        if pct > 0:
            wins += 1
        else:
            losses += 1

        peak_equity = max(peak_equity, equity)
        drawdown = peak_equity - equity
        max_drawdown = max(max_drawdown, drawdown)

    total_trades = wins + losses
    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
    avg_return = sum(returns) / len(returns) if returns else 0
    best_return = max(returns) if returns else 0
    worst_return = min(returns) if returns else 0

    # Sharpe-like ratio (simplified)
    if len(returns) >= 2:
        import math
        mean = avg_return
        variance = sum((r - mean) ** 2 for r in returns) / len(returns)
        std = math.sqrt(variance)
        sharpe = mean / std if std > 0 else 0
    else:
        sharpe = 0

    return {
        "strategy": strategy,
        "trades": total_trades,
        "wins": wins,
        "losses": losses,
        "win_rate": round(win_rate, 1),
        "total_pnl": round(total_pnl, 2),
        "avg_return": round(avg_return, 2),
        "best_return": round(best_return, 2),
        "worst_return": round(worst_return, 2),
        "max_drawdown": round(max_drawdown, 2),
        "sharpe_ratio": round(sharpe, 3),
        "position_size": position_size,
        "filters": {
            "min_mc": min_mc,
            "max_mc": max_mc,
            "chains": chains,
        },
    }


def compare_strategies(strategies: list) -> list:
    """Run multiple backtests and return comparison."""
    results = []
    for params in strategies:
        result = run_backtest(**params)
        results.append(result)
    return sorted(results, key=lambda x: x.get("total_pnl", 0), reverse=True)
