from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from app.dependencies.auth import ApprovedAdmin, require_technical_admin
from app.schemas.access import AccessApprovalRequest, PendingPersonnel
from app.services.supabase import approve_personnel_access, list_pending_personnel

router = APIRouter(prefix="/access", tags=["access"])


@router.get("/pending", response_model=list[PendingPersonnel])
async def get_pending_access_requests(
    _: Annotated[ApprovedAdmin, Depends(require_technical_admin)],
) -> list[PendingPersonnel]:
    return await list_pending_personnel()


@router.post("/{personnel_id}/approve", status_code=204)
async def approve_access_request(
    personnel_id: UUID,
    request: AccessApprovalRequest,
    _: Annotated[ApprovedAdmin, Depends(require_technical_admin)],
) -> None:
    await approve_personnel_access(personnel_id, request.roles)
