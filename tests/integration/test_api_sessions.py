import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.main import app
from backend.database import get_db
from backend.models import User, Session as SessionModel, Round, ImageTypeEnum, Image


@pytest.fixture
def test_user_in_db(test_db: Session):
    """Fixture tworzący testowego użytkownika w bazie danych."""
    user = User(username="test_user", password_hash="$2b$12$qZWyJ4QNZfZT6VF9nNm7YOqQLMK.JPxTgSKQD7Xtx7oK7yK3xDx7a")  # hash dla hasła "test_password"
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user


@pytest.fixture
def test_images(test_db: Session):
    """Fixture tworzący testowe obrazy w bazie danych."""
    # Dodajemy kilka obrazów pozytywnych
    pos_images = []
    for i in range(10):
        img = Image(
            path=f"/test/pos/image_{i}.jpg",
            type=ImageTypeEnum.POSITIVE,
            embedding=[0.1] * 512,  # Przykładowy embedding
            total_successes=0,
            total_failures=0,
            total_profit_factor=1.0
        )
        test_db.add(img)
        pos_images.append(img)
        
    # Dodajemy kilka obrazów negatywnych
    neg_images = []
    for i in range(10):
        img = Image(
            path=f"/test/neg/image_{i}.jpg",
            type=ImageTypeEnum.NEGATIVE,
            embedding=[0.1] * 512,  # Przykładowy embedding
            total_successes=0,
            total_failures=0,
            total_profit_factor=1.0
        )
        test_db.add(img)
        neg_images.append(img)
    
    test_db.commit()
    
    # Odświeżamy obiekty, aby miały ID
    for img in pos_images + neg_images:
        test_db.refresh(img)
    
    return {"positive": pos_images, "negative": neg_images}


@pytest.fixture
def test_token(test_user_in_db):
    """Fixture zwracający token testowego użytkownika."""
    client = TestClient(app)
    response = client.post(
        "/token",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "username": "test_user",
            "password": "test_password"
        }
    )
    assert response.status_code == 200
    token_data = response.json()
    return token_data["access_token"]


@pytest.fixture
def authorized_client(test_token):
    """Fixture zwracający autoryzowanego klienta testowego."""
    client = TestClient(app)
    client.headers = {"Authorization": f"Bearer {test_token}"}
    return client


@pytest.fixture
def test_session(test_db: Session, test_user_in_db, test_images):
    """Fixture tworzący testową sesję w bazie danych."""
    # Przygotuj dane dla puli
    pos_pool = []
    for i in range(6):
        pos_pool.append({
            "id": test_images["positive"][i].id,
            "successes": 0,
            "failures": 0,
            "origin": "random"
        })
    
    neg_pool = []
    for i in range(6):
        neg_pool.append({
            "id": test_images["negative"][i].id,
            "successes": 0,
            "failures": 0,
            "origin": "random"
        })
        
    # Utwórz sesję
    session = SessionModel(
        user_id=test_user_in_db.id,
        status="ACTIVE",
        pos_pool_json=pos_pool,
        neg_pool_json=neg_pool,
        session_profit_factor=1.0,
        remaining_pairs=6
    )
    test_db.add(session)
    test_db.commit()
    test_db.refresh(session)
    return session


def test_create_session(authorized_client, test_db, monkeypatch):
    """Test tworzenia nowej sesji."""
    # Zastąp funkcję pobierania puli obrazów, aby użyła obrazów testowych
    def mock_get_initial_pool(*args, **kwargs):
        return {
            "pos_pool": [{"id": 1, "successes": 0, "failures": 0, "origin": "random"}] * 6,
            "neg_pool": [{"id": 2, "successes": 0, "failures": 0, "origin": "random"}] * 6
        }
    
    import backend.sessions
    monkeypatch.setattr(backend.sessions, "get_initial_pool", mock_get_initial_pool)
    
    response = authorized_client.post("/api/sessions")
    assert response.status_code == 201
    
    # Sprawdź, czy sesja została utworzona
    session_data = response.json()
    assert "id" in session_data
    assert session_data["status"] == "ACTIVE"
    assert session_data["remaining_pairs"] == 6
    assert session_data["session_profit_factor"] == 1.0


