from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

#: Formato del checksum: SHA-256 hexadecimal en minúsculas (64 caracteres).
CHECKSUM_REGEX = r"^[a-f0-9]{64}$"


class DocumentCreate(BaseModel):
    """Datos requeridos para crear un documento (contrato: POST /api/v1/documents)."""

    name: str = Field(min_length=1, max_length=255)
    original_filename: str = Field(min_length=1, max_length=255)
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

    id: str
    name: str
    original_filename: str
    checksum: str
    file_size: int
    page_count: int
    extracted_text: str
    is_processed: bool
    created_at: datetime
    updated_at: datetime
