"""
Trading API
===========

REST API endpoints for trading operations.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from mortar_trading.config import get_settings, Direction, Confidence
from mortar_trading.web.auth import User, get_current_user, get_current_admin
from mortar_trading.web.app import get_engine

logger = structlog.get_logger(__name__)

router = APIRouter()


# Request/Response Models
class StatusResponse(BaseModel):
    """System status response."""
    running: bool
    environment: str
    uptime_seconds: float | None = None
    master_bias: dict[str, Any]
    components: dict[str, bool]


class PositionResponse(BaseModel):
    """Position information."""
    symbol: str
    side: str
    quantity: float
    entry_price: float
    current_price: float | None = None
    unrealized_pnl: float
    realized_pnl: float
    leverage: float
    liquidation_price: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    opened_at: datetime


class OrderResponse(BaseModel):
    """Order information."""
    order_id: str
    symbol: str
    side: str
    order_type: str
    quantity: float
    price: float | None = None
    filled_quantity: float
    status: str
    created_at: datetime


class AccountResponse(BaseModel):
    """Account information."""
    balance: float
    available_balance: float
    equity: float
    margin_used: float
    unrealized_pnl: float
    realized_pnl_today: float


class RiskStatusResponse(BaseModel):
    """Risk management status."""
    circuit_breaker_active: bool
    circuit_breaker_until: str | None = None
    daily_pnl: float
    weekly_pnl: float
    monthly_pnl: float
    regime_adjustment: float
    limits: dict[str, float]


class MasterInputRequest(BaseModel):
    """Master input update request."""
    direction: str = Field(..., description="strong_bear, bear, neutral, bull, strong_bull")
    confidence: str = Field(default="medium", description="low, medium, high")


class ManualOrderRequest(BaseModel):
    """Manual order request."""
    symbol: str
    side: str = Field(..., description="buy or sell")
    order_type: str = Field(default="market", description="market, limit, stop_market")
    quantity: float
    price: float | None = None
    stop_price: float | None = None
    reduce_only: bool = False


class KeyLevelsRequest(BaseModel):
    """Key levels update request."""
    support: float | None = None
    resistance: float | None = None


class PerformanceResponse(BaseModel):
    """Performance metrics."""
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    total_pnl: float
    avg_win: float
    avg_loss: float
    profit_factor: float
    max_drawdown: float
    sharpe_ratio: float | None = None


class SentimentResponse(BaseModel):
    """Sentiment data for a symbol."""
    symbol: str
    current_score: float
    zscore: float
    momentum: float
    direction: str
    sources: dict[str, float]
    timestamp: datetime


class VolatilityResponse(BaseModel):
    """Volatility data for a symbol."""
    symbol: str
    current_volatility: float
    forecast_1d: float | None = None
    regime: str
    percentile: float
    timestamp: datetime


class RegimeResponse(BaseModel):
    """Market regime information."""
    symbol: str
    regime: str
    confidence: float
    trend_strength: float
    volatility_percentile: float
    strategy_adjustments: dict[str, Any]


# System Routes
@router.get("/status", response_model=StatusResponse)
async def get_status(current_user: Annotated[User, Depends(get_current_user)]):
    """Get current system status."""
    engine = get_engine()
    if not engine:
        raise HTTPException(status_code=503, detail="Engine not initialized")

    status = engine.get_status()
    return StatusResponse(**status)


@router.post("/start")
async def start_engine(current_admin: Annotated[User, Depends(get_current_admin)]):
    """Start the trading engine (admin only)."""
    engine = get_engine()
    if not engine:
        raise HTTPException(status_code=503, detail="Engine not initialized")

    if engine._running:
        return {"message": "Engine already running"}

    # Engine is started via lifespan, this is for manual restart
    return {"message": "Use system restart to start engine"}


@router.post("/stop")
async def stop_engine(current_admin: Annotated[User, Depends(get_current_admin)]):
    """Stop the trading engine (admin only)."""
    engine = get_engine()
    if not engine:
        raise HTTPException(status_code=503, detail="Engine not initialized")

    await engine.stop()
    logger.info("Engine stopped by admin", user=current_admin.username)
    return {"message": "Engine stopped"}


# Account Routes
@router.get("/account", response_model=AccountResponse)
async def get_account(current_user: Annotated[User, Depends(get_current_user)]):
    """Get account information."""
    engine = get_engine()
    if not engine:
        raise HTTPException(status_code=503, detail="Engine not initialized")

    account = await engine.state.get_account()
    return AccountResponse(
        balance=account.balance,
        available_balance=account.available_balance,
        equity=account.equity,
        margin_used=account.margin_used,
        unrealized_pnl=account.unrealized_pnl,
        realized_pnl_today=account.realized_pnl_today,
    )


# Position Routes
@router.get("/positions", response_model=list[PositionResponse])
async def get_positions(current_user: Annotated[User, Depends(get_current_user)]):
    """Get all open positions."""
    engine = get_engine()
    if not engine:
        raise HTTPException(status_code=503, detail="Engine not initialized")

    positions = await engine.state.get_all_positions()
    return [
        PositionResponse(
            symbol=p.symbol,
            side=p.side.value,
            quantity=p.quantity,
            entry_price=p.entry_price,
            current_price=p.current_price,
            unrealized_pnl=p.unrealized_pnl,
            realized_pnl=p.realized_pnl,
            leverage=p.leverage,
            liquidation_price=p.liquidation_price,
            stop_loss=p.stop_loss_price,
            take_profit=p.take_profit_price,
            opened_at=p.opened_at,
        )
        for p in positions
    ]


@router.get("/positions/{symbol}", response_model=PositionResponse)
async def get_position(
    symbol: str,
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Get position for a specific symbol."""
    engine = get_engine()
    if not engine:
        raise HTTPException(status_code=503, detail="Engine not initialized")

    position = await engine.state.get_position(symbol.upper())
    if not position:
        raise HTTPException(status_code=404, detail="Position not found")

    return PositionResponse(
        symbol=position.symbol,
        side=position.side.value,
        quantity=position.quantity,
        entry_price=position.entry_price,
        current_price=position.current_price,
        unrealized_pnl=position.unrealized_pnl,
        realized_pnl=position.realized_pnl,
        leverage=position.leverage,
        liquidation_price=position.liquidation_price,
        stop_loss=position.stop_loss_price,
        take_profit=position.take_profit_price,
        opened_at=position.opened_at,
    )


