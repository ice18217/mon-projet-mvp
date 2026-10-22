from collections.abc import Generator
from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.dependencies.auth import require_authenticated_user
from app.main import app
from app.routers import access
from app.schemas.access import PendingPersonnel
from app.services import supabase

ADMIN_ID = UUID("00000000-0000-4000-8000-000000000001")
PERSONNEL_ID = UUID("00000000-0000-4000-8000-000000000002")


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def set_authenticated_admin(
    monkeypatch: pytest.MonkeyPatch, client: TestClient
) -> None:
    async def authenticated_user() -> UUID:
        return ADMIN_ID

    app.dependency_overrides[require_authenticated_user] = authenticated_user
    monkeypatch.setattr(
        supabase,
        "get_personnel_profile",
        AsyncMock(
            return_value={
                "id": str(ADMIN_ID),
                "actif": True,
                "acces_approuve": True,
            }
        ),
    )
    monkeypatch.setattr(
        supabase,
        "get_personnel_roles",
        AsyncMock(return_value={"admin_technique"}),
    )


def test_pending_access_requires_authentication(client: TestClient) -> None:
    response = client.get("/access/pending")

    assert response.status_code == 401


def test_pending_access_rejects_unapproved_user(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def authenticated_user() -> UUID:
        return ADMIN_ID

    app.dependency_overrides[require_authenticated_user] = authenticated_user
    monkeypatch.setattr(supabase, "get_personnel_profile", AsyncMock(return_value=None))

    response = client.get("/access/pending")

    assert response.status_code == 403
    assert response.json()["detail"] == "Compte non approuvé ou inactif."


def test_pending_access_rejects_user_without_admin_role(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def authenticated_user() -> UUID:
        return ADMIN_ID

    app.dependency_overrides[require_authenticated_user] = authenticated_user
    monkeypatch.setattr(
        supabase,
        "get_personnel_profile",
        AsyncMock(
            return_value={
                "id": str(ADMIN_ID),
                "actif": True,
                "acces_approuve": True,
            }
        ),
    )
    monkeypatch.setattr(
        supabase, "get_personnel_roles", AsyncMock(return_value={"personnel"})
    )

    response = client.get("/access/pending")

    assert response.status_code == 403
    assert response.json()["detail"] == "Rôle administrateur technique requis."


def test_admin_can_list_pending_access(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    set_authenticated_admin(monkeypatch, client)
    pending_person = PendingPersonnel(
        id=PERSONNEL_ID,
        nom="Exemple",
        prenom="Agent",
        email="agent@example.test",
        type="permanent",
        created_at="2026-10-15T00:00:00Z",
    )
    monkeypatch.setattr(
        access, "list_pending_personnel", AsyncMock(return_value=[pending_person])
    )

    response = client.get("/access/pending")

    assert response.status_code == 200
    assert response.json()[0]["id"] == str(PERSONNEL_ID)
    assert response.json()[0]["email"] == "agent@example.test"


def test_admin_approves_with_selected_roles(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    set_authenticated_admin(monkeypatch, client)
    approve = AsyncMock()
    monkeypatch.setattr(access, "approve_personnel_access", approve)

    response = client.post(
        f"/access/{PERSONNEL_ID}/approve",
        json={"roles": ["personnel", "finance"]},
    )

    assert response.status_code == 204
    approve.assert_awaited_once()
    assert approve.await_args.args == (
        PERSONNEL_ID,
        [supabase.AssignableRole.PERSONNEL, supabase.AssignableRole.FINANCE],
    )


@pytest.mark.parametrize(
    "roles",
    [[], ["admin_technique"], ["personnel", "personnel"]],
)
def test_admin_cannot_submit_empty_privileged_or_duplicate_roles(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    roles: list[str],
) -> None:
    set_authenticated_admin(monkeypatch, client)

    response = client.post(
        f"/access/{PERSONNEL_ID}/approve",
        json={"roles": roles},
    )

    assert response.status_code == 422
