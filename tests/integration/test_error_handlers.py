"""Errores HTTP consistentes: todo error sale como RFC 9457 Problem Details.

No necesitan MongoDB: la app apunta a un puerto donde no hay base, así que
también prueban qué pasa cuando la base no responde.
"""

from collections.abc import Iterator

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import Settings
from app.dependencies import get_document_service
from app.main import create_app

URL = "/api/v1/documents"
PROBLEM_JSON = "application/problem+json"

VALID_DOCUMENT = {
    "name": "informe",
    "original_filename": "informe.pdf",
    "checksum": "a" * 64,
    "file_size": 1024,
    "page_count": 3,
    "extracted_text": "texto",
    "is_processed": True,
}


@pytest.fixture
def app_sin_base() -> FastAPI:
    # Puerto sin MongoDB y timeout corto: cada operación falla en 200 ms.
    settings = Settings(
        _env_file=None,
        database_url="mongodb://127.0.0.1:1",
        database_timeout_ms=200,
    )
    return create_app(settings)


@pytest.fixture
def client(app_sin_base: FastAPI) -> Iterator[TestClient]:
    with TestClient(app_sin_base, raise_server_exceptions=False) as client:
        yield client


def assert_problem(
    response: httpx.Response, status: int, title: str
) -> dict[str, object]:
    assert response.status_code == status
    assert response.headers["content-type"] == PROBLEM_JSON
    body = response.json()
    assert body["type"] == "about:blank"
    assert body["status"] == status
    assert body["title"] == title
    assert isinstance(body["detail"], str) and body["detail"]
    assert body["instance"].endswith(response.request.url.path)
    return body


def test_una_ruta_inexistente_responde_404_problem_details(client: TestClient) -> None:
    response = client.get("/api/v1/no-existe")

    assert_problem(response, 404, "Not Found")


def test_un_metodo_no_permitido_responde_405_problem_details_con_allow(
    client: TestClient,
) -> None:
    response = client.patch(f"{URL}/1", json={"name": "x"})

    assert_problem(response, 405, "Method Not Allowed")
    assert "allow" in response.headers


class ServiceQueFalla:
    async def get_document(self, document_id: int) -> None:
        raise RuntimeError("detalle interno que no debe salir")


def test_un_error_no_previsto_responde_500_sin_detalles_internos(
    app_sin_base: FastAPI,
) -> None:
    app_sin_base.dependency_overrides[get_document_service] = ServiceQueFalla
    with TestClient(app_sin_base, raise_server_exceptions=False) as client:
        response = client.get(f"{URL}/1")

    body = assert_problem(response, 500, "Internal Server Error")
    assert "detalle interno" not in response.text
    assert "Traceback" not in str(body["detail"])


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("post", URL, VALID_DOCUMENT),
        ("get", URL, None),
        ("get", f"{URL}/1", None),
        ("put", f"{URL}/1", {"name": "nuevo"}),
        ("delete", f"{URL}/1", None),
    ],
)
def test_sin_base_de_datos_responde_503_problem_details(
    client: TestClient, method: str, path: str, body: dict[str, object] | None
) -> None:
    response = client.request(method, path, json=body)

    problem = assert_problem(response, 503, "Service Unavailable")
    assert "base de datos" in str(problem["detail"])
    # Sin Retry-After: es una caída, no una carga pasajera (el circuit breaker
    # del orquestador la tiene que contar como fallo).
    assert "retry-after" not in response.headers


def test_openapi_no_documenta_422_porque_la_validacion_responde_400(
    app_sin_base: FastAPI,
) -> None:
    spec = app_sin_base.openapi()

    for path, operations in spec["paths"].items():
        for method, operation in operations.items():
            assert "422" not in operation["responses"], f"{method.upper()} {path}"
    schemas = spec.get("components", {}).get("schemas", {})
    assert "HTTPValidationError" not in schemas


def test_openapi_documenta_503_en_los_endpoints_de_documentos(
    app_sin_base: FastAPI,
) -> None:
    spec = app_sin_base.openapi()

    for path, operations in spec["paths"].items():
        if not path.startswith(URL):
            continue
        for method, operation in operations.items():
            assert "503" in operation["responses"], f"{method.upper()} {path}"
