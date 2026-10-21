"""Excepciones de dominio de document-store.

Las lanzan el service y el repositorio; la capa HTTP las traduce a códigos
de estado. Viven aparte para que el repositorio no dependa del service.
"""


class DocumentError(Exception):
    """Base de las excepciones de dominio."""


class DocumentAlreadyExistsError(DocumentError):
    """Ya existe un documento con el mismo checksum (HTTP 409)."""

    def __init__(self, checksum: str) -> None:
        super().__init__(f"Ya existe un documento con el checksum {checksum}.")
        self.checksum = checksum


class DocumentNotFoundError(DocumentError):
    """No existe un documento con el ID indicado (HTTP 404)."""

    def __init__(self, document_id: int) -> None:
        super().__init__(f"No existe un documento con id {document_id}.")
        self.document_id = document_id


class DatabaseUnavailableError(DocumentError):
    """MongoDB no responde (HTTP 503).

    La lanza el repositorio cuando falla la conexión con la base, para que
    las capas de arriba no dependan de las excepciones de PyMongo.
    """

    def __init__(self) -> None:
        super().__init__("La base de datos no está disponible; reintentar más tarde.")
