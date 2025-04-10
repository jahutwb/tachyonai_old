from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from typing import List, Any, Dict, Tuple, Optional
from sqlalchemy.orm import Session
import traceback
import logging
import numpy as np
import random
import json
from datetime import datetime

from ..database import get_db
from ..models import User, Session as SessionModel, Round, Image
from .. import schemas
from ..auth import get_current_user
from ..schemas import SessionResponse
from ..genetic_pool import generate_pool_with_genetic_algorithm, get_random_pool, calculate_centroid, PoolImageItem
from ..embedding import find_nearest_image

router = APIRouter()
logger = logging.getLogger(__name__)


def get_last_completed_session(db: Session, user_id: int) -> Optional[SessionModel]:
    """
    Pobiera ostatnią zakończoną sesję użytkownika.
    
    Args:
        db: Sesja bazy danych
        user_id: ID użytkownika
    
    Returns:
        Ostatnia zakończona sesja lub None, jeśli nie ma żadnej
    """
    return db.query(SessionModel).filter(
        SessionModel.user_id == user_id,
        SessionModel.status == "COMPLETED"
    ).order_by(SessionModel.ended_at.desc()).first()


@router.post("/sessions", response_model=schemas.SessionCreateResponse, status_code=status.HTTP_200_OK)
def create_session(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """
    Sprawdza status sesji użytkownika i zwraca odpowiednią informację.
    Logika:
    1. Sprawdza czy istnieje jakakolwiek sesja użytkownika - jeśli nie, tworzy nową z losową pulą
    2. Sprawdza czy istnieje aktywna sesja - jeśli tak, zwraca informację o niej
    3. Sprawdza czy istnieje sesja PENDING - jeśli tak, aktywuje ją
    4. Sprawdza czy istnieje zakończona sesja - jeśli tak, tworzy nową z pulą generowaną algorytmem quasi-genetycznym
    """
    try:
        # Sprawdź czy istnieje jakakolwiek sesja dla użytkownika
        any_session = db.query(SessionModel).filter(
            SessionModel.user_id == current_user.id
        ).first()
        
        # 1. Jeśli nie ma żadnej sesji, tworzymy nową z losową pulą
        if not any_session:
            logger.info(f"Brak jakiejkolwiek sesji dla użytkownika {current_user.id}, tworzenie nowej z losową pulą")
            pos_pool_json, neg_pool_json = get_random_pool(db, 6)
            
            # Dodatkowe zabezpieczenie przed nieprawidłowymi danymi JSON
            if not pos_pool_json or not neg_pool_json:
                logger.warning("Pule obrazów są puste, używam pustych list")
                pos_pool_json = []
                neg_pool_json = []
            
            new_session = SessionModel(
                user_id=current_user.id,
                status="ACTIVE",
                pos_pool_json=pos_pool_json,
                neg_pool_json=neg_pool_json,
                session_profit_factor=1.0,
                remaining_pairs=6,
                started_at=datetime.utcnow()
            )
            db.add(new_session)
            db.commit()
            db.refresh(new_session)
            
            # Zwróć informacje o nowej sesji
            return {
                "session_exists": True,
                "session_status": "ACTIVE",
                "session_id": new_session.id,
                "has_unfinished_round": False,
                "unfinished_round_id": None,
                "session_stats": {
                    "success_count": 0,
                    "failure_count": 0,
                    "success_rate": 0,
                    "profit_factor": 1.0,
                    "remaining_pairs": new_session.remaining_pairs
                }
            }
        
        # 2. Sprawdź czy istnieje aktywna sesja
        active_session = db.query(SessionModel).filter(
            SessionModel.user_id == current_user.id,
            SessionModel.status == "ACTIVE"
        ).first()
        
        if active_session:
            logger.info(f"Znaleziono aktywną sesję {active_session.id} dla użytkownika {current_user.id}")
            
            # Sprawdź, czy są jakieś niedokończone rundy
            unfinished_round = db.query(Round).filter(
                Round.session_id == active_session.id,
                Round.result == None
            ).order_by(Round.id.desc()).first()
            
            # Obliczyć statystyki sesji
            pos_pool_json = active_session.pos_pool_json if isinstance(active_session.pos_pool_json, list) else json.loads(active_session.pos_pool_json)
            neg_pool_json = active_session.neg_pool_json if isinstance(active_session.neg_pool_json, list) else json.loads(active_session.neg_pool_json)
            
            success_count = sum(item.get("successes", 0) for item in pos_pool_json) + sum(item.get("successes", 0) for item in neg_pool_json)
            failure_count = sum(item.get("failures", 0) for item in pos_pool_json) + sum(item.get("failures", 0) for item in neg_pool_json)
            
            return {
                "session_exists": True,
                "session_status": "ACTIVE",
                "session_id": active_session.id,
                "has_unfinished_round": unfinished_round is not None,
                "unfinished_round_id": unfinished_round.id if unfinished_round else None,
                "session_stats": {
                    "success_count": success_count,
                    "failure_count": failure_count,
                    "success_rate": success_count / (success_count + failure_count) * 100 if (success_count + failure_count) > 0 else 0,
                    "profit_factor": active_session.session_profit_factor,
                    "remaining_pairs": active_session.remaining_pairs
                }
            }
            
        # 3. Sprawdź czy istnieje sesja PENDING
        pending_session = db.query(SessionModel).filter(
            SessionModel.user_id == current_user.id,
            SessionModel.status == "PENDING"
        ).first()
        
        if pending_session:
            logger.info(f"Znaleziono sesję PENDING {pending_session.id} dla użytkownika {current_user.id}, aktywuję ją")
            
            # Aktywuj sesję PENDING
            pending_session.status = "ACTIVE"
            pending_session.started_at = datetime.utcnow()
            db.commit()
            db.refresh(pending_session)
            
            # Obliczyć statystyki dla nowej puli
            pos_pool_json = pending_session.pos_pool_json if isinstance(pending_session.pos_pool_json, list) else json.loads(pending_session.pos_pool_json)
            neg_pool_json = pending_session.neg_pool_json if isinstance(pending_session.neg_pool_json, list) else json.loads(pending_session.neg_pool_json)
            
            # Zwróć informacje o aktywowanej sesji
            return {
                "session_exists": True,
                "session_status": "ACTIVE",
                "session_id": pending_session.id,
                "has_unfinished_round": False,
                "unfinished_round_id": None,
                "session_stats": {
                    "success_count": 0,
                    "failure_count": 0,
                    "success_rate": 0,
                    "profit_factor": 1.0,
                    "remaining_pairs": pending_session.remaining_pairs
                }
            }
        
        # 4. Jeśli nie ma aktywnej ani oczekującej sesji, ale istnieje zakończona, tworzymy nową z pulą generowaną algorytmem
        completed_session = get_last_completed_session(db, current_user.id)
        
        if completed_session:
            logger.info(f"Znaleziono zakończoną sesję {completed_session.id}, generuję nową pulę algorytmem quasi-genetycznym")
            pos_pool_json, neg_pool_json = generate_pool_with_genetic_algorithm(completed_session, db)
            
            # Dodatkowe zabezpieczenie przed nieprawidłowymi danymi JSON
            if not pos_pool_json or not neg_pool_json:
                logger.warning("Pule obrazów są puste, używam pustych list")
                pos_pool_json = []
                neg_pool_json = []
            
            new_session = SessionModel(
                user_id=current_user.id,
                status="ACTIVE",
                pos_pool_json=pos_pool_json,
                neg_pool_json=neg_pool_json,
                session_profit_factor=1.0,
                remaining_pairs=6,
                started_at=datetime.utcnow()
            )
            db.add(new_session)
            db.commit()
            db.refresh(new_session)
            
            # Zwróć informacje o nowej sesji
            return {
                "session_exists": True,
                "session_status": "ACTIVE",
                "session_id": new_session.id,
                "has_unfinished_round": False,
                "unfinished_round_id": None,
                "session_stats": {
                    "success_count": 0,
                    "failure_count": 0,
                    "success_rate": 0,
                    "profit_factor": 1.0,
                    "remaining_pairs": new_session.remaining_pairs
                }
            }
        
        # Ten przypadek nie powinien nigdy wystąpić, ale dodajemy dla pewności
        logger.error(f"Nieoczekiwany stan: użytkownik {current_user.id} ma sesję, ale nie jest ani aktywna, ani oczekująca, ani zakończona")
        raise HTTPException(status_code=500, detail="Nieoczekiwany stan sesji")
            
    except Exception as e:
        logger.error(f"Błąd podczas sprawdzania/tworzenia sesji: {str(e)}")
        logger.error(traceback.format_exc())
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sessions/resume/{session_id}", response_model=schemas.Session)
def resume_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Wznawia istniejącą sesję.
    """
    try:
        # Pobierz sesję i sprawdź czy istnieje
        session = db.query(SessionModel).filter(
            SessionModel.id == session_id,
            SessionModel.user_id == current_user.id
        ).first()
        
        if not session:
            raise HTTPException(status_code=404, detail="Sesja nie znaleziona")
        
        # Sprawdź czy sesja ma status ACTIVE
        if session.status == "ACTIVE":
            return session
        
        # Jeśli sesja ma status PENDING, aktywuj ją
        if session.status == "PENDING":
            session.status = "ACTIVE"
            session.started_at = datetime.utcnow()
            session.session_profit_factor = 1.0
            
            # Sprawdź czy pule są puste
            if not session.pos_pool_json or not session.neg_pool_json:
                logger.info(f"Pule są puste, generuję nową pulę")
                pos_pool_json, neg_pool_json = get_random_pool(db, 6)
                session.pos_pool_json = pos_pool_json
                session.neg_pool_json = neg_pool_json
                session.remaining_pairs = 6
            
            db.commit()
            db.refresh(session)
            return session
        
        # Jeśli sesja ma status COMPLETED, zwróć błąd
        if session.status == "COMPLETED":
            raise HTTPException(status_code=400, detail="Nie można wznowić zakończonej sesji")
        
        # Na wszelki wypadek, jeśli status jest nieznany
        raise HTTPException(status_code=400, detail=f"Nie można wznowić sesji o statusie {session.status}")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Błąd podczas wznawiania sesji: {str(e)}")
        logger.error(traceback.format_exc())
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions/{session_id}", response_model=schemas.Session)
def get_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Pobiera szczegóły sesji o podanym ID."""
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        logger.warning(f"Sesja {session_id} nie znaleziona")
        raise HTTPException(status_code=404, detail="Sesja nie znaleziona")
    if session.user_id != current_user.id:
        logger.warning(f"Brak dostępu do sesji {session_id} dla użytkownika {current_user.id}")
        raise HTTPException(status_code=403, detail="Brak dostępu do tej sesji")
    return session


@router.get("/sessions/{session_id}/summary", response_model=schemas.SessionSummary)
def get_session_summary(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Pobiera podsumowanie sesji o podanym ID."""
    try:
        logger.info(f"Pobieram podsumowanie sesji {session_id} dla użytkownika {current_user.id}")
        
        session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
        if not session:
            logger.warning(f"Sesja {session_id} nie znaleziona")
            raise HTTPException(status_code=404, detail="Sesja nie znaleziona")
        if session.user_id != current_user.id:
            logger.warning(f"Brak dostępu do sesji {session_id} dla użytkownika {current_user.id}")
            raise HTTPException(status_code=403, detail="Brak dostępu do tej sesji")
        
        logger.info(f"Sesja {session_id} znaleziona, status: {session.status}, session_profit_factor: {session.session_profit_factor:.6f}, remaining_pairs: {session.remaining_pairs}")
        
        # Pobierz liczbę sukcesów i porażek
        success_count = db.query(Round).filter(
            Round.session_id == session_id, Round.result == "SUCCESS"
        ).count()
        
        failure_count = db.query(Round).filter(
            Round.session_id == session_id, Round.result == "FAILURE"
        ).count()
        
        logger.info(f"Statystyki sesji {session_id}: success_count={success_count}, failure_count={failure_count}, total_rounds={success_count + failure_count}")
        
        # Inicjalizacja pustych list dla rankingów, nawet jeśli nie znajdziemy odpowiednich obrazów
        pos_ranking = []
        neg_ranking = []
        
        # Inicjalizacja pustych list dla pul bodźców, jeśli nie są dostępne w sesji
        pos_stimuli = session.pos_pool_json if session.pos_pool_json else []
        neg_stimuli = session.neg_pool_json if session.neg_pool_json else []
        
        # Pobierz wszystkie rundy dla sesji, aby obliczyć cumulative_factor dla każdego bodźca
        rounds = db.query(Round).filter(Round.session_id == session_id).all()
        
        # Słowniki do przechowywania cumulative_factor dla każdego bodźca
        pos_cumulative_factors = {}
        neg_cumulative_factors = {}
        
        # Słowniki do przechowywania liczby sukcesów i porażek dla każdego bodźca
        pos_success_counts = {}
        pos_failure_counts = {}
        neg_success_counts = {}
        neg_failure_counts = {}
        
        # Inicjalizuj cumulative_factor=1.0 dla wszystkich bodźców w puli
        for item in pos_stimuli:
            if "id" in item:
                pos_cumulative_factors[item["id"]] = 1.0
                pos_success_counts[item["id"]] = 0
                pos_failure_counts[item["id"]] = 0
                
        for item in neg_stimuli:
            if "id" in item:
                neg_cumulative_factors[item["id"]] = 1.0
                neg_success_counts[item["id"]] = 0
                neg_failure_counts[item["id"]] = 0
                
        # Oblicz cumulative_factor i zlicz sukcesy/porażki dla każdego bodźca na podstawie rund
        for round_obj in rounds:
            if round_obj.result == "SUCCESS":
                # Dla bodźca pozytywnego (wyświetlonego w przypadku sukcesu)
                if round_obj.pos_image_id in pos_cumulative_factors:
                    pos_cumulative_factors[round_obj.pos_image_id] *= (1 + round_obj.profit_fraction)
                    pos_success_counts[round_obj.pos_image_id] = pos_success_counts.get(round_obj.pos_image_id, 0) + 1
                
                # Dla bodźca negatywnego (przetrwanie - nie wyświetlony w przypadku sukcesu)
                if round_obj.neg_image_id in neg_cumulative_factors:
                    neg_cumulative_factors[round_obj.neg_image_id] *= (1 + round_obj.profit_fraction)
                    neg_success_counts[round_obj.neg_image_id] = neg_success_counts.get(round_obj.neg_image_id, 0) + 1
            elif round_obj.result == "FAILURE":
                # Dla bodźca pozytywnego (nie wyświetlony w przypadku porażki)
                if round_obj.pos_image_id in pos_failure_counts:
                    pos_failure_counts[round_obj.pos_image_id] = pos_failure_counts.get(round_obj.pos_image_id, 0) + 1
                
                # Dla bodźca negatywnego (wyświetlony w przypadku porażki)
                if round_obj.neg_image_id in neg_failure_counts:
                    neg_failure_counts[round_obj.neg_image_id] = neg_failure_counts.get(round_obj.neg_image_id, 0) + 1
        
        # Jeśli mamy dane w pos_pool_json, przygotuj ranking obrazów pozytywnych
        if session.pos_pool_json:
            logger.info(f"Przygotowuję ranking obrazów pozytywnych, liczba obrazów w puli: {len(session.pos_pool_json)}")
            
            try:
                # Pobierz IDs obrazów z puli
                pos_ids = [item["id"] for item in session.pos_pool_json if "id" in item]
                
                if pos_ids:
                    # Pobierz obrazy z bazy danych
                    pos_images = db.query(Image).filter(Image.id.in_(pos_ids)).all()
                    logger.info(f"Znaleziono {len(pos_images)} obrazów pozytywnych w bazie danych")
                    
                    # Mapowanie id->item z puli
                    pos_pool_dict = {item["id"]: item for item in session.pos_pool_json if "id" in item}
                    
                    # Tworzenie rankingu obrazów pozytywnych
                    for img in pos_images:
                        pool_data = pos_pool_dict.get(img.id, {})
                        
                        # Użyj obliczonych wartości sukcesów i porażek z rund
                        successes = pos_success_counts.get(img.id, 0)
                        failures = pos_failure_counts.get(img.id, 0)
                        
                        # Użyj obliczonego cumulative_factor lub 1.0 jeśli brak
                        cumulative_factor = pos_cumulative_factors.get(img.id, 1.0)
                        
                        logger.info(f"Obraz pozytywny id={img.id}: successes={successes}, failures={failures}, cumulative_factor={cumulative_factor:.6f}")
                        
                        # Dodaj obrazy do rankingu
                        pos_ranking.append({
                            "id": img.id,
                            "successes": successes,
                            "failures": failures,
                            "cumulative_factor": cumulative_factor,
                            "origin": pool_data.get("origin", "random"),
                            "parent": pool_data.get("parent") if pool_data.get("origin") == "child" else None
                        })
                        logger.info(f"Dodano obraz id={img.id} do rankingu pozytywnego")
                
                # Sortuj ranking według liczby sukcesów z puli (malejąco)
                pos_ranking = sorted(pos_ranking, key=lambda x: x["successes"], reverse=True)
                logger.info(f"Ranking obrazów pozytywnych gotowy, liczba obrazów: {len(pos_ranking)}")
            except Exception as e:
                logger.error(f"Błąd podczas przygotowywania rankingu pozytywnego: {str(e)}")
                logger.error(traceback.format_exc())
        
        # Jeśli mamy dane w neg_pool_json, przygotuj ranking obrazów negatywnych
        if session.neg_pool_json:
            logger.info(f"Przygotowuję ranking obrazów negatywnych, liczba obrazów w puli: {len(session.neg_pool_json)}")
            
            try:
                # Pobierz IDs obrazów z puli
                neg_ids = [item["id"] for item in session.neg_pool_json if "id" in item]
                
                if neg_ids:
                    # Pobierz obrazy z bazy danych
                    neg_images = db.query(Image).filter(Image.id.in_(neg_ids)).all()
                    logger.info(f"Znaleziono {len(neg_images)} obrazów negatywnych w bazie danych")
                    
                    # Mapowanie id->item z puli
                    neg_pool_dict = {item["id"]: item for item in session.neg_pool_json if "id" in item}
                    
                    # Tworzenie rankingu obrazów negatywnych
                    for img in neg_images:
                        pool_data = neg_pool_dict.get(img.id, {})
                        
                        # Użyj obliczonych wartości sukcesów i porażek z rund
                        successes = neg_success_counts.get(img.id, 0)
                        failures = neg_failure_counts.get(img.id, 0)
                        
                        # Użyj obliczonego cumulative_factor lub 1.0 jeśli brak
                        cumulative_factor = neg_cumulative_factors.get(img.id, 1.0)
                        
                        logger.info(f"Obraz negatywny id={img.id}: successes={successes}, failures={failures}, cumulative_factor={cumulative_factor:.6f}")
                        
                        # Dodaj obrazy do rankingu
                        neg_ranking.append({
                            "id": img.id,
                            "successes": successes,
                            "failures": failures,
                            "cumulative_factor": cumulative_factor,
                            "origin": pool_data.get("origin", "random"),
                            "parent": pool_data.get("parent") if pool_data.get("origin") == "child" else None
                        })
                        logger.info(f"Dodano obraz id={img.id} do rankingu negatywnego")
                
                # Sortuj ranking według liczby sukcesów z puli (malejąco)
                neg_ranking = sorted(neg_ranking, key=lambda x: x["successes"], reverse=True)
                logger.info(f"Ranking obrazów negatywnych gotowy, liczba obrazów: {len(neg_ranking)}")
            except Exception as e:
                logger.error(f"Błąd podczas przygotowywania rankingu negatywnego: {str(e)}")
                logger.error(traceback.format_exc())
        
        # Utwórz obiekt podsumowania
        summary = {
            "id": session.id,
            "status": session.status,
            "started_at": session.started_at,
            "session_profit_factor": session.session_profit_factor,
            "remaining_pairs": session.remaining_pairs,
            "success_count": success_count,
            "failure_count": failure_count,
            "round_count": success_count + failure_count,
            "pos_stimuli": pos_stimuli,
            "neg_stimuli": neg_stimuli,
            "pos_ranking": pos_ranking,
            "neg_ranking": neg_ranking
        }
        
        logger.info(f"Podsumowanie sesji {session_id} zostało wygenerowane pomyślnie: {len(pos_ranking)} obrazów pozytywnych w rankingu, {len(neg_ranking)} obrazów negatywnych w rankingu")
        
        return summary
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Błąd podczas pobierania podsumowania sesji: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Błąd serwera: {str(e)}")


@router.get("/sessions/{session_id}/rounds", response_model=List[schemas.RoundResponse])
def get_rounds_for_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Pobiera listę rund dla sesji o podanym ID."""
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        logger.warning(f"Sesja {session_id} nie znaleziona")
        raise HTTPException(status_code=404, detail="Sesja nie znaleziona")
    if session.user_id != current_user.id:
        logger.warning(f"Brak dostępu do sesji {session_id} dla użytkownika {current_user.id}")
        raise HTTPException(status_code=403, detail="Brak dostępu do tej sesji")
    
    rounds = db.query(Round).filter(Round.session_id == session_id).order_by(Round.round_number).all()
    logger.info(f"Pobrano {len(rounds)} rund dla sesji {session_id}")
    return rounds


@router.get("/sessions/{session_id}/next-pool-stats", response_model=schemas.NextPoolStats)
def get_next_pool_stats(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    background_tasks: BackgroundTasks = BackgroundTasks(),
):
    """Pobiera statystyki puli dla następnej sesji, która może być w trakcie generowania."""
    try:
        logger.info(f"Pobieranie statystyk puli dla następnej sesji, na podstawie sesji {session_id}")
        
        # Sprawdź, czy sesja istnieje i należy do bieżącego użytkownika
        session = db.query(SessionModel).filter(
            SessionModel.id == session_id,
            SessionModel.user_id == current_user.id
        ).first()
        if not session:
            raise HTTPException(status_code=404, detail="Sesja nie znaleziona lub brak dostępu")
            
        # Sprawdź czy istnieje już wygenerowana ale nieużyta sesja dla użytkownika
        next_session = db.query(SessionModel).filter(
            SessionModel.user_id == current_user.id,
            SessionModel.status == "PENDING"
        ).order_by(SessionModel.id.desc()).first()
        
        # Jeśli nie ma jeszcze wygenerowanej sesji PENDING, zwracamy informację, że pula nie jest jeszcze gotowa
        if not next_session:
            logger.info(f"Brak sesji PENDING, nie można wygenerować puli dla sesji {session_id}")
            
            # W tym przypadku zwracamy informację, że pula nie jest jeszcze gotowa
            return {
                "is_ready": False,
                "session_id": None,
                "total_count": 0,
                "random_count": 0,
                "bought_count": 0,
                "child_count": 0,
                "pos_total": 0,
                "pos_random": 0,
                "pos_bought": 0,
                "pos_child": 0,
                "neg_total": 0,
                "neg_random": 0,
                "neg_bought": 0,
                "neg_child": 0,
                "message": "Brak gotowej puli, należy utworzyć nową sesję"
            }
        
        # Przygotowanie zmiennych na wypadek błędu
        pos_pool = []
        neg_pool = []
        
        # Bezpieczne parsowanie JSON puli pozytywnych
        try:
            if isinstance(next_session.pos_pool_json, str):
                pos_pool = json.loads(next_session.pos_pool_json)
            else:
                pos_pool = next_session.pos_pool_json if next_session.pos_pool_json is not None else []
            logger.info(f"Pomyślnie sparsowano JSON pozytywnej puli: {len(pos_pool)} elementów")
        except json.JSONDecodeError as e:
            logger.error(f"Błąd parsowania JSON dla pozytywnej puli w sesji {next_session.id}: {str(e)}")
        except Exception as e:
            logger.error(f"Nieoczekiwany błąd podczas parsowania JSON pozytywnej puli: {str(e)}")
        
        # Bezpieczne parsowanie JSON puli negatywnych
        try:
            if isinstance(next_session.neg_pool_json, str):
                neg_pool = json.loads(next_session.neg_pool_json)
            else:
                neg_pool = next_session.neg_pool_json if next_session.neg_pool_json is not None else []
            logger.info(f"Pomyślnie sparsowano JSON negatywnej puli: {len(neg_pool)} elementów")
        except json.JSONDecodeError as e:
            logger.error(f"Błąd parsowania JSON dla negatywnej puli w sesji {next_session.id}: {str(e)}")
        except Exception as e:
            logger.error(f"Nieoczekiwany błąd podczas parsowania JSON negatywnej puli: {str(e)}")
    
        # Inicjalizacja słowników dla statystyk
        origins = {"random": 0, "bought": 0, "child": 0}
        pos_origins = {"random": 0, "bought": 0, "child": 0}
        neg_origins = {"random": 0, "bought": 0, "child": 0}
        
        # Oblicz statystyki pozytywnych bodźców
        for item in pos_pool:
            try:
                # Sprawdźmy, czy item jest słownikiem czy listą
                if isinstance(item, dict):
                    origin = item.get("origin", "random")  # Domyślnie "random" jeśli pole nie istnieje
                    
                    # Sprawdź, czy origin zaczyna się od "child_of_" - jeśli tak, to jest to dziecko
                    if origin.startswith("child_of_"):
                        pos_origins["child"] += 1
                    elif origin.startswith("random_fallback_for_"):
                        pos_origins["random"] += 1
                    elif origin in pos_origins:
                        pos_origins[origin] += 1
                    else:
                        # Jeśli origin nie pasuje do żadnej kategorii, traktujemy jako random
                        pos_origins["random"] += 1
                else:
                    # Jeśli item nie jest słownikiem, traktujemy go jako dane bez origin (domyślnie random)
                    pos_origins["random"] += 1
            except Exception as e:
                logger.error(f"Błąd podczas analizy pozytywnego bodźca: {str(e)}, item={item}")
                
        # Oblicz statystyki negatywnych bodźców
        for item in neg_pool:
            try:
                # Sprawdźmy, czy item jest słownikiem czy listą
                if isinstance(item, dict):
                    origin = item.get("origin", "random")  # Domyślnie "random" jeśli pole nie istnieje
                    
                    # Sprawdź, czy origin zaczyna się od "child_of_" - jeśli tak, to jest to dziecko
                    if origin.startswith("child_of_"):
                        neg_origins["child"] += 1
                    elif origin.startswith("random_fallback_for_"):
                        neg_origins["random"] += 1
                    elif origin in neg_origins:
                        neg_origins[origin] += 1
                    else:
                        # Jeśli origin nie pasuje do żadnej kategorii, traktujemy jako random
                        neg_origins["random"] += 1
                else:
                    # Jeśli item nie jest słownikiem, traktujemy go jako dane bez origin (domyślnie random)
                    neg_origins["random"] += 1
            except Exception as e:
                logger.error(f"Błąd podczas analizy negatywnego bodźca: {str(e)}, item={item}")
        
        # Sumy ogólne
        for key in origins:
            origins[key] = pos_origins[key] + neg_origins[key]
                
        total_count = len(pos_pool) + len(neg_pool)
                
        return {
            "is_ready": True,
            "session_id": next_session.id,
            "total_count": total_count,
            "random_count": origins["random"],
            "bought_count": origins["bought"],
            "child_count": origins["child"],
            "pos_total": len(pos_pool),
            "pos_random": pos_origins["random"],
            "pos_bought": pos_origins["bought"],
            "pos_child": pos_origins["child"],
            "neg_total": len(neg_pool),
            "neg_random": neg_origins["random"],
            "neg_bought": neg_origins["bought"],
            "neg_child": neg_origins["child"],
            "message": "Pula gotowa do użycia"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Błąd podczas pobierania statystyk puli: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sessions/generate-pending", response_model=schemas.Session)
def generate_pending_session(
    request: schemas.GenerateNewPoolRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Rozpoczyna generowanie nowej puli dla użytkownika na podstawie poprzedniej sesji
    i tworzy nową sesję w statusie PENDING.
    """
    try:
        logger.info(f"Rozpoczynam generowanie nowej puli dla użytkownika {current_user.id}")
        
        # Pobieramy poprzednią sesję (jeśli podano jej ID)
        previous_session = None
        if request.previous_session_id:
            previous_session = db.query(SessionModel).filter(
                SessionModel.id == request.previous_session_id,
                SessionModel.user_id == current_user.id
            ).first()
            
            if not previous_session:
                logger.warning(f"Nie znaleziono sesji {request.previous_session_id} dla użytkownika {current_user.id}")
                raise HTTPException(status_code=404, detail="Poprzednia sesja nie znaleziona")
        else:
            # Jeśli nie podano ID, szukamy ostatniej zakończonej sesji
            previous_session = get_last_completed_session(db, current_user.id)
        
        # Jeśli brak poprzedniej sesji, zwracamy błąd
        if not previous_session:
            logger.warning(f"Brak poprzedniej sesji dla użytkownika {current_user.id}")
            raise HTTPException(status_code=404, detail="Brak poprzedniej sesji")
        
        # Generujemy nowe pule na podstawie poprzedniej sesji
        pos_pool_json, neg_pool_json = generate_pool_with_genetic_algorithm(previous_session, db)
        
        # Tworzymy nową sesję PENDING z wygenerowaną pulą
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
        db.commit()
        db.refresh(new_session)
        
        logger.info(f"Utworzono nową sesję PENDING (id={new_session.id}) dla użytkownika {current_user.id}")
        
        return {
            "status": "success", 
            "message": "Nowa pula wygenerowana", 
            "session_id": new_session.id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Błąd podczas generowania nowej puli: {str(e)}")
        logger.error(traceback.format_exc())
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Błąd serwera: {str(e)}")


@router.post("/sessions/{session_id}/trigger-pool-generation", response_model=schemas.Message)
def trigger_pool_generation(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Triggera generowanie nowej puli dla użytkownika po kliknięciu podsumowania sesji."""
    try:
        # Sprawdź czy sesja istnieje i należy do bieżącego użytkownika
        session = db.query(SessionModel).filter(
            SessionModel.id == session_id,
            SessionModel.user_id == current_user.id
        ).first()
        
        if not session:
            raise HTTPException(status_code=404, detail="Sesja nie znaleziona")
        
        # Usuń istniejącą sesję PENDING, jeśli istnieje
        existing_pending = db.query(SessionModel).filter(
            SessionModel.user_id == current_user.id,
            SessionModel.status == "PENDING"
        ).first()
        
        if existing_pending:
            logger.info(f"Usuwam istniejącą sesję PENDING (id={existing_pending.id}) dla użytkownika {current_user.id}")
            db.delete(existing_pending)
            db.commit()
        
        # Wykorzystaj istniejącą funkcję generate_pending_session
        # Przygotuj obiekt request zgodny z oczekiwanym przez generate_pending_session
        request = schemas.GenerateNewPoolRequest(previous_session_id=session_id)
        
        # Wywołaj funkcję generate_pending_session
        logger.info(f"Wywołuję generate_pending_session dla sesji {session_id}")
        result = generate_pending_session(request, current_user, db)
        
        return {"message": "Rozpoczęto generowanie nowej puli"}
        
    except Exception as e:
        logger.error(f"Błąd podczas triggerowania generowania puli: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions/{session_id}/pool-status", response_model=dict)
def get_pool_status(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Sprawdza status sesji i zwraca informacje o następnej sesji (jeśli istnieje).
    """
    try:
        # Znajdź aktualną sesję
        current_session = db.query(SessionModel).filter(
            SessionModel.id == session_id,
            SessionModel.user_id == current_user.id
        ).first()
        if not current_session:
            raise HTTPException(status_code=404, detail="Nie znaleziono sesji")
            
        # Sprawdź czy istnieje następna sesja
        next_session = db.query(SessionModel).filter(
            SessionModel.user_id == current_user.id,
            SessionModel.id > session_id
        ).order_by(SessionModel.id.asc()).first()
        
        if next_session:
            # Przeanalizuj pule następnej sesji
            pos_pool = json.loads(next_session.pos_pool_json)
            neg_pool = json.loads(next_session.neg_pool_json)
            
            # Policz statystyki
            pos_stats = {
                "total": len(pos_pool),
                "bought": sum(1 for item in pos_pool if item["origin"] == "bought"),
                "children": sum(1 for item in pos_pool if item["origin"] == "child"),
                "random": sum(1 for item in pos_pool if item["origin"] == "random")
            }
            
            neg_stats = {
                "total": len(neg_pool),
                "bought": sum(1 for item in neg_pool if item["origin"] == "bought"),
                "children": sum(1 for item in neg_pool if item["origin"] == "child"),
                "random": sum(1 for item in neg_pool if item["origin"] == "random")
            }
            
            return {
                "has_next_session": True,
                "next_session_id": next_session.id,
                "next_session_status": next_session.status,
                "pos_pool": pos_stats,
                "neg_pool": neg_stats
            }
        else:
            return {
                "has_next_session": False,
                "next_session_id": None,
                "next_session_status": None,
                "pos_pool": None,
                "neg_pool": None
            }
            
    except Exception as e:
        logger.error(f"Błąd podczas sprawdzania statusu puli: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) 