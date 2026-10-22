from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AttendanceEventType(StrEnum):
    ENTREE = "entree"
    SORTIE = "sortie"


class QRCredentialStatus(BaseModel):
    has_active_credential: bool


class QRCredentialIssue(BaseModel):
    qr_image: str


class QRScanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    payload: str = Field(min_length=1, max_length=200)
    type_pointage: AttendanceEventType
    idempotency_key: UUID


class QRScanResult(BaseModel):
    id_pointage: UUID
    id_personnel: UUID
    nom: str
    prenom: str
    date_heure: datetime
    type_pointage: AttendanceEventType
    duplicate: bool
