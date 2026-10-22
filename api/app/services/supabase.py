import asyncio
import base64
import hashlib
import io
import logging
import re
import secrets
from collections import defaultdict
from datetime import UTC, date, datetime
from http import HTTPStatus
from typing import TypedDict
from uuid import UUID

import httpx
import qrcode
from fastapi import HTTPException, status
from pydantic import ValidationError

from app.core.config import get_settings
from app.schemas.access import AssignableRole, PendingPersonnel
from app.schemas.attendance_alerts import (
    AttendanceAlert,
    PersonnelOption,
    ScheduleRecord,
)
from app.schemas.attendance_corrections import (
    AttendanceCorrectionHistoryEntry,
    AttendanceCorrectionRecord,
)
from app.schemas.attendance_dashboard import DashboardSchedule
from app.schemas.daily_attendance import AttendanceEvent
from app.schemas.payroll_export import PayrollAttendancePerson
from app.schemas.qr_attendance import AttendanceEventType, QRScanResult
from app.services.attendance_calculation import (
    CASABLANCA_TIMEZONE,
    local_day_bounds,
)

logger = logging.getLogger(__name__)
REQUEST_TIMEOUT = 10.0
QR_PAYLOAD_PATTERN = re.compile(
    r"^eigsi-attendance:v1:"
    r"(?P<personnel_id>[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-"
    r"[89ab][0-9a-f]{3}-[0-9a-f]{12}):"
    r"(?P<token>[A-Za-z0-9_-]{43})$",
    re.IGNORECASE,
)


class PersonnelProfile(TypedDict):
    id: str
    actif: bool
    acces_approuve: bool


def _service_headers() -> dict[str, str]:
    settings = get_settings()
    return {
        "apikey": settings.supabase_service_role_key,
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
        "Content-Type": "application/json",
    }


async def verify_access_token(access_token: str) -> UUID:
    settings = get_settings()
    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            response = await client.get(
                f"{settings.supabase_url}/auth/v1/user",
                headers={
                    "apikey": settings.supabase_anon_key,
                    "Authorization": f"Bearer {access_token}",
                },
            )
    except httpx.RequestError as exc:
        logger.exception("Supabase Auth is unavailable while verifying a token.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Le service d'authentification est indisponible.",
        ) from exc

    if response.status_code in (401, 403):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session invalide ou expirée.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if response.is_error:
        logger.error("Supabase Auth token verification failed: %s", response.status_code)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="La vérification de la session a échoué.",
        )

    try:
        return UUID(response.json()["id"])
    except (KeyError, TypeError, ValueError) as exc:
        logger.exception("Supabase Auth returned an invalid user response.")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Réponse invalide du service d'authentification.",
        ) from exc


async def _service_request(
    method: str,
    path: str,
    *,
    params: list[tuple[str, str]] | None = None,
    json: dict[str, object] | None = None,
    map_qr_errors: bool = False,
    map_schedule_errors: bool = False,
    map_correction_errors: bool = False,
) -> httpx.Response:
    settings = get_settings()
    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            response = await client.request(
                method,
                f"{settings.supabase_url}{path}",
                headers=_service_headers(),
                params=params,
                json=json,
            )
    except httpx.RequestError as exc:
        logger.exception("Supabase database API is unavailable.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Le service de données est indisponible.",
        ) from exc

    if response.is_error:
        logger.error(
            "Supabase service request %s %s failed: %s",
            method,
            path,
            response.status_code,
        )
        if map_qr_errors and response.status_code in (400, 403):
            try:
                error_body = response.json()
            except ValueError:
                error_body = None
            if isinstance(error_body, dict):
                error_code = error_body.get("code")
                if error_code == "22023":
                    raise HTTPException(
                        status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
                        detail="Le QR est invalide ou a été révoqué.",
                    )
                if error_code == "42501":
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Le compte n’est plus autorisé à effectuer ce pointage.",
                    )
        if map_schedule_errors and response.status_code in (400, 403):
            try:
                error_body = response.json()
            except ValueError:
                error_body = None
            if isinstance(error_body, dict):
                error_code = error_body.get("code")
                if error_code == "22023":
                    raise HTTPException(
                        status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
                        detail="Les données d’horaire ou d’alerte sont invalides.",
                    )
                if error_code == "42501":
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Un rôle RH ou Scolarité actif est requis.",
                    )
        if map_correction_errors and response.status_code in (400, 403, 404):
            try:
                error_body = response.json()
            except ValueError:
                error_body = None
            if isinstance(error_body, dict):
                error_code = error_body.get("code")
                if error_code == "22023":
                    raise HTTPException(
                        status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
                        detail=(
                            "L’heure doit rester dans la même journée locale "
                            "et être différente de l’heure effective."
                        ),
                    )
                if error_code == "42501":
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Un rôle RH ou Scolarité actif est requis.",
                    )
                if error_code == "P0002":
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Le pointage à corriger n’existe pas.",
                    )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="L'opération sur les accès a échoué.",
        )
    return response


