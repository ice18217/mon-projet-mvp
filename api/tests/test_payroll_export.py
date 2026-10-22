import asyncio
import csv
import io
from collections.abc import Generator
from datetime import UTC, date, datetime
from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import UUID

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.dependencies.auth import (
    require_authenticated_user,
    require_payroll_export_operator,
)
from app.main import app
from app.routers import payroll
from app.schemas.daily_attendance import AttendanceEvent
from app.schemas.payroll_export import (
    PayrollAttendancePerson,
    PayrollExportPerson,
)
from app.services import payroll_export, supabase
from app.services.attendance_calculation import local_day_bounds

OPERATOR_ID = UUID("20000000-0000-4000-8000-000000000002")
PERSONNEL_ID = UUID("30000000-0000-4000-8000-000000000003")
POINTAGE_ID = UUID("40000000-0000-4000-8000-000000000004")


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_payroll_export_requires_authentication(client: TestClient) -> None:
    response = client.get("/payroll/weekly-export?week_start=2026-10-05")
    assert response.status_code == 401


@pytest.mark.parametrize("role", ["rh", "finance"])
def test_payroll_export_allows_rh_and_finance_roles(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    role: str,
) -> None:
    async def authenticated_user() -> UUID:
        return OPERATOR_ID

    app.dependency_overrides[require_authenticated_user] = authenticated_user
    monkeypatch.setattr(
        supabase,
        "get_personnel_profile",
        AsyncMock(
            return_value={
                "id": str(OPERATOR_ID),
                "actif": True,
                "acces_approuve": True,
            }
        ),
    )
    monkeypatch.setattr(
        supabase,
        "get_personnel_roles",
        AsyncMock(return_value={role}),
    )
    export = AsyncMock(return_value=[])
    monkeypatch.setattr(payroll, "create_weekly_payroll_export", export)

    response = client.get("/payroll/weekly-export?week_start=2026-10-05")

    assert response.status_code == 200
    export.assert_awaited_once_with(date(2026, 10, 5))


def test_payroll_export_rejects_other_roles(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def authenticated_user() -> UUID:
        return OPERATOR_ID

    app.dependency_overrides[require_authenticated_user] = authenticated_user
    monkeypatch.setattr(
        supabase,
        "get_personnel_profile",
        AsyncMock(
            return_value={
                "id": str(OPERATOR_ID),
                "actif": True,
                "acces_approuve": True,
            }
        ),
    )
    monkeypatch.setattr(
        supabase,
        "get_personnel_roles",
        AsyncMock(return_value={"scolarite"}),
    )

    response = client.get("/payroll/weekly-export?week_start=2026-10-05")

    assert response.status_code == 403


@pytest.mark.parametrize("week_start", ["2026-10-06", "2026-10-12", "2099-01-05"])
def test_payroll_export_rejects_invalid_or_unfinished_weeks(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    week_start: str,
) -> None:
    app.dependency_overrides[require_payroll_export_operator] = lambda: OPERATOR_ID
    export = AsyncMock()
    monkeypatch.setattr(payroll, "create_weekly_payroll_export", export)

    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz: object = None) -> datetime:
            return datetime(2026, 10, 15, 11, 0, tzinfo=UTC).astimezone(tz)

    monkeypatch.setattr(payroll, "datetime", FrozenDateTime)
    response = client.get(
        f"/payroll/weekly-export?week_start={week_start}"
    )

    assert response.status_code == 422
    export.assert_not_awaited()


def test_payroll_export_returns_french_excel_csv(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app.dependency_overrides[require_payroll_export_operator] = lambda: OPERATOR_ID
    export = AsyncMock(
        return_value=[
            PayrollExportPerson(
                id_personnel=PERSONNEL_ID,
                nom="=SUM(A1:A2);Dupont",
                prenom="Zoé",
                heures=Decimal("4.25"),
                jours_complets=1,
                jours_a_revoir=2,
            )
        ]
    )
    monkeypatch.setattr(payroll, "create_weekly_payroll_export", export)

    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz: object = None) -> datetime:
            return datetime(2026, 10, 15, 11, 0, tzinfo=UTC).astimezone(tz)

    monkeypatch.setattr(payroll, "datetime", FrozenDateTime)
    response = client.get("/payroll/weekly-export?week_start=2026-10-05")

    assert response.status_code == 200
    assert response.headers["content-type"] == "text/csv; charset=utf-8"
    assert "heures-eigsi-2026-10-05_2026-10-11.csv" in response.headers[
        "content-disposition"
    ]
    assert response.content.startswith(b"\xef\xbb\xbf")
    rows = list(
        csv.reader(
            io.StringIO(response.content.decode("utf-8-sig")),
            delimiter=";",
        )
    )
    assert rows[0] == [
        "Identifiant personnel",
        "Nom",
        "Prénom",
        "Début de semaine",
        "Fin de semaine",
        "Heures admissibles",
        "Journées complètes retenues",
        "Journées à revoir",
    ]
    assert rows[1] == [
        str(PERSONNEL_ID),
        "'=SUM(A1:A2);Dupont",
        "Zoé",
        "2026-10-05",
        "2026-10-11",
        "4,25",
        "1",
        "2",
    ]


