"""
SIH26099 — Backend Application

AI-Driven Standardization and Harmonization of Material Codes Across CPSEs.

FastAPI application entrypoint.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.v1.router import api_v1_router


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    application = FastAPI(
        title="SIH26099 — Material Code Harmonization",
        description=(
            "AI-Driven Standardization and Harmonization "
            "of Material Codes Across CPSEs"
        ),
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # --- CORS ---
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["*"],
    )

    # --- Routers ---
    application.include_router(
        api_v1_router,
        prefix=settings.api_v1_prefix,
    )

    return application


app = create_app()