async def get_personnel_profile(user_id: UUID) -> PersonnelProfile | None:
    response = await _service_request(
        "GET",
        "/rest/v1/personnel",
        params=[
            ("auth_user_id", f"eq.{user_id}"),
            ("select", "id,actif,acces_approuve"),
            ("limit", "1"),
        ],
    )
    rows = response.json()
    if not isinstance(rows, list) or not rows:
        return None
    row = rows[0]
    if not isinstance(row, dict):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Réponse invalide du service de données.",
        )
    if (
        not isinstance(row.get("id"), str)
        or not isinstance(row.get("actif"), bool)
        or not isinstance(row.get("acces_approuve"), bool)
    ):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Réponse invalide du service de données.",
        )
    return {
        "id": row["id"],
        "actif": row["actif"],
        "acces_approuve": row["acces_approuve"],
    }


async def get_personnel_roles(personnel_id: UUID) -> set[str]:
    response = await _service_request(
        "GET",
        "/rest/v1/acces_utilisateur",
        params=[
            ("id_personnel", f"eq.{personnel_id}"),
            ("select", "role,date_debut,date_fin"),
        ],
    )
    rows = response.json()
    if not isinstance(rows, list):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Réponse invalide du service de données.",
        )

    now = datetime.now(UTC)
    active_roles: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        try:
            starts_at = datetime.fromisoformat(
                row["date_debut"].replace("Z", "+00:00")  # noqa: FURB162
            )
            ends_at = (
                datetime.fromisoformat(
                    row["date_fin"].replace("Z", "+00:00")  # noqa: FURB162
                )
                if row["date_fin"]
                else None
            )
        except (AttributeError, KeyError, TypeError, ValueError):
            logger.exception("Supabase returned an invalid access-role record.")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Réponse invalide du service de données.",
            )

        if starts_at <= now and (ends_at is None or ends_at > now):
            active_roles.add(row["role"])
    return active_roles


async def list_pending_personnel() -> list[PendingPersonnel]:
    response = await _service_request(
        "GET",
        "/rest/v1/personnel",
        params=[
            ("actif", "eq.true"),
            ("acces_approuve", "eq.false"),
            ("select", "id,nom,prenom,email,type,created_at"),
            ("order", "created_at.asc"),
        ],
    )
    rows = response.json()
    if not isinstance(rows, list):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Réponse invalide du service de données.",
        )
    try:
        return [PendingPersonnel.model_validate(row) for row in rows]
    except ValidationError as exc:
        logger.exception("Supabase returned an invalid pending-personnel record.")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Réponse invalide du service de données.",
        ) from exc


async def approve_personnel_access(
    personnel_id: UUID, roles: list[AssignableRole]
) -> None:
    await _service_request(
        "POST",
        "/rest/v1/rpc/approve_personnel_access",
        json={
            "target_personnel": str(personnel_id),
            "approved_roles": [role.value for role in roles],
        },
    )


async def get_qr_credential_status(personnel_id: UUID) -> bool:
    response = await _service_request(
        "GET",
        "/rest/v1/personnel_qr_credential",
        params=[
            ("id_personnel", f"eq.{personnel_id}"),
            ("select", "id_personnel,revoked_at"),
            ("limit", "1"),
        ],
    )
    rows = response.json()
    if not isinstance(rows, list):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Réponse invalide du service de données.",
        )
    if not rows:
        return False
    row = rows[0]
    if not isinstance(row, dict) or "revoked_at" not in row:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Réponse invalide du service de données.",
        )
    return row["revoked_at"] is None


