from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, field_validator

from app.schemas.qr_attendance import AttendanceEventType


class DailyAttendanceStatus(StrEnum):
    COMPLETE = "complete"
    INCOMPLETE = "incomplete"
    ANOMALY = "anomaly"
    INCOMPLETE_ANOMALY = "incomplete_anomaly"


class AttendanceInterval(BaseModel):
    entree: datetime
    sortie: datetime
    duree_secondes: int


class DailyAttendanceSummary(BaseModel):
    date: date
    fuseau_horaire: str
    status: DailyAttendanceStatus
    total_secondes: int
    intervals: list[AttendanceInterval]
    event_count: int


class AttendanceEvent(BaseModel):
    date_heure: datetime
    type_pointage: AttendanceEventType

    @field_validator("date_heure")
    @classmethod
    def timestamp_must_be_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Le pointage doit avoir un fuseau horaire explicite.")
        return value