def test_get_session(authorized_client, test_session):
    """Test pobierania informacji o sesji."""
    response = authorized_client.get(f"/api/sessions/{test_session.id}")
    assert response.status_code == 200
    
    session_data = response.json()
    assert session_data["id"] == test_session.id
    assert session_data["status"] == test_session.status
    assert session_data["remaining_pairs"] == test_session.remaining_pairs
    assert session_data["session_profit_factor"] == test_session.session_profit_factor


def test_get_session_summary(authorized_client, test_session, test_db):
    """Test pobierania podsumowania sesji."""
    # Dodaj kilka rund do sesji
    round1 = Round(
        session_id=test_session.id,
        round_number=1,
        pos_image_id=1,
        neg_image_id=2,
        user_choice_side="LEFT",
        user_action="BUY",
        start_price=50000.0,
        end_price=50100.0,
        profit_fraction=0.002,
        result="SUCCESS"
    )
    
    round2 = Round(
        session_id=test_session.id,
        round_number=2,
        pos_image_id=3,
        neg_image_id=4,
        user_choice_side="RIGHT",
        user_action="SELL",
        start_price=50100.0,
        end_price=50000.0,
        profit_fraction=-0.002,
        result="FAILURE"
    )
    
    test_db.add(round1)
    test_db.add(round2)
    test_db.commit()
    
    response = authorized_client.get(f"/api/sessions/{test_session.id}/summary")
    assert response.status_code == 200
    
    summary_data = response.json()
    assert summary_data["id"] == test_session.id
    assert summary_data["success_count"] == 1
    assert summary_data["failure_count"] == 1
    assert summary_data["session_profit_factor"] == 1.0  # Wartość nie jest aktualizowana w teście


def test_get_rounds_for_session(authorized_client, test_session, test_db):
    """Test pobierania rund dla sesji."""
    # Dodaj kilka rund do sesji
    round1 = Round(
        session_id=test_session.id,
        round_number=1,
        pos_image_id=1,
        neg_image_id=2,
        user_choice_side="LEFT",
        user_action="BUY",
        start_price=50000.0,
        end_price=50100.0,
        profit_fraction=0.002,
        result="SUCCESS"
    )
    
    test_db.add(round1)
    test_db.commit()
    
    response = authorized_client.get(f"/api/sessions/{test_session.id}/rounds")
    assert response.status_code == 200
    
    rounds_data = response.json()
    assert len(rounds_data) == 1
    assert rounds_data[0]["session_id"] == test_session.id
    assert rounds_data[0]["pos_image_id"] == 1
    assert rounds_data[0]["neg_image_id"] == 2
    assert rounds_data[0]["result"] == "SUCCESS"


def test_get_next_round(authorized_client, test_session):
    """Test pobierania następnej rundy."""
    response = authorized_client.get(f"/api/rounds/next?session_id={test_session.id}")
    assert response.status_code == 200
    
    round_data = response.json()
    assert "id" in round_data
    assert round_data["session_id"] == test_session.id
    assert round_data["round_number"] == 1
    assert "pos_image_id" in round_data
    assert "neg_image_id" in round_data


def test_submit_round_choice(authorized_client, test_session, test_db, monkeypatch):
    """Test przesyłania wyboru użytkownika w rundzie."""
    # Utwórz rundę
    response = authorized_client.get(f"/api/rounds/next?session_id={test_session.id}")
    assert response.status_code == 200
    round_data = response.json()
    
    # Zamockuj funkcję oczekiwania na zmianę ceny
    def mock_wait_for_price_change(*args, **kwargs):
        return 50100.0, 0.002  # end_price, profit_fraction
    
    import backend.btc_price
    monkeypatch.setattr(backend.btc_price, "wait_for_price_change", mock_wait_for_price_change)
    
    # Wyślij wybór
    response = authorized_client.post(
        "/api/rounds/choice",
        json={
            "session_id": test_session.id,
            "round_id": round_data["id"],
            "side": "LEFT"
        }
    )
    
    assert response.status_code == 200
    result_data = response.json()
    
    assert result_data["start_price"] > 0
    assert result_data["end_price"] > 0
    assert "profit_fraction" in result_data
    assert "result" in result_data
    assert "stimulus_url" in result_data


def test_user_sessions(authorized_client, test_session):
    """Test pobierania sesji użytkownika."""
    response = authorized_client.get("/api/user/sessions")
    assert response.status_code == 200
    
    sessions_data = response.json()
    assert len(sessions_data) >= 1
    assert sessions_data[0]["id"] == test_session.id 