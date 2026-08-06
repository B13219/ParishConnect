from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response

from app.api.health import router as health_router
from app.api.routes import router as api_router
from app.core.settings import settings


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Church management and engagement API.",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[origin.strip() for origin in settings.cors_origins.split(",")],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health_router, tags=["health"])
    app.include_router(api_router, prefix=settings.api_prefix)

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    def landing_page() -> str:
        return f"""
        <!doctype html>
        <html lang="en">
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <title>ParishConnect API</title>
            <style>
                body {{
                    margin: 0;
                    min-height: 100vh;
                    display: grid;
                    place-items: center;
                    font-family: Arial, sans-serif;
                    color: #0b1f55;
                    background: #f6f8fb;
                }}
                main {{
                    width: min(860px, calc(100% - 48px));
                    background: #fff;
                    border: 1px solid #d8e0ef;
                    border-radius: 8px;
                    padding: 32px;
                    box-shadow: 0 16px 48px rgba(11, 31, 85, 0.08);
                }}
                h1 {{ margin: 0 0 8px; font-size: 34px; }}
                p {{ margin: 0 0 22px; color: #31405f; line-height: 1.55; }}
                .grid {{
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
                    gap: 12px;
                    margin: 24px 0;
                }}
                .metric {{
                    border: 1px solid #d8e0ef;
                    border-radius: 8px;
                    padding: 16px;
                    background: #fbfcff;
                }}
                .metric strong {{ display: block; font-size: 20px; margin-bottom: 4px; }}
                a {{
                    color: #0f5bb5;
                    font-weight: 700;
                    text-decoration: none;
                    margin-right: 18px;
                }}
            </style>
        </head>
        <body>
            <main>
                <h1>ParishConnect</h1>
                <p>
                    Church management and engagement API skeleton for members,
                    visitors, attendance, messaging, and stewardship.
                </p>
                <div class="grid">
                    <div class="metric"><strong>0.1.0</strong>API Version</div>
                    <div class="metric"><strong>11</strong>Database Tables</div>
                    <div class="metric"><strong>5</strong>Core Modules</div>
                </div>
                <a href="/docs">Open API Docs</a>
                <a href="/health">Health Check</a>
                <a href="{settings.api_prefix}/">API Overview</a>
            </main>
        </body>
        </html>
        """

    @app.get("/favicon.ico", include_in_schema=False)
    def favicon() -> Response:
        return Response(status_code=204)

    return app


app = create_app()
