from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.daily_attendance import AttendanceEvent


class PayrollAttendancePerson(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id_personnel: UUID
    nom: str
    prenom: str
    pointages: list[AttendanceEvent]


class PayrollExportPerson(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id_personnel: UUID
    nom: str
    prenom: str
    heures: Decimal = Field(ge=Decimal(0))
    jours_complets: int = Field(ge=0)
    jours_a_revoir: int = Field(ge=0)
