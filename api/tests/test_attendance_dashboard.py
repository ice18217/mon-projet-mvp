import asyncio
from collections.abc import Generator
from datetime import UTC, date, datetime
from unittest.mock import AsyncMock
from uuid import UUID

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.dependencies.auth import (
    require_attendance_operator,
    require_authenticated_user,
)
from app.main import app
from app.routers import attendance
from app.schemas.attendance_alerts import PersonnelOption
from app.schemas.attendance_dashboard import DashboardSchedule
from app.schemas.daily_attendance import AttendanceEvent
from app.services import supabase

OPERATOR_ID = UUID("20000000-0000-4000-8000-000000000002")
PRESENT_ID = UUID("30000000-0000-4000-8000-000000000003")
LATE_ID = UUID("40000000-0000-4000-8000-000000000004")
ABSENT_ID = UUID("50000000-0000-4000-8000-000000000005")
PENDING_ID = UUID("60000000-0000-4000-8000-000000000006")
UNSCHEDULED_ID = UUID("70000000-0000-4000-8000-000000000007")


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_dashboard_requires_authentication(client: TestClient) -> None:
    response = client.get("/attendance/dashboard")
    assert response.status_code == 401


def test_dashboard_rejects_non_operator(
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
        AsyncMock(return_value={"personnel"}),
    )

    response = client.get("/attendance/dashboard")
    assert response.status_code == 403


