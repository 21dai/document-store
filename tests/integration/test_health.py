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


def test_ready_responde_503_con_problem_details_si_mongodb_no_responde(
    client: TestClient,
) -> None:
    # Readiness: sin base no puede atender, aunque el proceso esté vivo.
    response = client.get("/ready")

    assert response.status_code == 503
    assert response.headers["content-type"] == "application/problem+json"
    body = response.json()
    assert body["status"] == 503
    assert (
        body["detail"] == "La base de datos no está disponible; reintentar más tarde."
    )
    assert body["instance"].endswith("/ready")


def test_ready_responde_200_con_mongodb_disponible(api_client: TestClient) -> None:
    response = api_client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_ready_documenta_el_503_en_openapi(client: TestClient) -> None:
    responses = client.get("/openapi.json").json()["paths"]["/ready"]["get"][
        "responses"
    ]

    assert {"200", "503"} <= set(responses)
    # Mismo esquema que el 503 de los endpoints de documentos.
    schema = next(iter(responses["503"]["content"].values()))["schema"]
    assert schema["$ref"].endswith("/ProblemDetail")
