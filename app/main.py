import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from pymongo import AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import PyMongoError

from app.config import Settings, get_settings
from app.repositories.mongo_document_repository import ensure_indexes
from app.routers import documents, health

logger = logging.getLogger(__name__)

# Espera entre intentos de crear los índices si MongoDB no estaba al arrancar.
INDEX_RETRY_SECONDS = 2.0


async def _ensure_indexes_until_ready(database: AsyncDatabase) -> None:
    """Reintenta crear los índices hasta que MongoDB responda."""
    while True:
        await asyncio.sleep(INDEX_RETRY_SECONDS)
        try:
            await ensure_indexes(database)
        except PyMongoError as exc:
            logger.warning("MongoDB sigue sin responder; índices pendientes: %s", exc)
        else:
            logger.info("Índices de MongoDB creados")
            return


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Abre la conexión a MongoDB, asegura los índices y la cierra al final.

    Si MongoDB no responde al arrancar, la app arranca igual (`/health` no
    depende de la base) y los índices se crean en segundo plano apenas la
    base esté disponible.
    """
    settings: Settings = app.state.settings
    client: AsyncMongoClient = AsyncMongoClient(
        settings.database_url,
        tz_aware=True,
        connectTimeoutMS=settings.database_timeout_ms,
        serverSelectionTimeoutMS=settings.database_timeout_ms,
    )
    database = client[settings.database_name]
    app.state.mongo_client = client
    app.state.mongo_db = database

    retry_task: asyncio.Task[None] | None = None
    try:
        await ensure_indexes(database)
    except PyMongoError as exc:
        logger.warning("No se pudieron crear los índices al arrancar: %s", exc)
        retry_task = asyncio.create_task(_ensure_indexes_until_ready(database))
    try:
        yield
    finally:
        if retry_task is not None:
            retry_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await retry_task
        await client.close()


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.debug,
        lifespan=lifespan,
    )
    app.state.settings = settings

    app.include_router(health.router)
    app.include_router(documents.router, prefix=settings.api_v1_prefix)

    return app


app = create_app()
