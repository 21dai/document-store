from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


@pytest.fixture
def client() -> Iterator[TestClient]:
    # Sin MongoDB a propósito: /health solo dice que el proceso está vivo, y
    # así el test no crea índices en la base `document_store` de la máquina.
    settings = Settings(
        _env_file=None, database_url="mongodb://127.0.0.1:1", database_timeout_ms=200
    )
    with TestClient(create_app(settings)) as client:
        yield client


def test_health_returns_status_ok(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
