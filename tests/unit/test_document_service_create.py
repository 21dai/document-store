import pytest

from app.exceptions import DocumentAlreadyExistsError
from app.models.document import Document
from app.schemas.document import DocumentCreate
from app.services.document_service import DocumentService
from tests.fakes import InMemoryDocumentRepository

CHECKSUM = "a" * 64


def make_payload(**overrides: object) -> DocumentCreate:
    data: dict[str, object] = {
        "name": "Filosofia Lean",
        "original_filename": "Filosofia Lean.pdf",
        "checksum": CHECKSUM,
        "file_size": 734000,
        "page_count": 42,
        "extracted_text": "Texto extraído del PDF...",
        "is_processed": True,
    }
    data.update(overrides)
    return DocumentCreate.model_validate(data)


@pytest.fixture
def repository() -> InMemoryDocumentRepository:
    return InMemoryDocumentRepository()


@pytest.fixture
def service(repository: InMemoryDocumentRepository) -> DocumentService:
    return DocumentService(repository)


async def test_crea_el_documento_con_id_y_los_datos_recibidos(
    service: DocumentService, repository: InMemoryDocumentRepository
) -> None:
    created = await service.create_document(make_payload())

    assert created.id == 1
    assert created.name == "Filosofia Lean"
    assert created.checksum == CHECKSUM
    assert created.page_count == 42
    assert created.is_processed is True
    assert repository.documents[1] == created


async def test_rechaza_un_checksum_que_ya_existe(service: DocumentService) -> None:
    await service.create_document(make_payload())

    with pytest.raises(DocumentAlreadyExistsError):
        await service.create_document(make_payload(name="Otro nombre"))


async def test_no_guarda_nada_si_el_checksum_ya_existe(
    service: DocumentService, repository: InMemoryDocumentRepository
) -> None:
    await service.create_document(make_payload())

    with pytest.raises(DocumentAlreadyExistsError):
        await service.create_document(make_payload())

    assert len(repository.documents) == 1


async def test_propaga_el_duplicado_que_detecta_la_base(
    repository: InMemoryDocumentRepository,
) -> None:
    # Dos altas simultáneas pasan la verificación previa: la detecta el
    # repositorio (índice único) y el service la deja propagar igual.
    class RaceRepository(InMemoryDocumentRepository):
        async def get_by_checksum(self, checksum: str) -> Document | None:
            return None

    race = RaceRepository()
    service = DocumentService(race)
    await service.create_document(make_payload())

    with pytest.raises(DocumentAlreadyExistsError):
        await service.create_document(make_payload())
