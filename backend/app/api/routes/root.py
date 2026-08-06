from fastapi import APIRouter

from app.core.settings import settings

router = APIRouter()


@router.get("/")
def product_overview() -> dict[str, object]:
    return {
        "name": "ParishConnect",
        "service": settings.app_name,
        "version": settings.app_version,
        "status": "skeleton-ready",
        "modules": [
            "members",
            "visitors",
            "attendance",
            "messages",
            "stewardship",
            "reports",
        ],
        "links": {
            "health": "/health",
            "docs": "/docs",
            "api": settings.api_prefix,
        },
    }

