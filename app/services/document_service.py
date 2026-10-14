from app.models.document import Document
from app.repositories.document_repository import DocumentRepository
from app.schemas.document import DocumentCreate, DocumentUpdate


class DocumentAlreadyExistsError(Exception):
    """Ya existe un documento con el mismo checksum (HTTP 409)."""


class DocumentNotFoundError(Exception):
    """No existe un documento con el ID indicado (HTTP 404)."""


class DocumentService:
    """Lógica de negocio de documentos.

    Depende de la abstracción DocumentRepository (no de MongoDB), siguiendo
    el principio de inversión de dependencias (DIP).
    """

    def __init__(self, repository: DocumentRepository) -> None:
        self._repository = repository

    async def create_document(self, payload: DocumentCreate) -> Document:
        existing = await self._repository.get_by_checksum(payload.checksum)
        if existing is not None:
            raise DocumentAlreadyExistsError(payload.checksum)
        document = Document(**payload.model_dump())
        return await self._repository.create(document)

    async def get_document(self, document_id: str) -> Document:
        document = await self._repository.get_by_id(document_id)
        if document is None:
            raise DocumentNotFoundError(document_id)
        return document

    async def list_documents(self, skip: int, limit: int) -> list[Document]:
        return await self._repository.list(skip=skip, limit=limit)

    async def update_document(self, document_id: str, payload: DocumentUpdate) -> Document:
        document = await self.get_document(document_id)
        document.name = payload.name
        updated = await self._repository.update(document)
        if updated is None:
            raise DocumentNotFoundError(document_id)
        return updated

    async def delete_document(self, document_id: str) -> None:
        deleted = await self._repository.delete(document_id)
        if not deleted:
            raise DocumentNotFoundError(document_id)