async def issue_personnel_qr(personnel_id: UUID) -> str:
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode("ascii")).hexdigest()
    await _service_request(
        "POST",
        "/rest/v1/rpc/rotate_personnel_qr_credential",
        json={
            "target_personnel": str(personnel_id),
            "new_token_hash": token_hash,
        },
    )

    payload = f"eigsi-attendance:v1:{personnel_id}:{token}"
    image = qrcode.make(payload)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


async def record_qr_attendance(
    *,
    payload: str,
    type_pointage: AttendanceEventType,
    idempotency_key: UUID,
    operator_user_id: UUID,
) -> QRScanResult:
    match = QR_PAYLOAD_PATTERN.fullmatch(payload)
    if match is None:
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            detail="Le format du QR est invalide.",
        )

    personnel_id = UUID(match.group("personnel_id"))
    token_hash = hashlib.sha256(match.group("token").encode("ascii")).hexdigest()
    response = await _service_request(
        "POST",
        "/rest/v1/rpc/record_qr_attendance",
        json={
            "target_personnel": str(personnel_id),
            "presented_token_hash": token_hash,
            "selected_event_type": type_pointage.value,
            "request_id": str(idempotency_key),
            "operator_user_id": str(operator_user_id),
        },
        map_qr_errors=True,
    )
    rows = response.json()
    if not isinstance(rows, list) or len(rows) != 1:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Réponse invalide du service de pointage.",
        )
    try:
        return QRScanResult.model_validate(rows[0])
    except ValidationError as exc:
        logger.exception("Supabase returned an invalid attendance record.")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Réponse invalide du service de pointage.",
        ) from exc


async def _get_effective_attendance_corrections(
    pointage_rows: list[dict[str, object]],
) -> dict[UUID, tuple[datetime, list[AttendanceCorrectionHistoryEntry]]]:
    if not pointage_rows:
        return {}

    try:
        original_by_id = {
            UUID(row["id"]): datetime.fromisoformat(
                row["date_heure"]
            )
            for row in pointage_rows
        }
        correction_rows: list[dict[str, object]] = []
        pointage_ids = list(original_by_id)
        for offset in range(0, len(pointage_ids), 100):
            batch_ids = pointage_ids[offset : offset + 100]
            response = await _service_request(
                "GET",
                "/rest/v1/correction_pointage",
                params=[
                    (
                        "id_pointage",
                        f"in.({','.join(str(pointage_id) for pointage_id in batch_ids)})",
                    ),
                    (
                        "select",
                        (
                            "id_pointage,revision,date_correction,motif,"
                            "ancienne_valeur,nouvelle_valeur"
                        ),
                    ),
                    ("order", "id_pointage.asc,revision.asc"),
                    ("limit", "5000"),
                ],
            )
            batch_rows = response.json()
            if not isinstance(batch_rows, list) or len(batch_rows) >= 5000:
                raise ValueError("Correction history is invalid or too large.")
            correction_rows.extend(batch_rows)

        history_by_id: dict[
            UUID, list[AttendanceCorrectionHistoryEntry]
        ] = defaultdict(list)
        effective_by_id = dict(original_by_id)
        for row in sorted(
            correction_rows,
            key=lambda item: (item["id_pointage"], item["revision"]),
        ):
            pointage_id = UUID(row["id_pointage"])
            original_timestamp = original_by_id.get(pointage_id)
            if original_timestamp is None:
                raise ValueError("Correction does not match requested attendance.")
            entry = AttendanceCorrectionHistoryEntry.model_validate(row)
            current = effective_by_id[pointage_id]
            if (
                entry.ancienne_valeur != current
                or entry.nouvelle_valeur == current
                or entry.nouvelle_valeur.astimezone(CASABLANCA_TIMEZONE).date()
                != original_timestamp.astimezone(CASABLANCA_TIMEZONE).date()
            ):
                raise ValueError("Correction history is inconsistent.")
            history_by_id[pointage_id].append(entry)
            effective_by_id[pointage_id] = entry.nouvelle_valeur
    except (
        AttributeError,
        KeyError,
        TypeError,
        ValueError,
        ValidationError,
    ) as exc:
        logger.exception("Supabase returned invalid attendance corrections.")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="L’historique des corrections est invalide.",
        ) from exc

    return {
        pointage_id: (effective_by_id[pointage_id], history)
        for pointage_id, history in history_by_id.items()
    }


