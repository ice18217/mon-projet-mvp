from datetime import UTC, date, datetime, time, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.dependencies.auth import (
    require_approved_personnel,
    require_attendance_operator,
)
from app.schemas.attendance_alerts import (
    AttendanceAlertList,
    ScheduleInput,
    ScheduleOverview,
)
from app.schemas.attendance_corrections import (
    AttendanceCorrectionDay,
    AttendanceCorrectionInput,
)
from app.schemas.attendance_dashboard import (
    AttendanceDashboard,
    AttendanceDashboardCounts,
    DashboardPersonnel,
    DashboardPresenceStatus,
)
from app.schemas.daily_attendance import DailyAttendanceSummary
from app.schemas.qr_attendance import (
    AttendanceEventType,
    QRCredentialIssue,
    QRCredentialStatus,
    QRScanRequest,
    QRScanResult,
)
from app.services.attendance_calculation import (
    CASABLANCA_TIMEZONE,
    calculate_daily_attendance,
)
from app.services.supabase import (
    correct_attendance_pointage,
    evaluate_daily_attendance_alerts,
    get_attendance_correction_day,
    get_attendance_dashboard_data,
    get_personnel_daily_attendance,
    get_qr_credential_status,
    get_schedule_overview,
    issue_personnel_qr,
    record_qr_attendance,
    resolve_attendance_alert,
    upsert_personnel_schedule,
)

router = APIRouter(prefix="/attendance", tags=["attendance"])
ALERT_GRACE_MINUTES = 10


@router.get("/qr/me", response_model=QRCredentialStatus)
async def get_my_qr_status(
    personnel_id: Annotated[UUID, Depends(require_approved_personnel)],
) -> QRCredentialStatus:
    return QRCredentialStatus(
        has_active_credential=await get_qr_credential_status(personnel_id)
    )


@router.post("/qr/me", response_model=QRCredentialIssue)
async def create_my_qr(
    personnel_id: Annotated[UUID, Depends(require_approved_personnel)],
) -> QRCredentialIssue:
    image = await issue_personnel_qr(personnel_id)
    return QRCredentialIssue(qr_image=f"data:image/png;base64,{image}")


@router.post("/scan", response_model=QRScanResult)
async def scan_personnel_qr(
    request: QRScanRequest,
    operator_user_id: Annotated[UUID, Depends(require_attendance_operator)],
) -> QRScanResult:
    return await record_qr_attendance(
        payload=request.payload,
        type_pointage=request.type_pointage,
        idempotency_key=request.idempotency_key,
        operator_user_id=operator_user_id,
    )


@router.get("/me/daily-summary", response_model=DailyAttendanceSummary)
async def get_my_daily_attendance_summary(
    personnel_id: Annotated[UUID, Depends(require_approved_personnel)],
    requested_date: Annotated[date | None, Query(alias="date")] = None,
) -> DailyAttendanceSummary:
    day = requested_date or datetime.now(CASABLANCA_TIMEZONE).date()
    if day == date.max:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="La date demandée ne peut pas être traitée.",
        )
    events = await get_personnel_daily_attendance(personnel_id, day)
    return calculate_daily_attendance(day, events)


@router.get("/dashboard", response_model=AttendanceDashboard)
async def get_attendance_dashboard(
    _: Annotated[UUID, Depends(require_attendance_operator)],
    requested_date: Annotated[date | None, Query(alias="date")] = None,
) -> AttendanceDashboard:
    now = datetime.now(CASABLANCA_TIMEZONE)
    day = requested_date or now.date()
    if day > now.date():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Le tableau de bord ne prend pas en charge les dates futures.",
        )

    personnel, schedules, events_by_person = await get_attendance_dashboard_data(
        day
    )
    schedule_by_person = {schedule.id_personnel: schedule for schedule in schedules}
    rows: list[DashboardPersonnel] = []
    for person in personnel:
        events = events_by_person.get(person.id, [])
        summary = calculate_daily_attendance(day, events)
        schedule = schedule_by_person.get(person.id)
        presence_status = DashboardPresenceStatus.NO_SCHEDULE
        schedule_start = None
        schedule_end = None
        activity = None
        if schedule is not None:
            schedule_start = schedule.debut
            schedule_end = schedule.fin
            activity = schedule.type_activite
            entries = [
                event.date_heure
                for event in events
                if event.type_pointage == AttendanceEventType.ENTREE
                and schedule.debut <= event.date_heure <= schedule.fin
            ]
            if entries:
                first_entry = min(entries)
                presence_status = (
                    DashboardPresenceStatus.LATE
                    if first_entry
                    > schedule.debut + timedelta(minutes=ALERT_GRACE_MINUTES)
                    else DashboardPresenceStatus.PRESENT
                )
            elif now >= schedule.fin:
                presence_status = DashboardPresenceStatus.ABSENT
            else:
                presence_status = DashboardPresenceStatus.PENDING

        rows.append(
            DashboardPersonnel(
                id_personnel=person.id,
                nom=person.nom,
                prenom=person.prenom,
                statut_presence=presence_status,
                debut_horaire=schedule_start,
                fin_horaire=schedule_end,
                type_activite=activity,
                total_secondes=summary.total_secondes,
                etat_calcul=summary.status,
                nombre_pointages=summary.event_count,
            )
        )

    counts = {
        status_value.value: sum(
            row.statut_presence == status_value for row in rows
        )
        for status_value in DashboardPresenceStatus
    }
    return AttendanceDashboard(
        date=day,
        fuseau_horaire="Africa/Casablanca",
        effectif=len(rows),
        compteurs=AttendanceDashboardCounts(**counts),
        personnel=rows,
    )


