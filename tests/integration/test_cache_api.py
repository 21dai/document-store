"""Cache de documentos con la app completa: MongoDB real y Redis simulado."""

from collections.abc import Iterator

import fakeredis
import pytest
from fastapi.testclient import TestClient
from pymongo import MongoClient

from app.cache import document_cache
from app.config import Settings
from app.main import create_app
from tests.conftest import TEST_DATABASE_URL

URL = "/api/v1/documents"
NEW_DOCUMENT = {
    "name": "informe",
    "original_filename": "informe.pdf",
    "checksum": "c" * 64,
    "file_size": 1024,
    "page_count": 3,
    "extracted_text": "texto",
    "is_processed": True,
}


@pytest.fixture
def fake_redis(monkeypatch: pytest.MonkeyPatch) -> fakeredis.FakeAsyncRedis:
    server = fakeredis.FakeAsyncRedis()
    monkeypatch.setattr(
        document_cache.Redis, "from_url", lambda *args, **kwargs: server
    )
    return server


def make_client(database_name: str, redis_url: str) -> TestClient:
    settings = Settings(
        _env_file=None,
        database_url=TEST_DATABASE_URL,
        database_name=database_name,
        redis_url=redis_url,
    )
    return TestClient(create_app(settings))


@pytest.fixture
def cached_client(
    database_name: str, fake_redis: fakeredis.FakeAsyncRedis
) -> Iterator[TestClient]:
    with make_client(database_name, "redis://redis:6379/0") as client:
        yield client


def rename_in_mongodb(database_name: str, document_id: int, name: str) -> None:
    """Cambia el documento directo en MongoDB, sin pasar por la API ni el cache."""
    with MongoClient(TEST_DATABASE_URL) as client:
        client[database_name]["documents"].update_one(
            {"id": document_id}, {"$set": {"name": name}}
        )


def test_get_por_id_responde_desde_el_cache(
    cached_client: TestClient, database_name: str, fake_redis: fakeredis.FakeAsyncRedis
) -> None:
    created = cached_client.post(URL, json=NEW_DOCUMENT).json()
    rename_in_mongodb(database_name, created["id"], "cambiado por fuera")

    response = cached_client.get(f"{URL}/{created['id']}")

    # Respondió el cache (escrito en el alta), no MongoDB.
    assert response.status_code == 200
    assert response.json()["name"] == "informe"


def test_renombrar_por_la_api_actualiza_el_cache(cached_client: TestClient) -> None:
    created = cached_client.post(URL, json=NEW_DOCUMENT).json()

    cached_client.put(f"{URL}/{created['id']}", json={"name": "nuevo"})

    assert cached_client.get(f"{URL}/{created['id']}").json()["name"] == "nuevo"


def test_borrar_por_la_api_invalida_el_cache(cached_client: TestClient) -> None:
    created = cached_client.post(URL, json=NEW_DOCUMENT).json()

    cached_client.delete(f"{URL}/{created['id']}")

    assert cached_client.get(f"{URL}/{created['id']}").status_code == 404


def test_con_redis_caido_el_servicio_sigue_respondiendo_desde_mongodb(
    database_name: str,
) -> None:
    # Puerto sin Redis: cada operación del cache falla y se ignora.
    with make_client(database_name, "redis://127.0.0.1:1/0") as client:
        created = client.post(URL, json=NEW_DOCUMENT)
        response = client.get(f"{URL}/{created.json()['id']}")

    assert created.status_code == 201
    assert response.status_code == 200
    assert response.json()["name"] == "informe"
