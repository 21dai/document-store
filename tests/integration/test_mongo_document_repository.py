"""Repositorio MongoDB contra una base real y aislada (ver tests/conftest.py)."""

import asyncio
from dataclasses import replace

import pytest
from pymongo.asynchronous.database import AsyncDatabase

from app.exceptions import DocumentAlreadyExistsError
from app.models.document import Document
from app.repositories.mongo_document_repository import (
    MongoDocumentRepository,
    ensure_indexes,
    to_mongo,
)


def make_document(checksum: str = "a" * 64, name: str = "informe") -> Document:
    return Document(
        name=name,
        original_filename=f"{name}.pdf",
        checksum=checksum,
        file_size=1024,
        page_count=3,
        extracted_text="texto",
        is_processed=True,
    )


@pytest.fixture
async def repository(mongo_database: AsyncDatabase) -> MongoDocumentRepository:
    await ensure_indexes(mongo_database)
    return MongoDocumentRepository(mongo_database)


async def test_ensure_indexes_crea_indices_unicos_para_id_y_checksum(
    mongo_database: AsyncDatabase,
) -> None:
    await ensure_indexes(mongo_database)

    indexes = await mongo_database["documents"].index_information()
    unique_keys = {
        tuple(key for key, _ in spec["key"])
        for spec in indexes.values()
        if spec.get("unique")
    }
    assert ("id",) in unique_keys
    assert ("checksum",) in unique_keys


async def test_ensure_indexes_es_idempotente(mongo_database: AsyncDatabase) -> None:
    await ensure_indexes(mongo_database)
    await ensure_indexes(mongo_database)


async def test_create_asigna_ids_secuenciales_desde_uno(
    repository: MongoDocumentRepository,
) -> None:
    first = await repository.create(make_document("a" * 64))
    second = await repository.create(make_document("b" * 64))

    assert (first.id, second.id) == (1, 2)


async def test_los_ids_son_unicos_con_altas_concurrentes(
    repository: MongoDocumentRepository,
) -> None:
    documents = [make_document(f"{i:064x}", name=f"doc{i}") for i in range(25)]

    created = await asyncio.gather(*(repository.create(d) for d in documents))

    assert sorted(d.id for d in created) == list(range(1, 26))


async def test_un_checksum_repetido_lanza_documento_duplicado(
    repository: MongoDocumentRepository,
) -> None:
    await repository.create(make_document("c" * 64))

    with pytest.raises(DocumentAlreadyExistsError):
        await repository.create(make_document("c" * 64, name="otro nombre"))


async def test_el_unico_garantizado_por_la_base_aunque_lleguen_a_la_vez(
    repository: MongoDocumentRepository,
) -> None:
    results = await asyncio.gather(
        *(repository.create(make_document("d" * 64)) for _ in range(5)),
        return_exceptions=True,
    )

    created = [r for r in results if isinstance(r, Document)]
    rejected = [r for r in results if isinstance(r, DocumentAlreadyExistsError)]
    assert len(created) == 1
    assert len(rejected) == 4


async def test_un_documento_guardado_se_reconstruye_igual(
    repository: MongoDocumentRepository,
) -> None:
    created = await repository.create(make_document("e" * 64))

    assert await repository.get_by_id(created.id) == created
    assert await repository.get_by_checksum("e" * 64) == created


async def test_buscar_algo_inexistente_devuelve_none(
    repository: MongoDocumentRepository,
) -> None:
    assert await repository.get_by_id(999) is None
    assert await repository.get_by_checksum("f" * 64) is None


async def test_list_devuelve_los_documentos_ordenados_por_id(
    repository: MongoDocumentRepository, mongo_database: AsyncDatabase
) -> None:
    # Se insertan al revés para que el orden no dependa del de inserción.
    for index in (3, 1, 2):
        document = make_document(f"{index:064x}", name=f"doc{index}")
        await mongo_database["documents"].insert_one(
            to_mongo(replace(document, id=index))
        )

    documents = await repository.list(skip=0, limit=10)

    assert [d.id for d in documents] == [1, 2, 3]


async def test_list_respeta_skip_y_limit(repository: MongoDocumentRepository) -> None:
    for index in range(5):
        await repository.create(make_document(f"{index:064x}", name=f"doc{index}"))

    page = await repository.list(skip=1, limit=2)

    assert [d.id for d in page] == [2, 3]


async def test_list_sin_documentos_devuelve_lista_vacia(
    repository: MongoDocumentRepository,
) -> None:
    assert await repository.list(skip=0, limit=10) == []
