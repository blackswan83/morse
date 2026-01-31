"""
Web Application
===============

FastAPI web server for Mortar Trading.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from mortar_trading.config import Settings, get_settings
from mortar_trading.core import TradingEngine
from mortar_trading.web.api import router as api_router
from mortar_trading.web.auth import router as auth_router
from mortar_trading.web.websocket import router as ws_router

logger = structlog.get_logger(__name__)

# Global engine instance
_engine: TradingEngine | None = None


def get_engine() -> TradingEngine | None:
    """Get the global trading engine instance."""
    return _engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    global _engine

    settings = get_settings()
    logger.info("Starting Mortar Trading Web Application")

    # Initialize trading engine
    _engine = TradingEngine(settings)
    await _engine.initialize()

    # Start engine in background (don't block)
    engine_task = asyncio.create_task(_engine.start())

    yield

    # Shutdown
    logger.info("Shutting down...")
    await _engine.stop()
    engine_task.cancel()


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = settings or get_settings()

    app = FastAPI(
        title="Mortar Trading",
        description="Crypto Volatility Trading Bot",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure appropriately for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers
    app.include_router(auth_router, prefix="/api/auth", tags=["Authentication"])
    app.include_router(api_router, prefix="/api", tags=["Trading"])
    app.include_router(ws_router, prefix="/ws", tags=["WebSocket"])

    # Static files (for frontend)
    try:
        from pathlib import Path
        static_path = Path(__file__).parent / "static"
        if static_path.exists():
            app.mount("/static", StaticFiles(directory=str(static_path)), name="static")
    except Exception:
        pass

    # Templates
    try:
        from pathlib import Path
        templates_path = Path(__file__).parent / "templates"
        if templates_path.exists():
            templates = Jinja2Templates(directory=str(templates_path))

            @app.get("/", include_in_schema=False)
            async def index(request: Request):
                return templates.TemplateResponse("index.html", {"request": request})
    except Exception:
        pass

    # Exception handlers
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error(f"Unhandled exception: {exc}")
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )

    # Health check
    @app.get("/health", tags=["System"])
    async def health_check():
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "engine_running": _engine is not None and _engine._running,
        }

    return app


# Create default app instance
app = create_app()
