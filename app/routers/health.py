from fastapi import APIRouter, status
from pymongo.errors import PyMongoError

from app.dependencies import DatabaseDep
from app.exceptions import DatabaseUnavailableError
from app.schemas.error import ProblemDetail

router = APIRouter(tags=["health"])


@router.get("/health", summary="Liveness: el proceso está vivo")
async def health() -> dict[str, str]:
    """No toca MongoDB: responde aunque la base esté caída."""
    return {"status": "ok"}


@router.get(
    "/ready",
    summary="Readiness: MongoDB responde",
    responses={
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "model": ProblemDetail,
            "description": "La base de datos no está disponible",
        }
    },
)
async def ready(database: DatabaseDep) -> dict[str, str]:
    """Hace `ping` a MongoDB con la conexión de la app. La usa el HEALTHCHECK de Docker.

    Si la base no responde falla en `DATABASE_TIMEOUT_MS` (3 s por defecto)
    y responde 503 con Problem Details.
    """
    try:
        await database.command("ping")
    except PyMongoError as exc:
        raise DatabaseUnavailableError() from exc
    return {"status": "ready"}
