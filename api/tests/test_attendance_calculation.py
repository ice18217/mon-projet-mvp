from datetime import UTC, date, datetime

from app.schemas.daily_attendance import (
    AttendanceEvent,
    DailyAttendanceStatus,
)
from app.schemas.qr_attendance import AttendanceEventType
from app.services.attendance_calculation import (
    CASABLANCA_TIMEZONE,
    calculate_daily_attendance,
    local_day_bounds,
)

DAY = date(2026, 10, 15)


def event(hour: int, minute: int, kind: AttendanceEventType) -> AttendanceEvent:
    return AttendanceEvent(
        date_heure=datetime(2026, 10, 15, hour, minute, tzinfo=UTC),
        type_pointage=kind,
    )


def test_one_complete_interval_calculates_duration() -> None:
    summary = calculate_daily_attendance(
        DAY,
        [
            event(8, 0, AttendanceEventType.ENTREE),
            event(16, 30, AttendanceEventType.SORTIE),
        ],
    )

    assert summary.status == DailyAttendanceStatus.COMPLETE
    assert summary.total_secondes == 8 * 60 * 60 + 30 * 60
    assert len(summary.intervals) == 1


def test_multiple_complete_intervals_are_summed() -> None:
    summary = calculate_daily_attendance(
        DAY,
        [
            event(8, 0, AttendanceEventType.ENTREE),
            event(12, 0, AttendanceEventType.SORTIE),
            event(13, 0, AttendanceEventType.ENTREE),
            event(17, 30, AttendanceEventType.SORTIE),
        ],
    )

    assert summary.status == DailyAttendanceStatus.COMPLETE
    assert summary.total_secondes == 8 * 60 * 60 + 30 * 60
    assert len(summary.intervals) == 2


def test_open_entry_is_not_counted_and_day_is_incomplete() -> None:
    summary = calculate_daily_attendance(
        DAY,
        [
            event(8, 0, AttendanceEventType.ENTREE),
        ],
    )

    assert summary.status == DailyAttendanceStatus.INCOMPLETE
    assert summary.total_secondes == 0
    assert summary.intervals == []


def test_valid_interval_is_preserved_alongside_incomplete_entry() -> None:
    summary = calculate_daily_attendance(
        DAY,
        [
            event(8, 0, AttendanceEventType.ENTREE),
            event(12, 0, AttendanceEventType.SORTIE),
            event(13, 0, AttendanceEventType.ENTREE),
        ],
    )

    assert summary.status == DailyAttendanceStatus.INCOMPLETE
    assert summary.total_secondes == 4 * 60 * 60
    assert len(summary.intervals) == 1


def test_orphan_exit_is_reported_as_anomaly() -> None:
    summary = calculate_daily_attendance(
        DAY,
        [event(17, 0, AttendanceEventType.SORTIE)],
    )

    assert summary.status == DailyAttendanceStatus.ANOMALY
    assert summary.total_secondes == 0


def test_duplicate_entries_make_ambiguous_sequence_anomalous() -> None:
    summary = calculate_daily_attendance(
        DAY,
        [
            event(8, 0, AttendanceEventType.ENTREE),
            event(9, 0, AttendanceEventType.ENTREE),
            event(17, 0, AttendanceEventType.SORTIE),
        ],
    )

    assert summary.status == DailyAttendanceStatus.ANOMALY
    assert summary.total_secondes == 0


def test_duplicate_timestamp_events_are_excluded_as_ambiguous() -> None:
    timestamp = datetime(2026, 10, 15, 8, 0, tzinfo=UTC)
    summary = calculate_daily_attendance(
        DAY,
        [
            AttendanceEvent(
                date_heure=timestamp,
                type_pointage=AttendanceEventType.ENTREE,
            ),
            AttendanceEvent(
                date_heure=timestamp,
                type_pointage=AttendanceEventType.SORTIE,
            ),
        ],
    )

    assert summary.status == DailyAttendanceStatus.ANOMALY
    assert summary.total_secondes == 0


def test_anomaly_and_open_entry_are_reported_together() -> None:
    summary = calculate_daily_attendance(
        DAY,
        [
            event(8, 0, AttendanceEventType.ENTREE),
            event(9, 0, AttendanceEventType.ENTREE),
            event(10, 0, AttendanceEventType.ENTREE),
        ],
    )

    assert summary.status == DailyAttendanceStatus.INCOMPLETE_ANOMALY
    assert summary.total_secondes == 0


def test_valid_intervals_before_and_after_anomaly_are_counted() -> None:
    summary = calculate_daily_attendance(
        DAY,
        [
            event(7, 0, AttendanceEventType.ENTREE),
            event(8, 0, AttendanceEventType.SORTIE),
            event(9, 0, AttendanceEventType.ENTREE),
            event(10, 0, AttendanceEventType.ENTREE),
            event(11, 0, AttendanceEventType.SORTIE),
            event(12, 0, AttendanceEventType.ENTREE),
            event(13, 0, AttendanceEventType.SORTIE),
        ],
    )

    assert summary.status == DailyAttendanceStatus.ANOMALY
    assert summary.total_secondes == 2 * 60 * 60
    assert len(summary.intervals) == 2


def test_day_bounds_follow_casablanca_timezone() -> None:
    start, end = local_day_bounds(date(2026, 10, 15))

    assert start.tzinfo is not None
    assert end.tzinfo is not None
    assert start.astimezone(CASABLANCA_TIMEZONE).date() == date(2026, 10, 15)
    assert end.astimezone(CASABLANCA_TIMEZONE).date() == date(2026, 10, 16)
