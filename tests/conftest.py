import pytest
import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
import sys
from dotenv import load_dotenv

# Dodanie katalogu nadrzędnego do ścieżki, aby móc importować z backend
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.main import app
from backend.database import Base, get_db
from backend.auth import get_password_hash
from backend.models import User, Image, ImageTypeEnum

# Ładowanie zmiennych środowiskowych z pliku .env.test
load_dotenv(".env.test", override=True)

# Konfiguracja testowej bazy danych
TEST_DATABASE_URL = "sqlite:///./test.db"


@pytest.fixture(scope="session")
def test_engine():
    """Tworzy silnik testowej bazy danych w pamięci."""
    # Używamy SQLite w pamięci
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    # Tworzymy wszystkie tabele
    Base.metadata.create_all(bind=engine)
    return engine


@pytest.fixture(scope="function")
def test_db(test_engine):
    """Tworzy sesję testowej bazy danych."""
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    # Utwórz sesję bazy danych
    session = SessionLocal()
    
    # Dodaj testowego użytkownika
    hashed_password = get_password_hash("test_password")
    test_user = User(username="test_user", password_hash=hashed_password)
    session.add(test_user)
    session.commit()
    
    # Dodaj testowe obrazy
    for i in range(5):
        img_pos = Image(
            path=f"/test/pos/image_{i}.jpg",
            type=ImageTypeEnum.POSITIVE,
            embedding=[0.1] * 512,
            total_successes=i,
            total_failures=0,
            total_profit_factor=1.0 + (i * 0.01)
        )
        img_neg = Image(
            path=f"/test/neg/image_{i}.jpg",
            type=ImageTypeEnum.NEGATIVE,
            embedding=[0.1] * 512,
            total_successes=i,
            total_failures=0,
            total_profit_factor=1.0 + (i * 0.01)
        )
        session.add(img_pos)
        session.add(img_neg)
    
    session.commit()
    
    # Zwróć sesję
    yield session
    
    # Wyczyszczenie tabeli po teście
    for tbl in reversed(Base.metadata.sorted_tables):
        session.execute(tbl.delete())
    session.commit()
    # Zamknij sesję po teście
    session.close()


@pytest.fixture(scope="function")
def test_client(test_db):
    """Tworzy testowego klienta FastAPI z podpiętą testową bazą danych."""
    def override_get_db():
        try:
            yield test_db
        finally:
            pass
        
    # Nadpisz funkcję get_db aby korzystała z testowej bazy
    app.dependency_overrides[get_db] = override_get_db
    
    # Utwórz testowego klienta
    with TestClient(app) as client:
        yield client
    
    # Wyczyść nadpisania po teście
    app.dependency_overrides = {}


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
def test_user_token(test_client, test_user):
    """Zwraca token JWT dla testowego użytkownika."""
    response = test_client.post(
        "/token",
        data={"username": test_user.username, "password": "password123"}
    )
    return response.json()["access_token"]


@pytest.fixture
def test_admin_token(test_client, test_admin):
    """Zwraca token JWT dla testowego administratora."""
    response = test_client.post(
        "/token",
        data={"username": test_admin.username, "password": "admin123"}
    )
    return response.json()["access_token"] 