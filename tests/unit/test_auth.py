import pytest
from backend import auth
from datetime import timedelta


def test_password_hashing():
    """Test, czy haszowanie i weryfikacja hasła działają poprawnie."""
    password = "test_password"
    hashed = auth.get_password_hash(password)
    
    # Hasz powinien być inny niż oryginalne hasło
    assert hashed != password
    
    # Weryfikacja powinna zwrócić True dla poprawnego hasła
    assert auth.verify_password(password, hashed) == True
    
    # Weryfikacja powinna zwrócić False dla niepoprawnego hasła
    assert auth.verify_password("wrong_password", hashed) == False


def test_jwt_token_creation():
    """Test, czy tworzenie tokenu JWT działa poprawnie."""
    username = "testuser"
    data = {"sub": username}
    
    # Tworzenie tokenu z określonym czasem wygaśnięcia
    token = auth.create_access_token(data, expires_delta=timedelta(minutes=30))
    
    # Token powinien być stringiem
    assert isinstance(token, str)
    
    # Token powinien mieć odpowiednią długość (przynajmniej 50 znaków)
    assert len(token) > 50


def test_authenticate_user(test_db, test_user):
    """Test, czy autentykacja użytkownika działa poprawnie."""
    # Powinno zwrócić obiekt użytkownika dla poprawnych danych
    user = auth.authenticate_user(test_db, "testuser", "password123")
    assert user is not None
    assert user.username == "testuser"
    
    # Powinno zwrócić False dla niepoprawnego hasła
    user = auth.authenticate_user(test_db, "testuser", "wrong_password")
    assert user is False
    
    # Powinno zwrócić False dla nieistniejącego użytkownika
    user = auth.authenticate_user(test_db, "nonexistent", "password123")
    assert user is False


def test_decode_access_token():
    """Test, czy dekodowanie tokenu JWT działa poprawnie."""
    username = "testuser"
    data = {"sub": username}
    
    # Tworzenie tokenu z określonym czasem wygaśnięcia
    token = auth.create_access_token(data, expires_delta=timedelta(minutes=30))
    
    # Dekodowanie tokenu powinno zwrócić oryginalną zawartość
    decoded = auth.decode_access_token(token)
    assert decoded is not None
    assert decoded["sub"] == username
    
    # Próba dekodowania nieprawidłowego tokenu powinna zwrócić None
    invalid_token = "invalid.token.string"
    decoded = auth.decode_access_token(invalid_token)
    assert decoded is None