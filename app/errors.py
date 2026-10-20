"""Traducción de errores a respuestas HTTP con formato RFC 9457 (Problem Details).

Es el mismo formato que usan pdf-extractext y orchestrator-service:
`{"type", "title", "status", "detail", "instance"}` con
`Content-Type: application/problem+json`.
"""

from http import HTTPStatus

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.exceptions import DocumentAlreadyExistsError
from app.schemas.error import ProblemDetail

PROBLEM_JSON = "application/problem+json"


def problem_response(request: Request, status_code: int, detail: str) -> JSONResponse:
    """Arma una respuesta Problem Details para el código y el detalle dados."""
    problem = ProblemDetail(
        title=HTTPStatus(status_code).phrase,
        status=status_code,
        detail=detail,
        instance=str(request.url),
    )
    return JSONResponse(
        status_code=status_code,
        content=problem.model_dump(),
        media_type=PROBLEM_JSON,
    )


async def _validation_error(request: Request, exc: Exception) -> JSONResponse:
    """Request inválida (campo faltante, tipo o formato incorrecto, JSON roto): 400.

    El contrato del servicio usa 400 para los datos inválidos, no el 422 que
    FastAPI devuelve por defecto.
    """
    assert isinstance(exc, RequestValidationError)
    parts = []
    for error in exc.errors():
        location = ".".join(str(part) for part in error.get("loc", ()))
        parts.append(f"{location}: {error.get('msg')}" if location else error["msg"])
    detail = "Datos inválidos: " + "; ".join(parts) if parts else "Datos inválidos."
    return problem_response(request, status.HTTP_400_BAD_REQUEST, detail)


async def _already_exists(request: Request, exc: Exception) -> JSONResponse:
    return problem_response(request, status.HTTP_409_CONFLICT, str(exc))


def register_error_handlers(app: FastAPI) -> None:
    """Registra los handlers globales de errores."""
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.add_exception_handler(DocumentAlreadyExistsError, _already_exists)
