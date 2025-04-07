from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import random
import logging
import traceback
from sqlalchemy.sql import func

from ..database import get_db
from ..models import User, Session as SessionModel, Round, Image, ImageTypeEnum
from .. import schemas
from ..auth import get_current_user

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/rounds/next", response_model=schemas.RoundCreate)
def get_next_round(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Pobiera następną rundę dla sesji o podanym ID."""
    try:
        logger.info(f"Pobieranie następnej rundy dla sesji {session_id}")
        
        # Sprawdź czy sesja istnieje i należy do bieżącego użytkownika
        session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
        if not session:
            logger.warning(f"Sesja {session_id} nie znaleziona")
            raise HTTPException(status_code=404, detail="Sesja nie znaleziona")
        if session.user_id != current_user.id:
            logger.warning(f"Brak dostępu do sesji {session_id} dla użytkownika {current_user.id}")
            raise HTTPException(status_code=403, detail="Brak dostępu do tej sesji")
        
        # Sprawdź, czy sesja jest aktywna
        if session.status != "ACTIVE":
            logger.warning(f"Sesja {session_id} nie jest aktywna - status: {session.status}")
            raise HTTPException(status_code=400, detail="Sesja nie jest aktywna")
        
        # Sprawdź, czy pozostały jeszcze pary do rozegrania
        if session.remaining_pairs <= 0:
            logger.warning(f"Brak dostępnych par w sesji {session_id}")
            raise HTTPException(status_code=400, detail="Brak dostępnych par w sesji")
        
        # Pobierz liczbę rund w sesji, aby ustalić numer rundy
        round_count = db.query(Round).filter(Round.session_id == session_id).count()
        round_number = round_count + 1
        logger.info(f"Tworzenie rundy numer {round_number} dla sesji {session_id}")
        
        # Pobierz obrazy do rundy
        try:
            # Uproszczona logika wyboru obrazów - w prawdziwej aplikacji będzie bardziej skomplikowana
            # Pobierz losowy obraz pozytywny i negatywny
            pos_images = db.query(Image).filter(Image.type == ImageTypeEnum.POSITIVE).limit(100).all()
            neg_images = db.query(Image).filter(Image.type == ImageTypeEnum.NEGATIVE).limit(100).all()
            
            if not pos_images or not neg_images:
                logger.error(f"Brak dostępnych obrazów w bazie danych")
                raise HTTPException(status_code=500, detail="Brak dostępnych obrazów")
            
            pos_image = random.choice(pos_images)
            neg_image = random.choice(neg_images)
            
            logger.info(f"Wybrano obrazy: pos_id={pos_image.id}, neg_id={neg_image.id}")
        except Exception as e:
            logger.error(f"Błąd podczas wyboru obrazów: {str(e)}")
            logger.error(traceback.format_exc())
            raise HTTPException(status_code=500, detail=f"Błąd podczas wyboru obrazów: {str(e)}")
        
        # Losowanie, która strona to kupno (BUY), a która sprzedaż (SELL)
        left_action = random.choice(["BUY", "SELL"])
        right_action = "SELL" if left_action == "BUY" else "BUY"
        logger.info(f"Przypisane akcje: left={left_action}, right={right_action}")
        
        # Utwórz nową rundę
        try:
            new_round = Round(
                session_id=session_id,
                round_number=round_number,
                pos_image_id=pos_image.id,
                neg_image_id=neg_image.id,
                start_price=50000.0,  # Przykładowa wartość
                left_action=left_action,
                right_action=right_action
            )
            
            db.add(new_round)
            db.commit()
            db.refresh(new_round)
            logger.info(f"Utworzono nową rundę id={new_round.id} dla sesji {session_id}")
            
            return new_round
        except Exception as db_error:
            logger.error(f"Błąd bazy danych podczas tworzenia rundy: {str(db_error)}")
            logger.error(traceback.format_exc())
            db.rollback()
            raise HTTPException(status_code=500, detail=f"Błąd bazy danych: {str(db_error)}")
            
    except HTTPException:
        # Przepuść wyjątki HTTPException, aby zachować ich szczegóły
        raise
    except Exception as e:
        logger.error(f"Nieoczekiwany błąd w get_next_round: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Nieoczekiwany błąd: {str(e)}")


@router.post("/rounds/choice", response_model=schemas.RoundResult)
def submit_round_choice(
    choice: schemas.RoundChoice,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Przetwarza wybór użytkownika w rundzie i zwraca wynik."""
    try:
        logger.info(f"Przetwarzanie wyboru dla rundy {choice.round_id}, sesji {choice.session_id}, strona: {choice.side}")
        
        # Sprawdź, czy runda istnieje
        round_obj = db.query(Round).filter(Round.id == choice.round_id).first()
        if not round_obj:
            logger.warning(f"Runda {choice.round_id} nie znaleziona")
            raise HTTPException(status_code=404, detail="Runda nie znaleziona")
        
        # Sprawdź, czy sesja należy do bieżącego użytkownika
        session = db.query(SessionModel).filter(SessionModel.id == round_obj.session_id).first()
        if not session or session.user_id != current_user.id:
            logger.warning(f"Brak dostępu do rundy {choice.round_id} dla użytkownika {current_user.id}")
            raise HTTPException(status_code=403, detail="Brak dostępu do tej rundy")
        
        # Określ akcję użytkownika na podstawie strony i przypisanej akcji
        if choice.side == "LEFT":
            user_action = round_obj.left_action
        else:  # RIGHT
            user_action = round_obj.right_action
            
        logger.info(f"Wybrana akcja: {user_action} (strona: {choice.side})")
        
        start_price = round_obj.start_price
        
        # Dla uproszczenia, losowo generujemy zmianę ceny
        price_change = random.uniform(-0.01, 0.01)  # +/- 1%
        end_price = start_price * (1 + price_change)
        logger.info(f"Zmiana ceny: {price_change:.6f}, start_price: {start_price}, end_price: {end_price}")
        
        # Obliczanie zysku
        if (user_action == "BUY" and price_change > 0) or (user_action == "SELL" and price_change < 0):
            result = "SUCCESS"
            profit_fraction = abs(price_change)
            # Obrazek pozytywny
            stimulus_id = round_obj.pos_image_id
            logger.info(f"SUKCES! profit_fraction: {profit_fraction:.6f}, wyświetlam pozytywny bodziec (id: {stimulus_id})")
            
            # Pobierz obiekty obrazów
            pos_image = db.query(Image).filter(Image.id == round_obj.pos_image_id).first()
            neg_image = db.query(Image).filter(Image.id == round_obj.neg_image_id).first()
            
            if pos_image:
                logger.info(f"Aktualizuję obraz pozytywny (id: {pos_image.id}): successes: {pos_image.total_successes} -> {pos_image.total_successes + 1}, profit_factor: {pos_image.total_profit_factor:.6f} -> {pos_image.total_profit_factor * (1 + profit_fraction):.6f}")
                # Aktualizuj liczniki dla obrazu pozytywnego (wyświetlony w przypadku sukcesu)
                pos_image.total_successes += 1
                pos_image.total_profit_factor *= (1 + profit_fraction)
                
                # Aktualizuj pole pos_pool_json w sesji
                if session.pos_pool_json:
                    pos_pool = session.pos_pool_json
                    for item in pos_pool:
                        if item["id"] == pos_image.id:
                            old_successes = item.get("successes", 0)
                            item["successes"] = old_successes + 1
                            logger.info(f"Aktualizuję pos_pool_json dla obrazu {pos_image.id}: successes {old_successes} -> {item['successes']}")
                            break
                    session.pos_pool_json = pos_pool
            
            if neg_image:
                logger.info(f"Aktualizuję obraz negatywny (przetrwanie) (id: {neg_image.id}): successes: {neg_image.total_successes} -> {neg_image.total_successes + 1}, profit_factor: {neg_image.total_profit_factor:.6f} -> {neg_image.total_profit_factor * (1 + profit_fraction):.6f}")
                # Negatywny obraz przetrwał rundę (nie został wyświetlony)
                neg_image.total_successes += 1
                neg_image.total_profit_factor *= (1 + profit_fraction)
                
                # Aktualizuj pole neg_pool_json w sesji
                if session.neg_pool_json:
                    neg_pool = session.neg_pool_json
                    for item in neg_pool:
                        if item["id"] == neg_image.id:
                            old_successes = item.get("successes", 0)
                            item["successes"] = old_successes + 1
                            logger.info(f"Aktualizuję neg_pool_json dla obrazu {neg_image.id}: successes {old_successes} -> {item['successes']}")
                            break
                    session.neg_pool_json = neg_pool
        else:
            result = "FAILURE"
            profit_fraction = -abs(price_change)
            # Obrazek negatywny
            stimulus_id = round_obj.neg_image_id
            logger.info(f"PORAŻKA! profit_fraction: {profit_fraction:.6f}, wyświetlam negatywny bodziec (id: {stimulus_id})")
            # Zmniejsz pozostałe pary tylko w przypadku porażki
            logger.info(f"Zmniejszam remaining_pairs: {session.remaining_pairs} -> {session.remaining_pairs - 1}")
            session.remaining_pairs -= 1
            
            # Pobierz obiekty obrazów
            pos_image = db.query(Image).filter(Image.id == round_obj.pos_image_id).first()
            neg_image = db.query(Image).filter(Image.id == round_obj.neg_image_id).first()
            
            if pos_image:
                logger.info(f"Aktualizuję obraz pozytywny (porażka) (id: {pos_image.id}): failures: {pos_image.total_failures} -> {pos_image.total_failures + 1}, profit_factor: {pos_image.total_profit_factor:.6f} -> {pos_image.total_profit_factor * (1 + profit_fraction):.6f}")
                # Aktualizuj liczniki dla obrazu pozytywnego (nie wyświetlony w przypadku porażki)
                pos_image.total_failures += 1
                pos_image.total_profit_factor *= (1 + profit_fraction)
                
                # Aktualizuj pole pos_pool_json w sesji
                if session.pos_pool_json:
                    pos_pool = session.pos_pool_json
                    for item in pos_pool:
                        if item["id"] == pos_image.id:
                            old_failures = item.get("failures", 0)
                            item["failures"] = old_failures + 1
                            logger.info(f"Aktualizuję pos_pool_json dla obrazu {pos_image.id}: failures {old_failures} -> {item['failures']}")
                            break
                    session.pos_pool_json = pos_pool
            
            if neg_image:
                logger.info(f"Aktualizuję obraz negatywny (wyświetlony) (id: {neg_image.id}): failures: {neg_image.total_failures} -> {neg_image.total_failures + 1}, profit_factor: {neg_image.total_profit_factor:.6f} -> {neg_image.total_profit_factor * (1 + profit_fraction):.6f}")
                # Aktualizuj liczniki dla obrazu negatywnego (wyświetlony w przypadku porażki)
                neg_image.total_failures += 1
                neg_image.total_profit_factor *= (1 + profit_fraction)
                
                # Aktualizuj pole neg_pool_json w sesji
                if session.neg_pool_json:
                    neg_pool = session.neg_pool_json
                    for item in neg_pool:
                        if item["id"] == neg_image.id:
                            old_failures = item.get("failures", 0)
                            item["failures"] = old_failures + 1
                            logger.info(f"Aktualizuję neg_pool_json dla obrazu {neg_image.id}: failures {old_failures} -> {item['failures']}")
                            break
                    session.neg_pool_json = neg_pool
            
            # W przypadku porażki usuwamy obie pary z puli (nie zmieniamy JSON, tylko flagę remaining_pairs)
        
        # Aktualizacja rundy
        round_obj.user_choice_side = choice.side
        round_obj.user_action = user_action
        round_obj.end_price = end_price
        round_obj.profit_fraction = profit_fraction
        round_obj.result = result
        round_obj.completed_at = func.now()
        
        # Aktualizacja sesji
        old_profit_factor = session.session_profit_factor
        session.session_profit_factor *= (1 + profit_fraction)
        logger.info(f"Aktualizuję session_profit_factor: {old_profit_factor:.6f} -> {session.session_profit_factor:.6f}")
        
        if session.remaining_pairs <= 0:
            logger.info(f"Sesja {session.id} zakończona (remaining_pairs = 0), ustawiam status=COMPLETED")
            session.status = "COMPLETED"
            session.ended_at = func.now()
        
        # Zapisz wszystkie zmiany do bazy danych
        db.commit()
        db.refresh(round_obj)
        db.refresh(session)
        if pos_image:
            db.refresh(pos_image)
        if neg_image:
            db.refresh(neg_image)
        
        # Zwróć URL obrazka bodźca
        stimulus = db.query(Image).filter(Image.id == stimulus_id).first()
        stimulus_url = f"/api/images/{stimulus_id}/thumbnail" if stimulus else None
        
        logger.info(f"Zakończono rundę {round_obj.id} z wynikiem {result}, profit_fraction={profit_fraction:.6f}, stimulus_url={stimulus_url}")
        
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
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Błąd w submit_round_choice: {str(e)}")
        logger.error(traceback.format_exc())
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Błąd przetwarzania wyboru: {str(e)}") 