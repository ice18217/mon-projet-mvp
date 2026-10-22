from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.services import supabase

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class ApprovedAdmin:
    user_id: UUID


async def require_authenticated_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(bearer_scheme)
    ],
) -> UUID:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentification requise.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return await supabase.verify_access_token(credentials.credentials)


async def require_technical_admin(
    user_id: Annotated[UUID, Depends(require_authenticated_user)],
) -> ApprovedAdmin:
    profile = await supabase.get_personnel_profile(user_id)
    if (
        profile is None
        or not profile["actif"]
        or not profile["acces_approuve"]
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Compte non approuvé ou inactif.",
        )

    roles = await supabase.get_personnel_roles(UUID(profile["id"]))
    if "admin_technique" not in roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Rôle administrateur technique requis.",
        )

    return ApprovedAdmin(user_id=user_id)


async def require_approved_personnel(
    user_id: Annotated[UUID, Depends(require_authenticated_user)],
) -> UUID:
    profile = await supabase.get_personnel_profile(user_id)
    if (
        profile is None
        or not profile["actif"]
        or not profile["acces_approuve"]
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Compte non approuvé ou inactif.",
        )

    roles = await supabase.get_personnel_roles(UUID(profile["id"]))
    if "personnel" not in roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Le rôle Personnel est requis.",
        )

    return UUID(profile["id"])


async def require_attendance_operator(
    user_id: Annotated[UUID, Depends(require_authenticated_user)],
) -> UUID:
    profile = await supabase.get_personnel_profile(user_id)
    if (
        profile is None
        or not profile["actif"]
        or not profile["acces_approuve"]
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Compte non approuvé ou inactif.",
        )

    roles = await supabase.get_personnel_roles(UUID(profile["id"]))
    if not roles.intersection({"rh", "scolarite"}):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Un rôle RH ou Scolarité est requis.",
        )

    return user_id


async def require_payroll_export_operator(
    user_id: Annotated[UUID, Depends(require_authenticated_user)],
) -> UUID:
    profile = await supabase.get_personnel_profile(user_id)
    if (
        profile is None
        or not profile["actif"]
        or not profile["acces_approuve"]
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Compte non approuvé ou inactif.",
        )

    roles = await supabase.get_personnel_roles(UUID(profile["id"]))
    if not roles.intersection({"rh", "finance"}):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Un rôle RH ou Finance est requis pour l’export.",
        )

    return user_id
