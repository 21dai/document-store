"""PUT /api/v1/documents/{id} contra MongoDB real y aislado."""

from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.repositories import mongo_document_repository

URL = "/api/v1/documents"
PAYLOAD = {
    "name": "Informe original",
    "original_filename": "informe.pdf",
    "checksum": "9" * 64,
    "file_size": 734_000,
    "page_count": 42,
    "extracted_text": "Texto extraido del PDF.",
    "is_processed": True,
}
UPDATED_AT = datetime(2040, 2, 3, 4, 5, 6, 789000, tzinfo=UTC)


def create_document(client: TestClient) -> dict[str, Any]:
    response = client.post(URL, json=PAYLOAD)
    assert response.status_code == 201
    return response.json()


def assert_problem_details(
    response: Any, *, status_code: int, title: str, instance_suffix: str
) -> None:
    assert response.status_code == status_code
    assert response.headers["content-type"] == "application/problem+json"
    body = response.json()
    assert body["status"] == status_code
    assert body["title"] == title
    assert body["detail"]
    assert body["instance"].endswith(instance_suffix)


def test_actualizar_devuelve_el_documento_completo_y_persiste_el_cambio(
    api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created = create_document(api_client)
    monkeypatch.setattr(mongo_document_repository, "utc_now", lambda: UPDATED_AT)

    response = api_client.put(
        f"{URL}/{created['id']}", json={"name": "  Informe actualizado  "}
    )

    assert response.status_code == 200
    updated = response.json()
    assert updated == {
        **created,
        "name": "Informe actualizado",
        "updated_at": UPDATED_AT.isoformat().replace("+00:00", "Z"),
    }
    assert updated["created_at"] == created["created_at"]
    assert updated["updated_at"] != created["updated_at"]
    assert datetime.fromisoformat(updated["updated_at"]).utcoffset() is not None

    persisted = api_client.get(f"{URL}/{created['id']}")
    assert persisted.status_code == 200
    assert persisted.json() == updated


def test_actualizar_un_documento_inexistente_responde_404_problem_details(
    api_client: TestClient,
) -> None:
    response = api_client.put(f"{URL}/999", json={"name": "Nuevo nombre"})

    assert_problem_details(
        response,
        status_code=404,
        title="Not Found",
        instance_suffix=f"{URL}/999",
    )
    assert "999" in response.json()["detail"]


def test_openapi_documenta_el_contrato_del_put(api_client: TestClient) -> None:
    specification = api_client.get("/openapi.json").json()
    operation = specification["paths"][f"{URL}/{{document_id}}"]["put"]

    assert {"200", "400", "404"} <= operation["responses"].keys()
    assert operation["requestBody"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/DocumentUpdate"
    }
    assert specification["components"]["schemas"]["DocumentUpdate"][
        "additionalProperties"
    ] is False


@pytest.mark.parametrize("document_id", ["abc", "0", "-5", "1.5"])
def test_actualizar_con_id_invalido_responde_400_problem_details(
    api_client: TestClient,
    document_id: str,
) -> None:
    response = api_client.put(
        f"{URL}/{document_id}", json={"name": "Nuevo nombre"}
    )

    assert_problem_details(
        response,
        status_code=400,
        title="Bad Request",
        instance_suffix=f"{URL}/{document_id}",
    )


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"name": ""},
        {"name": "   "},
        {"name": None},
        {"name": 123},
        {"name": True},
        {"name": ["informe"]},
        {"name": {"value": "informe"}},
        {"name": "x" * 256},
    ],
)
def test_actualizar_con_payload_invalido_responde_400_problem_details(
    api_client: TestClient,
    payload: dict[str, Any],
) -> None:
    response = api_client.put(f"{URL}/1", json=payload)

    assert_problem_details(
        response,
        status_code=400,
        title="Bad Request",
        instance_suffix=f"{URL}/1",
    )


def test_actualizar_sin_body_responde_400_problem_details(
    api_client: TestClient,
) -> None:
    response = api_client.put(f"{URL}/1")

    assert_problem_details(
        response,
        status_code=400,
        title="Bad Request",
        instance_suffix=f"{URL}/1",
    )


def test_actualizar_con_json_malformado_responde_400_problem_details(
    api_client: TestClient,
) -> None:
    response = api_client.put(
        f"{URL}/1",
        content=b'{"name":',
        headers={"content-type": "application/json"},
    )

    assert_problem_details(
        response,
        status_code=400,
        title="Bad Request",
        instance_suffix=f"{URL}/1",
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("id", 999),
        ("checksum", "a" * 64),
        ("original_filename", "otro.pdf"),
        ("file_size", 1),
        ("page_count", 1),
        ("extracted_text", "contenido reemplazado"),
        ("is_processed", False),
        ("created_at", "2030-01-01T00:00:00Z"),
        ("updated_at", "2030-01-01T00:00:00Z"),
        ("campo_desconocido", "valor"),
    ],
)
def test_actualizar_rechaza_campos_no_editables_sin_modificar_el_documento(
    api_client: TestClient,
    field: str,
    value: Any,
) -> None:
    created = create_document(api_client)

    response = api_client.put(
        f"{URL}/{created['id']}",
        json={"name": "Nombre que no debe persistirse", field: value},
    )

    assert_problem_details(
        response,
        status_code=400,
        title="Bad Request",
        instance_suffix=f"{URL}/{created['id']}",
    )
    persisted = api_client.get(f"{URL}/{created['id']}")
    assert persisted.status_code == 200
    assert persisted.json() == created
