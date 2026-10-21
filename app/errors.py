"""Traducción de errores a respuestas HTTP con formato RFC 9457 (Problem Details).

Es el mismo formato que usan pdf-extractext y orchestrator-service:
`{"type", "title", "status", "detail", "instance"}` con
`Content-Type: application/problem+json`. Todo error sale así, también los
que arma FastAPI (ruta inexistente, método no permitido) y los no previstos.

| Situación                                   | Código |
|---------------------------------------------|--------|
| Datos inválidos (body, path o query)        | 400    |
| Documento inexistente o ruta inexistente    | 404    |
| Método no permitido                         | 405    |
| Checksum repetido                           | 409    |
| Error no previsto                           | 500    |
| MongoDB no responde                         | 503    |

El servicio nunca responde 422: la validación es estricta y sale como 400.
"""

from collections.abc import Mapping
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.exceptions import (
    DatabaseUnavailableError,
    DocumentAlreadyExistsError,
    DocumentNotFoundError,
)
from app.schemas.error import ProblemDetail

PROBLEM_JSON = "application/problem+json"

_INTERNAL_ERROR_DETAIL = "Error interno del servidor."

#: Esquemas que FastAPI agrega a OpenAPI para su 422 por defecto.
_DEFAULT_422_SCHEMAS = ("HTTPValidationError", "ValidationError")


def problem_response(
    request: Request,
    status_code: int,
    detail: str,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
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
        headers=headers,
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


async def _http_error(request: Request, exc: Exception) -> JSONResponse:
    """Errores HTTP de FastAPI/Starlette (404 de ruta, 405, ...) en el mismo formato.

    Conserva los headers del error, como el `Allow` de un 405.
    """
    assert isinstance(exc, StarletteHTTPException)
    return problem_response(request, exc.status_code, str(exc.detail), exc.headers)


async def _already_exists(request: Request, exc: Exception) -> JSONResponse:
    return problem_response(request, status.HTTP_409_CONFLICT, str(exc))


async def _not_found(request: Request, exc: Exception) -> JSONResponse:
    return problem_response(request, status.HTTP_404_NOT_FOUND, str(exc))


async def _database_unavailable(request: Request, exc: Exception) -> JSONResponse:
    """MongoDB no responde: 503 sin Retry-After.

    Es una caída, no una carga pasajera: el circuit breaker del orquestador
    tiene que contarla como fallo.
    """
    return problem_response(request, status.HTTP_503_SERVICE_UNAVAILABLE, str(exc))


async def _unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    """Fallback de errores no previstos: 500 sin detalles internos.

    El mensaje y el traceback no salen en la respuesta; Starlette vuelve a
    lanzar la excepción después de responder y el servidor la registra.
    """
    return problem_response(
        request, status.HTTP_500_INTERNAL_SERVER_ERROR, _INTERNAL_ERROR_DETAIL
    )


def register_error_handlers(app: FastAPI) -> None:
    """Registra los handlers globales de errores."""
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.add_exception_handler(StarletteHTTPException, _http_error)
    app.add_exception_handler(DocumentAlreadyExistsError, _already_exists)
    app.add_exception_handler(DocumentNotFoundError, _not_found)
    app.add_exception_handler(DatabaseUnavailableError, _database_unavailable)
    app.add_exception_handler(Exception, _unexpected_error)
    _document_400_instead_of_422(app)


def _document_400_instead_of_422(app: FastAPI) -> None:
    """Saca de OpenAPI el 422 que FastAPI agrega por defecto.

    El servicio responde 400 a los datos inválidos (cada endpoint lo
    documenta); dejar el 422 en `/docs` describiría una respuesta que nunca
    ocurre.
    """
    build_openapi = app.openapi

    def openapi() -> dict[str, Any]:
        if app.openapi_schema is None:
            schema = build_openapi()
            for operations in schema.get("paths", {}).values():
                for operation in operations.values():
                    operation.get("responses", {}).pop("422", None)
            schemas = schema.get("components", {}).get("schemas", {})
            for name in _DEFAULT_422_SCHEMAS:
                schemas.pop(name, None)
            app.openapi_schema = schema
        return app.openapi_schema

    app.openapi = openapi  # type: ignore[method-assign]
