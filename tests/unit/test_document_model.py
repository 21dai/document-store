from datetime import UTC, datetime

from app.models.document import Document
from app.repositories.mongo_document_repository import from_mongo, to_mongo

CHECKSUM = "a" * 64


def make_document(**overrides: object) -> Document:
    data: dict[str, object] = {
        "name": "Filosofia Lean",
        "original_filename": "Filosofia Lean.pdf",
        "checksum": CHECKSUM,
        "file_size": 734000,
        "page_count": 42,
        "extracted_text": "Texto extraído del PDF...",
        "is_processed": True,
    }
    data.update(overrides)
    return Document(**data)  # type: ignore[arg-type]


def test_un_documento_nuevo_no_tiene_id_hasta_persistirse() -> None:
    assert make_document().id is None


def test_las_fechas_son_utc_con_precision_de_milisegundos() -> None:
    document = make_document()

    assert document.created_at.tzinfo is UTC
    assert document.created_at.microsecond % 1000 == 0
    assert document.updated_at == document.created_at


def test_la_serializacion_ida_y_vuelta_conserva_todos_los_campos() -> None:
    document = make_document(id=7)

    assert from_mongo(to_mongo(document)) == document


def test_to_mongo_guarda_los_campos_del_contrato() -> None:
    data = to_mongo(make_document(id=7))

    assert set(data) == {
        "id",
        "name",
        "original_filename",
        "checksum",
        "file_size",
        "page_count",
        "extracted_text",
        "is_processed",
        "created_at",
        "updated_at",
    }


def test_from_mongo_ignora_el_id_interno_y_campos_desconocidos() -> None:
    data = to_mongo(make_document(id=3))
    data["_id"] = "id interno de MongoDB"
    data["campo_de_una_version_futura"] = 1

    document = from_mongo(data)

    assert document.id == 3
    assert document.created_at == datetime.fromisoformat(data["created_at"].isoformat())
