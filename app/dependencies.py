from typing import Annotated

from fastapi import Depends, Request
from pymongo.asynchronous.database import AsyncDatabase

from app.cache.document_cache import DocumentCache
from app.config import Settings, get_settings
from app.repositories.cached_document_repository import CachedDocumentRepository
from app.repositories.document_repository import DocumentRepository
from app.repositories.mongo_document_repository import MongoDocumentRepository
from app.services.document_service import DocumentService

SettingsDep = Annotated[Settings, Depends(get_settings)]


def get_database(request: Request) -> AsyncDatabase:
    """Devuelve la base de datos configurada en el lifespan de la app."""
    return request.app.state.mongo_db


DatabaseDep = Annotated[AsyncDatabase, Depends(get_database)]


def get_document_cache(request: Request) -> DocumentCache:
    """Devuelve el cache creado en el lifespan (desactivado sin `REDIS_URL`)."""
    return request.app.state.document_cache


DocumentCacheDep = Annotated[DocumentCache, Depends(get_document_cache)]


def get_document_repository(
    database: DatabaseDep, cache: DocumentCacheDep
) -> DocumentRepository:
    """Inyecta el repositorio de MongoDB envuelto en el cache (DIP + decorador)."""
    return CachedDocumentRepository(MongoDocumentRepository(database), cache)


DocumentRepositoryDep = Annotated[DocumentRepository, Depends(get_document_repository)]


def get_document_service(repository: DocumentRepositoryDep) -> DocumentService:
    return DocumentService(repository)


DocumentServiceDep = Annotated[DocumentService, Depends(get_document_service)]
