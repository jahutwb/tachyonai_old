from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import random

from ..database import get_db
from ..models import User, Session as SessionModel, Round, Image, ImageTypeEnum
from .. import schemas
from ..auth import get_current_user

router = APIRouter()


@router.get("/rounds/next", response_model=schemas.RoundCreate)
def get_next_round(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Pobiera następną rundę dla sesji o podanym ID."""
    # Sprawdź czy sesja istnieje i należy do bieżącego użytkownika
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Sesja nie znaleziona")
    if session.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Brak dostępu do tej sesji")
    
    # Sprawdź, czy sesja jest aktywna
    if session.status != "ACTIVE":
        raise HTTPException(status_code=400, detail="Sesja nie jest aktywna")
    
    # Sprawdź, czy pozostały jeszcze pary do rozegrania
    if session.remaining_pairs <= 0:
        raise HTTPException(status_code=400, detail="Brak dostępnych par w sesji")
    
    # Pobierz liczbę rund w sesji, aby ustalić numer rundy
    round_count = db.query(Round).filter(Round.session_id == session_id).count()
    round_number = round_count + 1
    
    # Uproszczona logika wyboru obrazów - w prawdziwej aplikacji będzie bardziej skomplikowana
    # Pobierz losowy obraz pozytywny i negatywny
    pos_images = db.query(Image).filter(Image.type == ImageTypeEnum.POSITIVE).limit(100).all()
    neg_images = db.query(Image).filter(Image.type == ImageTypeEnum.NEGATIVE).limit(100).all()
    
    if not pos_images or not neg_images:
        raise HTTPException(status_code=500, detail="Brak dostępnych obrazów")
    
    pos_image = random.choice(pos_images)
    neg_image = random.choice(neg_images)
    
    # Utwórz nową rundę
    new_round = Round(
        session_id=session_id,
        round_number=round_number,
        pos_image_id=pos_image.id,
        neg_image_id=neg_image.id,
        start_price=50000.0,  # Przykładowa wartość
    )
    
    db.add(new_round)
    db.commit()
    db.refresh(new_round)
    
    return new_round


@router.post("/rounds/choice", response_model=schemas.RoundResult)
def submit_round_choice(
    choice: schemas.RoundChoice,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Przetwarza wybór użytkownika w rundzie i zwraca wynik."""
    # Sprawdź, czy runda istnieje
    round_obj = db.query(Round).filter(Round.id == choice.round_id).first()
    if not round_obj:
        raise HTTPException(status_code=404, detail="Runda nie znaleziona")
    
    # Sprawdź, czy sesja należy do bieżącego użytkownika
    session = db.query(SessionModel).filter(SessionModel.id == round_obj.session_id).first()
    if not session or session.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Brak dostępu do tej rundy")
    
    # Uproszczona logika przetwarzania wyboru - w prawdziwej aplikacji będzie bardziej skomplikowana
    # Symulujemy zmiany ceny i obliczamy zysk
    user_action = "BUY" if choice.side == "LEFT" else "SELL"
    start_price = round_obj.start_price
    
    # Dla uproszczenia, losowo generujemy zmianę ceny
    price_change = random.uniform(-0.01, 0.01)  # +/- 1%
    end_price = start_price * (1 + price_change)
    
    # Obliczanie zysku
    if (user_action == "BUY" and price_change > 0) or (user_action == "SELL" and price_change < 0):
        result = "SUCCESS"
        profit_fraction = abs(price_change)
        # Obrazek pozytywny
        stimulus_id = round_obj.pos_image_id
    else:
        result = "FAILURE"
        profit_fraction = -abs(price_change)
        # Obrazek negatywny
        stimulus_id = round_obj.neg_image_id
    
    # Aktualizacja rundy
    round_obj.user_choice_side = choice.side
    round_obj.user_action = user_action
    round_obj.end_price = end_price
    round_obj.profit_fraction = profit_fraction
    round_obj.result = result
    
    # Aktualizacja sesji
    session.session_profit_factor *= (1 + profit_fraction)
    session.remaining_pairs -= 1
    
    if session.remaining_pairs <= 0:
        session.status = "COMPLETED"
    
    db.commit()
    db.refresh(round_obj)
    
    # Zwróć URL obrazka bodźca
    stimulus = db.query(Image).filter(Image.id == stimulus_id).first()
    stimulus_url = f"/api/images/{stimulus_id}/thumbnail" if stimulus else None
    
    return {
        "round_id": round_obj.id,
        "session_id": round_obj.session_id,
        "start_price": round_obj.start_price,
        "end_price": round_obj.end_price,
        "profit_fraction": round_obj.profit_fraction,
        "result": round_obj.result,
        "remaining_pairs": session.remaining_pairs,
        "session_profit_factor": session.session_profit_factor,
        "stimulus_url": stimulus_url
    } 