async def get_payroll_attendance_data(
    period_start: date,
    period_end_exclusive: date,
) -> list[PayrollAttendancePerson]:
    start, _ = local_day_bounds(period_start)
    end, _ = local_day_bounds(period_end_exclusive)
    pointage_response = await _service_request(
        "GET",
        "/rest/v1/pointage",
        params=[
            ("date_heure", f"gte.{start.isoformat()}"),
            ("date_heure", f"lt.{end.isoformat()}"),
            ("select", "id,id_personnel,date_heure,type_pointage"),
            ("order", "id_personnel.asc,date_heure.asc"),
            ("limit", "5000"),
        ],
    )
    try:
        pointage_rows = pointage_response.json()
        if not isinstance(pointage_rows, list) or len(pointage_rows) >= 5000:
            raise ValueError("Weekly attendance data is invalid or too large.")
        if not pointage_rows:
            return []

        personnel_response = await _service_request(
            "GET",
            "/rest/v1/personnel",
            params=[
                ("select", "id,nom,prenom"),
                ("limit", "1000"),
            ],
        )
        personnel_rows = personnel_response.json()
        if not isinstance(personnel_rows, list) or len(personnel_rows) >= 1000:
            raise ValueError("Personnel data is invalid or too large.")
        personnel_by_id = {
            UUID(person["id"]): (person["nom"], person["prenom"])
            for person in personnel_rows
        }
        corrections_by_id = await _get_effective_attendance_corrections(
            pointage_rows
        )
        pointages_by_person: dict[UUID, list[AttendanceEvent]] = defaultdict(list)
        start_utc = start.astimezone(UTC)
        end_utc = end.astimezone(UTC)
        for row in pointage_rows:
            personnel_id = UUID(row["id_personnel"])
            if personnel_id not in personnel_by_id:
                raise ValueError("Attendance personnel record is missing.")
            original = datetime.fromisoformat(row["date_heure"])
            effective = corrections_by_id.get(UUID(row["id"]), (original, []))[0]
            event = AttendanceEvent(
                date_heure=effective,
                type_pointage=row["type_pointage"],
            )
            event_utc = event.date_heure.astimezone(UTC)
            if not start_utc <= event_utc < end_utc:
                raise ValueError("Attendance event is outside the requested week.")
            pointages_by_person[personnel_id].append(event)

        return [
            PayrollAttendancePerson(
                id_personnel=personnel_id,
                nom=personnel_by_id[personnel_id][0],
                prenom=personnel_by_id[personnel_id][1],
                pointages=events,
            )
            for personnel_id, events in sorted(
                pointages_by_person.items(),
                key=lambda item: (
                    personnel_by_id[item[0]][0].casefold(),
                    personnel_by_id[item[0]][1].casefold(),
                    str(item[0]),
                ),
            )
        ]
    except (
        AttributeError,
        KeyError,
        TypeError,
        ValueError,
        ValidationError,
    ) as exc:
        logger.exception("Supabase returned invalid weekly payroll data.")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Les pointages de la période sont invalides.",
        ) from exc


