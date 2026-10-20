import pytest

pytestmark = pytest.mark.django_db


def test_register_login_and_me(api_client):
    payload = {
        "username": "nadia",
        "email": "Nadia@Example.com",
        "password": "Str0ng-pass-2026",
        "first_name": "Nadia",
    }
    response = api_client.post("/api/v1/auth/register/", payload)
    assert response.status_code == 201, response.json()
    assert response.json()["email"] == "nadia@example.com"
    assert "password" not in response.json()

    token = api_client.post(
        "/api/v1/auth/token/", {"username": "nadia", "password": "Str0ng-pass-2026"}
    )
    assert token.status_code == 200
    access = token.json()["access"]

    me = api_client.get("/api/v1/auth/me/", HTTP_AUTHORIZATION=f"Bearer {access}")
    assert me.status_code == 200
    assert me.json()["username"] == "nadia"
    assert api_client.get("/api/v1/auth/me/").status_code == 401


def test_register_rejects_duplicate_email_and_weak_password(api_client, user):
    dup = api_client.post(
        "/api/v1/auth/register/",
        {"username": "x", "email": "RAHIM@example.com", "password": "Str0ng-pass-2026"},
    )
    assert dup.status_code == 400
    weak = api_client.post(
        "/api/v1/auth/register/", {"username": "y", "email": "y@example.com", "password": "123"}
    )
    assert weak.status_code == 400


def test_openapi_schema_renders(api_client):
    response = api_client.get("/api/schema/")
    assert response.status_code == 200
    assert b"/api/v1/orders/" in response.content
