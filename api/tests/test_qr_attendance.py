import asyncio
import base64
import hashlib
from collections.abc import Generator
from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import UUID

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.dependencies.auth import (
    require_approved_personnel,
    require_attendance_operator,
    require_authenticated_user,
)
from app.main import app
from app.routers import attendance
from app.schemas.qr_attendance import AttendanceEventType, QRScanResult
from app.services import supabase

PERSONNEL_ID = UUID("10000000-0000-4000-8000-000000000001")
OPERATOR_ID = UUID("20000000-0000-4000-8000-000000000002")
REQUEST_ID = UUID("30000000-0000-4000-8000-000000000003")
TOKEN = "a" * 43
QR_PAYLOAD = f"eigsi-attendance:v1:{PERSONNEL_ID}:{TOKEN}"


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_qr_status_requires_authentication(client: TestClient) -> None:
    response = client.get("/attendance/qr/me")

    assert response.status_code == 401


def test_member_can_check_and_issue_own_qr(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    app.dependency_overrides[require_approved_personnel] = lambda: PERSONNEL_ID
    status_check = AsyncMock(return_value=False)
    issue = AsyncMock(return_value=base64.b64encode(b"\x89PNG\r\n\x1a\n").decode())
    monkeypatch.setattr(attendance, "get_qr_credential_status", status_check)
    monkeypatch.setattr(attendance, "issue_personnel_qr", issue)

    status_response = client.get("/attendance/qr/me")
    issue_response = client.post("/attendance/qr/me")

    assert status_response.status_code == 200
    assert status_response.json() == {"has_active_credential": False}
    assert issue_response.status_code == 200
    assert issue_response.json()["qr_image"].startswith("data:image/png;base64,")
    issue.assert_awaited_once_with(PERSONNEL_ID)


def test_scanning_requires_authentication(client: TestClient) -> None:
    response = client.post(
        "/attendance/scan",
        json={
            "payload": QR_PAYLOAD,
            "type_pointage": "entree",
            "idempotency_key": str(REQUEST_ID),
        },
    )

    assert response.status_code == 401


def test_operator_scan_rejects_invalid_event_type(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    app.dependency_overrides[require_attendance_operator] = lambda: OPERATOR_ID
    record = AsyncMock()
    monkeypatch.setattr(attendance, "record_qr_attendance", record)

    response = client.post(
        "/attendance/scan",
        json={
            "payload": QR_PAYLOAD,
            "type_pointage": "invalid",
            "idempotency_key": str(REQUEST_ID),
        },
    )

    assert response.status_code == 422
    record.assert_not_awaited()


def test_operator_scan_records_explicit_event_type(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    app.dependency_overrides[require_attendance_operator] = lambda: OPERATOR_ID
    timestamp = datetime(2026, 10, 15, 8, 0, tzinfo=UTC)
    result = QRScanResult(
        id_pointage=UUID("40000000-0000-4000-8000-000000000004"),
        id_personnel=PERSONNEL_ID,
        nom="Exemple",
        prenom="Agent",
        date_heure=timestamp,
        type_pointage=AttendanceEventType.SORTIE,
        duplicate=False,
    )
    record = AsyncMock(return_value=result)
    monkeypatch.setattr(attendance, "record_qr_attendance", record)

    response = client.post(
        "/attendance/scan",
        json={
            "payload": QR_PAYLOAD,
            "type_pointage": "sortie",
            "idempotency_key": str(REQUEST_ID),
        },
    )

    assert response.status_code == 200
    assert response.json()["type_pointage"] == "sortie"
    assert response.json()["date_heure"] == timestamp.isoformat().replace("+00:00", "Z")
    record.assert_awaited_once_with(
        payload=QR_PAYLOAD,
        type_pointage=AttendanceEventType.SORTIE,
        idempotency_key=REQUEST_ID,
        operator_user_id=OPERATOR_ID,
    )


@pytest.mark.parametrize("roles", [{"personnel"}, {"finance"}, set()])
def test_non_attendance_role_cannot_scan(
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

    response = client.post(
        "/attendance/scan",
        json={
            "payload": QR_PAYLOAD,
            "type_pointage": "entree",
            "idempotency_key": str(REQUEST_ID),
        },
    )

    assert response.status_code == 403


def test_qr_issuance_rejects_unapproved_personnel(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def authenticated_user() -> UUID:
        return PERSONNEL_ID

    app.dependency_overrides[require_authenticated_user] = authenticated_user
    monkeypatch.setattr(supabase, "get_personnel_profile", AsyncMock(return_value=None))

    response = client.get("/attendance/qr/me")

    assert response.status_code == 403


def test_qr_issuance_requires_personnel_role(
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

    response = client.get("/attendance/qr/me")

    assert response.status_code == 403


def test_issue_qr_stores_hash_and_returns_png(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(supabase.secrets, "token_urlsafe", lambda _: TOKEN)
    request = AsyncMock(return_value=httpx.Response(204))
    monkeypatch.setattr(supabase, "_service_request", request)

    image = asyncio.run(supabase.issue_personnel_qr(PERSONNEL_ID))

    assert base64.b64decode(image).startswith(b"\x89PNG\r\n\x1a\n")
    request.assert_awaited_once()
    submitted = request.await_args.kwargs["json"]
    assert submitted["target_personnel"] == str(PERSONNEL_ID)
    assert submitted["new_token_hash"] == hashlib.sha256(TOKEN.encode()).hexdigest()
    assert TOKEN not in str(submitted)


def test_scan_hashes_token_and_sends_server_generated_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    timestamp = datetime(2026, 10, 15, 8, 0, tzinfo=UTC)
    response = httpx.Response(
        200,
        json=[
            {
                "id_pointage": "40000000-0000-4000-8000-000000000004",
                "id_personnel": str(PERSONNEL_ID),
                "nom": "Exemple",
                "prenom": "Agent",
                "date_heure": timestamp.isoformat(),
                "type_pointage": "entree",
                "duplicate": False,
            }
        ],
    )
    request = AsyncMock(return_value=response)
    monkeypatch.setattr(supabase, "_service_request", request)

    result = asyncio.run(
        supabase.record_qr_attendance(
            payload=QR_PAYLOAD,
            type_pointage=AttendanceEventType.ENTREE,
            idempotency_key=REQUEST_ID,
            operator_user_id=OPERATOR_ID,
        )
    )

    assert result.id_personnel == PERSONNEL_ID
    submitted = request.await_args.kwargs["json"]
    assert submitted["target_personnel"] == str(PERSONNEL_ID)
    assert submitted["presented_token_hash"] == hashlib.sha256(
        TOKEN.encode()
    ).hexdigest()
    assert submitted["selected_event_type"] == "entree"
    assert submitted["request_id"] == str(REQUEST_ID)
    assert submitted["operator_user_id"] == str(OPERATOR_ID)
    assert TOKEN not in str(submitted)


def test_malformed_qr_never_calls_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = AsyncMock()
    monkeypatch.setattr(supabase, "_service_request", request)

    with pytest.raises(HTTPException) as error:
        asyncio.run(
            supabase.record_qr_attendance(
                payload="invalid",
                type_pointage=AttendanceEventType.ENTREE,
                idempotency_key=REQUEST_ID,
                operator_user_id=OPERATOR_ID,
            )
        )

    assert error.value.status_code == 422
    request.assert_not_awaited()
