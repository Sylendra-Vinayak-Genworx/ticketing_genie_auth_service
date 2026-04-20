from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from sqlalchemy import text

from src.api.middleware.error_handler import register_exception_handlers
from src.api.rest.routes.auth import router as auth_router
from src.api.rest.routes.team_routes import router as team_router
from src.config.settings import get_settings
from src.data.clients.postgres_client import engine
from src.data.models.postgres.base import Base
from src.observability.logging.logger import setup_logging

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Lifespan.

    Args:
        app (FastAPI): Input parameter.

    Returns:
        AsyncGenerator[None, None]: The expected output.
    """
    async with engine.begin() as conn:
        await conn.execute(text("CREATE SCHEMA IF NOT EXISTS auth"))
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


def create_app() -> FastAPI:
    """
    Create app.

    Returns:
        FastAPI: The expected output.
    """
    setup_logging()
    app = FastAPI(
        title="Auth Service",
        version="1.0.0",
        description=(
            "## Authentication\n"
            "Use `POST /api/v1/auth/login` to get an access token, "
            "then click **Authorize** and paste it."
        ),
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost",
            "http://localhost:80",
            "http://127.0.0.1",
            "https://ticketing-genie-frontend-717740758627.us-east1.run.app",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(team_router, prefix="/api/v1")

    def custom_openapi() -> dict:
        """
        Custom openapi.

        Returns:
            dict: The expected output.
        """
        if app.openapi_schema:
            return app.openapi_schema
        schema = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes,
        )
        schema.setdefault("components", {})["securitySchemes"] = {
            "BearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
            }
        }
        for path_data in schema.get("paths", {}).values():
            for operation in path_data.values():
                if isinstance(operation, dict):
                    operation.setdefault("security", [{"BearerAuth": []}])
        app.openapi_schema = schema
        return schema

    app.openapi = custom_openapi
    return app
