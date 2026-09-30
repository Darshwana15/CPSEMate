"""
API v1 router.

Central router for the /api/v1/ namespace.
Domain routers will be included here in later phases.
"""

from fastapi import APIRouter

from app.api.v1.endpoints import materials, reviews, cpses, national_materials, audit, dashboard

api_v1_router = APIRouter()

@api_v1_router.get("/health")
def health_check() -> dict:
    """
    Health check endpoint.

    Returns a simple deterministic response confirming
    the application is alive.
    """
    return {"status": "ok"}

api_v1_router.include_router(materials.router, prefix="/materials", tags=["materials"])
api_v1_router.include_router(reviews.router, prefix="/reviews", tags=["reviews"])
api_v1_router.include_router(cpses.router, prefix="/cpses", tags=["cpses"])
api_v1_router.include_router(national_materials.router, prefix="/national-materials", tags=["national_materials"])
api_v1_router.include_router(audit.router, prefix="/audit", tags=["audit"])
api_v1_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
