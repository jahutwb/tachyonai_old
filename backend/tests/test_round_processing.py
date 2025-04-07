import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
import json
from unittest.mock import MagicMock, patch
import random

from backend.main import app
from backend.models import User, Session as SessionModel, Round, Image, ImageTypeEnum
from backend.routers.rounds import submit_round_choice
from backend.schemas import RoundChoice

client = TestClient(app)

@pytest.fixture
def mock_db():
    """Tworzy mocka bazy danych"""
    return MagicMock()

@pytest.fixture
def mock_user():
    """Tworzy mocka użytkownika"""
    user = MagicMock()
    user.id = 1
    return user

@pytest.fixture
def mock_session(mock_user):
    """Tworzy mocka sesji"""
    session = MagicMock()
    session.id = 1
    session.user_id = mock_user.id
    session.status = "ACTIVE"
    session.session_profit_factor = 1.0
    session.remaining_pairs = 5
    session.pos_pool_json = [
        {"id": 101, "successes": 0, "failures": 0},
        {"id": 102, "successes": 0, "failures": 0},
    ]
    session.neg_pool_json = [
        {"id": 201, "successes": 0, "failures": 0},
        {"id": 202, "successes": 0, "failures": 0},
    ]
    return session

@pytest.fixture
def mock_round(mock_session):
    """Tworzy mocka rundy"""
    round_obj = MagicMock()
    round_obj.id = 1
    round_obj.session_id = mock_session.id
    round_obj.pos_image_id = 101
    round_obj.neg_image_id = 201
    round_obj.left_action = "BUY"
    round_obj.right_action = "SELL"
    round_obj.start_price = 50000.0
    return round_obj

@pytest.fixture
def mock_pos_image():
    """Tworzy mocka obrazu pozytywnego"""
    pos_image = MagicMock()
    pos_image.id = 101
    pos_image.type = ImageTypeEnum.POSITIVE
    pos_image.total_successes = 0
    pos_image.total_failures = 0
    pos_image.total_profit_factor = 1.0
    return pos_image

@pytest.fixture
def mock_neg_image():
    """Tworzy mocka obrazu negatywnego"""
    neg_image = MagicMock()
    neg_image.id = 201
    neg_image.type = ImageTypeEnum.NEGATIVE
    neg_image.total_successes = 0
    neg_image.total_failures = 0
    neg_image.total_profit_factor = 1.0
    return neg_image

def test_process_round_success(mock_db, mock_user, mock_session, mock_round, mock_pos_image, mock_neg_image):
    """Test przetwarzania rundy z wynikiem sukcesu - powinien zwiększyć liczniki sukcesów obu obrazów"""
    # Przygotowanie danych testowych
    choice = RoundChoice(session_id=mock_session.id, round_id=mock_round.id, side="LEFT")
    
    # Konfiguracja zapytań do bazy danych
    mock_db.query.return_value.filter.return_value.first.side_effect = [
        mock_round,  # pierwsze wywołanie - runda
        mock_session,  # drugie wywołanie - sesja
        mock_pos_image,  # trzecie wywołanie - obraz pozytywny
        mock_neg_image,  # czwarte wywołanie - obraz negatywny
        mock_pos_image,  # piąte wywołanie - stimulus
    ]
    
    # Symulacja zmiany ceny na pozytywną (dla akcji BUY)
    with patch('random.uniform', return_value=0.005):  # Wzrost ceny o 0.5%
        result = submit_round_choice(choice, mock_user, mock_db)
    
    # Sprawdzenie czy obrazy zostały zaktualizowane poprawnie
    assert mock_pos_image.total_successes == 1
    assert mock_neg_image.total_successes == 1
    assert mock_pos_image.total_failures == 0
    assert mock_neg_image.total_failures == 0
    
    # Sprawdzenie czy liczniki sukcesów w puli zostały zaktualizowane
    pos_pool_item = next(item for item in mock_session.pos_pool_json if item["id"] == mock_pos_image.id)
    neg_pool_item = next(item for item in mock_session.neg_pool_json if item["id"] == mock_neg_image.id)
    
    assert pos_pool_item["successes"] == 1
    assert neg_pool_item["successes"] == 1
    assert pos_pool_item.get("failures", 0) == 0
    assert neg_pool_item.get("failures", 0) == 0
    
    # Sprawdzenie czy remaining_pairs nie zostało zmniejszone
    assert mock_session.remaining_pairs == 5
    
    # Sprawdzenie czy result pokazuje SUCCESS
    assert result["result"] == "SUCCESS"

