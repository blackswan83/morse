"""
WebSocket Support
=================

Real-time updates via WebSocket connections.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Any, Set

import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from jose import JWTError, jwt

from mortar_trading.core.events import Event, EventType, get_event_bus
from mortar_trading.web.auth import SECRET_KEY, ALGORITHM, get_user
from mortar_trading.web.app import get_engine

logger = structlog.get_logger(__name__)

router = APIRouter()


class ConnectionManager:
    """Manage WebSocket connections."""

    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.user_connections: dict[str, Set[WebSocket]] = {}
        self._subscriptions: dict[WebSocket, Set[str]] = {}

    async def connect(self, websocket: WebSocket, username: str) -> None:
        """Accept and register a WebSocket connection."""
        await websocket.accept()
        self.active_connections.add(websocket)

        if username not in self.user_connections:
            self.user_connections[username] = set()
        self.user_connections[username].add(websocket)

        self._subscriptions[websocket] = {"all"}  # Subscribe to all by default

        logger.info(f"WebSocket connected", username=username, total=len(self.active_connections))

    def disconnect(self, websocket: WebSocket, username: str) -> None:
        """Remove a WebSocket connection."""
        self.active_connections.discard(websocket)

        if username in self.user_connections:
            self.user_connections[username].discard(websocket)

        self._subscriptions.pop(websocket, None)

        logger.info(f"WebSocket disconnected", username=username)

    def subscribe(self, websocket: WebSocket, channels: list[str]) -> None:
        """Subscribe to specific channels."""
        if websocket not in self._subscriptions:
            self._subscriptions[websocket] = set()
        self._subscriptions[websocket].update(channels)

    def unsubscribe(self, websocket: WebSocket, channels: list[str]) -> None:
        """Unsubscribe from channels."""
        if websocket in self._subscriptions:
            for channel in channels:
                self._subscriptions[websocket].discard(channel)

    async def send_to_user(self, username: str, message: dict) -> None:
        """Send message to all connections of a user."""
        connections = self.user_connections.get(username, set())
        for connection in connections:
            try:
                await connection.send_json(message)
            except Exception:
                pass

    async def broadcast(self, message: dict, channel: str = "all") -> None:
        """Broadcast message to all subscribed connections."""
        disconnected = []

        for websocket in self.active_connections:
            subscriptions = self._subscriptions.get(websocket, set())
            if "all" in subscriptions or channel in subscriptions:
                try:
                    await websocket.send_json(message)
                except Exception:
                    disconnected.append(websocket)

        # Clean up disconnected
        for ws in disconnected:
            self.active_connections.discard(ws)


# Global connection manager
manager = ConnectionManager()


def verify_ws_token(token: str) -> str | None:
    """Verify WebSocket authentication token."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if username and get_user(username):
            return username
        return None
    except JWTError:
        return None


async def setup_event_forwarding():
    """Set up event forwarding to WebSocket clients."""
    event_bus = get_event_bus()

    # Events to forward
    events_to_forward = [
        EventType.TICK,
        EventType.CANDLE,
        EventType.ORDER_PLACED,
        EventType.ORDER_FILLED,
        EventType.ORDER_CANCELLED,
        EventType.POSITION_OPENED,
        EventType.POSITION_CLOSED,
        EventType.REGIME_CHANGE,
        EventType.VOLATILITY_UPDATE,
        EventType.SENTIMENT_UPDATE,
        EventType.RISK_LIMIT_BREACH,
        EventType.CIRCUIT_BREAKER_TRIGGERED,
        EventType.MASTER_INPUT_UPDATE,
    ]

    async def forward_event(event: Event) -> None:
        """Forward event to WebSocket clients."""
        message = {
            "type": "event",
            "event_type": event.event_type.value,
            "symbol": event.symbol,
            "payload": event.payload,
            "timestamp": datetime.utcnow().isoformat(),
        }

        # Determine channel
        if event.symbol:
            channel = f"symbol:{event.symbol}"
        else:
            channel = event.event_type.value

        await manager.broadcast(message, channel)
        await manager.broadcast(message, "all")

    for event_type in events_to_forward:
        event_bus.subscribe(event_type, forward_event)


@router.websocket("/stream")
async def websocket_stream(
    websocket: WebSocket,
    token: str = Query(..., description="JWT access token"),
):
    """
    WebSocket endpoint for real-time updates.

    Connect with: ws://host/ws/stream?token=YOUR_JWT_TOKEN

    Messages sent to client:
    - type: "event" - Trading events (orders, positions, etc.)
    - type: "tick" - Price updates
    - type: "status" - System status updates

    Messages from client:
    - {"action": "subscribe", "channels": ["symbol:BTCUSDT", "orders"]}
    - {"action": "unsubscribe", "channels": ["symbol:BTCUSDT"]}
    - {"action": "ping"}
    """
    # Verify token
    username = verify_ws_token(token)
    if not username:
        await websocket.close(code=4001, reason="Invalid token")
        return

    await manager.connect(websocket, username)

    # Setup event forwarding on first connection
    if len(manager.active_connections) == 1:
        await setup_event_forwarding()

    try:
        # Send initial status
        engine = get_engine()
        if engine:
            await websocket.send_json({
                "type": "status",
                "connected": True,
                "engine_running": engine._running,
                "timestamp": datetime.utcnow().isoformat(),
            })

        # Message loop
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30)
                message = json.loads(data)

                action = message.get("action")

                if action == "subscribe":
                    channels = message.get("channels", [])
                    manager.subscribe(websocket, channels)
                    await websocket.send_json({
                        "type": "subscribed",
                        "channels": channels,
                    })

                elif action == "unsubscribe":
                    channels = message.get("channels", [])
                    manager.unsubscribe(websocket, channels)
                    await websocket.send_json({
                        "type": "unsubscribed",
                        "channels": channels,
                    })

                elif action == "ping":
                    await websocket.send_json({
                        "type": "pong",
                        "timestamp": datetime.utcnow().isoformat(),
                    })

                elif action == "get_status":
                    engine = get_engine()
                    if engine:
                        await websocket.send_json({
                            "type": "status",
                            "data": engine.get_status(),
                            "timestamp": datetime.utcnow().isoformat(),
                        })

            except asyncio.TimeoutError:
                # Send heartbeat on timeout
                await websocket.send_json({
                    "type": "heartbeat",
                    "timestamp": datetime.utcnow().isoformat(),
                })

    except WebSocketDisconnect:
        manager.disconnect(websocket, username)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket, username)


@router.websocket("/prices")
async def websocket_prices(
    websocket: WebSocket,
    token: str = Query(..., description="JWT access token"),
    symbols: str = Query("BTCUSDT,ETHUSDT", description="Comma-separated symbols"),
):
    """
    WebSocket endpoint for price updates only.

    Lightweight endpoint for just price data.
    """
    username = verify_ws_token(token)
    if not username:
        await websocket.close(code=4001, reason="Invalid token")
        return

    await websocket.accept()

    symbol_list = [s.strip().upper() for s in symbols.split(",")]

    try:
        while True:
            # In production, this would stream from exchange WebSocket
            # For now, send periodic updates
            engine = get_engine()
            if engine:
                for symbol in symbol_list:
                    position = await engine.state.get_position(symbol)
                    price = position.current_price if position else None

                    await websocket.send_json({
                        "type": "price",
                        "symbol": symbol,
                        "price": price,
                        "timestamp": datetime.utcnow().isoformat(),
                    })

            await asyncio.sleep(1)

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"Price WebSocket error: {e}")
