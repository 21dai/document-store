from datetime import UTC, datetime

import pytest

from app.exceptions import DocumentNotFoundError
from app.models.document import Document
from app.schemas.document import DocumentUpdate
from app.services.document_service import DocumentService
from tests.fakes import InMemoryDocumentRepository


def make_document() -> Document:
    created_at = datetime(2026, 1, 15, 12, 30, tzinfo=UTC)
    return Document(
        name="Nombre original",
        original_filename="archivo-original.pdf",
        checksum="a" * 64,
        file_size=734000,
        page_count=42,
        extracted_text="Texto extraido del PDF",
        is_processed=True,
        created_at=created_at,
        updated_at=created_at,
    )


@pytest.fixture
def repository() -> InMemoryDocumentRepository:
    return InMemoryDocumentRepository()


@pytest.fixture
def service(repository: InMemoryDocumentRepository) -> DocumentService:
    return DocumentService(repository)


async def test_actualiza_el_nombre_del_documento(
    service: DocumentService, repository: InMemoryDocumentRepository
) -> None:
    original = await repository.create(make_document())

    updated = await service.update_document(
        original.id or 0, DocumentUpdate(name="Nombre actualizado")
    )

    assert updated.id == original.id
    assert updated.name == "Nombre actualizado"
    assert repository.documents[updated.id or 0] == updated


async def test_documento_inexistente_lanza_no_encontrado(
    service: DocumentService,
) -> None:
    with pytest.raises(DocumentNotFoundError) as caught:
        await service.update_document(99, DocumentUpdate(name="Nombre actualizado"))

    assert caught.value.document_id == 99


async def test_conserva_todos_los_campos_protegidos(
    service: DocumentService, repository: InMemoryDocumentRepository
) -> None:
    original = await repository.create(make_document())
    protected_fields = (
        "id",
        "checksum",
        "original_filename",
        "file_size",
        "page_count",
        "extracted_text",
        "is_processed",
        "created_at",
    )
    expected = {field: getattr(original, field) for field in protected_fields}

    updated = await service.update_document(
        original.id or 0, DocumentUpdate(name="Nombre actualizado")
    )

    assert {field: getattr(updated, field) for field in protected_fields} == expected


async def test_documento_que_desaparece_durante_update_lanza_no_encontrado() -> None:
    class DisappearingRepository(InMemoryDocumentRepository):
        async def update(self, document: Document) -> Document | None:
            self.documents.pop(document.id or 0, None)
            return None

    repository = DisappearingRepository()
    original = await repository.create(make_document())
    service = DocumentService(repository)

    with pytest.raises(DocumentNotFoundError) as caught:
        await service.update_document(
            original.id or 0, DocumentUpdate(name="Nombre actualizado")
        )

    assert caught.value.document_id == original.id
    assert await repository.get_by_id(original.id or 0) is None


async def test_update_fallido_no_muta_el_objeto_previamente_leido() -> None:
    class RejectingRepository(InMemoryDocumentRepository):
        async def update(self, document: Document) -> Document | None:
            return None

    repository = RejectingRepository()
    original = await repository.create(make_document())
    service = DocumentService(repository)

    with pytest.raises(DocumentNotFoundError):
        await service.update_document(
            original.id or 0, DocumentUpdate(name="Nombre actualizado")
        )

    assert original.name == "Nombre original"
    assert repository.documents[original.id or 0].name == "Nombre original"
