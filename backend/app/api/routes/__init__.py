from fastapi import APIRouter

from app.api.routes.admin import router as admin_router
from app.api.routes.attendance import router as attendance_router
from app.api.routes.auth import router as auth_router
from app.api.routes.imports import router as imports_router
from app.api.routes.member_portal import router as member_portal_router
from app.api.routes.members import router as members_router
from app.api.routes.messages import router as messages_router
from app.api.routes.reports import router as reports_router
from app.api.routes.root import router as root_router
from app.api.routes.staff_engagement import router as staff_engagement_router
from app.api.routes.stewardship import router as stewardship_router

router = APIRouter()
router.include_router(root_router, tags=["product"])
router.include_router(auth_router, prefix="/auth", tags=["auth"])
router.include_router(admin_router, prefix="/admin", tags=["admin"])
router.include_router(members_router, prefix="/members", tags=["members"])
router.include_router(member_portal_router, prefix="/member-portal", tags=["member-portal"])
router.include_router(attendance_router, prefix="/attendance", tags=["attendance"])
router.include_router(imports_router, prefix="/imports", tags=["imports"])
router.include_router(messages_router, prefix="/messages", tags=["messages"])
router.include_router(stewardship_router, prefix="/stewardship", tags=["stewardship"])
router.include_router(staff_engagement_router, prefix="/staff", tags=["staff-engagement"])
router.include_router(reports_router, prefix="/reports", tags=["reports"])
