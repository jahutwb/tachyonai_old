import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
import uuid
import os
import logging

from backend.main import app
from backend.database import get_db
from backend.models import User, UserRoleEnum
from backend.auth import get_password_hash, verify_password, authenticate_user

# Włączamy debugowanie
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_direct_auth(test_db: Session):
    """Test bezpośredniego uwierzytelniania z pominięciem fixtures."""
    # 1. Przygotowanie użytkownika testowego z określonym hasłem
    # Używamy UUID dla unikalnej nazwy użytkownika
    unique_id = str(uuid.uuid4())[:8]
    username = f"auth_test_user_{unique_id}"
    password = "test_password123"
    
    # Najpierw upewnij się, że nie ma takiego użytkownika
    existing_user = test_db.query(User).filter(User.username == username).first()
    if existing_user:
        test_db.delete(existing_user)
        test_db.commit()
    
    # Debugujemy zmienne środowiskowe dla JWT
    logger.info(f"JWT_SECRET: {os.environ.get('JWT_SECRET', 'nie ustawione')}")
    logger.info(f"JWT_ALGORITHM: {os.environ.get('JWT_ALGORITHM', 'nie ustawione')}")
    
    # Generujemy hash
    hashed_password = get_password_hash(password)
    logger.info(f"Wygenerowany hash: {hashed_password}")
    
    # Utwórz nowego użytkownika
    user = User(
        username=username,
        password_hash=hashed_password,
        role=UserRoleEnum.USER
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    
    # 2. Weryfikacja bezpośrednio hasła
    logger.info(f"Weryfikacja hasła bezpośrednio: {verify_password(password, user.password_hash)}")
    assert verify_password(password, user.password_hash)
    
    # 2.5 Testujemy funkcję authenticate_user bezpośrednio
    auth_result = authenticate_user(test_db, username, password)
    logger.info(f"Uwierzytelnienie bezpośrednie: {auth_result}")
    assert auth_result, "Uwierzytelnienie bezpośrednie nie powiodło się"
    
    # 3. Test logowania przez API
    client = TestClient(app)
    
    # Debugowanie: sprawdzamy czy użytkownik istnieje przed wywołaniem API
    db_user = test_db.query(User).filter(User.username == username).first()
    logger.info(f"Użytkownik w bazie przed API: {db_user is not None}")
    if db_user:
        logger.info(f"Hash w bazie: {db_user.password_hash}")
    
    # FastAPI TestClient wymaga dokładnie takiego formatu dla OAuth2PasswordRequestForm
    response = client.post(
        "/token",
        data={
            "username": username,
            "password": password,
            "grant_type": "password"  # To jest kluczowe dla OAuth2
        }
    )
    
    # Logujemy odpowiedź dla debugowania
    logger.info(f"Odpowiedź API: {response.status_code} - {response.text}")
    
    # Asercje
    assert response.status_code == 200, f"Błąd uwierzytelniania: {response.text}"
    token_data = response.json()
    assert "access_token" in token_data
    assert token_data["token_type"] == "bearer"
