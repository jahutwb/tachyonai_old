from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import random
import logging
import traceback
import json
from sqlalchemy.sql import func
from typing import Dict, List, Optional

from ..database import get_db
from ..models import User, Session as SessionModel, Round, Image, ImageTypeEnum
from .. import schemas
from ..auth import get_current_user
from ..routers.sessions import generate_pool_with_genetic_algorithm

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

        logger.info(f"Stan sesji {session_id} po pobraniu z bazy:")
        logger.info(f"Status: {session.status}")
        logger.info(f"Remaining pairs: {session.remaining_pairs}")
        logger.info(f"Pos pool: {[(item['id'], item.get('failures', 0), item.get('successes', 0)) for item in session.pos_pool_json]}")
        logger.info(f"Neg pool: {[(item['id'], item.get('failures', 0), item.get('successes', 0)) for item in session.neg_pool_json]}")

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
        
        try:
            # Filtruj pule obrazów - tylko failures=0
            try:
                # Bezpieczne przetwarzanie JSON
                pos_pool_json = json.loads(session.pos_pool_json) if isinstance(session.pos_pool_json, str) else session.pos_pool_json
                neg_pool_json = json.loads(session.neg_pool_json) if isinstance(session.neg_pool_json, str) else session.neg_pool_json
                
                # Zabezpieczenie przed None
                if pos_pool_json is None:
                    pos_pool_json = []
                if neg_pool_json is None:
                    neg_pool_json = []
                    
                valid_pos_pool = [item for item in pos_pool_json if item.get("failures", 0) == 0]
                valid_neg_pool = [item for item in neg_pool_json if item.get("failures", 0) == 0]
            except Exception as json_error:
                logger.error(f"Błąd przetwarzania JSON: {str(json_error)}")
                valid_pos_pool = []
                valid_neg_pool = []

            logger.info(f"Stan pul po filtrowaniu (tylko failures=0):")
            logger.info(f"Pozytywne: {[(item['id'], item.get('failures', 0)) for item in valid_pos_pool]}")
            logger.info(f"Negatywne: {[(item['id'], item.get('failures', 0)) for item in valid_neg_pool]}")

            # Sprawdź, czy są dostępne pary obrazów
            if not valid_pos_pool or not valid_neg_pool:
                logger.warning(f"Brak dostępnych par obrazów w sesji {session_id}")
                # Zakończ sesję, jeśli nie ma dostępnych par
                session.status = "COMPLETED"
                session.remaining_pairs = 0
                session.ended_at = func.now()
                db.commit()
                raise HTTPException(
                    status_code=400,
                    detail="Brak dostępnych par obrazów w sesji. Sesja została zakończona."
                )
                
            # Wybierz losowy obraz z przefiltrowanych pul
            pos_item = random.choice(valid_pos_pool)
            neg_item = random.choice(valid_neg_pool)
            
            # Pobierz obiekty obrazów z bazy danych
            pos_image = db.query(Image).filter(Image.id == pos_item["id"]).first()
            neg_image = db.query(Image).filter(Image.id == neg_item["id"]).first()
            
            if not pos_image or not neg_image:
                logger.error(f"Nie znaleziono obrazów w bazie danych: pos_id={pos_item['id']}, neg_id={neg_item['id']}")
                raise HTTPException(status_code=500, detail="Nieprawidłowe referencje obrazów w puli")
            
            logger.info(f"Wybrano obrazy z puli (failures=0): pos_id={pos_image.id}, neg_id={neg_image.id}")
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Błąd podczas wyboru obrazów z puli: {str(e)}")
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
            
            return {
                "id": new_round.id,
                "session_id": new_round.session_id,
                "round_number": new_round.round_number,
                "pos_image_id": new_round.pos_image_id,
                "neg_image_id": new_round.neg_image_id,
                "start_price": new_round.start_price,
                "left_action": new_round.left_action,
                "right_action": new_round.right_action,
                "created_at": new_round.created_at
            }
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
        logger.info(f"Przetwarzanie wyboru dla rundy {choice.round_id}, sesji {choice.session_id}")
        
        # Sprawdź, czy runda istnieje
        round_obj = db.query(Round).filter(Round.id == choice.round_id).first()
        if not round_obj:
            raise HTTPException(status_code=404, detail="Runda nie znaleziona")
        
        # Sprawdź, czy sesja należy do bieżącego użytkownika
        session = db.query(SessionModel).filter(SessionModel.id == round_obj.session_id).first()
        if not session or session.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Brak dostępu do tej rundy")
        
        # Określ akcję użytkownika
        user_action = round_obj.left_action if choice.side == "LEFT" else round_obj.right_action
        
        # Symulacja zmiany ceny
        price_change = random.uniform(-0.01, 0.01)
        end_price = round_obj.start_price * (1 + price_change)
        
        # Przygotuj kopie JSON-ów z puli
        try:
            pos_pool = json.loads(session.pos_pool_json) if isinstance(session.pos_pool_json, str) else session.pos_pool_json
            neg_pool = json.loads(session.neg_pool_json) if isinstance(session.neg_pool_json, str) else session.neg_pool_json
            
            # Zabezpieczenie przed None
            if pos_pool is None:
                pos_pool = []
            if neg_pool is None:
                neg_pool = []
                
            logger.info("Stan pul przed aktualizacją:")
            logger.info(f"Pozytywna: {[(i['id'], i.get('failures', 0), i.get('successes', 0)) for i in pos_pool]}")
            logger.info(f"Negatywna: {[(i['id'], i.get('failures', 0), i.get('successes', 0)) for i in neg_pool]}")
        except Exception as e:
            logger.error(f"Błąd przy odczycie JSON pool: {str(e)}")
            pos_pool = []
            neg_pool = []
        
        # Oblicz wynik i zaktualizuj pule
        if (user_action == "BUY" and price_change > 0) or (user_action == "SELL" and price_change < 0):
            result = "SUCCESS"
            profit_fraction = abs(price_change)
            stimulus_id = round_obj.pos_image_id
            
            # Aktualizuj successes dla obu obrazów w pulach
            for item in pos_pool:
                if item["id"] == round_obj.pos_image_id:
                    item["successes"] = item.get("successes", 0) + 1
                    logger.info(f"SUCCESS: Zwiększam successes dla pos_image {item['id']}: {item['successes']}")
            
            for item in neg_pool:
                if item["id"] == round_obj.neg_image_id:
                    item["successes"] = item.get("successes", 0) + 1
                    logger.info(f"SUCCESS: Zwiększam successes dla neg_image {item['id']}: {item['successes']}")
        else:
            result = "FAILURE"
            profit_fraction = -abs(price_change)
            stimulus_id = round_obj.neg_image_id
            
            # Aktualizuj failures dla obu obrazów w pulach
            for item in pos_pool:
                if item["id"] == round_obj.pos_image_id:
                    item["failures"] = item.get("failures", 0) + 1
                    logger.info(f"FAILURE: Zwiększam failures dla pos_image {item['id']}: {item['failures']}")
            
            for item in neg_pool:
                if item["id"] == round_obj.neg_image_id:
                    item["failures"] = item.get("failures", 0) + 1
                    logger.info(f"FAILURE: Zwiększam failures dla neg_image {item['id']}: {item['failures']}")
            
            # Nie zmniejszamy już ręcznie remaining_pairs, będzie to obliczone później dynamicznie
        
        logger.info("Stan pul po aktualizacji:")
        logger.info(f"Pozytywna: {[(i['id'], i.get('failures', 0), i.get('successes', 0)) for i in pos_pool]}")
        logger.info(f"Negatywna: {[(i['id'], i.get('failures', 0), i.get('successes', 0)) for i in neg_pool]}")
        
        # Aktualizuj sesję - wymuszamy wykrycie zmian w polach JSON
        session.session_profit_factor *= (1 + profit_fraction)
        
        # Aktualizujemy pola JSON w sesji - bezpośrednie przypisanie
        session.pos_pool_json = pos_pool
        session.neg_pool_json = neg_pool
        
        # Oznaczamy pola jako zmodyfikowane
        from sqlalchemy.orm import attributes
        attributes.flag_modified(session, "pos_pool_json")
        attributes.flag_modified(session, "neg_pool_json")
        
        # Sprawdź liczbę dostępnych par (liczba obrazów z failures=0)
        valid_pos_pool = [item for item in pos_pool if item.get("failures", 0) == 0]
        valid_neg_pool = [item for item in neg_pool if item.get("failures", 0) == 0]
        
        available_pairs = min(len(valid_pos_pool), len(valid_neg_pool))
        logger.info(f"Dostępne pary po aktualizacji: {available_pairs} (valid_pos: {len(valid_pos_pool)}, valid_neg: {len(valid_neg_pool)})")
        
        # Aktualizuj remaining_pairs na podstawie rzeczywistej liczby dostępnych par
        session.remaining_pairs = available_pairs
        
        # Zakończ sesję, tylko jeśli nie ma dostępnych par
        if available_pairs <= 0:
            session.status = "COMPLETED"
            session.ended_at = func.now()
            logger.info(f"Kończę sesję {session.id} - brak dostępnych par")
            
            # Automatycznie rozpocznij generowanie nowej puli w tle
            try:
                logger.info(f"Rozpoczynam automatyczne generowanie nowej puli dla użytkownika {current_user.id}")
                pos_pool_json, neg_pool_json = generate_pool_with_genetic_algorithm(session, db)
                
                # Tworzę nową sesję PENDING z wygenerowaną pulą
                new_session = SessionModel(
                    user_id=current_user.id,
                    status="PENDING",
                    pos_pool_json=pos_pool_json,
                    neg_pool_json=neg_pool_json,
                    session_profit_factor=1.0,
                    remaining_pairs=6,
                    started_at=None  # Zostanie ustawione przy aktywacji
                )
                
                db.add(new_session)
                logger.info(f"Utworzono nową sesję PENDING (id={new_session.id}) dla użytkownika {current_user.id}")
            except Exception as e:
                logger.error(f"Błąd podczas automatycznego generowania nowej puli: {str(e)}")
                logger.error(traceback.format_exc())
        
        # Zapisz wszystkie zmiany w jednej transakcji
        db.commit()
        
        # Odśwież wszystkie obiekty
        db.refresh(session)
        db.refresh(round_obj)
        
        # Aktualizuj statystyki obrazów w bazie
        pos_image = db.query(Image).filter(Image.id == round_obj.pos_image_id).first()
        neg_image = db.query(Image).filter(Image.id == round_obj.neg_image_id).first()
        
        if result == "SUCCESS":
            pos_image.total_successes += 1
            neg_image.total_successes += 1
        else:
            pos_image.total_failures += 1
            neg_image.total_failures += 1
        
        pos_image.total_profit_factor *= (1 + profit_fraction)
        neg_image.total_profit_factor *= (1 + profit_fraction)
        
        # Aktualizuj rundę
        round_obj.user_choice_side = choice.side
        round_obj.user_action = user_action
        round_obj.end_price = end_price
        round_obj.profit_fraction = profit_fraction
        round_obj.result = result
        round_obj.completed_at = func.now()
        
        # Zapisz zmiany w rundzie
        db.commit()
        db.refresh(round_obj)
        
        # Pobierz URL obrazka bodźca
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
            "stimulus_url": stimulus_url,
            "left_action": round_obj.left_action,
            "right_action": round_obj.right_action
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Błąd w submit_round_choice: {str(e)}")
        logger.error(traceback.format_exc())
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Błąd przetwarzania wyboru: {str(e)}") 