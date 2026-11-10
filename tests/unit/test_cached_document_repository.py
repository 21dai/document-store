"""Repositorio con cache (cache-aside): decorador sobre el repositorio de MongoDB."""

from dataclasses import replace

import pytest

from app.exceptions import DatabaseUnavailableError
from app.models.document import Document
from app.repositories.cached_document_repository import CachedDocumentRepository
from tests.fakes import InMemoryDocumentRepository


class MemoryCache:
    """Cache en memoria con la misma interfaz que el de Redis."""

    def __init__(self) -> None:
        self.entries: dict[int, Document] = {}

    async def get(self, document_id: int) -> Document | None:
        return self.entries.get(document_id)

    async def set(self, document: Document) -> None:
        assert document.id is not None
        self.entries[document.id] = document

    async def delete(self, document_id: int) -> None:
        self.entries.pop(document_id, None)

    async def aclose(self) -> None:
        pass


class CountingRepository(InMemoryDocumentRepository):
    """Repositorio en memoria que cuenta las lecturas por id (las ahorra el cache)."""

    def __init__(self) -> None:
        super().__init__()
        self.reads_by_id = 0
        self.fail_with: Exception | None = None

    async def get_by_id(self, document_id: int) -> Document | None:
        self.reads_by_id += 1
        return await super().get_by_id(document_id)

    async def delete(self, document_id: int) -> bool:
        if self.fail_with is not None:
            raise self.fail_with
        return await super().delete(document_id)


def make_document(checksum: str = "a" * 64) -> Document:
    return Document(
        name="informe",
        original_filename="informe.pdf",
        checksum=checksum,
        file_size=1024,
        page_count=3,
        extracted_text="texto",
        is_processed=True,
    )


@pytest.fixture
def inner() -> CountingRepository:
    return CountingRepository()


@pytest.fixture
def cache() -> MemoryCache:
    return MemoryCache()


@pytest.fixture
def repository(
    inner: CountingRepository, cache: MemoryCache
) -> CachedDocumentRepository:
    return CachedDocumentRepository(inner, cache)


async def test_el_alta_deja_el_documento_en_cache(
    repository: CachedDocumentRepository, cache: MemoryCache
) -> None:
    created = await repository.create(make_document())

    assert cache.entries == {created.id: created}


async def test_get_by_id_sale_del_cache_sin_leer_mongodb(
    repository: CachedDocumentRepository, inner: CountingRepository
) -> None:
    created = await repository.create(make_document())

    assert await repository.get_by_id(created.id) == created  # type: ignore[arg-type]
    assert inner.reads_by_id == 0


async def test_si_no_esta_en_cache_lee_mongodb_y_lo_guarda(
    repository: CachedDocumentRepository, inner: CountingRepository, cache: MemoryCache
) -> None:
    created = await inner.create(make_document())  # guardado sin pasar por el cache

    first = await repository.get_by_id(created.id)  # type: ignore[arg-type]
    second = await repository.get_by_id(created.id)  # type: ignore[arg-type]

    assert first == second == created
    assert inner.reads_by_id == 1
    assert cache.entries[created.id] == created  # type: ignore[index]


async def test_un_id_inexistente_no_se_guarda_en_cache(
    repository: CachedDocumentRepository, cache: MemoryCache
) -> None:
    assert await repository.get_by_id(99) is None
    assert cache.entries == {}


async def test_renombrar_actualiza_el_cache(
    repository: CachedDocumentRepository, cache: MemoryCache
) -> None:
    created = await repository.create(make_document())

    updated = await repository.update(replace(created, name="nuevo nombre"))

    assert updated is not None
    assert cache.entries[created.id].name == "nuevo nombre"  # type: ignore[index]


async def test_renombrar_un_id_inexistente_invalida_el_cache(
    repository: CachedDocumentRepository, cache: MemoryCache
) -> None:
    stale = replace(make_document(), id=5)
    cache.entries[5] = stale  # entrada vieja de un documento que ya no existe

    assert await repository.update(replace(stale, name="otro")) is None
    assert 5 not in cache.entries


async def test_borrar_invalida_el_cache(
    repository: CachedDocumentRepository, cache: MemoryCache
) -> None:
    created = await repository.create(make_document())

    assert await repository.delete(created.id) is True  # type: ignore[arg-type]
    assert cache.entries == {}


async def test_si_falla_el_borrado_igual_invalida_el_cache(
    repository: CachedDocumentRepository, inner: CountingRepository, cache: MemoryCache
) -> None:
    created = await repository.create(make_document())
    inner.fail_with = DatabaseUnavailableError()

    with pytest.raises(DatabaseUnavailableError):
        await repository.delete(created.id)  # type: ignore[arg-type]

    # Invalidar de más solo cuesta una lectura a MongoDB; de menos, datos viejos.
    assert cache.entries == {}


async def test_listar_y_buscar_por_checksum_no_usan_el_cache(
    repository: CachedDocumentRepository, cache: MemoryCache
) -> None:
    created = await repository.create(make_document())
    cache.entries.clear()

    assert await repository.list(skip=0, limit=10) == [created]
    assert await repository.get_by_checksum("a" * 64) == created
    assert cache.entries == {}
