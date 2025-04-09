import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
import json
import uuid
from datetime import timedelta

from backend.main import app
from backend.database import get_db
from backend.models import User, Session as SessionModel, Round, ImageTypeEnum, Image, UserRoleEnum
from backend.auth import get_password_hash, create_access_token
from tests.conftest import create_test_user, get_test_user_token, get_authorized_client

@pytest.fixture
def test_user_in_db(test_db: Session):
    """Fixture umieszczający testowego użytkownika w bazie danych."""
    return create_test_user(test_db)

@pytest.fixture
def test_token(test_user_in_db):
    """
    Fixture zwracający token testowego użytkownika.
    Generujemy token bezpośrednio używając tej samej funkcji co w aplikacji.
    """
    return get_test_user_token(test_user_in_db)

@pytest.fixture
def authorized_client(test_token):
    """Klient z ustawionym nagłówkiem autoryzacji."""
    return get_authorized_client(test_token)

@pytest.fixture
def test_image(test_db):
    """Fixture tworzący testowy obraz."""
    image = Image(
        path="/test/image.jpg",
        type=ImageTypeEnum.POSITIVE,
        embedding=[0.1] * 10,
    )
    test_db.add(image)
    test_db.commit()
    test_db.refresh(image)
    return image

@pytest.fixture
def test_session(test_db, test_user_in_db, test_image):
    """Fixture tworzący testową sesję."""
    # Tworzenie struktury dla pul obrazów
    pos_pool = [{"id": test_image.id, "successes": 0, "failures": 0, "origin": "random"}]
    neg_pool = [{"id": test_image.id, "successes": 0, "failures": 0, "origin": "random"}]

    # Tworzenie sesji
    session = SessionModel(
        user_id=test_user_in_db.id,
        status="ACTIVE",
        pos_pool_json=json.dumps(pos_pool),
        neg_pool_json=json.dumps(neg_pool),
        session_profit_factor=1.0,
        remaining_pairs=6,
    )
    test_db.add(session)
    test_db.commit()
    test_db.refresh(session)
    return session

@pytest.fixture
def test_round(test_db, test_session, test_image):
    """Fixture tworzący testową rundę."""
    round = Round(
        session_id=test_session.id,
        round_number=1,
        pos_image_id=test_image.id,
        neg_image_id=test_image.id,
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

def test_create_session(authorized_client, test_db, monkeypatch):
    """Test tworzenia nowej sesji."""
    # Zastąp funkcję pobierania puli obrazów, aby użyła obrazów testowych
    def mock_get_initial_pool(*args, **kwargs):
        # Pobierz dostępne obrazy z bazy danych - to zapewni że użyjemy istniejących ID
        pos_images = test_db.query(Image).filter(Image.type == ImageTypeEnum.POSITIVE).limit(6).all()
        neg_images = test_db.query(Image).filter(Image.type == ImageTypeEnum.NEGATIVE).limit(6).all()

        pos_pool = [{"id": img.id, "successes": 0, "failures": 0, "origin": "random"} for img in pos_images]
        neg_pool = [{"id": img.id, "successes": 0, "failures": 0, "origin": "random"} for img in neg_images]

        return {
            "pos_pool": pos_pool,
            "neg_pool": neg_pool
        }

    import backend.sessions
    monkeypatch.setattr(backend.sessions, "get_initial_pool", mock_get_initial_pool)

    response = authorized_client.post("/api/sessions")
    assert response.status_code == 201
    # Sprawdź, czy sesja została utworzona
    data = response.json()
    assert "id" in data
    assert data["status"] == "ACTIVE"

def test_get_session(authorized_client, test_session):
    """Test pobierania sesji."""
    response = authorized_client.get(f"/sessions/{test_session.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == test_session.id
    assert data["status"] == test_session.status

def test_get_rounds(authorized_client, test_session, test_round):
    """Test pobierania rund dla sesji."""
    response = authorized_client.get(f"/sessions/{test_session.id}/rounds")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == test_round.id

def test_get_session_summary(authorized_client, test_session, test_round):
    """Test pobierania podsumowania sesji."""
    response = authorized_client.get(f"/sessions/{test_session.id}/summary")
    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == test_session.id

def test_submit_user_choice(authorized_client, test_round):
    """Test przesyłania wyboru użytkownika w rundzie."""
    choice_data = {
        "session_id": test_round.session_id, 
        "round_id": test_round.id,
        "side": "LEFT"
    }
    response = authorized_client.post(f"/rounds/choice", json=choice_data)
    assert response.status_code == 200
    data = response.json()
    assert data["round_id"] == test_round.id
    assert "result" in data

def test_stimulus_url_in_round_response(authorized_client, test_db, test_user_in_db, monkeypatch):
    """Test sprawdzający czy URL bodźca jest zwracany w odpowiedzi rundy."""
    # Tworzenie obrazu testowego
    image = Image(
        path="/test/stimulus_image.jpg",
        type=ImageTypeEnum.POSITIVE,
        embedding=[0.1] * 10,
    )
    test_db.add(image)
    test_db.commit()
    test_db.refresh(image)

    # Tworzenie struktury dla pul obrazów
    pos_pool = [{"id": image.id, "successes": 0, "failures": 0, "origin": "random"}]
    neg_pool = [{"id": image.id, "successes": 0, "failures": 0, "origin": "random"}]

    # Tworzenie sesji
    session = SessionModel(
        user_id=test_user_in_db.id,
        status="ACTIVE",
        pos_pool_json=json.dumps(pos_pool),
        neg_pool_json=json.dumps(neg_pool),
        session_profit_factor=1.0,
        remaining_pairs=6,
    )
    test_db.add(session)
    test_db.commit()
    test_db.refresh(session)

    # Tworzenie rundy
    round = Round(
        session_id=session.id,
        round_number=1,
        pos_image_id=image.id,
        neg_image_id=image.id,
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

    # Nadpisanie funkcji get_wait_for_price_change, aby nie musiała czekać na zmianę ceny
    def mock_wait_for_price_change(*args, **kwargs):
        return 50100.0, 0.002  # end_price, profit_fraction

    import backend.btc_price
    monkeypatch.setattr(backend.btc_price, "wait_for_price_change", mock_wait_for_price_change)

    # Wywołanie endpoint'u do wysłania wyboru
    choice_data = {
        "session_id": session.id, 
        "round_id": round.id,
        "side": "LEFT"
    }
    response = authorized_client.post(f"/rounds/choice", json=choice_data)
    
    assert response.status_code == 200
    data = response.json()

    # Sprawdzenie, czy URL bodźca został poprawnie zwrócony
    assert "stimulus_url" in data
    assert "token=" in data["stimulus_url"] # Token powinien być w URL