def test_weekly_export_includes_complete_days_and_excludes_other_days(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    person = PayrollAttendancePerson(
        id_personnel=PERSONNEL_ID,
        nom="Dupont",
        prenom="Zoé",
        pointages=[
            AttendanceEvent(
                date_heure=datetime.fromisoformat("2026-10-05T08:10:00+01:00"),
                type_pointage="entree",
            ),
            AttendanceEvent(
                date_heure=datetime.fromisoformat("2026-10-05T12:10:00+01:00"),
                type_pointage="sortie",
            ),
            AttendanceEvent(
                date_heure=datetime.fromisoformat("2026-10-06T08:00:00+01:00"),
                type_pointage="entree",
            ),
            AttendanceEvent(
                date_heure=datetime.fromisoformat("2026-10-06T10:00:00+01:00"),
                type_pointage="entree",
            ),
            AttendanceEvent(
                date_heure=datetime.fromisoformat("2026-10-07T08:00:00+01:00"),
                type_pointage="sortie",
            ),
        ],
    )
    query = AsyncMock(return_value=[person])
    monkeypatch.setattr(
        payroll_export,
        "get_payroll_attendance_data",
        query,
    )

    result = asyncio.run(
        payroll_export.create_weekly_payroll_export(date(2026, 10, 5))
    )

    query.assert_awaited_once_with(date(2026, 10, 5), date(2026, 10, 12))
    assert len(result) == 1
    assert result[0].heures == Decimal("4.00")
    assert result[0].jours_complets == 1
    assert result[0].jours_a_revoir == 2


def test_payroll_data_uses_effective_corrected_timestamps(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pointage_id = str(POINTAGE_ID)
    personnel_id = str(PERSONNEL_ID)
    request = AsyncMock(
        side_effect=[
            httpx.Response(
                200,
                json=[
                    {
                        "id": pointage_id,
                        "id_personnel": personnel_id,
                        "date_heure": "2026-10-05T07:00:00+00:00",
                        "type_pointage": "entree",
                    },
                    {
                        "id": "50000000-0000-4000-8000-000000000005",
                        "id_personnel": personnel_id,
                        "date_heure": "2026-10-05T11:00:00+00:00",
                        "type_pointage": "sortie",
                    },
                ],
            ),
            httpx.Response(
                200,
                json=[
                    {
                        "id": personnel_id,
                        "nom": "Dupont",
                        "prenom": "Zoé",
                    }
                ],
            ),
            httpx.Response(
                200,
                json=[
                    {
                        "id_pointage": pointage_id,
                        "revision": 1,
                        "date_correction": "2026-10-06T09:00:00+01:00",
                        "motif": "Correction de l’heure",
                        "ancienne_valeur": "2026-10-05T07:00:00+00:00",
                        "nouvelle_valeur": "2026-10-05T07:10:00+00:00",
                    }
                ],
            ),
        ]
    )
    monkeypatch.setattr(supabase, "_service_request", request)

    result = asyncio.run(
        supabase.get_payroll_attendance_data(
            date(2026, 10, 5),
            date(2026, 10, 12),
        )
    )

    assert len(result) == 1
    assert result[0].id_personnel == PERSONNEL_ID
    assert result[0].pointages[0].date_heure.isoformat() == (
        "2026-10-05T07:10:00+00:00"
    )
    pointage_params = request.await_args_list[0].kwargs["params"]
    start, _ = local_day_bounds(date(2026, 10, 5))
    end, _ = local_day_bounds(date(2026, 10, 12))
    assert ("date_heure", f"gte.{start.isoformat()}") in pointage_params
    assert ("date_heure", f"lt.{end.isoformat()}") in pointage_params


def test_payroll_data_rejects_truncated_week_query(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = AsyncMock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "id": str(POINTAGE_ID),
                    "id_personnel": str(PERSONNEL_ID),
                    "date_heure": "2026-10-05T07:00:00+00:00",
                    "type_pointage": "entree",
                }
            ]
            * 5000,
        )
    )
    monkeypatch.setattr(supabase, "_service_request", request)

    with pytest.raises(HTTPException) as error:
        asyncio.run(
            supabase.get_payroll_attendance_data(
                date(2026, 10, 5),
                date(2026, 10, 12),
            )
        )
    assert error.value.status_code == 502
    request.assert_awaited_once()
