"""DELETE /api/v1/documents/{id} contra MongoDB real."""

import pytest
from fastapi.testclient import TestClient

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


def create_document(client: TestClient) -> dict[str, object]:
    response = client.post(URL, json=PAYLOAD)
    assert response.status_code == 201
    return response.json()


def test_eliminar_documento_existente_responde_204_y_lo_borra(
    api_client: TestClient,
) -> None:
    created = create_document(api_client)

    response = api_client.delete(f"{URL}/{created['id']}")

    assert response.status_code == 204
    assert response.content == b""
    assert api_client.get(f"{URL}/{created['id']}").status_code == 404


def test_eliminar_documento_inexistente_responde_404_problem_details(
    api_client: TestClient,
) -> None:
    response = api_client.delete(f"{URL}/999")

    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"
    body = response.json()
    assert body["status"] == 404
    assert body["title"] == "Not Found"
    assert "999" in body["detail"]
    assert body["instance"].endswith(f"{URL}/999")


@pytest.mark.parametrize("document_id", ["abc", "0", "-5", "1.5"])
def test_eliminar_con_id_invalido_responde_400_problem_details(
    api_client: TestClient, document_id: str
) -> None:
    response = api_client.delete(f"{URL}/{document_id}")

    assert response.status_code == 400
    assert response.headers["content-type"] == "application/problem+json"


def test_openapi_documenta_el_contrato_del_delete(api_client: TestClient) -> None:
    specification = api_client.get("/openapi.json").json()
    operation = specification["paths"][f"{URL}/{{document_id}}"]["delete"]

    assert {"204", "400", "404"} <= operation["responses"].keys()
    assert "content" not in operation["responses"]["204"]
