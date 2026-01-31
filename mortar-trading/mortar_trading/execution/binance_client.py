"""
Binance Futures Client
======================

Exchange connector for Binance Futures.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import time
from datetime import datetime
from typing import Any
from urllib.parse import urlencode

import aiohttp
import structlog

from mortar_trading.config import Settings
from mortar_trading.core.state import Order, OrderSide, OrderType, OrderStatus, Position, PositionSide

logger = structlog.get_logger(__name__)


class BinanceFuturesClient:
    """
    Async client for Binance Futures API.

    Supports:
    - Account information
    - Order placement and management
    - Position management
    - Market data
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self._session: aiohttp.ClientSession | None = None

        # API credentials
        self._api_key = (
            settings.exchange.api_key.get_secret_value()
            if settings.exchange.api_key
            else None
        )
        self._api_secret = (
            settings.exchange.api_secret.get_secret_value()
            if settings.exchange.api_secret
            else None
        )

    @property
    def base_url(self) -> str:
        """Get API base URL."""
        return self.settings.exchange.rest_endpoint

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self) -> None:
        """Close HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()

    def _sign(self, params: dict[str, Any]) -> str:
        """Sign request parameters."""
        if not self._api_secret:
            return ""

        query_string = urlencode(params)
        signature = hmac.new(
            self._api_secret.encode(),
            query_string.encode(),
            hashlib.sha256,
        ).hexdigest()
        return signature

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
        signed: bool = False,
    ) -> dict[str, Any]:
        """Make API request."""
        session = await self._get_session()

        url = f"{self.base_url}{endpoint}"
        params = params or {}

        headers = {}
        if self._api_key:
            headers["X-MBX-APIKEY"] = self._api_key

        if signed:
            params["timestamp"] = int(time.time() * 1000)
            params["signature"] = self._sign(params)

        try:
            if method == "GET":
                async with session.get(url, params=params, headers=headers) as response:
                    data = await response.json()
                    if response.status != 200:
                        raise Exception(f"API error: {data}")
                    return data
            elif method == "POST":
                async with session.post(url, params=params, headers=headers) as response:
                    data = await response.json()
                    if response.status != 200:
                        raise Exception(f"API error: {data}")
                    return data
            elif method == "DELETE":
                async with session.delete(url, params=params, headers=headers) as response:
                    data = await response.json()
                    if response.status != 200:
                        raise Exception(f"API error: {data}")
                    return data
            else:
                raise ValueError(f"Unknown method: {method}")

        except aiohttp.ClientError as e:
            logger.error(f"HTTP error: {e}")
            raise

    # Account endpoints

    async def get_account_info(self) -> dict[str, Any]:
        """Get account information."""
        return await self._request("GET", "/fapi/v2/account", signed=True)

    async def get_balance(self) -> dict[str, float]:
        """Get account balances."""
        account = await self.get_account_info()
        balances = {}
        for asset in account.get("assets", []):
            if float(asset.get("walletBalance", 0)) > 0:
                balances[asset["asset"]] = {
                    "wallet": float(asset["walletBalance"]),
                    "available": float(asset["availableBalance"]),
                    "unrealized_pnl": float(asset.get("unrealizedProfit", 0)),
                }
        return balances

    async def get_positions(self) -> list[dict[str, Any]]:
        """Get open positions."""
        account = await self.get_account_info()
        positions = []
        for pos in account.get("positions", []):
            if float(pos.get("positionAmt", 0)) != 0:
                positions.append({
                    "symbol": pos["symbol"],
                    "side": "long" if float(pos["positionAmt"]) > 0 else "short",
                    "quantity": abs(float(pos["positionAmt"])),
                    "entry_price": float(pos["entryPrice"]),
                    "unrealized_pnl": float(pos.get("unrealizedProfit", 0)),
                    "leverage": int(pos.get("leverage", 1)),
                    "liquidation_price": float(pos.get("liquidationPrice", 0)),
                })
        return positions

    # Order endpoints

    async def place_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: float,
        price: float | None = None,
        stop_price: float | None = None,
        reduce_only: bool = False,
        time_in_force: str = "GTC",
        client_order_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Place a new order.

        Args:
            symbol: Trading pair (e.g., BTCUSDT)
            side: BUY or SELL
            order_type: LIMIT, MARKET, STOP, etc.
            quantity: Order quantity
            price: Limit price (for LIMIT orders)
            stop_price: Stop price (for STOP orders)
            reduce_only: Reduce-only flag
            time_in_force: Time in force (GTC, IOC, FOK)
            client_order_id: Custom order ID

        Returns:
            Order response
        """
        params = {
            "symbol": symbol,
            "side": side.upper(),
            "type": order_type.upper(),
            "quantity": quantity,
        }

        if price:
            params["price"] = price
        if stop_price:
            params["stopPrice"] = stop_price
        if reduce_only:
            params["reduceOnly"] = "true"
        if time_in_force and order_type.upper() != "MARKET":
            params["timeInForce"] = time_in_force
        if client_order_id:
            params["newClientOrderId"] = client_order_id

        logger.info(
            "Placing order",
            symbol=symbol,
            side=side,
            type=order_type,
            quantity=quantity,
            price=price,
        )

        return await self._request("POST", "/fapi/v1/order", params, signed=True)

    async def cancel_order(
        self,
        symbol: str,
        order_id: int | None = None,
        client_order_id: str | None = None,
    ) -> dict[str, Any]:
        """Cancel an order."""
        params = {"symbol": symbol}
        if order_id:
            params["orderId"] = order_id
        if client_order_id:
            params["origClientOrderId"] = client_order_id

        logger.info("Cancelling order", symbol=symbol, order_id=order_id)

        return await self._request("DELETE", "/fapi/v1/order", params, signed=True)

    async def cancel_all_orders(self, symbol: str) -> dict[str, Any]:
        """Cancel all open orders for a symbol."""
        params = {"symbol": symbol}
        logger.info("Cancelling all orders", symbol=symbol)
        return await self._request("DELETE", "/fapi/v1/allOpenOrders", params, signed=True)

    async def get_order(
        self,
        symbol: str,
        order_id: int | None = None,
        client_order_id: str | None = None,
    ) -> dict[str, Any]:
        """Get order status."""
        params = {"symbol": symbol}
        if order_id:
            params["orderId"] = order_id
        if client_order_id:
            params["origClientOrderId"] = client_order_id

        return await self._request("GET", "/fapi/v1/order", params, signed=True)

    async def get_open_orders(self, symbol: str | None = None) -> list[dict[str, Any]]:
        """Get all open orders."""
        params = {}
        if symbol:
            params["symbol"] = symbol
        return await self._request("GET", "/fapi/v1/openOrders", params, signed=True)

    # Leverage and margin

    async def set_leverage(self, symbol: str, leverage: int) -> dict[str, Any]:
        """Set leverage for a symbol."""
        params = {
            "symbol": symbol,
            "leverage": leverage,
        }
        logger.info("Setting leverage", symbol=symbol, leverage=leverage)
        return await self._request("POST", "/fapi/v1/leverage", params, signed=True)

    async def set_margin_type(self, symbol: str, margin_type: str) -> dict[str, Any]:
        """Set margin type (ISOLATED or CROSSED)."""
        params = {
            "symbol": symbol,
            "marginType": margin_type.upper(),
        }
        return await self._request("POST", "/fapi/v1/marginType", params, signed=True)

    # Market data

    async def get_ticker(self, symbol: str) -> dict[str, Any]:
        """Get current ticker price."""
        params = {"symbol": symbol}
        return await self._request("GET", "/fapi/v1/ticker/price", params)

    async def get_order_book(self, symbol: str, limit: int = 20) -> dict[str, Any]:
        """Get order book."""
        params = {"symbol": symbol, "limit": limit}
        return await self._request("GET", "/fapi/v1/depth", params)

    async def get_mark_price(self, symbol: str) -> dict[str, Any]:
        """Get mark price and funding rate."""
        params = {"symbol": symbol}
        return await self._request("GET", "/fapi/v1/premiumIndex", params)


