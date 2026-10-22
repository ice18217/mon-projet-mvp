import logging
from collections import defaultdict
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from app.schemas.daily_attendance import DailyAttendanceStatus
from app.schemas.payroll_export import (
    PayrollAttendancePerson,
    PayrollExportPerson,
)
from app.services.attendance_calculation import (
    CASABLANCA_TIMEZONE,
    calculate_daily_attendance,
)
from app.services.supabase import get_payroll_attendance_data

logger = logging.getLogger(__name__)
HOURS_QUANTUM = Decimal("0.01")


async def create_weekly_payroll_export(
    week_start: date,
) -> list[PayrollExportPerson]:
    week_end_exclusive = week_start + timedelta(days=7)
    personnel = await get_payroll_attendance_data(
        week_start,
        week_end_exclusive,
    )
    result = [
        _calculate_person_week(person, week_start)
        for person in personnel
    ]
    logger.info(
        "Prepared weekly payroll export for %s: %s personnel.",
        week_start.isoformat(),
        len(result),
    )
    return result


def _calculate_person_week(
    person: PayrollAttendancePerson,
    week_start: date,
) -> PayrollExportPerson:
    events_by_day = defaultdict(list)
    for event in person.pointages:
        local_day = event.date_heure.astimezone(CASABLANCA_TIMEZONE).date()
        if not week_start <= local_day < week_start + timedelta(days=7):
            raise ValueError("Attendance event is outside the requested week.")
        events_by_day[local_day].append(event)

    accepted_seconds = 0
    complete_days = 0
    review_days = 0
    for day, events in events_by_day.items():
        summary = calculate_daily_attendance(day, events)
        if summary.status == DailyAttendanceStatus.COMPLETE:
            accepted_seconds += summary.total_secondes
            complete_days += 1
        else:
            review_days += 1

    hours = (Decimal(accepted_seconds) / Decimal(3600)).quantize(
        HOURS_QUANTUM,
        rounding=ROUND_HALF_UP,
    )
    return PayrollExportPerson(
        id_personnel=person.id_personnel,
        nom=person.nom,
        prenom=person.prenom,
        heures=hours,
        jours_complets=complete_days,
        jours_a_revoir=review_days,
    )
