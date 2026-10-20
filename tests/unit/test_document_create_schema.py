import pytest
from pydantic import ValidationError

from app.schemas.document import DocumentCreate

VALID = {
    "name": "Filosofia Lean",
    "original_filename": "Filosofia Lean.pdf",
    "checksum": "a" * 64,
    "file_size": 734000,
    "page_count": 42,
    "extracted_text": "Texto extraído del PDF...",
    "is_processed": True,
}


def with_(**changes: object) -> dict[str, object]:
    return {**VALID, **changes}


def test_acepta_un_documento_valido() -> None:
    document = DocumentCreate.model_validate_json(_json(VALID))

    assert document.name == "Filosofia Lean"


def test_acepta_texto_extraido_vacio() -> None:
    DocumentCreate.model_validate_json(_json(with_(extracted_text="")))


def test_quita_los_espacios_del_nombre() -> None:
    document = DocumentCreate.model_validate_json(_json(with_(name="  informe  ")))

    assert document.name == "informe"


@pytest.mark.parametrize(
    "changes",
    [
        {"name": ""},
        {"name": "   "},
        {"name": "x" * 256},
        {"original_filename": ""},
        {"checksum": "A" * 64},
        {"checksum": "a" * 63},
        {"checksum": "g" * 64},
        {"file_size": -1},
        {"page_count": -1},
        {"file_size": "734000"},
        {"file_size": 1.5},
        {"extracted_text": 123},
        {"extracted_text": None},
        {"is_processed": "true"},
        {"is_processed": 1},
    ],
)
def test_rechaza_datos_invalidos(changes: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        DocumentCreate.model_validate_json(_json(with_(**changes)))


@pytest.mark.parametrize("missing", sorted(VALID))
def test_todos_los_campos_son_obligatorios(missing: str) -> None:
    data = {k: v for k, v in VALID.items() if k != missing}

    with pytest.raises(ValidationError):
        DocumentCreate.model_validate_json(_json(data))


def _json(data: dict[str, object]) -> str:
    import json

    return json.dumps(data)
