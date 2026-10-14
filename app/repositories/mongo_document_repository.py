from datetime import datetime, timezone
from typing import Any

from pymongo import ReturnDocument
from pymongo.asynchronous.database import AsyncDatabase

from app.models.document import Document
from app.repositories.document_repository import DocumentRepository


class MongoDocumentRepository(DocumentRepository):
    """Implementación de DocumentRepository sobre MongoDB (PyMongo async).

    El índice único sobre `checksum` (garantía de duplicados a nivel base de
    datos) se configura en el issue #3 junto con el resto de la persistencia.
    """

    COLLECTION_NAME = "documents"

    def __init__(self, database: AsyncDatabase) -> None:
        self._collection = database[self.COLLECTION_NAME]

    async def create(self, document: Document) -> Document:
        await self._collection.insert_one(self._to_mongo(document))
        return document

    async def get_by_id(self, document_id: str) -> Document | None:
        data = await self._collection.find_one({"id": document_id})
        return self._from_mongo(data) if data else None

    async def get_by_checksum(self, checksum: str) -> Document | None:
        data = await self._collection.find_one({"checksum": checksum})
        return self._from_mongo(data) if data else None

    async def list(self, skip: int, limit: int) -> list[Document]:
        cursor = self._collection.find().skip(skip).limit(limit)
        return [self._from_mongo(data) async for data in cursor]

    async def update(self, document: Document) -> Document | None:
        document.updated_at = datetime.now(timezone.utc)
        data = await self._collection.find_one_and_update(
            {"id": document.id},
            {"$set": {"name": document.name, "updated_at": document.updated_at}},
            return_document=ReturnDocument.AFTER,
        )
        return self._from_mongo(data) if data else None

    async def delete(self, document_id: str) -> bool:
        result = await self._collection.delete_one({"id": document_id})
        return result.deleted_count == 1

    @staticmethod
    def _to_mongo(document: Document) -> dict[str, Any]:
        return {
            "id": document.id,
            "name": document.name,
            "original_filename": document.original_filename,
            "checksum": document.checksum,
            "file_size": document.file_size,
            "page_count": document.page_count,
            "extracted_text": document.extracted_text,
            "is_processed": document.is_processed,
            "created_at": document.created_at,
            "updated_at": document.updated_at,
        }

    @staticmethod
    def _from_mongo(data: dict[str, Any]) -> Document:
        data.pop("_id", None)
        return Document(**data)
