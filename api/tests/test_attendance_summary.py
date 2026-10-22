import asyncio
from collections.abc import Generator
from datetime import date, datetime
from unittest.mock import AsyncMock
from uuid import UUID

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.dependencies.auth import (
    require_approved_personnel,
    require_authenticated_user,
)
from app.main import app
from app.routers import attendance
from app.schemas.daily_attendance import AttendanceEvent
from app.schemas.qr_attendance import AttendanceEventType
from app.services import supabase
from app.services.attendance_calculation import local_day_bounds

PERSONNEL_ID = UUID("50000000-0000-4000-8000-000000000005")


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_daily_summary_requires_authentication(client: TestClient) -> None:
    response = client.get("/attendance/me/daily-summary")

    assert response.status_code == 401


def test_daily_summary_returns_calculated_personal_events(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    app.dependency_overrides[require_approved_personnel] = lambda: PERSONNEL_ID
    query = AsyncMock(
        return_value=[
            AttendanceEvent(
                date_heure=datetime.fromisoformat("2026-10-15T07:00:00+00:00"),
                type_pointage=AttendanceEventType.ENTREE,
            ),
            AttendanceEvent(
                date_heure=datetime.fromisoformat("2026-10-15T15:00:00+00:00"),
                type_pointage=AttendanceEventType.SORTIE,
            ),
        ]
    )
    monkeypatch.setattr(attendance, "get_personnel_daily_attendance", query)

    response = client.get("/attendance/me/daily-summary?date=2026-10-15")

    assert response.status_code == 200
    assert response.json()["date"] == "2026-10-15"
    assert response.json()["fuseau_horaire"] == "Africa/Casablanca"
    assert response.json()["status"] == "complete"
    assert response.json()["total_secondes"] == 8 * 60 * 60
    query.assert_awaited_once_with(PERSONNEL_ID, date(2026, 10, 15))


@pytest.mark.parametrize("requested_date", ["not-a-date", "2026-02-30"])
def test_daily_summary_rejects_invalid_date(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    requested_date: str,
) -> None:
    app.dependency_overrides[require_approved_personnel] = lambda: PERSONNEL_ID
    query = AsyncMock()
    monkeypatch.setattr(attendance, "get_personnel_daily_attendance", query)

    response = client.get(
        "/attendance/me/daily-summary",
        params={"date": requested_date},
    )

    assert response.status_code == 422
    query.assert_not_awaited()


def test_daily_summary_rejects_user_without_personnel_role(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def authenticated_user() -> UUID:
        return PERSONNEL_ID

    app.dependency_overrides[require_authenticated_user] = authenticated_user
    monkeypatch.setattr(
        supabase,
        "get_personnel_profile",
        AsyncMock(
            return_value={
                "id": str(PERSONNEL_ID),
                "actif": True,
                "acces_approuve": True,
            }
        ),
    )
    monkeypatch.setattr(
        supabase, "get_personnel_roles", AsyncMock(return_value={"finance"})
    )

    response = client.get("/attendance/me/daily-summary")

    assert response.status_code == 403


def test_daily_attendance_query_is_scoped_and_uses_local_day_bounds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = AsyncMock(
        side_effect=[
            httpx.Response(
                200,
                json=[
                    {
                        "id": "30000000-0000-4000-8000-000000000003",
                        "date_heure": "2026-10-15T07:00:00+00:00",
                        "type_pointage": "entree",
                    }
                ],
            ),
            httpx.Response(
                200,
                json=[
                    {
                        "id_pointage": "30000000-0000-4000-8000-000000000003",
                        "revision": 1,
                        "date_correction": "2026-10-15T09:00:00+01:00",
                        "motif": "Correction de l’heure",
                        "ancienne_valeur": "2026-10-15T07:00:00+00:00",
                        "nouvelle_valeur": "2026-10-15T07:10:00+00:00",
                    }
                ],
            ),
        ]
    )
    monkeypatch.setattr(supabase, "_service_request", request)

    events = asyncio.run(
        supabase.get_personnel_daily_attendance(
            PERSONNEL_ID,
            date(2026, 10, 15),
        )
    )

    assert len(events) == 1
    assert events[0].date_heure.isoformat() == "2026-10-15T07:10:00+00:00"
    assert request.await_args_list[0].args == ("GET", "/rest/v1/pointage")
    params = dict(request.await_args_list[0].kwargs["params"])
    assert params["id_personnel"] == f"eq.{PERSONNEL_ID}"
    start, end = local_day_bounds(date(2026, 10, 15))
    assert params["date_heure"] == f"lt.{end.isoformat()}"
    assert (
        "date_heure",
        f"gte.{start.isoformat()}",
    ) in request.await_args_list[0].kwargs["params"]
    assert params["select"] == "id,date_heure,type_pointage"
    assert request.await_count == 2


def test_daily_attendance_query_rejects_malformed_supabase_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = AsyncMock(
        return_value=httpx.Response(200, json=[{"date_heure": "not-a-date"}])
    )
    monkeypatch.setattr(supabase, "_service_request", request)

    with pytest.raises(HTTPException) as error:
        asyncio.run(
            supabase.get_personnel_daily_attendance(
                PERSONNEL_ID,
                date(2026, 10, 15),
            )
        )

    assert error.value.status_code == 502


def test_daily_attendance_query_rejects_events_outside_requested_day(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, end = local_day_bounds(date(2026, 10, 15))
    request = AsyncMock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "date_heure": end.isoformat(),
                    "type_pointage": "entree",
                }
            ],
        )
    )
    monkeypatch.setattr(supabase, "_service_request", request)

    with pytest.raises(HTTPException) as error:
        asyncio.run(
            supabase.get_personnel_daily_attendance(
                PERSONNEL_ID,
                date(2026, 10, 15),
            )
        )

    assert error.value.status_code == 502
