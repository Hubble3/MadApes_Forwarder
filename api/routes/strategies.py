"""Strategy engine API endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional

from api.auth import verify_api_key
from db import get_connection, get_signal_by_id
from madapes.formatting import safe_float
from madapes.services.strategy_service import (
    evaluate_strategies,
    get_best_strategy,
    get_strategy_definitions,
)
from madapes.services.caller_service import get_caller

router = APIRouter()


class EvaluateRequest(BaseModel):
    signal_id: int


@router.get("/")
async def list_strategies(api_key: str = Depends(verify_api_key)):
    """List all strategy definitions with name, description, and criteria."""
    return {"strategies": get_strategy_definitions()}


@router.post("/evaluate")
async def evaluate_signal_strategies(
    req: EvaluateRequest,
    api_key: str = Depends(verify_api_key),
):
    """Test a signal against all strategies. Accepts signal_id."""
    signal = get_signal_by_id(req.signal_id)
    if not signal:
        raise HTTPException(status_code=404, detail="Signal not found")

    # Build signal_data dict from the DB row
    signal_data = {key: signal[key] for key in signal.keys()}

    # Build enrichment_data from signal's stored enrichment fields
    enrichment_data = {
        "fdv": signal["original_market_cap"] or signal["current_market_cap"],
        "market_cap": signal["original_market_cap"] or signal["current_market_cap"],
        "liquidity": signal["original_liquidity"] or signal["current_liquidity"],
        "chain": signal["chain"],
    }

    # Build caller_data
    sender_id = signal["sender_id"]
    caller = get_caller(sender_id) if sender_id else None
    if caller:
        caller_data = {
            "composite_score": caller.composite_score,
            "total_signals": caller.total_signals,
            "win_count": caller.win_count,
            "loss_count": caller.loss_count,
        }
    else:
        caller_data = {
            "composite_score": 0,
            "total_signals": 0,
            "win_count": 0,
            "loss_count": 0,
        }

    # Build safety_result
    safety_result = {
        "safety_score": signal["safety_score"],
    }

    # Patterns from tags
    tags_str = signal["tags"] or ""
    patterns = [t.strip() for t in tags_str.split(",") if t.strip()] if tags_str else []

    # Multi-caller count: check how many unique senders forwarded same token
    multi_caller_count = 1
    if signal["token_address"]:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT COUNT(DISTINCT sender_id) as cnt FROM signals WHERE token_address = ?",
                (signal["token_address"],),
            ).fetchone()
            multi_caller_count = row["cnt"] if row else 1

    eligible = evaluate_strategies(
        signal_data, enrichment_data, caller_data, safety_result,
        patterns, multi_caller_count,
    )
    best = eligible[0] if eligible else None

    # Also return all strategy evaluations (including non-eligible) for debugging
    all_results = []
    from madapes.services.strategy_service import _EVALUATORS
    for evaluator in _EVALUATORS:
        try:
            result = evaluator(
                signal_data, enrichment_data, caller_data, safety_result,
                patterns, multi_caller_count,
            )
            all_results.append(result)
        except Exception as e:
            all_results.append({
                "eligible": False,
                "strategy": evaluator.__name__.replace("_eval_", ""),
                "reason": str(e),
            })

    return {
        "signal_id": req.signal_id,
        "eligible_strategies": eligible,
        "best_strategy": best,
        "all_evaluations": all_results,
    }


@router.get("/performance")
async def strategy_performance(api_key: str = Depends(verify_api_key)):
    """Per-strategy P&L from portfolio_entries, grouped by strategy column."""
    with get_connection() as conn:
        # Check if strategy column exists in signals
        cols = conn.execute("PRAGMA table_info(signals)").fetchall()
        col_names = {r["name"] for r in cols}
        if "strategy" not in col_names:
            return {"performance": {}, "message": "Strategy column not yet populated."}

        # Check if strategy column exists in portfolio_entries
        pe_cols = conn.execute("PRAGMA table_info(portfolio_entries)").fetchall()
        pe_col_names = {r["name"] for r in pe_cols}

        if "strategy" in pe_col_names:
            # Query portfolio_entries directly
            rows = conn.execute("""
                SELECT
                    COALESCE(strategy, 'none') as strategy_name,
                    COUNT(*) as total_trades,
                    SUM(CASE WHEN status = 'closed' AND realized_pnl > 0 THEN 1 ELSE 0 END) as wins,
                    SUM(CASE WHEN status = 'closed' AND realized_pnl <= 0 THEN 1 ELSE 0 END) as losses,
                    SUM(CASE WHEN status = 'closed' THEN 1 ELSE 0 END) as closed,
                    ROUND(SUM(COALESCE(realized_pnl, 0)), 2) as total_realized_pnl,
                    ROUND(SUM(COALESCE(unrealized_pnl, 0)), 2) as total_unrealized_pnl,
                    ROUND(AVG(CASE WHEN status = 'closed' THEN realized_pnl_pct END), 2) as avg_return_pct,
                    ROUND(MAX(CASE WHEN status = 'closed' THEN realized_pnl_pct END), 2) as best_return_pct,
                    ROUND(MIN(CASE WHEN status = 'closed' THEN realized_pnl_pct END), 2) as worst_return_pct
                FROM portfolio_entries
                GROUP BY COALESCE(strategy, 'none')
                ORDER BY SUM(COALESCE(realized_pnl, 0)) DESC
            """).fetchall()
        else:
            # Fall back to joining signals table
            rows = conn.execute("""
                SELECT
                    COALESCE(s.strategy, 'none') as strategy_name,
                    COUNT(*) as total_trades,
                    SUM(CASE WHEN pe.status = 'closed' AND pe.realized_pnl > 0 THEN 1 ELSE 0 END) as wins,
                    SUM(CASE WHEN pe.status = 'closed' AND pe.realized_pnl <= 0 THEN 1 ELSE 0 END) as losses,
                    SUM(CASE WHEN pe.status = 'closed' THEN 1 ELSE 0 END) as closed,
                    ROUND(SUM(COALESCE(pe.realized_pnl, 0)), 2) as total_realized_pnl,
                    ROUND(SUM(COALESCE(pe.unrealized_pnl, 0)), 2) as total_unrealized_pnl,
                    ROUND(AVG(CASE WHEN pe.status = 'closed' THEN pe.realized_pnl_pct END), 2) as avg_return_pct,
                    ROUND(MAX(CASE WHEN pe.status = 'closed' THEN pe.realized_pnl_pct END), 2) as best_return_pct,
                    ROUND(MIN(CASE WHEN pe.status = 'closed' THEN pe.realized_pnl_pct END), 2) as worst_return_pct
                FROM portfolio_entries pe
                JOIN signals s ON pe.signal_id = s.id
                GROUP BY COALESCE(s.strategy, 'none')
                ORDER BY SUM(COALESCE(pe.realized_pnl, 0)) DESC
            """).fetchall()

    strategies = {}
    for r in rows:
        name = r["strategy_name"]
        closed = r["closed"] or 0
        wins = r["wins"] or 0
        strategies[name] = {
            "total_trades": r["total_trades"],
            "wins": wins,
            "losses": r["losses"] or 0,
            "closed": closed,
            "win_rate": round((wins / closed * 100) if closed > 0 else 0, 1),
            "total_realized_pnl": r["total_realized_pnl"] or 0,
            "total_unrealized_pnl": r["total_unrealized_pnl"] or 0,
            "avg_return_pct": r["avg_return_pct"] or 0,
            "best_return_pct": r["best_return_pct"] or 0,
            "worst_return_pct": r["worst_return_pct"] or 0,
        }

    return {"performance": strategies}
