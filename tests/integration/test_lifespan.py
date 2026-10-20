from fastapi.testclient import TestClient
from pymongo import MongoClient

from app.config import Settings
from app.main import create_app
from tests.conftest import TEST_DATABASE_URL


def unique_index_keys(database_name: str) -> set[tuple[str, ...]]:
    with MongoClient(TEST_DATABASE_URL) as client:
        indexes = client[database_name]["documents"].index_information()
    return {
        tuple(key for key, _ in spec["key"])
        for spec in indexes.values()
        if spec.get("unique")
    }


def test_al_arrancar_la_app_crea_los_indices_de_la_base(database_name: str) -> None:
    settings = Settings(
        _env_file=None, database_url=TEST_DATABASE_URL, database_name=database_name
    )

    with TestClient(create_app(settings)):
        assert {("id",), ("checksum",)} <= unique_index_keys(database_name)


def test_la_app_arranca_y_responde_health_aunque_mongodb_no_este() -> None:
    # Puerto sin MongoDB: el healthcheck no debe depender de la base.
    settings = Settings(
        _env_file=None,
        database_url="mongodb://127.0.0.1:1",
        database_timeout_ms=200,
    )

    with TestClient(create_app(settings)) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