async def get_personnel_daily_attendance(
    personnel_id: UUID,
    day: date,
) -> list[AttendanceEvent]:
    start, end = local_day_bounds(day)
    response = await _service_request(
        "GET",
        "/rest/v1/pointage",
        params=[
            ("id_personnel", f"eq.{personnel_id}"),
            ("date_heure", f"gte.{start.isoformat()}"),
            ("date_heure", f"lt.{end.isoformat()}"),
            ("select", "id,date_heure,type_pointage"),
            ("order", "date_heure.asc"),
            ("limit", "1000"),
        ],
    )
    try:
        rows = response.json()
    except ValueError as exc:
        logger.exception("Supabase returned invalid attendance JSON.")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Réponse invalide du service de pointage.",
        ) from exc

    if not isinstance(rows, list):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Réponse invalide du service de pointage.",
        )
    try:
        correction_by_pointage = await _get_effective_attendance_corrections(
            rows
        )
        events = [
            AttendanceEvent(
                date_heure=correction_by_pointage.get(
                    UUID(row["id"]), (None, [])
                )[0]
                or datetime.fromisoformat(
                    row["date_heure"]
                ),
                type_pointage=row["type_pointage"],
            )
            for row in rows
        ]
    except (
        AttributeError,
        KeyError,
        TypeError,
        ValueError,
        ValidationError,
    ) as exc:
        logger.exception("Supabase returned invalid attendance data.")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Réponse invalide du service de pointage.",
        ) from exc

    if len(events) == 1000:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                "La journée contient trop de pointages pour un calcul fiable. "
                "Contactez l’administration."
            ),
        )

    start_utc = start.astimezone(UTC)
    end_utc = end.astimezone(UTC)
    if any(
        not start_utc <= event.date_heure.astimezone(UTC) < end_utc
        for event in events
    ):
        logger.error("Supabase returned attendance outside the requested local day.")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Réponse invalide du service de pointage.",
        )
    return events


async def get_schedule_overview(
    day: date,
) -> tuple[list[PersonnelOption], list[ScheduleRecord]]:
    personnel_response = await _service_request(
        "GET",
        "/rest/v1/personnel",
        params=[
            ("actif", "eq.true"),
            ("select", "id,nom,prenom,email"),
            ("order", "nom.asc,prenom.asc"),
            ("limit", "1000"),
        ],
    )
    schedule_response = await _service_request(
        "GET",
        "/rest/v1/emploi_du_temps",
        params=[
            ("date_jour_locale", f"eq.{day.isoformat()}"),
            ("select", "id,id_personnel,date_jour_locale,debut,fin,type_activite"),
            ("order", "debut.asc"),
            ("limit", "1000"),
        ],
    )
    try:
        personnel_rows = personnel_response.json()
        schedule_rows = schedule_response.json()
    except ValueError as exc:
        logger.exception("Supabase returned invalid schedule JSON.")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Réponse invalide du service d’horaires.",
        ) from exc

    if (
        not isinstance(personnel_rows, list)
        or not isinstance(schedule_rows, list)
        or len(personnel_rows) >= 1000
        or len(schedule_rows) >= 1000
    ):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Réponse invalide ou trop volumineuse du service d’horaires.",
        )

    try:
        personnel = [
            PersonnelOption.model_validate(row) for row in personnel_rows
        ]
        schedules: list[ScheduleRecord] = []
        personnel_by_id = {person.id: person for person in personnel}
        for row in schedule_rows:
            person_id = UUID(row["id_personnel"])
            person = personnel_by_id.get(person_id)
            if person is None:
                continue
            record = ScheduleRecord.model_validate(
                {
                    **row,
                    "date": row["date_jour_locale"],
                    "heure_debut": datetime.fromisoformat(
                        row["debut"]
                    ).astimezone(CASABLANCA_TIMEZONE).time().replace(tzinfo=None),
                    "heure_fin": datetime.fromisoformat(
                        row["fin"]
                    ).astimezone(CASABLANCA_TIMEZONE).time().replace(tzinfo=None),
                    "nom": person.nom,
                    "prenom": person.prenom,
                }
            )
            schedules.append(record)
    except (AttributeError, KeyError, TypeError, ValueError, ValidationError) as exc:
        logger.exception("Supabase returned an invalid schedule record.")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Réponse invalide du service d’horaires.",
        ) from exc
    return personnel, schedules


