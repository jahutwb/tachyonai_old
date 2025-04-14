import pytest
from fastapi.testclient import TestClient
from backend.main import app


def test_login_endpoint(test_client, test_user):
    """Test endpointu logowania."""
    # Pomyślne logowanie
    response = test_client.post(
        "/token",
        data={"username": test_user.username, "password": "test_password"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "token_type" in data
    assert data["token_type"] == "bearer"

    # Niepoprawne dane logowania
    response = test_client.post(
        "/token",
        data={"username": test_user.username, "password": "wrong_password"}
    )
    assert response.status_code == 401
    error_data = response.json()
    assert "code" in error_data
    assert "message" in error_data
    assert error_data["code"] == "AUTHENTICATION_ERROR"

    # Nieistniejący użytkownik
    response = test_client.post(
        "/token",
        data={"username": "nonexistent", "password": "password123"}
    )
    assert response.status_code == 401
    error_data = response.json()
    assert "code" in error_data
    assert "message" in error_data
    assert error_data["code"] == "AUTHENTICATION_ERROR"


def test_signup_endpoint(test_client):
    """Test endpointu rejestracji."""
    # Pomyślna rejestracja
    response = test_client.post(
        "/signup",
        json={"username": "newuser", "password": "newpassword"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "newuser"
    assert "id" in data

    # Rejestracja z istniejącą nazwą użytkownika
    response = test_client.post(
        "/signup",
        json={"username": "newuser", "password": "anotherpassword"}
    )
    assert response.status_code == 400
    error_data = response.json()
    assert "code" in error_data
    assert "message" in error_data
    assert error_data["code"] == "BAD_REQUEST"


def test_me_endpoint(test_client, test_user, test_user_token):
    """Test endpointu zwracającego dane zalogowanego użytkownika."""
    # Poprawne żądanie z tokenem
    response = test_client.get(
        "/users/me",
        headers={"Authorization": f"Bearer {test_user_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == test_user.username
    assert "id" in data

    # Niepoprawny token
    response = test_client.get(
        "/users/me",
        headers={"Authorization": "Bearer invalid_token"}
    )
    assert response.status_code == 401
    error_data = response.json()
    assert "code" in error_data
    assert "message" in error_data
    assert error_data["code"] == "AUTHENTICATION_ERROR"

    # Brak tokenu
    response = test_client.get("/users/me")
    assert response.status_code == 401
    error_data = response.json()
    assert "code" in error_data
    assert "message" in error_data
    assert error_data["code"] == "AUTHENTICATION_ERROR"