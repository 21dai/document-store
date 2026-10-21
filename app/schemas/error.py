from pydantic import BaseModel


class ProblemDetail(BaseModel):
    """Cuerpo de error según RFC 9457 (application/problem+json).

    Todas las respuestas de error del servicio usan este formato; los
    handlers que lo arman están en `app/errors.py`.
    """

    type: str = "about:blank"
    title: str
    status: int
    detail: str | None = None
    instance: str | None = None
