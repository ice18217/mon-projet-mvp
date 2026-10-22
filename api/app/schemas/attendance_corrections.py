from datetime import date, datetime, time
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.qr_attendance import AttendanceEventType


class AttendanceCorrectionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: date
    heure: time
    motif: str = Field(min_length=5, max_length=500)

    @field_validator("heure")
    @classmethod
    def time_must_have_minute_precision(cls, value: time) -> time:
        if value.second != 0 or value.microsecond != 0 or value.tzinfo is not None:
            raise ValueError("L’heure corrigée doit être une heure locale HH:MM.")
        return value

    @field_validator("motif")
    @classmethod
    def reason_must_not_be_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if len(cleaned) < 5:
            raise ValueError("Le motif doit contenir au moins 5 caractères.")
        return cleaned


class AttendanceCorrectionHistoryEntry(BaseModel):
    revision: int = Field(ge=1)
    date_correction: datetime
    motif: str
    ancienne_valeur: datetime
    nouvelle_valeur: datetime

    @field_validator("date_correction", "ancienne_valeur", "nouvelle_valeur")
    @classmethod
    def timestamp_must_be_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("La correction doit comporter un fuseau explicite.")
        return value


class EffectiveAttendancePointage(BaseModel):
    id_pointage: UUID
    id_personnel: UUID
    type_pointage: AttendanceEventType
    date_heure_originale: datetime
    date_heure_effective: datetime
    historique: list[AttendanceCorrectionHistoryEntry]

    @field_validator("date_heure_originale", "date_heure_effective")
    @classmethod
    def timestamp_must_be_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Le pointage doit comporter un fuseau explicite.")
        return value


class AttendanceCorrectionRecord(EffectiveAttendancePointage):
    nom: str
    prenom: str


class AttendanceCorrectionDay(BaseModel):
    date: date
    fuseau_horaire: str
    pointages: list[AttendanceCorrectionRecord]
