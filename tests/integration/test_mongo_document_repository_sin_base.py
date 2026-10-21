"""El repositorio traduce la caída de MongoDB a una excepción de dominio.

No necesita MongoDB: apunta a un puerto donde no hay base.
"""

from collections.abc import AsyncIterator, Awaitable, Callable

import pytest
from pymongo import AsyncMongoClient

from app.exceptions import DatabaseUnavailableError
from app.models.document import Document
from app.repositories.mongo_document_repository import MongoDocumentRepository

DOCUMENT = Document(
    name="informe",
    original_filename="informe.pdf",
    checksum="a" * 64,
    file_size=1024,
    page_count=3,
    extracted_text="texto",
    is_processed=True,
    id=1,
)


@pytest.fixture
async def repository() -> AsyncIterator[MongoDocumentRepository]:
    client: AsyncMongoClient = AsyncMongoClient(
        "mongodb://127.0.0.1:1", serverSelectionTimeoutMS=200
    )
    try:
        yield MongoDocumentRepository(client["document_store_sin_base"])
    finally:
        await client.close()


Operation = Callable[[MongoDocumentRepository], Awaitable[object]]

OPERATIONS: dict[str, Operation] = {
    "create": lambda repo: repo.create(DOCUMENT),
    "get_by_id": lambda repo: repo.get_by_id(1),
    "get_by_checksum": lambda repo: repo.get_by_checksum("a" * 64),
    "list": lambda repo: repo.list(skip=0, limit=10),
    "update": lambda repo: repo.update(DOCUMENT),
    "delete": lambda repo: repo.delete(1),
}


@pytest.mark.parametrize("operation", OPERATIONS.values(), ids=OPERATIONS.keys())
async def test_sin_base_lanza_base_de_datos_no_disponible(
    repository: MongoDocumentRepository, operation: Operation
) -> None:
    with pytest.raises(DatabaseUnavailableError):
        await operation(repository)
