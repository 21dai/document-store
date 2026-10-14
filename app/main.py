from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from pymongo import AsyncMongoClient

from app.config import get_settings
from app.routers import documents, health


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Gestiona el ciclo de vida de la conexión a MongoDB."""
    settings = get_settings()
    client: AsyncMongoClient = AsyncMongoClient(settings.mongo_uri)
    app.state.mongo_client = client
    app.state.mongo_db = client[settings.mongo_db_name]
    try:
        yield
    finally:
        await client.close()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.debug,
        lifespan=lifespan,
    )

    app.include_router(health.router)
    app.include_router(documents.router, prefix=settings.api_v1_prefix)

    return app


app = create_app()
