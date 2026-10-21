import pytest

from app.exceptions import DocumentNotFoundError
from app.models.document import Document
from app.services.document_service import DocumentService
from tests.fakes import InMemoryDocumentRepository


def make_document() -> Document:
    return Document(
        name="informe",
        original_filename="informe.pdf",
        checksum="a" * 64,
        file_size=100,
        page_count=1,
        extracted_text="texto",
        is_processed=True,
    )


async def test_delete_document_elimina_el_documento() -> None:
    repository = InMemoryDocumentRepository()
    document = await repository.create(make_document())
    service = DocumentService(repository)

    result = await service.delete_document(document.id or 0)

    assert result is None
    assert await repository.get_by_id(document.id or 0) is None


async def test_delete_document_inexistente_lanza_no_encontrado() -> None:
    service = DocumentService(InMemoryDocumentRepository())

    with pytest.raises(DocumentNotFoundError) as caught:
        await service.delete_document(99)

    assert caught.value.document_id == 99
