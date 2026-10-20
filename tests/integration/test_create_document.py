"""POST /api/v1/documents contra MongoDB real (ver tests/conftest.py)."""

from datetime import datetime

from fastapi.testclient import TestClient
from pymongo import MongoClient

from tests.conftest import TEST_DATABASE_URL

URL = "/api/v1/documents"
PAYLOAD = {
    "name": "Filosofia Lean",
    "original_filename": "Filosofia Lean.pdf",
    "checksum": "a" * 64,
    "file_size": 734000,
    "page_count": 42,
    "extracted_text": "Texto extraído del PDF...",
    "is_processed": True,
}


def test_crea_el_documento_y_responde_201_con_el_contrato(
    api_client: TestClient,
) -> None:
    response = api_client.post(URL, json=PAYLOAD)

    assert response.status_code == 201
    body = response.json()
    assert body["id"] == 1
    assert {k: body[k] for k in PAYLOAD} == PAYLOAD
    created_at = datetime.fromisoformat(body["created_at"])
    assert created_at.utcoffset() is not None
    assert body["updated_at"] == body["created_at"]


def test_el_documento_queda_guardado_en_mongodb(
    api_client: TestClient, database_name: str
) -> None:
    api_client.post(URL, json=PAYLOAD)

    with MongoClient(TEST_DATABASE_URL) as client:
        stored = client[database_name]["documents"].find_one({"checksum": "a" * 64})
    assert stored is not None
    assert stored["id"] == 1
    assert stored["name"] == "Filosofia Lean"


def test_los_ids_son_secuenciales(api_client: TestClient) -> None:
    first = api_client.post(URL, json=PAYLOAD).json()
    second = api_client.post(URL, json={**PAYLOAD, "checksum": "b" * 64}).json()

    assert (first["id"], second["id"]) == (1, 2)


def test_un_checksum_repetido_responde_409_problem_details(
    api_client: TestClient,
) -> None:
    api_client.post(URL, json=PAYLOAD)

    response = api_client.post(URL, json={**PAYLOAD, "name": "Otro nombre"})

    assert response.status_code == 409
    assert response.headers["content-type"] == "application/problem+json"
    body = response.json()
    assert body["status"] == 409
    assert body["title"] == "Conflict"
    assert "a" * 64 in body["detail"]
    assert body["instance"].endswith(URL)


def test_datos_invalidos_responden_400_problem_details(
    api_client: TestClient,
) -> None:
    response = api_client.post(URL, json={**PAYLOAD, "checksum": "no-es-sha256"})

    assert response.status_code == 400
    assert response.headers["content-type"] == "application/problem+json"
    body = response.json()
    assert body["status"] == 400
    assert body["title"] == "Bad Request"
    assert "checksum" in body["detail"]


def test_un_body_que_no_es_json_responde_400(api_client: TestClient) -> None:
    response = api_client.post(
        URL, content=b"esto no es json", headers={"content-type": "application/json"}
    )

    assert response.status_code == 400


def test_un_campo_faltante_responde_400(api_client: TestClient) -> None:
    data = {k: v for k, v in PAYLOAD.items() if k != "name"}

    response = api_client.post(URL, json=data)

    assert response.status_code == 400
    assert "name" in response.json()["detail"]
