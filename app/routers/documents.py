from typing import Annotated, Any

from fastapi import APIRouter, Path, Query, status

from app.dependencies import DocumentServiceDep
from app.schemas.document import DocumentCreate, DocumentResponse, DocumentUpdate
from app.schemas.error import ProblemDetail

#: Todas las operaciones usan MongoDB: si no responde, 503.
_UNAVAILABLE: dict[int | str, dict[str, Any]] = {
    status.HTTP_503_SERVICE_UNAVAILABLE: {
        "model": ProblemDetail,
        "description": "La base de datos no está disponible",
    }
}

router = APIRouter(prefix="/documents", tags=["documents"], responses=_UNAVAILABLE)

#: Id de documento en la ruta: entero positivo (si no, 400).
DocumentId = Annotated[int, Path(gt=0, description="Id entero del documento")]

#: Respuestas de error documentadas en OpenAPI (cuerpo RFC 9457).
_BAD_REQUEST: dict[int | str, dict[str, Any]] = {
    status.HTTP_400_BAD_REQUEST: {"model": ProblemDetail}
}
_NOT_FOUND: dict[int | str, dict[str, Any]] = {
    status.HTTP_404_NOT_FOUND: {
        "model": ProblemDetail,
        "description": "No existe un documento con ese id",
    }
}


@router.post(
    "",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear un documento",
    responses={
        **_BAD_REQUEST,
        status.HTTP_409_CONFLICT: {
            "model": ProblemDetail,
            "description": "Ya existe un documento con el mismo checksum",
        },
    },
)
async def create_document(
    payload: DocumentCreate,
    service: DocumentServiceDep,
) -> DocumentResponse:
    """Registra un documento ya procesado. El checksum debe ser único."""
    document = await service.create_document(payload)
    return DocumentResponse.model_validate(document)


@router.get(
    "",
    response_model=list[DocumentResponse],
    summary="Listar documentos con paginación",
    responses=_BAD_REQUEST,
)
async def list_documents(
    service: DocumentServiceDep,
    skip: int = Query(default=0, ge=0, description="Documentos a omitir"),
    limit: int = Query(default=10, ge=1, le=100, description="Máximo a devolver"),
) -> list[DocumentResponse]:
    """Página de documentos en orden de id ascendente (lista vacía si no hay)."""
    documents = await service.list_documents(skip=skip, limit=limit)
    return [DocumentResponse.model_validate(document) for document in documents]


@router.get(
    "/{document_id}",
    response_model=DocumentResponse,
    summary="Obtener un documento por ID",
    responses={**_BAD_REQUEST, **_NOT_FOUND},
)
async def get_document(
    document_id: DocumentId,
    service: DocumentServiceDep,
) -> DocumentResponse:
    """Devuelve el documento con ese id, o 404 si no existe."""
    document = await service.get_document(document_id)
    return DocumentResponse.model_validate(document)


@router.put(
    "/{document_id}",
    response_model=DocumentResponse,
    status_code=status.HTTP_200_OK,
    summary="Actualizar campos editables de un documento",
    responses={**_BAD_REQUEST, **_NOT_FOUND},
)
async def update_document(
    document_id: DocumentId,
    payload: DocumentUpdate,
    service: DocumentServiceDep,
) -> DocumentResponse:
    """Actualiza el nombre y devuelve el documento completo."""
    document = await service.update_document(document_id, payload)
    return DocumentResponse.model_validate(document)


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar un documento",
    responses={**_BAD_REQUEST, **_NOT_FOUND},
)
async def delete_document(
    document_id: DocumentId,
    service: DocumentServiceDep,
) -> None:
    """Elimina el documento con ese id, o responde 404 si no existe."""
    await service.delete_document(document_id)
