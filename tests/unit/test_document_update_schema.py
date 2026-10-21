import pytest
from pydantic import ValidationError

from app.schemas.document import DocumentUpdate


def test_acepta_un_nombre_valido() -> None:
    update = DocumentUpdate.model_validate({"name": "Informe final"})

    assert update.name == "Informe final"


def test_quita_los_espacios_de_los_extremos() -> None:
    update = DocumentUpdate.model_validate({"name": "  Informe final  "})

    assert update.name == "Informe final"


def test_acepta_un_nombre_normalizado_de_255_caracteres() -> None:
    update = DocumentUpdate.model_validate({"name": f"  {'x' * 255}  "})

    assert update.name == "x" * 255


def test_rechaza_un_nombre_normalizado_de_256_caracteres() -> None:
    with pytest.raises(ValidationError):
        DocumentUpdate.model_validate({"name": f"  {'x' * 256}  "})


def test_rechaza_un_nombre_ausente() -> None:
    with pytest.raises(ValidationError):
        DocumentUpdate.model_validate({})


def test_rechaza_un_nombre_vacio() -> None:
    with pytest.raises(ValidationError):
        DocumentUpdate.model_validate({"name": ""})


def test_rechaza_un_nombre_compuesto_solo_por_espacios() -> None:
    with pytest.raises(ValidationError):
        DocumentUpdate.model_validate({"name": "   "})


def test_rechaza_un_nombre_null() -> None:
    with pytest.raises(ValidationError):
        DocumentUpdate.model_validate({"name": None})


@pytest.mark.parametrize("name", [123, 1.5, True, False, [], {}])
def test_rechaza_tipos_incorrectos_para_el_nombre(name: object) -> None:
    with pytest.raises(ValidationError):
        DocumentUpdate.model_validate({"name": name})


def test_rechaza_un_campo_adicional() -> None:
    with pytest.raises(ValidationError):
        DocumentUpdate.model_validate(
            {"name": "Informe final", "description": "Campo no admitido"}
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("id", 7),
        ("checksum", "a" * 64),
        ("original_filename", "informe.pdf"),
        ("file_size", 734000),
        ("page_count", 42),
        ("extracted_text", "Texto extraido"),
        ("is_processed", True),
        ("created_at", "2026-10-21T12:00:00Z"),
        ("updated_at", "2026-10-21T12:00:00Z"),
    ],
)
def test_rechaza_un_campo_protegido_aunque_el_nombre_sea_valido(
    field: str, value: object
) -> None:
    with pytest.raises(ValidationError):
        DocumentUpdate.model_validate({"name": "Informe final", field: value})
