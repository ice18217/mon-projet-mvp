from collections import Counter
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.schemas.daily_attendance import (
    AttendanceEvent,
    AttendanceInterval,
    DailyAttendanceStatus,
    DailyAttendanceSummary,
)
from app.schemas.qr_attendance import AttendanceEventType

CASABLANCA_TIMEZONE = ZoneInfo("Africa/Casablanca")
CASABLANCA_TIMEZONE_NAME = "Africa/Casablanca"


def local_day_bounds(day: date) -> tuple[datetime, datetime]:
    start = datetime.combine(day, time.min, tzinfo=CASABLANCA_TIMEZONE)
    end = datetime.combine(day + timedelta(days=1), time.min, tzinfo=CASABLANCA_TIMEZONE)
    return start, end


def calculate_daily_attendance(
    day: date,
    events: list[AttendanceEvent],
) -> DailyAttendanceSummary:
    ordered_events = sorted(events, key=lambda event: event.date_heure)
    timestamp_counts = Counter(event.date_heure for event in ordered_events)
    ambiguous_timestamps = {
        timestamp for timestamp, count in timestamp_counts.items() if count > 1
    }
    has_anomaly = bool(ambiguous_timestamps)
    intervals: list[AttendanceInterval] = []
    pending_entry: datetime | None = None
    has_incomplete_entry = False

    for event in ordered_events:
        timestamp = event.date_heure
        if timestamp in ambiguous_timestamps:
            continue

        if event.type_pointage == AttendanceEventType.ENTREE:
            if pending_entry is None:
                pending_entry = timestamp
            else:
                has_anomaly = True
                pending_entry = None
        elif pending_entry is None:
            has_anomaly = True
        else:
            duration = int((timestamp - pending_entry).total_seconds())
            if duration <= 0:
                has_anomaly = True
            else:
                intervals.append(
                    AttendanceInterval(
                        entree=pending_entry,
                        sortie=timestamp,
                        duree_secondes=duration,
                    )
                )
            pending_entry = None

    if pending_entry is not None:
        has_incomplete_entry = True

    if has_anomaly and has_incomplete_entry:
        status = DailyAttendanceStatus.INCOMPLETE_ANOMALY
    elif has_anomaly:
        status = DailyAttendanceStatus.ANOMALY
    elif has_incomplete_entry:
        status = DailyAttendanceStatus.INCOMPLETE
    else:
        status = DailyAttendanceStatus.COMPLETE

    return DailyAttendanceSummary(
        date=day,
        fuseau_horaire=CASABLANCA_TIMEZONE_NAME,
        status=status,
        total_secondes=sum(interval.duree_secondes for interval in intervals),
        intervals=intervals,
        event_count=len(ordered_events),
    )
