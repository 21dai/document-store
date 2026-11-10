"""Cache de documentos en Redis (patrón Cache-Aside).

Redis es un backing service (12-Factor IV): se enchufa con `REDIS_URL`, sin
tocar el código. Guarda solo una copia: la fuente de verdad sigue siendo
MongoDB. Por eso cualquier fallo de Redis se registra y se ignora: sin Redis,
el servicio funciona igual, leyendo de MongoDB. El cache nunca es un punto de
falla.
"""

import json
import logging
from dataclasses import asdict
from datetime import datetime
from typing import Protocol

from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.config import Settings
from app.models.document import Document

logger = logging.getLogger(__name__)

#: Prefijo de las claves en Redis: `documento:7` es el documento con id 7.
KEY_PREFIX = "documento:"

_DATE_FIELDS = ("created_at", "updated_at")


def _key(document_id: int) -> str:
    return f"{KEY_PREFIX}{document_id}"


def _dumps(document: Document) -> str:
    data = asdict(document)
    for field in _DATE_FIELDS:
        data[field] = data[field].isoformat()
    return json.dumps(data, ensure_ascii=False)


def _loads(raw: bytes | str) -> Document:
    data = json.loads(raw)
    for field in _DATE_FIELDS:
        data[field] = datetime.fromisoformat(data[field])
    return Document(**data)


class DocumentCache(Protocol):
    """Lo que el repositorio necesita del cache (DIP)."""

    async def get(self, document_id: int) -> Document | None: ...

    async def set(self, document: Document) -> None: ...

    async def delete(self, document_id: int) -> None: ...

    async def aclose(self) -> None: ...


class NullDocumentCache:
    """Cache desactivado (sin `REDIS_URL`): nunca guarda nada."""

    async def get(self, document_id: int) -> Document | None:
        return None

    async def set(self, document: Document) -> None:
        pass

    async def delete(self, document_id: int) -> None:
        pass

    async def aclose(self) -> None:
        pass


class RedisDocumentCache:
    """Documentos en Redis como JSON, cada uno con vencimiento (TTL).

    El TTL acota cuánto puede durar un dato viejo si se pierde una
    invalidación (por ejemplo, porque Redis no respondía en ese momento).
    """

    def __init__(self, client: Redis, ttl_seconds: int) -> None:
        self._client = client
        self.ttl_seconds = ttl_seconds

    async def get(self, document_id: int) -> Document | None:
        try:
            raw = await self._client.get(_key(document_id))
        except RedisError as exc:
            logger.warning("Redis no responde; se lee de MongoDB: %s", exc)
            return None
        if raw is None:
            return None
        try:
            return _loads(raw)
        except (ValueError, TypeError, KeyError) as exc:
            logger.warning(
                "Entrada ilegible en Redis para el documento %s: %s", document_id, exc
            )
            return None

    async def set(self, document: Document) -> None:
        if document.id is None:
            return
        try:
            await self._client.set(
                _key(document.id), _dumps(document), ex=self.ttl_seconds
            )
        except RedisError as exc:
            logger.warning(
                "No se pudo guardar el documento %s en Redis: %s", document.id, exc
            )

    async def delete(self, document_id: int) -> None:
        try:
            await self._client.delete(_key(document_id))
        except RedisError as exc:
            logger.warning(
                "No se pudo invalidar el documento %s en Redis (dura hasta el TTL): %s",
                document_id,
                exc,
            )

    async def aclose(self) -> None:
        await self._client.aclose()


def build_document_cache(settings: Settings) -> DocumentCache:
    """Cache en Redis si hay `REDIS_URL`; si no, el cache desactivado.

    Timeouts cortos (`REDIS_TIMEOUT_MS`): si Redis no responde, se pasa a
    MongoDB enseguida en lugar de hacer esperar al cliente.
    """
    if not settings.redis_url:
        return NullDocumentCache()
    timeout = settings.redis_timeout_ms / 1000
    client = Redis.from_url(
        settings.redis_url, socket_timeout=timeout, socket_connect_timeout=timeout
    )
    return RedisDocumentCache(client, ttl_seconds=settings.cache_ttl_seconds)