async def get_attendance_dashboard_data(
    day: date,
) -> tuple[
    list[PersonnelOption],
    list[DashboardSchedule],
    dict[UUID, list[AttendanceEvent]],
]:
    start, end = local_day_bounds(day)
    responses = await asyncio.gather(
        _service_request(
            "GET",
            "/rest/v1/personnel",
            params=[
                ("actif", "eq.true"),
                ("select", "id,nom,prenom,email"),
                ("order", "nom.asc,prenom.asc"),
                ("limit", "1000"),
            ],
        ),
        _service_request(
            "GET",
            "/rest/v1/emploi_du_temps",
            params=[
                ("date_jour_locale", f"eq.{day.isoformat()}"),
                ("select", "id_personnel,debut,fin,type_activite"),
                ("limit", "1000"),
            ],
        ),
        _service_request(
            "GET",
            "/rest/v1/pointage",
            params=[
                ("date_heure", f"gte.{start.isoformat()}"),
                ("date_heure", f"lt.{end.isoformat()}"),
                ("select", "id,id_personnel,date_heure,type_pointage"),
                ("order", "date_heure.asc"),
                ("limit", "1000"),
            ],
        ),
    )

    try:
        personnel_rows, schedule_rows, attendance_rows = (
            response.json() for response in responses
        )
    except ValueError as exc:
        logger.exception("Supabase returned invalid attendance-dashboard JSON.")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Réponse invalide du tableau de bord.",
        ) from exc

    if not all(
        isinstance(rows, list)
        for rows in (personnel_rows, schedule_rows, attendance_rows)
    ):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Réponse invalide du tableau de bord.",
        )
    if any(
        len(rows) >= 1000
        for rows in (personnel_rows, schedule_rows, attendance_rows)
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                "Le volume de données de cette journée dépasse la limite "
                "du tableau de bord. Réduisez le périmètre ou contactez "
                "l’administration."
            ),
        )

    try:
        personnel = [
            PersonnelOption.model_validate(row) for row in personnel_rows
        ]
        personnel_ids = {person.id for person in personnel}
        schedules = [
            DashboardSchedule.model_validate(row) for row in schedule_rows
        ]
        if any(
            schedule.id_personnel not in personnel_ids
            or schedule.debut >= schedule.fin
            or schedule.debut.astimezone(CASABLANCA_TIMEZONE).date() != day
            or schedule.fin.astimezone(CASABLANCA_TIMEZONE).date() != day
            for schedule in schedules
        ):
            raise ValueError("Supabase returned an out-of-scope schedule.")

        correction_by_pointage = await _get_effective_attendance_corrections(
            attendance_rows
        )
        events_by_person: dict[UUID, list[AttendanceEvent]] = defaultdict(list)
        start_utc = start.astimezone(UTC)
        end_utc = end.astimezone(UTC)
        for row in attendance_rows:
            personnel_id = UUID(row["id_personnel"])
            effective_timestamp = correction_by_pointage.get(
                UUID(row["id"]), (None, [])
            )[0]
            event = AttendanceEvent.model_validate(
                {
                    "date_heure": effective_timestamp or row["date_heure"],
                    "type_pointage": row["type_pointage"],
                }
            )
            timestamp_utc = event.date_heure.astimezone(UTC)
            if not start_utc <= timestamp_utc < end_utc:
                raise ValueError("Supabase returned an out-of-day event.")
            if personnel_id in personnel_ids:
                events_by_person[personnel_id].append(event)
    except (AttributeError, KeyError, TypeError, ValueError, ValidationError) as exc:
        logger.exception("Supabase returned an invalid dashboard record.")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Réponse invalide du tableau de bord.",
        ) from exc

    return personnel, schedules, dict(events_by_person)


