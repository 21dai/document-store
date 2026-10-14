from pydantic import BaseModel


class ProblemDetail(BaseModel):
    """Cuerpo de error según RFC 9457 (application/problem+json).

    Los exception handlers que mapean las excepciones de dominio a este
    formato se implementan en el issue #8.
    """

    type: str = "about:blank"
    title: str
    status: int
    detail: str | None = None
    instance: str | None = None
