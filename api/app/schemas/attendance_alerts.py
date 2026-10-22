from datetime import date, datetime, time
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class PersonnelOption(BaseModel):
    id: UUID
    nom: str
    prenom: str
    email: str


class ScheduleInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id_personnel: UUID
    date: date
    heure_debut: time
    heure_fin: time
    type_activite: str = Field(min_length=1, max_length=120)

    @field_validator("heure_debut", "heure_fin")
    @classmethod
    def time_must_have_minute_precision(cls, value: time) -> time:
        if value.second != 0 or value.microsecond != 0 or value.tzinfo is not None:
            raise ValueError("L’horaire doit être une heure locale HH:MM.")
        return value

    @field_validator("type_activite")
    @classmethod
    def activity_must_not_be_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Le type d’activité ne peut pas être vide.")
        return cleaned

    @model_validator(mode="after")
    def schedule_must_fit_one_day(self) -> "ScheduleInput":
        if self.heure_fin <= self.heure_debut:
            raise ValueError(
                "L’horaire doit finir après son début et ne peut pas traverser minuit."
            )
        return self


class ScheduleRecord(BaseModel):
    id: UUID
    id_personnel: UUID
    date: date
    heure_debut: time
    heure_fin: time
    type_activite: str
    nom: str
    prenom: str


class ScheduleOverview(BaseModel):
    date: date
    personnel: list[PersonnelOption]
    horaires: list[ScheduleRecord]


class AttendanceAlertType(StrEnum):
    ABSENCE = "absence"
    RETARD = "retard"


class AttendanceAlertStatus(StrEnum):
    ENVOYEE = "envoyee"
    TRAITEE = "traitee"


class AttendanceAlert(BaseModel):
    id: UUID
    id_personnel: UUID
    id_emploi_du_temps: UUID
    date_alerte: datetime
    type: AttendanceAlertType
    statut: AttendanceAlertStatus
    nom: str
    prenom: str
    debut: datetime
    fin: datetime
    type_activite: str


class AttendanceAlertList(BaseModel):
    date: date
    seuil_retard_minutes: int
    alertes: list[AttendanceAlert]
