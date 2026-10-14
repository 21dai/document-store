from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Document:
    """Entidad de dominio de un documento procesado y persistido."""

    name: str
    original_filename: str
    checksum: str
    file_size: int
    page_count: int
    extracted_text: str
    is_processed: bool = False
    id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=_utc_now)
    updated_at: datetime = field(default_factory=_utc_now)
