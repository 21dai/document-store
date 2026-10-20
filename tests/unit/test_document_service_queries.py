import pytest

from app.exceptions import DocumentNotFoundError
from app.models.document import Document
from app.services.document_service import DocumentService
from tests.fakes import InMemoryDocumentRepository


def make_document(index: int) -> Document:
    return Document(
        name=f"doc{index}",
        original_filename=f"doc{index}.pdf",
        checksum=f"{index:064x}",
        file_size=100,
        page_count=1,
        extracted_text="texto",
        is_processed=True,
    )


@pytest.fixture
async def service() -> DocumentService:
    repository = InMemoryDocumentRepository()
    for index in range(1, 4):
        await repository.create(make_document(index))
    return DocumentService(repository)


async def test_get_document_devuelve_el_documento_existente(
    service: DocumentService,
) -> None:
    document = await service.get_document(2)

    assert document.id == 2
    assert document.name == "doc2"


async def test_get_document_inexistente_lanza_no_encontrado(
    service: DocumentService,
) -> None:
    with pytest.raises(DocumentNotFoundError) as caught:
        await service.get_document(99)

    assert caught.value.document_id == 99


async def test_list_documents_pagina_en_orden_de_id(service: DocumentService) -> None:
    page = await service.list_documents(skip=1, limit=1)

    assert [d.id for d in page] == [2]


async def test_list_documents_sin_resultados_devuelve_lista_vacia(
    service: DocumentService,
) -> None:
    assert await service.list_documents(skip=10, limit=5) == []
