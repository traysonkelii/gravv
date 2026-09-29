import httpx
import pytest

from tests.conftest import AuthAdmin, AuthUser, auth_headers


@pytest.fixture(scope="module")
async def user(auth_admin: AuthAdmin) -> AuthUser:
    return await auth_admin.create_user("me", "Mia Tester")


async def test_me_get_provisioned_profile(client: httpx.AsyncClient, user: AuthUser) -> None:
    r = await client.get("/api/v1/me", headers=auth_headers(user))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["profile"]["email"] == user.email
    assert body["profile"]["full_name"] == "Mia Tester"
    assert body["profile"]["onboarding_step"] == 0
    assert [m["kind"] for m in body["memberships"]] == ["personal"]
    assert body["memberships"][0]["role"] == "owner"
    assert body["profile"]["default_workspace_id"] == body["memberships"][0]["workspace_id"]


async def test_me_requires_token(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/v1/me")
    assert r.status_code == 401
    assert r.json()["type"].endswith("/unauthenticated")


async def test_me_update_and_interests(client: httpx.AsyncClient, user: AuthUser) -> None:
    r = await client.patch(
        "/api/v1/me",
        headers=auth_headers(user),
        json={
            "role_title": "Account Executive",
            "timezone": "America/New_York",
            "goals": {"close_deals": True, "free_text": "Land the satellite program"},
            "interests": [
                {"kind": "personal", "value": "Pinball"},
                {"kind": "personal", "value": "pinball"},
                {"kind": "professional", "value": "Government contracting"},
            ],
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["profile"]["role_title"] == "Account Executive"
    assert body["profile"]["goals"]["close_deals"] is True
    assert sorted((i["kind"], i["value"]) for i in body["interests"]) == [
        ("personal", "Pinball"),
        ("professional", "Government contracting"),
    ]


async def test_me_update_rejects_unknown_fields_and_bad_timezone(client: httpx.AsyncClient, user: AuthUser) -> None:
    r = await client.patch("/api/v1/me", headers=auth_headers(user), json={"email": "x@y.z"})
    assert r.status_code == 422
    assert r.json()["errors"][0]["field"] == "email"
    r = await client.patch("/api/v1/me", headers=auth_headers(user), json={"timezone": "Mars/Olympus"})
    assert r.status_code == 422


async def test_onboarding_steps_persist(client: httpx.AsyncClient, user: AuthUser) -> None:
    h = auth_headers(user)
    r = await client.patch(
        "/api/v1/me/onboarding",
        headers=h,
        json={"step": 1, "profile": {"full_name": "Mia T", "role_title": "AE", "timezone": "UTC"}},
    )
    assert r.status_code == 200 and r.json()["profile"]["onboarding_step"] == 1
    r = await client.patch(
        "/api/v1/me/onboarding",
        headers=h,
        json={"step": 2, "interests": [{"kind": "personal", "value": "Trail running"}]},
    )
    assert r.json()["profile"]["onboarding_step"] == 2
    r = await client.patch("/api/v1/me/onboarding", headers=h, json={"step": 3, "goals": {"strengthen": True}})
    assert r.json()["profile"]["goals"] == {
        "close_deals": False,
        "expand_network": False,
        "strengthen": True,
        "track_roi": False,
        "free_text": "",
    }
    r = await client.patch("/api/v1/me/onboarding", headers=h, json={"step": 4})
    r = await client.patch("/api/v1/me/onboarding", headers=h, json={"step": 5})
    assert r.json()["profile"]["onboarding_step"] == 5
    assert r.json()["profile"]["onboarding_completed_at"] is not None
    # going back to an earlier step never lowers progress
    r = await client.patch("/api/v1/me/onboarding", headers=h, json={"step": 2, "interests": []})
    assert r.json()["profile"]["onboarding_step"] == 5


async def test_onboarding_step_1_requires_profile(client: httpx.AsyncClient, user: AuthUser) -> None:
    r = await client.patch("/api/v1/me/onboarding", headers=auth_headers(user), json={"step": 1})
    assert r.status_code == 422