@router.get("/corrections", response_model=AttendanceCorrectionDay)
async def get_daily_attendance_corrections(
    _: Annotated[UUID, Depends(require_attendance_operator)],
    requested_date: Annotated[date | None, Query(alias="date")] = None,
) -> AttendanceCorrectionDay:
    now = datetime.now(CASABLANCA_TIMEZONE)
    day = requested_date or now.date()
    if day > now.date():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Les corrections ne sont pas disponibles pour les dates futures.",
        )
    pointages = await get_attendance_correction_day(day)
    return AttendanceCorrectionDay(
        date=day,
        fuseau_horaire="Africa/Casablanca",
        pointages=pointages,
    )


@router.post(
    "/corrections/{pointage_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def create_attendance_correction(
    pointage_id: UUID,
    correction: AttendanceCorrectionInput,
    operator_user_id: Annotated[UUID, Depends(require_attendance_operator)],
) -> None:
    now = datetime.now(CASABLANCA_TIMEZONE)
    if correction.date > now.date():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Une correction ne peut pas viser une date future.",
        )
    corrected_at = _local_schedule_datetime(
        correction.date,
        correction.heure,
    )
    if corrected_at > now:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Une correction ne peut pas viser une heure future.",
        )
    await correct_attendance_pointage(
        pointage_id=pointage_id,
        operator_user_id=operator_user_id,
        corrected_at=corrected_at,
        reason=correction.motif,
    )


@router.get("/schedules", response_model=ScheduleOverview)
async def get_schedule_day(
    _: Annotated[UUID, Depends(require_attendance_operator)],
    requested_date: Annotated[date | None, Query(alias="date")] = None,
) -> ScheduleOverview:
    day = requested_date or datetime.now(CASABLANCA_TIMEZONE).date()
    personnel, schedules = await get_schedule_overview(day)
    return ScheduleOverview(date=day, personnel=personnel, horaires=schedules)


@router.post("/schedules", status_code=status.HTTP_204_NO_CONTENT)
async def save_schedule(
    schedule: ScheduleInput,
    operator_user_id: Annotated[UUID, Depends(require_attendance_operator)],
) -> None:
    starts_at = _local_schedule_datetime(schedule.date, schedule.heure_debut)
    ends_at = _local_schedule_datetime(schedule.date, schedule.heure_fin)
    await upsert_personnel_schedule(
        personnel_id=schedule.id_personnel,
        operator_user_id=operator_user_id,
        day=schedule.date,
        starts_at=starts_at,
        ends_at=ends_at,
        activity_type=schedule.type_activite,
    )


@router.get("/alerts", response_model=AttendanceAlertList)
async def get_daily_alerts(
    operator_user_id: Annotated[UUID, Depends(require_attendance_operator)],
    requested_date: Annotated[date | None, Query(alias="date")] = None,
) -> AttendanceAlertList:
    day = requested_date or datetime.now(CASABLANCA_TIMEZONE).date()
    alerts = await evaluate_daily_attendance_alerts(
        day=day,
        operator_user_id=operator_user_id,
        grace_minutes=ALERT_GRACE_MINUTES,
    )
    return AttendanceAlertList(
        date=day,
        seuil_retard_minutes=ALERT_GRACE_MINUTES,
        alertes=alerts,
    )


@router.post("/alerts/{alert_id}/resolve", status_code=status.HTTP_204_NO_CONTENT)
async def resolve_daily_alert(
    alert_id: UUID,
    operator_user_id: Annotated[UUID, Depends(require_attendance_operator)],
) -> None:
    resolved = await resolve_attendance_alert(alert_id, operator_user_id)
    if not resolved:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="L’alerte est introuvable ou déjà traitée.",
        )


def _local_schedule_datetime(day: date, local_time: time) -> datetime:
    naive = datetime.combine(day, local_time)
    candidate = naive.replace(tzinfo=CASABLANCA_TIMEZONE, fold=0)
    round_trip = candidate.astimezone(UTC).astimezone(CASABLANCA_TIMEZONE)
    if round_trip.replace(tzinfo=None) != naive:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Cette heure locale n’existe pas en raison d’un changement d’heure.",
        )

    alternate = naive.replace(tzinfo=CASABLANCA_TIMEZONE, fold=1)
    if candidate.utcoffset() != alternate.utcoffset():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Cette heure locale est ambiguë en raison d’un changement d’heure.",
        )
    return candidate
