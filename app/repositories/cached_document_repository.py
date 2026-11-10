from app.cache.document_cache import DocumentCache
from app.models.document import Document
from app.repositories.document_repository import DocumentRepository


class CachedDocumentRepository(DocumentRepository):
    """Decorador del repositorio que agrega cache (patrón Cache-Aside).

    Envuelve al repositorio de MongoDB con la misma interfaz, así que el
    service no sabe que existe el cache (OCP de SOLID):

    - Lectura por id: primero el cache; si no está, MongoDB y se guarda.
    - Alta y renombre: el documento nuevo queda en el cache (write-through).
    - Borrado o renombre fallido: se invalida la entrada, aunque la operación
      falle. Invalidar de más solo cuesta una lectura a MongoDB; de menos,
      devolvería datos viejos.

    Listar y buscar por checksum van directo a MongoDB: una página cambia con
    cada alta o borrado, y el checksum solo se consulta al dar de alta.
    """

    def __init__(self, inner: DocumentRepository, cache: DocumentCache) -> None:
        self._inner = inner
        self._cache = cache

    async def create(self, document: Document) -> Document:
        created = await self._inner.create(document)
        await self._cache.set(created)
        return created

    async def get_by_id(self, document_id: int) -> Document | None:
        cached = await self._cache.get(document_id)
        if cached is not None:
            return cached
        document = await self._inner.get_by_id(document_id)
        if document is not None:
            await self._cache.set(document)
        return document

    async def get_by_checksum(self, checksum: str) -> Document | None:
        return await self._inner.get_by_checksum(checksum)

    async def list(self, skip: int, limit: int) -> list[Document]:
        return await self._inner.list(skip=skip, limit=limit)

    async def update(self, document: Document) -> Document | None:
        updated: Document | None = None
        try:
            updated = await self._inner.update(document)
        finally:
            if document.id is not None:
                if updated is None:
                    await self._cache.delete(document.id)
                else:
                    await self._cache.set(updated)
        return updated

    async def delete(self, document_id: int) -> bool:
        try:
            return await self._inner.delete(document_id)
        finally:
            await self._cache.delete(document_id)
