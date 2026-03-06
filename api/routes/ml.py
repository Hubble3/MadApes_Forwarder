"""ML and backtesting endpoints."""
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from typing import Optional, List

from api.auth import verify_api_key

router = APIRouter()


@router.post("/train")
async def train_models(api_key: str = Depends(verify_api_key)):
    """Train ML models on historical signal data."""
    from madapes.ml.training import train_classifier, train_regressor

    classifier_result = train_classifier()
    regressor_result = train_regressor()

    return {
        "classifier": classifier_result,
        "regressor": regressor_result,
    }


class BacktestParams(BaseModel):
    strategy: str = "all"
    min_mc: Optional[float] = None
    max_mc: Optional[float] = None
    chains: Optional[List[str]] = None
    position_size: float = 100.0


@router.post("/backtest")
async def run_backtest(params: BacktestParams, api_key: str = Depends(verify_api_key)):
    """Run a backtest with the given parameters."""
    from madapes.services.backtest_service import run_backtest

    result = run_backtest(
        strategy=params.strategy,
        min_mc=params.min_mc,
        max_mc=params.max_mc,
        chains=params.chains,
        position_size=params.position_size,
    )
    return result


@router.get("/patterns/{signal_id}")
async def get_patterns(signal_id: int, api_key: str = Depends(verify_api_key)):
    """Detect patterns for a specific signal."""
    from db import get_signal_by_id
    from madapes.services.pattern_service import detect_patterns, pattern_risk_level

    row = get_signal_by_id(signal_id)
    if not row:
        return {"error": "Signal not found"}

    patterns = detect_patterns(dict(row))
    return {
        "signal_id": signal_id,
        "patterns": patterns,
        "risk_level": pattern_risk_level(patterns),
    }
