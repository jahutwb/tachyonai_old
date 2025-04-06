import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
import os
import sys
from dotenv import load_dotenv

# Dodanie katalogu nadrzędnego do ścieżki, aby móc importować z backend
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.main import app
from backend.database import Base
from backend.auth import get_password_hash

# Ładowanie zmiennych środowiskowych z pliku .env.test
load_dotenv(".env.test", override=True)

# Konfiguracja testowej bazy danych
TEST_DATABASE_URL = "sqlite:///./test.db"


@pytest.fixture(scope="function")
def test_db():
    """Tworzy testową bazę danych i zwraca sesję."""
    engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    # Tworzenie tabel
    Base.metadata.create_all(bind=engine)
    
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()
        # Usuwanie wszystkich tabel po zakończeniu testu
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(test_db):
    """Zwraca klienta testowego FastAPI."""
    app.dependency_overrides = {}
    
    # Nadpisanie funkcji get_db
    def override_get_db():
        try:
            yield test_db
        finally:
            pass
    
    from backend.database import get_db
    app.dependency_overrides[get_db] = override_get_db
    
    with TestClient(app) as c:
        yield c


@pytest.fixture
def test_user(test_db):
    """Tworzy testowego użytkownika w bazie danych."""
    from backend.models import User, UserRoleEnum
    
    user = User(
        username="testuser",
        password_hash=get_password_hash("password123"),
        role=UserRoleEnum.USER
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user


@pytest.fixture
def test_admin(test_db):
    """Tworzy testowego administratora w bazie danych."""
    from backend.models import User, UserRoleEnum
    
    admin = User(
        username="testadmin",
        password_hash=get_password_hash("admin123"),
        role=UserRoleEnum.ADMIN
    )
    test_db.add(admin)
    test_db.commit()
    test_db.refresh(admin)
    return admin


@pytest.fixture
def test_user_token(client, test_user):
    """Zwraca token JWT dla testowego użytkownika."""
    response = client.post(
        "/token",
        data={"username": test_user.username, "password": "password123"}
    )
    return response.json()["access_token"]


@pytest.fixture
def test_admin_token(client, test_admin):
    """Zwraca token JWT dla testowego administratora."""
    response = client.post(
        "/token",
        data={"username": test_admin.username, "password": "admin123"}
    )
    return response.json()["access_token"] 