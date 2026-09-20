from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.api.health import router as health_router
from app.api.routes import router as api_router
from app.core.settings import settings

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"
MEMBER_FRONTEND_DIR = FRONTEND_DIR / "member-app"


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Vinyrd church management and engagement API.",
    )

    origins = [
        origin.strip()
        for origin in settings.cors_origins.split(",")
        if origin.strip()
    ]
    if origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    app.include_router(health_router, tags=["health"])
    app.include_router(api_router, prefix=settings.api_prefix)

    if MEMBER_FRONTEND_DIR.exists():
        app.mount(
            "/member",
            StaticFiles(directory=str(MEMBER_FRONTEND_DIR), html=True),
            name="member-app",
        )
    if FRONTEND_DIR.exists():
        app.mount(
            "/staff",
            StaticFiles(directory=str(FRONTEND_DIR), html=True),
            name="staff-console",
        )

    @app.get("/", include_in_schema=False)
    def landing_page() -> RedirectResponse:
        return RedirectResponse(url="/staff/", status_code=307)

    @app.get("/favicon.ico", include_in_schema=False)
    def favicon() -> RedirectResponse:
        return RedirectResponse(url="/staff/assets/vinyrd-mark.svg", status_code=307)

    return app


app = create_app()
