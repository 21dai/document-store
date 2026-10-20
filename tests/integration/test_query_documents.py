"""GET /api/v1/documents y GET /api/v1/documents/{id} contra MongoDB real."""

import pytest
from fastapi.testclient import TestClient

URL = "/api/v1/documents"


def create(client: TestClient, index: int) -> dict[str, object]:
    response = client.post(
        URL,
        json={
            "name": f"doc{index}",
            "original_filename": f"doc{index}.pdf",
            "checksum": f"{index:064x}",
            "file_size": 100 + index,
            "page_count": index,
            "extracted_text": f"texto {index}",
            "is_processed": True,
        },
    )
    assert response.status_code == 201
    return response.json()


def test_obtener_por_id_devuelve_el_documento(api_client: TestClient) -> None:
    created = create(api_client, 1)

    response = api_client.get(f"{URL}/{created['id']}")

    assert response.status_code == 200
    assert response.json() == created


def test_obtener_un_id_inexistente_responde_404_problem_details(
    api_client: TestClient,
) -> None:
    response = api_client.get(f"{URL}/999")

    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"
    body = response.json()
    assert body["status"] == 404
    assert body["title"] == "Not Found"
    assert "999" in body["detail"]
    assert body["instance"].endswith(f"{URL}/999")


@pytest.mark.parametrize("document_id", ["abc", "0", "-5", "1.5"])
def test_un_id_que_no_es_entero_positivo_responde_400(
    api_client: TestClient, document_id: str
) -> None:
    response = api_client.get(f"{URL}/{document_id}")

    assert response.status_code == 400
    assert response.headers["content-type"] == "application/problem+json"


def test_listar_sin_documentos_devuelve_200_con_lista_vacia(
    api_client: TestClient,
) -> None:
    response = api_client.get(URL)

    assert response.status_code == 200
    assert response.json() == []


def test_listar_devuelve_los_documentos_en_orden_de_id(api_client: TestClient) -> None:
    created = [create(api_client, index) for index in range(1, 4)]

    response = api_client.get(URL)

    assert response.status_code == 200
    assert response.json() == created


def test_listar_respeta_skip_y_limit(api_client: TestClient) -> None:
    created = [create(api_client, index) for index in range(1, 6)]

    response = api_client.get(URL, params={"skip": 1, "limit": 2})

    assert [d["id"] for d in response.json()] == [d["id"] for d in created[1:3]]


def test_por_defecto_lista_hasta_10_documentos(api_client: TestClient) -> None:
    for index in range(1, 13):
        create(api_client, index)

    response = api_client.get(URL)

    assert [d["id"] for d in response.json()] == list(range(1, 11))


def test_el_limite_maximo_es_100(api_client: TestClient) -> None:
    assert api_client.get(URL, params={"limit": 100}).status_code == 200


@pytest.mark.parametrize(
    "params",
    [{"skip": -1}, {"limit": 0}, {"limit": 101}, {"limit": "abc"}, {"skip": "x"}],
)
def test_parametros_de_paginacion_invalidos_responden_400(
    api_client: TestClient, params: dict[str, object]
) -> None:
    response = api_client.get(URL, params=params)

    assert response.status_code == 400
    assert response.headers["content-type"] == "application/problem+json"
