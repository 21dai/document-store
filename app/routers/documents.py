from fastapi import APIRouter, HTTPException, Query, status

from app.dependencies import DocumentServiceDep
from app.schemas.document import DocumentCreate, DocumentResponse, DocumentUpdate

router = APIRouter(prefix="/documents", tags=["documents"])

_NOT_IMPLEMENTED_DETAIL = "Este endpoint se implementa en un issue posterior (#4 a #7)."


@router.post(
    "",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear un documento",
)
async def create_document(
    payload: DocumentCreate,
    service: DocumentServiceDep,
) -> DocumentResponse:
    # Issue #4: Implementar creación de documentos.
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=_NOT_IMPLEMENTED_DETAIL,
    )


@router.get(
    "",
    response_model=list[DocumentResponse],
    summary="Listar documentos con paginación",
)
async def list_documents(
    service: DocumentServiceDep,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=10, ge=1, le=100),
) -> list[DocumentResponse]:
    # Issue #5: Implementar consultas y paginación.
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=_NOT_IMPLEMENTED_DETAIL,
    )


@router.get(
    "/{document_id}",
    response_model=DocumentResponse,
    summary="Obtener un documento por ID",
)
async def get_document(
    document_id: int,
    service: DocumentServiceDep,
) -> DocumentResponse:
    # Issue #5: Implementar consultas y paginación.
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=_NOT_IMPLEMENTED_DETAIL,
    )


@router.put(
    "/{document_id}",
    response_model=DocumentResponse,
    summary="Actualizar campos editables de un documento",
)
async def update_document(
    document_id: int,
    payload: DocumentUpdate,
    service: DocumentServiceDep,
) -> DocumentResponse:
    # Issue #6: Implementar actualización.
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=_NOT_IMPLEMENTED_DETAIL,
    )


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar un documento",
)
async def delete_document(
    document_id: int,
    service: DocumentServiceDep,
) -> None:
    # Issue #7: Implementar eliminación.
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=_NOT_IMPLEMENTED_DETAIL,
    )