class OrderBuilder:
    """Helper class to build orders with proper formatting."""

    def __init__(self, symbol: str):
        self.symbol = symbol
        self._side: str | None = None
        self._type: str = "MARKET"
        self._quantity: float = 0
        self._price: float | None = None
        self._stop_price: float | None = None
        self._reduce_only: bool = False
        self._time_in_force: str = "GTC"
        self._client_order_id: str | None = None

    def buy(self) -> "OrderBuilder":
        self._side = "BUY"
        return self

    def sell(self) -> "OrderBuilder":
        self._side = "SELL"
        return self

    def market(self) -> "OrderBuilder":
        self._type = "MARKET"
        return self

    def limit(self, price: float) -> "OrderBuilder":
        self._type = "LIMIT"
        self._price = price
        return self

    def stop_market(self, stop_price: float) -> "OrderBuilder":
        self._type = "STOP_MARKET"
        self._stop_price = stop_price
        return self

    def stop_limit(self, stop_price: float, limit_price: float) -> "OrderBuilder":
        self._type = "STOP"
        self._stop_price = stop_price
        self._price = limit_price
        return self

    def take_profit(self, stop_price: float) -> "OrderBuilder":
        self._type = "TAKE_PROFIT_MARKET"
        self._stop_price = stop_price
        return self

    def quantity(self, qty: float) -> "OrderBuilder":
        self._quantity = qty
        return self

    def reduce_only(self) -> "OrderBuilder":
        self._reduce_only = True
        return self

    def client_id(self, client_id: str) -> "OrderBuilder":
        self._client_order_id = client_id
        return self

    def build(self) -> dict[str, Any]:
        """Build order parameters."""
        if not self._side:
            raise ValueError("Order side not set")
        if self._quantity <= 0:
            raise ValueError("Order quantity must be positive")

        return {
            "symbol": self.symbol,
            "side": self._side,
            "order_type": self._type,
            "quantity": self._quantity,
            "price": self._price,
            "stop_price": self._stop_price,
            "reduce_only": self._reduce_only,
            "time_in_force": self._time_in_force,
            "client_order_id": self._client_order_id,
        }
