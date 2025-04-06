import pytest
from fastapi.testclient import TestClient
from backend.main import app


def test_login_endpoint(client, test_user):
    """Test endpointu logowania."""
    # Pomyślne logowanie
    response = client.post(
        "/token",
        data={"username": "testuser", "password": "password123"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "token_type" in data
    assert data["token_type"] == "bearer"

    # Niepoprawne dane logowania
    response = client.post(
        "/token",
        data={"username": "testuser", "password": "wrong_password"}
    )
    assert response.status_code == 401
    assert "detail" in response.json()

    # Nieistniejący użytkownik
    response = client.post(
        "/token",
        data={"username": "nonexistent", "password": "password123"}
    )
    assert response.status_code == 401
    assert "detail" in response.json()


def test_signup_endpoint(client):
    """Test endpointu rejestracji."""
    # Pomyślna rejestracja
    response = client.post(
        "/signup",
        json={"username": "newuser", "password": "newpassword"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "newuser"
    assert "id" in data

    # Rejestracja z istniejącą nazwą użytkownika
    response = client.post(
        "/signup",
        json={"username": "newuser", "password": "anotherpassword"}
    )
    assert response.status_code == 400
    assert "detail" in response.json()


def test_me_endpoint(client, test_user_token):
    """Test endpointu zwracającego dane zalogowanego użytkownika."""
    # Poprawne żądanie z tokenem
    response = client.get(
        "/users/me",
        headers={"Authorization": f"Bearer {test_user_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "testuser"
    assert "id" in data

    # Niepoprawny token
    response = client.get(
        "/users/me",
        headers={"Authorization": "Bearer invalid_token"}
    )
    assert response.status_code == 401
    assert "detail" in response.json()

    # Brak tokenu
    response = client.get("/users/me")
    assert response.status_code == 401
    assert "detail" in response.json() 