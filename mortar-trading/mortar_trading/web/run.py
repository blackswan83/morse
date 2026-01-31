"""
Web Application Runner
======================

Starts the FastAPI web server.
"""

import argparse
import os


def main():
    """Run the web application."""
    parser = argparse.ArgumentParser(description="Mortar Trading Web Server")
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host to bind to (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind to (default: 8000)",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload for development",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Number of worker processes (default: 1)",
    )

    args = parser.parse_args()

    # Set environment variable for config
    os.environ.setdefault("ENVIRONMENT", "development")

    import uvicorn

    print(f"""
    ╔══════════════════════════════════════════════════════════╗
    ║           Mortar Trading - Web Dashboard                 ║
    ╠══════════════════════════════════════════════════════════╣
    ║                                                          ║
    ║   Starting server at http://{args.host}:{args.port}                ║
    ║                                                          ║
    ║   Default credentials:                                   ║
    ║     Username: admin                                      ║
    ║     Password: admin123                                   ║
    ║                                                          ║
    ║   API Docs: http://{args.host}:{args.port}/api/docs                ║
    ║                                                          ║
    ╚══════════════════════════════════════════════════════════╝
    """)

    uvicorn.run(
        "mortar_trading.web.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        workers=args.workers if not args.reload else 1,
        log_level="info",
    )


if __name__ == "__main__":
    main()
