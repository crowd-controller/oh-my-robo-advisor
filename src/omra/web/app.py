"""FastAPI composition for the M0 readiness-only HTTP surface."""

from collections.abc import Callable

from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from omra.monitoring.readiness import ReadinessReport, ReadinessStatus


def create_app(provider: Callable[[], ReadinessReport]) -> FastAPI:
    """Create the M0 app without importing the runtime composition root."""
    application = FastAPI(title="Oh My Robo Advisor", version="0.1.0")

    @application.get("/readyz", response_model=ReadinessReport)
    def readyz() -> JSONResponse:
        report = provider()
        status_code = 200 if report.status is ReadinessStatus.READY else 503
        return JSONResponse(
            status_code=status_code,
            content=jsonable_encoder(report),
        )

    return application


__all__ = ["create_app"]
