"""User endpoint tests."""

from fastapi.testclient import TestClient


def test_health_check(client: TestClient) -> None:
    """Test health endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_create_user(client: TestClient) -> None:
    """Test user creation."""
    response = client.post(
        "/api/v1/users",
        json={
            "email": "test@example.com",
            "name": "Test User",
            "password": "securepassword123",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "test@example.com"
    assert data["name"] == "Test User"
    assert "id" in data
    assert "password" not in data


def test_create_user_invalid_email(client: TestClient) -> None:
    """Test user creation with invalid email."""
    response = client.post(
        "/api/v1/users",
        json={
            "email": "not-an-email",
            "name": "Test User",
            "password": "securepassword123",
        },
    )
    assert response.status_code == 422


def test_get_current_user_unauthorized(client: TestClient) -> None:
    """Test get current user without auth."""
    response = client.get("/api/v1/users/me")
    assert response.status_code == 401  # No auth header


def test_get_current_user_authorized(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """Test get current user with auth."""
    response = client.get("/api/v1/users/me", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "email" in data
    assert "name" in data
