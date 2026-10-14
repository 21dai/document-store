from typing import Annotated

from fastapi import Depends, Request
from pymongo.asynchronous.database import AsyncDatabase

from app.config import Settings, get_settings
from app.repositories.document_repository import DocumentRepository
from app.repositories.mongo_document_repository import MongoDocumentRepository
from app.services.document_service import DocumentService

SettingsDep = Annotated[Settings, Depends(get_settings)]


def get_database(request: Request) -> AsyncDatabase:
    """Devuelve la base de datos configurada en el lifespan de la app."""
    return request.app.state.mongo_db


DatabaseDep = Annotated[AsyncDatabase, Depends(get_database)]


def get_document_repository(database: DatabaseDep) -> DocumentRepository:
    """Inyecta la implementación Mongo del puerto DocumentRepository (DIP)."""
    return MongoDocumentRepository(database)


DocumentRepositoryDep = Annotated[DocumentRepository, Depends(get_document_repository)]


def get_document_service(repository: DocumentRepositoryDep) -> DocumentService:
    return DocumentService(repository)


DocumentServiceDep = Annotated[DocumentService, Depends(get_document_service)]
