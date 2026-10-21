"""Repositorio en memoria para probar el service sin MongoDB (test double fake)."""

from dataclasses import replace

from app.exceptions import DocumentAlreadyExistsError
from app.models.document import Document, utc_now
from app.repositories.document_repository import DocumentRepository


class InMemoryDocumentRepository(DocumentRepository):
    """Implementa el puerto con la misma semántica que el de MongoDB."""

    def __init__(self) -> None:
        self.documents: dict[int, Document] = {}
        self._last_id = 0

    async def create(self, document: Document) -> Document:
        if any(d.checksum == document.checksum for d in self.documents.values()):
            raise DocumentAlreadyExistsError(document.checksum)
        self._last_id += 1
        created = replace(document, id=self._last_id)
        self.documents[self._last_id] = created
        return created

    async def get_by_id(self, document_id: int) -> Document | None:
        return self.documents.get(document_id)

    async def get_by_checksum(self, checksum: str) -> Document | None:
        return next(
            (d for d in self.documents.values() if d.checksum == checksum), None
        )

    async def list(self, skip: int, limit: int) -> list[Document]:
        ordered = sorted(self.documents.values(), key=lambda d: d.id or 0)
        return ordered[skip : skip + limit]

    async def update(self, document: Document) -> Document | None:
        if document.id is None:
            return None
        current = self.documents.get(document.id)
        if current is None:
            return None
        updated = replace(current, name=document.name, updated_at=utc_now())
        self.documents[document.id] = updated
        return updated

    async def delete(self, document_id: int) -> bool:
        return self.documents.pop(document_id, None) is not None
