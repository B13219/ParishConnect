from fastapi import APIRouter

from app.core.settings import settings

router = APIRouter()


@router.get("/")
def product_overview() -> dict[str, object]:
    return {
        "name": "Vinyrd",
        "service": settings.app_name,
        "version": settings.app_version,
        "status": "pilot-ready",
        "modules": [
            "members",
            "member_portal",
            "visitors",
            "households",
            "communities",
            "ministries",
            "attendance",
            "messages",
            "pastoral_care",
            "sermons",
            "stewardship",
            "reports",
            "admin",
        ],
        "links": {
            "staff": "/staff/",
            "member": "/member/",
            "health": "/health",
            "docs": "/docs",
            "api": settings.api_prefix,
        },
    }