def test_process_round_failure(mock_db, mock_user, mock_session, mock_round, mock_pos_image, mock_neg_image):
    """Test przetwarzania rundy z wynikiem porażki - powinien zwiększyć liczniki porażek obu obrazów"""
    # Przygotowanie danych testowych
    choice = RoundChoice(session_id=mock_session.id, round_id=mock_round.id, side="LEFT")
    
    # Konfiguracja zapytań do bazy danych
    mock_db.query.return_value.filter.return_value.first.side_effect = [
        mock_round,  # pierwsze wywołanie - runda
        mock_session,  # drugie wywołanie - sesja
        mock_pos_image,  # trzecie wywołanie - obraz pozytywny
        mock_neg_image,  # czwarte wywołanie - obraz negatywny
        mock_neg_image,  # piąte wywołanie - stimulus
    ]
    
    # Symulacja zmiany ceny na negatywną (dla akcji BUY)
    with patch('random.uniform', return_value=-0.005):  # Spadek ceny o 0.5%
        result = submit_round_choice(choice, mock_user, mock_db)
    
    # Sprawdzenie czy obrazy zostały zaktualizowane poprawnie
    assert mock_pos_image.total_successes == 0
    assert mock_neg_image.total_successes == 0
    assert mock_pos_image.total_failures == 1
    assert mock_neg_image.total_failures == 1
    
    # Sprawdzenie czy liczniki porażek w puli zostały zaktualizowane
    pos_pool_item = next(item for item in mock_session.pos_pool_json if item["id"] == mock_pos_image.id)
    neg_pool_item = next(item for item in mock_session.neg_pool_json if item["id"] == mock_neg_image.id)
    
    assert pos_pool_item.get("successes", 0) == 0
    assert neg_pool_item.get("successes", 0) == 0
    assert pos_pool_item["failures"] == 1
    assert neg_pool_item["failures"] == 1
    
    # Sprawdzenie czy remaining_pairs zostało zmniejszone
    assert mock_session.remaining_pairs == 4
    
    # Sprawdzenie czy result pokazuje FAILURE
    assert result["result"] == "FAILURE"

def test_next_round_selection_valid_images(mock_db, mock_session):
    """Test, czy do wyboru są brane tylko obrazy z failures=0"""
    from backend.routers.rounds import get_next_round
    
    # Przygotowanie danych testowych - sesja z obrazami z różnymi licznikami porażek
    mock_session.pos_pool_json = [
        {"id": 101, "successes": 1, "failures": 0},  # powinien być brany pod uwagę 
        {"id": 102, "successes": 0, "failures": 1},  # nie powinien być brany pod uwagę
        {"id": 103, "successes": 2, "failures": 0},  # powinien być brany pod uwagę
    ]
    
    mock_session.neg_pool_json = [
        {"id": 201, "successes": 0, "failures": 0},  # powinien być brany pod uwagę
        {"id": 202, "successes": 1, "failures": 1},  # nie powinien być brany pod uwagę
        {"id": 203, "successes": 3, "failures": 0},  # powinien być brany pod uwagę
    ]
    
    # Przygotowanie mocków obrazów
    pos_image_101 = MagicMock()
    pos_image_101.id = 101
    pos_image_103 = MagicMock()
    pos_image_103.id = 103
    
    neg_image_201 = MagicMock()
    neg_image_201.id = 201
    neg_image_203 = MagicMock()
    neg_image_203.id = 203
    
    # Konfiguracja zapytań do bazy danych
    mock_db.query.return_value.filter.return_value.first.return_value = mock_session
    mock_db.query.return_value.filter.return_value.count.return_value = 3
    
    # Mockowanie wyboru obrazów z bazy danych
    with patch('random.choice') as mock_choice:
        # Pierwszy wybór to obraz pozytywny 101, drugi to negatywny 201
        mock_choice.side_effect = [
            {"id": 101, "successes": 1, "failures": 0},  # wybieramy pozytywny z failures=0
            {"id": 201, "successes": 0, "failures": 0}   # wybieramy negatywny z failures=0
        ]
        
        # Mockowanie zapytań do bazy danych dla pobrania obrazów
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            mock_session,  # pierwsze wywołanie - sesja
            pos_image_101,  # obraz pozytywny
            neg_image_201   # obraz negatywny
        ]
        
        # Uruchomienie funkcji
        with patch('backend.routers.rounds.random.choice') as mock_random_choice:
            mock_random_choice.side_effect = ["BUY", {"id": 101}, {"id": 201}]
            result = get_next_round(1, mock_user, mock_db)
        
        # Sprawdzenie, czy wybrane zostały tylko obrazy z failures=0
        mock_choice.assert_any_call([
            {"id": 101, "successes": 1, "failures": 0},
            {"id": 103, "successes": 2, "failures": 0}
        ])
        
        mock_choice.assert_any_call([
            {"id": 201, "successes": 0, "failures": 0},
            {"id": 203, "successes": 3, "failures": 0}
        ]) 