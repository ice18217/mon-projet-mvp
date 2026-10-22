import asyncio
from collections.abc import Generator
from datetime import date, time, timedelta
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
from app.schemas.attendance_alerts import ScheduleInput
from app.services import supabase

PERSONNEL_ID = UUID("10000000-0000-4000-8000-000000000001")
OPERATOR_ID = UUID("20000000-0000-4000-8000-000000000002")
SCHEDULE_ID = UUID("30000000-0000-4000-8000-000000000003")
ALERT_ID = UUID("40000000-0000-4000-8000-000000000004")


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_schedules_require_attendance_operator(client: TestClient) -> None:
    response = client.get("/attendance/schedules")
    assert response.status_code == 401


@pytest.mark.parametrize("roles", [{"personnel"}, {"finance"}, set()])
def test_non_rh_user_cannot_manage_schedules(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    roles: set[str],
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
    monkeypatch.setattr(supabase, "get_personnel_roles", AsyncMock(return_value=roles))

    response = client.get("/attendance/schedules")
    assert response.status_code == 403


def test_schedule_overview_uses_requested_day_and_operator(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    app.dependency_overrides[require_attendance_operator] = lambda: OPERATOR_ID
    query = AsyncMock(return_value=([], []))
    monkeypatch.setattr(attendance, "get_schedule_overview", query)

    response = client.get("/attendance/schedules?date=2026-10-15")

    assert response.status_code == 200
    assert response.json() == {
        "date": "2026-10-15",
        "personnel": [],
        "horaires": [],
    }
    query.assert_awaited_once_with(date(2026, 10, 15))


def test_schedule_input_converts_casablanca_local_times_to_utc(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    app.dependency_overrides[require_attendance_operator] = lambda: OPERATOR_ID
    save = AsyncMock()
    monkeypatch.setattr(attendance, "upsert_personnel_schedule", save)

    response = client.post(
        "/attendance/schedules",
        json={
            "id_personnel": str(PERSONNEL_ID),
            "date": "2026-07-15",
            "heure_debut": "08:00",
            "heure_fin": "17:00",
            "type_activite": "Travail",
        },
    )

    assert response.status_code == 204
    kwargs = save.await_args.kwargs
    assert kwargs["personnel_id"] == PERSONNEL_ID
    assert kwargs["operator_user_id"] == OPERATOR_ID
    assert kwargs["day"] == date(2026, 7, 15)
    assert kwargs["starts_at"].utcoffset() == timedelta(hours=1)
    assert kwargs["starts_at"].hour == 8
    assert kwargs["ends_at"].hour == 17


def test_schedule_rejects_a_slot_crossing_midnight(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    app.dependency_overrides[require_attendance_operator] = lambda: OPERATOR_ID
    save = AsyncMock()
    monkeypatch.setattr(attendance, "upsert_personnel_schedule", save)

    response = client.post(
        "/attendance/schedules",
        json={
            "id_personnel": str(PERSONNEL_ID),
            "date": "2026-10-15",
            "heure_debut": "22:00",
            "heure_fin": "02:00",
            "type_activite": "Travail",
        },
    )

    assert response.status_code == 422
    save.assert_not_awaited()


def test_schedule_rejects_nonexistent_casablanca_local_time(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    app.dependency_overrides[require_attendance_operator] = lambda: OPERATOR_ID
    save = AsyncMock()
    monkeypatch.setattr(attendance, "upsert_personnel_schedule", save)

    response = client.post(
        "/attendance/schedules",
        json={
            "id_personnel": str(PERSONNEL_ID),
            "date": "2026-03-22",
            "heure_debut": "02:30",
            "heure_fin": "04:00",
            "type_activite": "Travail",
        },
    )

    assert response.status_code == 422
    save.assert_not_awaited()


def test_schedule_model_rejects_blank_activity_and_seconds() -> None:
    common = {
        "id_personnel": PERSONNEL_ID,
        "date": date(2026, 10, 15),
        "heure_debut": time(8, 0),
        "heure_fin": time(17, 0),
    }

    with pytest.raises(ValueError):
        ScheduleInput(**common, type_activite="  ")
    with pytest.raises(ValueError):
        ScheduleInput(
            **{**common, "heure_debut": time(8, 0, 1)},
            type_activite="Travail",
        )


def test_alert_listing_applies_grace_period_for_operator(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    app.dependency_overrides[require_attendance_operator] = lambda: OPERATOR_ID
    evaluate = AsyncMock(return_value=[])
    monkeypatch.setattr(attendance, "evaluate_daily_attendance_alerts", evaluate)

    response = client.get("/attendance/alerts?date=2026-10-15")

    assert response.status_code == 200
    assert response.json() == {
        "date": "2026-10-15",
        "seuil_retard_minutes": 10,
        "alertes": [],
    }
    evaluate.assert_awaited_once_with(
        day=date(2026, 10, 15),
        operator_user_id=OPERATOR_ID,
        grace_minutes=10,
    )


def test_alert_resolution_is_restricted_to_operator(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    app.dependency_overrides[require_attendance_operator] = lambda: OPERATOR_ID
    resolve = AsyncMock(return_value=True)
    monkeypatch.setattr(attendance, "resolve_attendance_alert", resolve)

    response = client.post(f"/attendance/alerts/{ALERT_ID}/resolve")

    assert response.status_code == 204
    resolve.assert_awaited_once_with(ALERT_ID, OPERATOR_ID)


def test_alert_resolution_reports_missing_or_already_treated_alert(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    app.dependency_overrides[require_attendance_operator] = lambda: OPERATOR_ID
    monkeypatch.setattr(
        attendance, "resolve_attendance_alert", AsyncMock(return_value=False)
    )

    response = client.post(f"/attendance/alerts/{ALERT_ID}/resolve")

    assert response.status_code == 404


def test_schedule_service_rejects_invalid_supabase_records(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        supabase,
        "_service_request",
        AsyncMock(
            side_effect=[
                httpx.Response(
                    200,
                    json=[
                        {
                            "id": str(PERSONNEL_ID),
                            "nom": "Test",
                            "prenom": "Agent",
                            "email": "agent@example.test",
                        }
                    ],
                ),
                httpx.Response(
                    200,
                    json=[
                        {
                            "id": str(SCHEDULE_ID),
                            "id_personnel": str(PERSONNEL_ID),
                            "date_jour_locale": "2026-10-15",
                            "debut": "invalid-date",
                            "fin": "2026-10-15T16:00:00+00:00",
                            "type_activite": "Travail",
                        }
                    ],
                ),
            ]
        ),
    )

    with pytest.raises(HTTPException) as error:
        asyncio.run(supabase.get_schedule_overview(date(2026, 10, 15)))

    assert error.value.status_code == 502


def test_schedule_service_maps_supabase_utc_times_to_casablanca(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        supabase,
        "_service_request",
        AsyncMock(
            side_effect=[
                httpx.Response(
                    200,
                    json=[
                        {
                            "id": str(PERSONNEL_ID),
                            "nom": "Test",
                            "prenom": "Agent",
                            "email": "agent@example.test",
                        }
                    ],
                ),
                httpx.Response(
                    200,
                    json=[
                        {
                            "id": str(SCHEDULE_ID),
                            "id_personnel": str(PERSONNEL_ID),
                            "date_jour_locale": "2026-07-15",
                            "debut": "2026-07-15T07:00:00+00:00",
                            "fin": "2026-07-15T16:00:00+00:00",
                            "type_activite": "Travail",
                        }
                    ],
                ),
            ]
        ),
    )

    _, schedules = asyncio.run(supabase.get_schedule_overview(date(2026, 7, 15)))

    assert len(schedules) == 1
    assert schedules[0].heure_debut == time(8, 0)
    assert schedules[0].heure_fin == time(17, 0)
    assert schedules[0].nom == "Test"
