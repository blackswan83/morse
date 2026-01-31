"""
Mortar Trading Web Application
==============================

FastAPI-based web dashboard with authentication.

Usage:
    mortar-web --host 0.0.0.0 --port 8000

Default credentials:
    Username: admin
    Password: admin123
"""

from mortar_trading.web.app import app, create_app

__all__ = ["app", "create_app"]
