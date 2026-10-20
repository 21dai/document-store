from dataclasses import dataclass, field
from datetime import UTC, datetime


def utc_now() -> datetime:
    """Hora actual en UTC, truncada a milisegundos.

    MongoDB guarda las fechas con precisión de milisegundos: truncar al crear
    el documento hace que lo que devuelve el alta sea igual a lo que se lee
    después de la base.
    """
    now = datetime.now(UTC)
    return now.replace(microsecond=now.microsecond // 1000 * 1000)


@dataclass
class Document:
    """Entidad de dominio de un documento procesado y persistido.

    `id` es un entero secuencial que asigna el repositorio al guardarlo; un
    documento que todavía no se persistió tiene `id=None`.
    """

    name: str
    original_filename: str
    checksum: str
    file_size: int
    page_count: int
    extracted_text: str
    is_processed: bool = False
    id: int | None = None
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default=None)  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.updated_at is None:
            self.updated_at = self.created_at
