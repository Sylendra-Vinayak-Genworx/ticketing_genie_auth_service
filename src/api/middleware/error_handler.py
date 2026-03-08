from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from src.core.exceptions.auth import ApplicationError


def register_exception_handlers(app: FastAPI) -> None:
    """Register global exception handlers for the application."""

    @app.exception_handler(ApplicationError)
    async def application_error_handler(
        request: Request,
        exc: ApplicationError,
    ) -> JSONResponse:
        """Handle all custom application errors."""
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "detail": exc.detail,
                "errors": exc.details,
            },
            headers=exc.headers or {},
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        """Catch-all handler for unexpected errors."""
        return JSONResponse(
            status_code=500,
            content={
                "detail": "Internal server error",
            },
        )
