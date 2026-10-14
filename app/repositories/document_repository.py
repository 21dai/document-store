from abc import ABC, abstractmethod

from app.models.document import Document


class DocumentRepository(ABC):
    """Puerto de persistencia de documentos.

    Define las operaciones que la capa de servicio necesita, sin exponer
    detalles de MongoDB. Permite intercambiar la implementación (por ejemplo,
    un repositorio en memoria para tests unitarios) respetando DIP de SOLID.
    """

    @abstractmethod
    async def create(self, document: Document) -> Document:
        """Persiste un documento nuevo y lo devuelve."""

    @abstractmethod
    async def get_by_id(self, document_id: str) -> Document | None:
        """Devuelve el documento con ese ID, o None si no existe."""

    @abstractmethod
    async def get_by_checksum(self, checksum: str) -> Document | None:
        """Devuelve el documento con ese checksum, o None si no existe."""

    @abstractmethod
    async def list(self, skip: int, limit: int) -> list[Document]:
        """Devuelve una página de documentos según skip/limit."""

    @abstractmethod
    async def update(self, document: Document) -> Document | None:
        """Actualiza los campos editables del documento y lo devuelve."""

    @abstractmethod
    async def delete(self, document_id: str) -> bool:
        """Elimina el documento. Devuelve True si existía."""