@router.delete("/positions/{symbol}")
async def close_position(
    symbol: str,
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Close a position."""
    engine = get_engine()
    if not engine or not engine._executor:
        raise HTTPException(status_code=503, detail="Engine not initialized")

    position = await engine.state.get_position(symbol.upper())
    if not position:
        raise HTTPException(status_code=404, detail="Position not found")

    order = await engine._executor.close_position(position)
    if not order:
        raise HTTPException(status_code=500, detail="Failed to close position")

    logger.info(f"Position closed by user", symbol=symbol, user=current_user.username)
    return {"message": f"Position {symbol} closed", "order_id": str(order.order_id)}


# Order Routes
@router.get("/orders", response_model=list[OrderResponse])
async def get_orders(
    current_user: Annotated[User, Depends(get_current_user)],
    status: str = Query(None, description="Filter by status: open, filled, cancelled"),
):
    """Get orders."""
    engine = get_engine()
    if not engine:
        raise HTTPException(status_code=503, detail="Engine not initialized")

    if status == "open":
        orders = await engine.state.get_open_orders()
    else:
        orders = await engine.state.get_all_orders()

    return [
        OrderResponse(
            order_id=str(o.order_id),
            symbol=o.symbol,
            side=o.side.value,
            order_type=o.order_type.value,
            quantity=o.quantity,
            price=o.price,
            filled_quantity=o.filled_quantity,
            status=o.status.value,
            created_at=o.created_at,
        )
        for o in orders
    ]


@router.post("/orders", response_model=OrderResponse)
async def create_order(
    order_request: ManualOrderRequest,
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Create a manual order."""
    engine = get_engine()
    if not engine or not engine._executor:
        raise HTTPException(status_code=503, detail="Engine not initialized")

    # Check risk limits first
    if engine._risk_manager:
        signal = {
            "symbol": order_request.symbol.upper(),
            "side": order_request.side,
            "quantity": order_request.quantity,
            "order_type": order_request.order_type,
            "entry_price": order_request.price or 0,  # Will be fetched
        }
        approved = await engine._risk_manager.check_order(signal)
        if not approved:
            raise HTTPException(status_code=400, detail="Order rejected by risk manager")

    order = await engine._executor.execute({
        "symbol": order_request.symbol.upper(),
        "side": order_request.side,
        "order_type": order_request.order_type,
        "quantity": order_request.quantity,
        "limit_price": order_request.price,
        "stop_price": order_request.stop_price,
        "reduce_only": order_request.reduce_only,
    })

    if not order:
        raise HTTPException(status_code=500, detail="Failed to create order")

    logger.info(
        "Manual order created",
        symbol=order_request.symbol,
        user=current_user.username,
    )

    return OrderResponse(
        order_id=str(order.order_id),
        symbol=order.symbol,
        side=order.side.value,
        order_type=order.order_type.value,
        quantity=order.quantity,
        price=order.price,
        filled_quantity=order.filled_quantity,
        status=order.status.value,
        created_at=order.created_at,
    )


@router.delete("/orders/{order_id}")
async def cancel_order(
    order_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Cancel an order."""
    engine = get_engine()
    if not engine or not engine._executor:
        raise HTTPException(status_code=503, detail="Engine not initialized")

    # Find order by ID
    orders = await engine.state.get_open_orders()
    order = next((o for o in orders if str(o.order_id) == order_id), None)

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    success = await engine._executor.cancel_order(order)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to cancel order")

    logger.info("Order cancelled by user", order_id=order_id, user=current_user.username)
    return {"message": "Order cancelled"}


# Master Input Routes
@router.get("/master-input")
async def get_master_input(current_user: Annotated[User, Depends(get_current_user)]):
    """Get current master input settings."""
    engine = get_engine()
    if not engine:
        raise HTTPException(status_code=503, detail="Engine not initialized")

    return engine.get_master_bias()


@router.put("/master-input")
async def update_master_input(
    request: MasterInputRequest,
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Update master input direction."""
    engine = get_engine()
    if not engine:
        raise HTTPException(status_code=503, detail="Engine not initialized")

    try:
        engine.set_master_direction(request.direction, request.confidence)
        logger.info(
            "Master input updated",
            direction=request.direction,
            confidence=request.confidence,
            user=current_user.username,
        )
        return {"message": "Master input updated", "bias": engine.get_master_bias()}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/master-input/levels")
async def update_key_levels(
    request: KeyLevelsRequest,
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Update key support/resistance levels."""
    engine = get_engine()
    if not engine:
        raise HTTPException(status_code=503, detail="Engine not initialized")

    engine.set_key_levels(request.support, request.resistance)
    return {"message": "Key levels updated"}


# Risk Routes
@router.get("/risk", response_model=RiskStatusResponse)
async def get_risk_status(current_user: Annotated[User, Depends(get_current_user)]):
    """Get risk management status."""
    engine = get_engine()
    if not engine or not engine._risk_manager:
        raise HTTPException(status_code=503, detail="Engine not initialized")

    status = engine._risk_manager.get_risk_status()
    return RiskStatusResponse(**status)


# Performance Routes
@router.get("/performance", response_model=PerformanceResponse)
async def get_performance(current_user: Annotated[User, Depends(get_current_user)]):
    """Get performance metrics."""
    engine = get_engine()
    if not engine or not engine._monitor:
        raise HTTPException(status_code=503, detail="Engine not initialized")

    summary = engine._monitor.get_performance_summary()
    return PerformanceResponse(
        total_trades=summary.get("trades", 0),
        winning_trades=summary.get("wins", 0),
        losing_trades=summary.get("losses", 0),
        win_rate=summary.get("win_rate", 0),
        total_pnl=summary.get("total_pnl", 0),
        avg_win=summary.get("avg_win", 0),
        avg_loss=summary.get("avg_loss", 0),
        profit_factor=summary.get("profit_factor", 0),
        max_drawdown=0,  # TODO: Calculate from monitor
    )


# Market Data Routes
@router.get("/sentiment/{symbol}", response_model=SentimentResponse)
async def get_sentiment(
    symbol: str,
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Get sentiment data for a symbol."""
    engine = get_engine()
    if not engine or not engine._sentiment_engine:
        raise HTTPException(status_code=503, detail="Engine not initialized")

    sentiment = engine._sentiment_engine.get_sentiment(symbol.upper())
    signal = sentiment.get("signal", {})

    return SentimentResponse(
        symbol=symbol.upper(),
        current_score=signal.get("score", 0),
        zscore=signal.get("zscore", 0),
        momentum=sentiment.get("momentum", 0),
        direction=signal.get("direction", "neutral"),
        sources=sentiment.get("by_source", {}),
        timestamp=datetime.utcnow(),
    )


@router.get("/volatility/{symbol}", response_model=VolatilityResponse)
async def get_volatility(
    symbol: str,
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Get volatility data for a symbol."""
    engine = get_engine()
    if not engine or not engine._volatility_engine:
        raise HTTPException(status_code=503, detail="Engine not initialized")

    vol = engine._volatility_engine.get_current_volatility(symbol.upper())
    forecast = engine._volatility_engine.get_volatility_forecast(symbol.upper())

    return VolatilityResponse(
        symbol=symbol.upper(),
        current_volatility=vol.get("volatility", 0) or 0,
        forecast_1d=forecast.get("forecast"),
        regime=vol.get("regime", "unknown"),
        percentile=50,  # TODO: Get from model
        timestamp=datetime.utcnow(),
    )


@router.get("/regime/{symbol}", response_model=RegimeResponse)
async def get_regime(
    symbol: str,
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Get market regime for a symbol."""
    engine = get_engine()
    if not engine or not engine._regime_classifier:
        raise HTTPException(status_code=503, detail="Engine not initialized")

    regime_state = engine._regime_classifier.get_current_regime(symbol.upper())
    if not regime_state:
        raise HTTPException(status_code=404, detail="Regime data not available")

    adjustments = engine._regime_classifier.get_strategy_adjustments(regime_state.regime)

    return RegimeResponse(
        symbol=symbol.upper(),
        regime=regime_state.regime.value,
        confidence=regime_state.confidence,
        trend_strength=regime_state.trend_strength,
        volatility_percentile=regime_state.volatility_percentile,
        strategy_adjustments=adjustments,
    )


# Settings Routes
@router.get("/settings")
async def get_settings_route(current_user: Annotated[User, Depends(get_current_user)]):
    """Get current settings (non-sensitive)."""
    settings = get_settings()

    return {
        "environment": settings.environment.value,
        "exchange": {
            "name": settings.exchange.name,
            "testnet": settings.exchange.testnet,
        },
        "symbols": {
            "primary": settings.symbols.primary,
            "secondary": settings.symbols.secondary,
        },
        "timeframes": {
            "macro_primary": settings.timeframes.macro_primary,
            "meso_primary": settings.timeframes.meso_primary,
            "micro_primary": settings.timeframes.micro_primary,
        },
        "risk": {
            "max_leverage": settings.risk.max_leverage,
            "single_position_risk_pct": settings.risk.single_position_risk_pct,
            "total_portfolio_heat_pct": settings.risk.total_portfolio_heat_pct,
            "daily_loss_limit_pct": settings.risk.daily_loss_limit_pct,
        },
    }
