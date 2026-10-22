import asyncio
from collections.abc import Generator
from datetime import UTC, date, datetime
from unittest.mock import AsyncMock
from uuid import UUID

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.dependencies.auth import (
    require_attendance_operator,
)
from app.main import app
from app.routers import attendance
from app.schemas.attendance_corrections import AttendanceCorrectionInput
from app.services import supabase

OPERATOR_ID = UUID("20000000-0000-4000-8000-000000000002")
POINTAGE_ID = UUID("30000000-0000-4000-8000-000000000003")


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_correction_input_rejects_blank_reason_and_seconds() -> None:
    with pytest.raises(ValidationError):
        AttendanceCorrectionInput.model_validate(
            {"date": "2026-10-15", "heure": "08:30", "motif": "   "}
        )
    with pytest.raises(ValidationError):
        AttendanceCorrectionInput.model_validate(
            {"date": "2026-10-15", "heure": "08:30:15", "motif": "Erreur de saisie"}
        )


def test_corrections_require_attendance_operator(client: TestClient) -> None:
    response = client.get("/attendance/corrections")
    assert response.status_code == 401


def test_corrections_list_returns_daily_pointages(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app.dependency_overrides[require_attendance_operator] = lambda: OPERATOR_ID
    pointages = AsyncMock(return_value=[])
    monkeypatch.setattr(attendance, "get_attendance_correction_day", pointages)

    response = client.get("/attendance/corrections?date=2026-10-15")

    assert response.status_code == 200
    assert response.json() == {
        "date": "2026-10-15",
        "fuseau_horaire": "Africa/Casablanca",
        "pointages": [],
    }
    pointages.assert_awaited_once_with(date(2026, 10, 15))


def test_correction_rejects_future_date(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app.dependency_overrides[require_attendance_operator] = lambda: OPERATOR_ID
    save = AsyncMock()
    monkeypatch.setattr(attendance, "correct_attendance_pointage", save)

    response = client.post(
        f"/attendance/corrections/{POINTAGE_ID}",
        json={
            "date": "2099-01-01",
            "heure": "08:30",
            "motif": "Correction justifiée",
        },
    )

    assert response.status_code == 422
    save.assert_not_awaited()


def test_correction_submits_casablanca_timestamp(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app.dependency_overrides[require_attendance_operator] = lambda: OPERATOR_ID
    save = AsyncMock()
    monkeypatch.setattr(attendance, "correct_attendance_pointage", save)

    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz: object = None) -> datetime:
            return datetime(2026, 10, 15, 11, 0, tzinfo=UTC).astimezone(tz)

    monkeypatch.setattr(attendance, "datetime", FrozenDateTime)
    response = client.post(
        f"/attendance/corrections/{POINTAGE_ID}",
        json={
            "date": "2026-10-15",
            "heure": "08:30",
            "motif": "Correction justifiée",
        },
    )

    assert response.status_code == 204
    save.assert_awaited_once()
    assert save.await_args.kwargs["pointage_id"] == POINTAGE_ID
    assert save.await_args.kwargs["operator_user_id"] == OPERATOR_ID
    assert (
        save.await_args.kwargs["corrected_at"]
        .astimezone(supabase.CASABLANCA_TIMEZONE)
        .strftime("%Y-%m-%dT%H:%M")
        == "2026-10-15T08:30"
    )


def test_effective_correction_history_uses_latest_audited_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = "2026-10-15T08:00:00+01:00"
    first = "2026-10-15T08:15:00+01:00"
    second = "2026-10-15T08:20:00+01:00"
    request = AsyncMock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "id_pointage": str(POINTAGE_ID),
                    "revision": 1,
                    "date_correction": "2026-10-15T09:00:00+01:00",
                    "motif": "Première correction",
                    "ancienne_valeur": original,
                    "nouvelle_valeur": first,
                },
                {
                    "id_pointage": str(POINTAGE_ID),
                    "revision": 2,
                    "date_correction": "2026-10-15T09:05:00+01:00",
                    "motif": "Correction suivante",
                    "ancienne_valeur": first,
                    "nouvelle_valeur": second,
                },
            ],
        )
    )
    monkeypatch.setattr(supabase, "_service_request", request)

    effective = asyncio.run(
        supabase._get_effective_attendance_corrections(
            [
                {
                    "id": str(POINTAGE_ID),
                    "date_heure": original,
                }
            ]
        )
    )

    assert effective[POINTAGE_ID][0].isoformat() == second
    assert [entry.revision for entry in effective[POINTAGE_ID][1]] == [1, 2]


def test_effective_correction_history_rejects_cross_day_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = AsyncMock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "id_pointage": str(POINTAGE_ID),
                    "revision": 1,
                    "date_correction": "2026-10-15T09:00:00+01:00",
                    "motif": "Correction invalide",
                    "ancienne_valeur": "2026-10-15T08:00:00+01:00",
                    "nouvelle_valeur": "2026-10-16T08:00:00+01:00",
                }
            ],
        )
    )
    monkeypatch.setattr(supabase, "_service_request", request)

    with pytest.raises(HTTPException, match="L’historique des corrections est invalide"):
        asyncio.run(
            supabase._get_effective_attendance_corrections(
                [
                    {
                        "id": str(POINTAGE_ID),
                        "date_heure": "2026-10-15T08:00:00+01:00",
                    }
                ]
            )
        )
