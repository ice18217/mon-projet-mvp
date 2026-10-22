import csv
import io
from datetime import date, datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response

from app.dependencies.auth import require_payroll_export_operator
from app.services.attendance_calculation import CASABLANCA_TIMEZONE
from app.services.payroll_export import create_weekly_payroll_export

router = APIRouter(prefix="/payroll", tags=["payroll"])


@router.get("/weekly-export", response_class=Response)
async def download_weekly_payroll_export(
    _: Annotated[UUID, Depends(require_payroll_export_operator)],
    week_start: Annotated[date, Query()],
) -> Response:
    today = datetime.now(CASABLANCA_TIMEZONE).date()
    if (
        week_start > date.max - timedelta(days=6)
        or week_start.weekday() != 0
        or week_start + timedelta(days=6) >= today
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                "Choisissez un lundi correspondant à une semaine entièrement "
                "terminée en Africa/Casablanca."
            ),
        )

    week_end = week_start + timedelta(days=6)
    personnel = await create_weekly_payroll_export(week_start)
    output = io.StringIO(newline="")
    writer = csv.writer(
        output,
        delimiter=";",
        quoting=csv.QUOTE_MINIMAL,
        lineterminator="\r\n",
    )
    writer.writerow(
        [
            "Identifiant personnel",
            "Nom",
            "Prénom",
            "Début de semaine",
            "Fin de semaine",
            "Heures admissibles",
            "Journées complètes retenues",
            "Journées à revoir",
        ]
    )
    for person in personnel:
        hours = f"{person.heures:.2f}".replace(".", ",")
        writer.writerow(
            [
                str(person.id_personnel),
                _safe_spreadsheet_text(person.nom),
                _safe_spreadsheet_text(person.prenom),
                week_start.isoformat(),
                week_end.isoformat(),
                hours,
                person.jours_complets,
                person.jours_a_revoir,
            ]
        )

    content = "\ufeff" + output.getvalue()
    filename = (
        f"heures-eigsi-{week_start.isoformat()}_{week_end.isoformat()}.csv"
    )
    return Response(
        content=content.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _safe_spreadsheet_text(value: str) -> str:
    if value.lstrip(" \t\r\n")[:1] in {"=", "+", "-", "@", "\t", "\r"}:
        return f"'{value}"
    return value