async def get_attendance_correction_day(
    day: date,
) -> list[AttendanceCorrectionRecord]:
    start, end = local_day_bounds(day)
    pointages_response = await _service_request(
        "GET",
        "/rest/v1/pointage",
        params=[
            ("date_heure", f"gte.{start.isoformat()}"),
            ("date_heure", f"lt.{end.isoformat()}"),
            (
                "select",
                "id,id_personnel,date_heure,type_pointage",
            ),
            ("order", "date_heure.asc"),
            ("limit", "1000"),
        ],
    )
    personnel_response = await _service_request(
        "GET",
        "/rest/v1/personnel",
        params=[
            ("select", "id,nom,prenom"),
            ("limit", "1000"),
        ],
    )
    try:
        pointage_rows = pointages_response.json()
        personnel_rows = personnel_response.json()
        if (
            not isinstance(pointage_rows, list)
            or not isinstance(personnel_rows, list)
            or len(pointage_rows) >= 1000
            or len(personnel_rows) >= 1000
        ):
            raise ValueError("Attendance correction data is invalid or too large.")
        corrections_by_id = await _get_effective_attendance_corrections(
            pointage_rows
        )
        personnel_by_id = {
            UUID(person["id"]): (person["nom"], person["prenom"])
            for person in personnel_rows
        }
        records: list[AttendanceCorrectionRecord] = []
        for row in pointage_rows:
            pointage_id = UUID(row["id"])
            personnel_id = UUID(row["id_personnel"])
            personnel_name = personnel_by_id.get(personnel_id)
            if personnel_name is None:
                raise ValueError("Attendance personnel record is missing.")
            original = datetime.fromisoformat(
                row["date_heure"]
            )
            effective, history = corrections_by_id.get(
                pointage_id, (original, [])
            )
            records.append(
                AttendanceCorrectionRecord(
                    id_pointage=pointage_id,
                    id_personnel=personnel_id,
                    type_pointage=row["type_pointage"],
                    date_heure_originale=original,
                    date_heure_effective=effective,
                    historique=history,
                    nom=personnel_name[0],
                    prenom=personnel_name[1],
                )
            )
        return records
    except (
        AttributeError,
        KeyError,
        TypeError,
        ValueError,
        ValidationError,
    ) as exc:
        logger.exception("Supabase returned invalid attendance correction data.")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Réponse invalide des pointages à corriger.",
        ) from exc


async def correct_attendance_pointage(
    *,
    pointage_id: UUID,
    operator_user_id: UUID,
    corrected_at: datetime,
    reason: str,
) -> None:
    await _service_request(
        "POST",
        "/rest/v1/rpc/correct_attendance_pointage",
        json={
            "target_pointage": str(pointage_id),
            "operator_user_id": str(operator_user_id),
            "corrected_at": corrected_at.isoformat(),
            "correction_reason": reason,
        },
        map_correction_errors=True,
    )


async def upsert_personnel_schedule(
    *,
    personnel_id: UUID,
    operator_user_id: UUID,
    day: date,
    starts_at: datetime,
    ends_at: datetime,
    activity_type: str,
) -> None:
    await _service_request(
        "POST",
        "/rest/v1/rpc/upsert_personnel_schedule",
        json={
            "target_personnel": str(personnel_id),
            "operator_user_id": str(operator_user_id),
            "local_day": day.isoformat(),
            "starts_at": starts_at.isoformat(),
            "ends_at": ends_at.isoformat(),
            "activity_type": activity_type,
        },
        map_schedule_errors=True,
    )


async def evaluate_daily_attendance_alerts(
    *,
    day: date,
    operator_user_id: UUID,
    grace_minutes: int,
) -> list[AttendanceAlert]:
    response = await _service_request(
        "POST",
        "/rest/v1/rpc/evaluate_daily_attendance_alerts",
        json={
            "target_day": day.isoformat(),
            "operator_user_id": str(operator_user_id),
            "grace_minutes": grace_minutes,
        },
        map_schedule_errors=True,
    )
    try:
        rows = response.json()
    except ValueError as exc:
        logger.exception("Supabase returned invalid attendance-alert JSON.")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Réponse invalide du service d’alertes.",
        ) from exc
    if not isinstance(rows, list) or len(rows) >= 1000:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Réponse invalide ou trop volumineuse du service d’alertes.",
        )
    try:
        return [AttendanceAlert.model_validate(row) for row in rows]
    except ValidationError as exc:
        logger.exception("Supabase returned an invalid attendance alert.")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Réponse invalide du service d’alertes.",
        ) from exc


async def resolve_attendance_alert(
    alert_id: UUID,
    operator_user_id: UUID,
) -> bool:
    response = await _service_request(
        "POST",
        "/rest/v1/rpc/resolve_attendance_alert",
        json={
            "target_alert": str(alert_id),
            "operator_user_id": str(operator_user_id),
        },
        map_schedule_errors=True,
    )
    result = response.json()
    if not isinstance(result, bool):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Réponse invalide du service d’alertes.",
        )
    return result
