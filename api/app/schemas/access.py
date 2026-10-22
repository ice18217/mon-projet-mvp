from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AssignableRole(StrEnum):
    PERSONNEL = "personnel"
    RH = "rh"
    SCOLARITE = "scolarite"
    FINANCE = "finance"


class PendingPersonnel(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: UUID
    nom: str
    prenom: str
    email: str
    type: str
    created_at: datetime


class AccessApprovalRequest(BaseModel):
    roles: list[AssignableRole] = Field(min_length=1, max_length=4)

    @field_validator("roles")
    @classmethod
    def roles_must_be_unique(
        cls, roles: list[AssignableRole]
    ) -> list[AssignableRole]:
        if len(set(roles)) != len(roles):
            raise ValueError("Chaque rôle ne peut être sélectionné qu'une fois.")
        return roles
