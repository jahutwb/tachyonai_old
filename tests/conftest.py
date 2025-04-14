import pytest
import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from sqlalchemy.sql import text
from fastapi.testclient import TestClient
import sys
from dotenv import load_dotenv

# Dodanie katalogu nadrzędnego do ścieżki, aby móc importować z backend
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.main import app
from backend.database import Base, get_db
from backend.auth import get_password_hash, create_access_token
from backend.models import User, Image, ImageTypeEnum, UserRoleEnum
from datetime import timedelta
import uuid

# Ładowanie zmiennych środowiskowych z pliku .env.test
load_dotenv(".env.test", override=True)

# Konfiguracja testowej bazy danych
TEST_SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"

engine = create_engine(
    TEST_SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Funkcja, która będzie używana do nadpisania oryginalnej funkcji get_db w aplikacji
def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

# Nadpisanie funkcji get_db w aplikacji
app.dependency_overrides[get_db] = override_get_db

@pytest.fixture(scope="session")
def test_client():
    """Fixture do testowania API z FastAPI."""
    client = TestClient(app)
    return client

@pytest.fixture(scope="function")
def test_db():
    """Fixture tworzący testową bazę danych."""
    # Tworzenie tabel
    Base.metadata.create_all(bind=engine)

    # Inicjalizacja testowych obrazów, jeśli potrzebne
    init_test_images(TestingSessionLocal())

    # Zwrócenie sesji bazy danych
    db = TestingSessionLocal()

    try:
        yield db
    finally:
        # Czyszczenie bazy - usuwanie wszystkich danych
        db.execute(text("DELETE FROM rounds"))
        db.execute(text("DELETE FROM sessions"))
        db.execute(text("DELETE FROM users"))
        db.execute(text("DELETE FROM images"))

        db.commit()
        db.close()

def init_test_images(db):
    """Inicjalizacja testowych obrazów w bazie danych."""
    # Sprawdź czy już mamy obrazy w bazie
    images_count = db.query(Image).count()
    if images_count > 0:
        return

    # Dodaj testowe obrazy
    for i in range(1, 11):  # 10 obrazów każdego typu
        # Pozytywne obrazy
        pos_image = Image(
            path=f"test_images/positive_{i}.jpg",
            type=ImageTypeEnum.POSITIVE,
            embedding=[0.1 * i for _ in range(10)],  # Symulacja wektora embeddingu
        )
        db.add(pos_image)

        # Negatywne obrazy
        neg_image = Image(
            path=f"test_images/negative_{i}.jpg",
            type=ImageTypeEnum.NEGATIVE,
            embedding=[0.1 * i for _ in range(10)],  # Symulacja wektora embeddingu
        )
        db.add(neg_image)

    db.commit()

def create_test_user(db, username=None, password="test_password"):
    """Tworzy testowego użytkownika z unikalną nazwą"""
    # Generowanie unikalnej nazwy użytkownika
    if username is None:
        username = f"test_user_{str(uuid.uuid4())[:8]}"

    # Usunięcie istniejącego użytkownika o tej samej nazwie (jeśli istnieje)
    existing_user = db.query(User).filter(User.username == username).first()
    if existing_user:
        db.delete(existing_user)
        db.commit()

    # Tworzenie hashu hasła
    hashed_password = get_password_hash(password)

    # Tworzenie nowego użytkownika
    user = User(
        username=username,
        password_hash=hashed_password,
        role=UserRoleEnum.USER
    )

    db.add(user)
    db.commit()
    db.refresh(user)
    return user

def get_test_user_token(user):
    """Generuje token JWT dla testowego użytkownika"""
    access_token_expires = timedelta(minutes=30)
    access_token = create_access_token(
        data={"sub": user.username},
        expires_delta=access_token_expires
    )
    return access_token

def get_authorized_client(token):
    """Tworzy klienta testowego z ustawionym tokenem uwierzytelniającym"""
    client = TestClient(app)
    client.headers = {"Authorization": f"Bearer {token}"}
    return client

@pytest.fixture
def test_user(test_db):
    """Tworzy testowego użytkownika w bazie danych."""
    user = create_test_user(test_db)
    return user

@pytest.fixture
def test_user_token(test_user):
    """Zwraca token JWT dla testowego użytkownika."""
    return get_test_user_token(test_user)

@pytest.fixture
def authorized_client(test_user_token):
    """Zwraca klienta testowego z ustawionym tokenem uwierzytelniającym."""
    return get_authorized_client(test_user_token)

@pytest.fixture
def test_session(test_db, test_user):
    """Tworzy testową sesję w bazie danych."""
    from backend.models import Session as SessionModel
    import json

    # Tworzenie struktury dla pul obrazów
    pos_pool = [{"id": 1, "successes": 0, "failures": 0, "origin": "random"}]
    neg_pool = [{"id": 11, "successes": 0, "failures": 0, "origin": "random"}]

    # Tworzenie sesji
    session = SessionModel(
        user_id=test_user.id,
        status="ACTIVE",
        pos_pool_json=pos_pool,
        neg_pool_json=neg_pool,
        session_profit_factor=1.0,
        remaining_pairs=6,
    )
    test_db.add(session)
    test_db.commit()
    test_db.refresh(session)
    return session

@pytest.fixture
def test_round(test_db, test_session):
    """Tworzy testową rundę w bazie danych."""
    from backend.models import Round

    # Tworzenie rundy
    round = Round(
        session_id=test_session.id,
        round_number=1,
        pos_image_id=1,
        neg_image_id=11,
        user_choice_side=None,
        user_action=None,
        left_action="BUY",
        right_action="SELL",
        start_price=50000.0,
        end_price=None,
        profit_fraction=None,
        result=None,
        response_time=None
    )
    test_db.add(round)
    test_db.commit()
    test_db.refresh(round)
    return round