def test_dashboard_rejects_future_date(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app.dependency_overrides[require_attendance_operator] = lambda: OPERATOR_ID
    get_data = AsyncMock()
    monkeypatch.setattr(attendance, "get_attendance_dashboard_data", get_data)

    response = client.get("/attendance/dashboard?date=2099-01-01")

    assert response.status_code == 422
    get_data.assert_not_awaited()


def test_dashboard_calculates_presence_and_daily_hours(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app.dependency_overrides[require_attendance_operator] = lambda: OPERATOR_ID

    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz: object = None) -> datetime:
            return datetime(2026, 7, 15, 12, 0, tzinfo=UTC).astimezone(tz)

    day = date(2026, 7, 15)
    personnel = [
        PersonnelOption(
            id=person_id,
            nom=f"Nom {index}",
            prenom=f"Prénom {index}",
            email=f"user{index}@example.test",
        )
        for index, person_id in enumerate(
            [PRESENT_ID, LATE_ID, ABSENT_ID, PENDING_ID, UNSCHEDULED_ID]
        )
    ]
    schedules = [
        DashboardSchedule(
            id_personnel=person_id,
            debut=datetime.fromisoformat(f"2026-07-15T{start}:00+01:00"),
            fin=datetime.fromisoformat(f"2026-07-15T{end}:00+01:00"),
            type_activite="Travail",
        )
        for person_id, start, end in [
            (PRESENT_ID, "08", "17"),
            (LATE_ID, "08", "17"),
            (ABSENT_ID, "08", "11"),
            (PENDING_ID, "14", "17"),
        ]
    ]
    events = {
        PRESENT_ID: [
            AttendanceEvent(
                date_heure=datetime.fromisoformat("2026-07-15T07:05:00+00:00"),
                type_pointage="entree",
            ),
            AttendanceEvent(
                date_heure=datetime.fromisoformat("2026-07-15T11:00:00+00:00"),
                type_pointage="sortie",
            ),
        ],
        LATE_ID: [
            AttendanceEvent(
                date_heure=datetime.fromisoformat("2026-07-15T07:11:00+00:00"),
                type_pointage="entree",
            ),
            AttendanceEvent(
                date_heure=datetime.fromisoformat("2026-07-15T16:00:00+00:00"),
                type_pointage="sortie",
            ),
        ],
        UNSCHEDULED_ID: [
            AttendanceEvent(
                date_heure=datetime.fromisoformat("2026-07-15T07:00:00+00:00"),
                type_pointage="entree",
            ),
            AttendanceEvent(
                date_heure=datetime.fromisoformat("2026-07-15T11:00:00+00:00"),
                type_pointage="sortie",
            ),
        ],
    }
    monkeypatch.setattr(attendance, "datetime", FrozenDateTime)
    query = AsyncMock(return_value=(personnel, schedules, events))
    monkeypatch.setattr(attendance, "get_attendance_dashboard_data", query)

    response = client.get(f"/attendance/dashboard?date={day.isoformat()}")

    assert response.status_code == 200
    body = response.json()
    assert body["effectif"] == 5
    assert body["fuseau_horaire"] == "Africa/Casablanca"
    assert body["compteurs"] == {
        "present": 1,
        "retard": 1,
        "absent": 1,
        "en_attente": 1,
        "sans_horaire": 1,
    }
    rows = {row["id_personnel"]: row for row in body["personnel"]}
    assert rows[str(PRESENT_ID)]["statut_presence"] == "present"
    assert rows[str(PRESENT_ID)]["total_secondes"] == 3 * 60 * 60 + 55 * 60
    assert rows[str(LATE_ID)]["statut_presence"] == "retard"
    assert rows[str(ABSENT_ID)]["statut_presence"] == "absent"
    assert rows[str(PENDING_ID)]["statut_presence"] == "en_attente"
    assert rows[str(UNSCHEDULED_ID)]["statut_presence"] == "sans_horaire"
    assert rows[str(UNSCHEDULED_ID)]["total_secondes"] == 4 * 60 * 60


def test_dashboard_service_groups_personnel_schedules_and_attendance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    person_id = str(PRESENT_ID)
    request = AsyncMock(
        side_effect=[
            httpx.Response(
                200,
                json=[
                    {
                        "id": person_id,
                        "nom": "Nom",
                        "prenom": "Prénom",
                        "email": "person@example.test",
                    }
                ],
            ),
            httpx.Response(
                200,
                json=[
                    {
                        "id_personnel": person_id,
                        "debut": "2026-07-15T07:00:00+00:00",
                        "fin": "2026-07-15T16:00:00+00:00",
                        "type_activite": "Travail",
                    }
                ],
            ),
            httpx.Response(
                200,
                json=[
                    {
                        "id": "80000000-0000-4000-8000-000000000008",
                        "id_personnel": person_id,
                        "date_heure": "2026-07-15T07:05:00+00:00",
                        "type_pointage": "entree",
                    }
                ],
            ),
            httpx.Response(
                200,
                json=[
                    {
                        "id_pointage": "80000000-0000-4000-8000-000000000008",
                        "revision": 1,
                        "date_correction": "2026-07-15T09:00:00+00:00",
                        "motif": "Correction de l’heure",
                        "ancienne_valeur": "2026-07-15T07:05:00+00:00",
                        "nouvelle_valeur": "2026-07-15T07:15:00+00:00",
                    }
                ],
            ),
        ],
    )
    monkeypatch.setattr(supabase, "_service_request", request)

    personnel, schedules, events = asyncio.run(
        supabase.get_attendance_dashboard_data(date(2026, 7, 15))
    )

    assert [person.id for person in personnel] == [PRESENT_ID]
    assert len(schedules) == 1
    assert schedules[0].debut == datetime.fromisoformat(
        "2026-07-15T07:00:00+00:00"
    )
    assert len(events[PRESENT_ID]) == 1
    assert events[PRESENT_ID][0].date_heure.isoformat() == (
        "2026-07-15T07:15:00+00:00"
    )
    assert request.await_count == 4
    attendance_params = dict(request.await_args_list[2].kwargs["params"])
    assert attendance_params["date_heure"] == "lt.2026-07-16T00:00:00+01:00"


def test_dashboard_service_rejects_malformed_data(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = AsyncMock(
        side_effect=[
            httpx.Response(
                200,
                json=[
                    {
                        "id": str(PRESENT_ID),
                        "nom": "Nom",
                        "prenom": "Prénom",
                        "email": "person@example.test",
                    }
                ],
            ),
            httpx.Response(
                200,
                json=[
                    {
                        "id_personnel": str(PRESENT_ID),
                        "debut": "invalid",
                        "fin": "2026-07-15T16:00:00+00:00",
                        "type_activite": "Travail",
                    }
                ],
            ),
            httpx.Response(200, json=[]),
        ],
    )
    monkeypatch.setattr(supabase, "_service_request", request)

    with pytest.raises(HTTPException) as error:
        asyncio.run(supabase.get_attendance_dashboard_data(date(2026, 7, 15)))

    assert error.value.status_code == 502


def test_dashboard_service_rejects_truncated_query_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = AsyncMock(
        side_effect=[
            httpx.Response(200, json=[]),
            httpx.Response(200, json=[]),
            httpx.Response(
                200,
                json=[
                    {
                        "id_personnel": str(PRESENT_ID),
                        "date_heure": "2026-07-15T07:05:00+00:00",
                        "type_pointage": "entree",
                    }
                ]
                * 1000,
            ),
        ],
    )
    monkeypatch.setattr(supabase, "_service_request", request)

    with pytest.raises(HTTPException) as error:
        asyncio.run(supabase.get_attendance_dashboard_data(date(2026, 7, 15)))

    assert error.value.status_code == 422
