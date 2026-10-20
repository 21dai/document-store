from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

#: Formato del checksum: SHA-256 hexadecimal en minúsculas (64 caracteres).
CHECKSUM_REGEX = r"^[a-f0-9]{64}$"

#: Texto de 1 a 255 caracteres; los espacios de los extremos no cuentan.
NonEmptyName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
]


class DocumentCreate(BaseModel):
    """Datos requeridos para crear un documento (contrato: POST /api/v1/documents).

    Validación estricta: un número que llega como texto (`"734000"`) o un
    booleano como `"true"` o `1` se rechaza en lugar de convertirse.
    """

    model_config = ConfigDict(strict=True)

    name: NonEmptyName
    original_filename: NonEmptyName
    checksum: str = Field(pattern=CHECKSUM_REGEX)
    file_size: int = Field(ge=0)
    page_count: int = Field(ge=0)
    extracted_text: str
    is_processed: bool


class DocumentUpdate(BaseModel):
    """Campos editables de un documento (contrato: PUT /api/v1/documents/{id}).

    En la primera versión solo se puede actualizar el nombre.
    """

    name: str = Field(min_length=1, max_length=255)


class DocumentResponse(BaseModel):
    """Representación pública de un documento."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    original_filename: str
    checksum: str
    file_size: int
    page_count: int
    extracted_text: str
    is_processed: bool
    created_at: datetime
    updated_at: datetime
