from datetime import date, datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator

from app.schemas.daily_attendance import DailyAttendanceStatus


class DashboardPresenceStatus(StrEnum):
    PRESENT = "present"
    LATE = "retard"
    ABSENT = "absent"
    PENDING = "en_attente"
    NO_SCHEDULE = "sans_horaire"


class DashboardSchedule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id_personnel: UUID
    debut: datetime
    fin: datetime
    type_activite: str

    @field_validator("debut", "fin")
    @classmethod
    def timestamp_must_be_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("L’horaire doit comporter un fuseau explicite.")
        return value


class DashboardPersonnel(BaseModel):
    id_personnel: UUID
    nom: str
    prenom: str
    statut_presence: DashboardPresenceStatus
    debut_horaire: datetime | None
    fin_horaire: datetime | None
    type_activite: str | None
    total_secondes: int
    etat_calcul: DailyAttendanceStatus
    nombre_pointages: int


class AttendanceDashboardCounts(BaseModel):
    present: int
    retard: int
    absent: int
    en_attente: int
    sans_horaire: int


class AttendanceDashboard(BaseModel):
    date: date
    fuseau_horaire: str
    effectif: int
    compteurs: AttendanceDashboardCounts
    personnel: list[DashboardPersonnel]
