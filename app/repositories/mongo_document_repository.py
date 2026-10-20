from dataclasses import fields, replace
from typing import Any

from pymongo import ASCENDING, ReturnDocument
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import DuplicateKeyError

from app.exceptions import DocumentAlreadyExistsError
from app.models.document import Document, utc_now
from app.repositories.document_repository import DocumentRepository

DOCUMENTS = "documents"
COUNTERS = "counters"
# Documento de la colección `counters` que lleva el último id asignado.
DOCUMENTS_SEQUENCE = "documents"

_DOCUMENT_FIELDS = tuple(f.name for f in fields(Document))


def to_mongo(document: Document) -> dict[str, Any]:
    """Serializa un documento a su representación en MongoDB."""
    return {name: getattr(document, name) for name in _DOCUMENT_FIELDS}


def from_mongo(data: dict[str, Any]) -> Document:
    """Reconstruye un documento desde MongoDB.

    Toma solo los campos del modelo: ignora el `_id` interno y cualquier campo
    que haya agregado otra versión del servicio.
    """
    return Document(**{name: data[name] for name in _DOCUMENT_FIELDS if name in data})


async def ensure_indexes(database: AsyncDatabase) -> None:
    """Crea los índices únicos de `documents` (idempotente).

    La unicidad de `checksum` la garantiza la base, no solo el service: dos
    altas simultáneas del mismo PDF pasan la verificación previa y solo el
    índice evita guardarlo dos veces.
    """
    collection = database[DOCUMENTS]
    await collection.create_index([("id", ASCENDING)], unique=True, name="id_unico")
    await collection.create_index(
        [("checksum", ASCENDING)], unique=True, name="checksum_unico"
    )


class MongoDocumentRepository(DocumentRepository):
    """Implementación de DocumentRepository sobre MongoDB (PyMongo async)."""

    def __init__(self, database: AsyncDatabase) -> None:
        self._documents = database[DOCUMENTS]
        self._counters = database[COUNTERS]

    async def create(self, document: Document) -> Document:
        new_document = replace(document, id=await self._next_id())
        try:
            await self._documents.insert_one(to_mongo(new_document))
        except DuplicateKeyError as exc:
            if "checksum" in (exc.details or {}).get("keyPattern", {}):
                raise DocumentAlreadyExistsError(document.checksum) from exc
            raise
        return new_document

    async def get_by_id(self, document_id: int) -> Document | None:
        data = await self._documents.find_one({"id": document_id})
        return from_mongo(data) if data else None

    async def get_by_checksum(self, checksum: str) -> Document | None:
        data = await self._documents.find_one({"checksum": checksum})
        return from_mongo(data) if data else None

    async def list(self, skip: int, limit: int) -> list[Document]:
        cursor = self._documents.find().skip(skip).limit(limit)
        return [from_mongo(data) async for data in cursor]

    async def update(self, document: Document) -> Document | None:
        document.updated_at = utc_now()
        data = await self._documents.find_one_and_update(
            {"id": document.id},
            {"$set": {"name": document.name, "updated_at": document.updated_at}},
            return_document=ReturnDocument.AFTER,
        )
        return from_mongo(data) if data else None

    async def delete(self, document_id: int) -> bool:
        result = await self._documents.delete_one({"id": document_id})
        return result.deleted_count == 1

    async def _next_id(self) -> int:
        """Siguiente id secuencial, atómico aunque haya altas concurrentes.

        `$inc` con `upsert` es una sola operación atómica en MongoDB: dos
        altas a la vez nunca reciben el mismo número. Un alta que después
        falla (por ejemplo, checksum duplicado) deja un hueco en la secuencia.
        """
        counter = await self._counters.find_one_and_update(
            {"_id": DOCUMENTS_SEQUENCE},
            {"$inc": {"seq": 1}},
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
        if counter is None:  # no ocurre con upsert + AFTER; lo exige el tipado
            raise RuntimeError("MongoDB no devolvió el contador de documentos.")
        return int(counter["seq"])
