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
from ..genetic_pool import generate_pool_with_genetic_algorithm, get_random_pool, PoolImageItem
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
            
            # Bezpieczne sprawdzenie pól JSON
            try:
                if not pos_pool_json or not isinstance(pos_pool_json, list):
                    raise ValueError("Nieprawidłowy format pos_pool_json")
                
                if not neg_pool_json or not isinstance(neg_pool_json, list):
                    raise ValueError("Nieprawidłowy format neg_pool_json")
                
                # Sprawdź, czy obrazy mają wymagane pola
                for pool_name, pool in [("pozytywna", pos_pool_json), ("negatywna", neg_pool_json)]:
                    for i, item in enumerate(pool):
                        if not isinstance(item, dict):
                            raise ValueError(f"Obraz {i} w {pool_name} puli nie jest słownikiem")
                        
                        if "id" not in item:
                            raise ValueError(f"Obraz {i} w {pool_name} puli nie ma pola 'id'")
                
                logger.info(f"Pola JSON dla nowej sesji są prawidłowe")
                
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
                return schemas.SessionCreateResponse(
                    session_exists=True,
                    session_status="ACTIVE",
                    session_id=new_session.id,
                    has_unfinished_round=False,
                    unfinished_round_id=None,
                    session_stats={
                        "success_count": 0,
                        "failure_count": 0,
                        "success_rate": 0,
                        "profit_factor": 1.0,
                        "remaining_pairs": new_session.remaining_pairs
                    }
                )
                
            except ValueError as e:
                logger.error(f"Błąd walidacji pól JSON dla nowej sesji: {str(e)}")
                raise HTTPException(status_code=500, detail=f"Błąd walidacji danych sesji: {str(e)}")
        
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
            pos_pool_json = active_session.pos_pool_json
            neg_pool_json = active_session.neg_pool_json
            
            # Zabezpieczenie przed None
            if pos_pool_json is None:
                pos_pool_json = []
            if neg_pool_json is None:
                neg_pool_json = []
                
            logger.info(f"Pobrano aktywną sesję {active_session.id}")
            logger.info(f"Stan puli pozytywnej: {len(pos_pool_json)} elementów")
            logger.info(f"Stan puli negatywnej: {len(neg_pool_json)} elementów")
            
            success_count = db.query(Round).filter(
                Round.session_id == active_session.id, Round.result == "SUCCESS"
            ).count()
            
            failure_count = db.query(Round).filter(
                Round.session_id == active_session.id, Round.result == "FAILURE"
            ).count()
            
            session_stats = {
                "success_count": success_count,
                "failure_count": failure_count,
                "success_rate": success_count / (success_count + failure_count) * 100 if (success_count + failure_count) > 0 else 0,
                "profit_factor": active_session.session_profit_factor,
                "remaining_pairs": active_session.remaining_pairs
            }
            
            return schemas.SessionCreateResponse(
                session_exists=True,
                session_status="ACTIVE",
                session_id=active_session.id,
                has_unfinished_round=unfinished_round is not None,
                unfinished_round_id=unfinished_round.id if unfinished_round else None,
                session_stats=session_stats
            )
            
        # 3. Sprawdź czy istnieje sesja PENDING
        pending_session = db.query(SessionModel).filter(
            SessionModel.user_id == current_user.id,
            SessionModel.status == "PENDING"
        ).first()
        
        if pending_session:
            logger.info(f"Znaleziono sesję PENDING {pending_session.id} dla użytkownika {current_user.id}, aktywuję ją")
            
            # Bezpieczne sprawdzenie pól JSON
            try:
                if not pending_session.pos_pool_json or not isinstance(pending_session.pos_pool_json, list):
                    raise ValueError("Nieprawidłowy format pos_pool_json")
                
                if not pending_session.neg_pool_json or not isinstance(pending_session.neg_pool_json, list):
                    raise ValueError("Nieprawidłowy format neg_pool_json")
                
                # Sprawdź, czy obrazy mają wymagane pola
                for pool_name, pool in [("pozytywna", pending_session.pos_pool_json), ("negatywna", pending_session.neg_pool_json)]:
                    for i, item in enumerate(pool):
                        if not isinstance(item, dict):
                            raise ValueError(f"Obraz {i} w {pool_name} puli nie jest słownikiem")
                        
                        if "id" not in item:
                            raise ValueError(f"Obraz {i} w {pool_name} puli nie ma pola 'id'")
                
                logger.info(f"Pola JSON dla sesji PENDING {pending_session.id} są prawidłowe")
                
                session = pending_session
                session.status = "ACTIVE"
                session.started_at = datetime.utcnow()
                session.session_profit_factor = 1.0
                
                # Sprawdź liczbę par w pulach
                pos_count = len([item for item in session.pos_pool_json if item.get("failures", 0) == 0])
                neg_count = len([item for item in session.neg_pool_json if item.get("failures", 0) == 0])
                
                if pos_count < 1 or neg_count < 1:
                    logger.warning(f"Zbyt mało dostępnych par w sesji {session.id}: pozytywnych={pos_count}, negatywnych={neg_count}")
                    raise ValueError("Zbyt mało dostępnych par w pulach")
                
                session.remaining_pairs = min(pos_count, neg_count)
                
                db.commit()
                db.refresh(session)
                
                return schemas.SessionCreateResponse(
                    session_exists=True,
                    session_status="ACTIVE",
                    session_id=session.id,
                    has_unfinished_round=False,
                    unfinished_round_id=None,
                    session_stats={
                        "success_count": 0,
                        "failure_count": 0,
                        "success_rate": 0,
                        "profit_factor": session.session_profit_factor,
                        "remaining_pairs": session.remaining_pairs
                    }
                )
                
            except ValueError as e:
                logger.error(f"Błąd walidacji pól JSON dla sesji PENDING: {str(e)}")
                # Jeśli pule są nieprawidłowe, generujemy nową pulę
                logger.info(f"Generowanie nowej puli dla sesji {pending_session.id}")
                pos_pool_json, neg_pool_json = get_random_pool(db, 6)
                pending_session.pos_pool_json = pos_pool_json
                pending_session.neg_pool_json = neg_pool_json
                pending_session.remaining_pairs = 6
                
                pending_session.status = "ACTIVE"
                pending_session.started_at = datetime.utcnow()
                pending_session.session_profit_factor = 1.0
                
                db.commit()
                db.refresh(pending_session)
                return schemas.SessionCreateResponse(
                    session_exists=True,
                    session_status="ACTIVE",
                    session_id=pending_session.id,
                    has_unfinished_round=False,
                    unfinished_round_id=None,
                    session_stats={
                        "success_count": 0,
                        "failure_count": 0,
                        "success_rate": 0,
                        "profit_factor": pending_session.session_profit_factor,
                        "remaining_pairs": pending_session.remaining_pairs
                    }
                )
        
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
            return schemas.SessionCreateResponse(
                session_exists=True,
                session_status="ACTIVE",
                session_id=new_session.id,
                has_unfinished_round=False,
                unfinished_round_id=None,
                session_stats={
                    "success_count": 0,
                    "failure_count": 0,
                    "success_rate": 0,
                    "profit_factor": 1.0,
                    "remaining_pairs": new_session.remaining_pairs
                }
            )
        
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
            logger.info(f"Aktywacja sesji PENDING {session.id} dla użytkownika {current_user.id}")
            
            # Bezpieczne sprawdzenie pól JSON
            try:
                if not session.pos_pool_json or not isinstance(session.pos_pool_json, list):
                    logger.warning(f"Nieprawidłowy format pos_pool_json w sesji {session.id}")
                    raise ValueError("Nieprawidłowy format pos_pool_json")
                
                if not session.neg_pool_json or not isinstance(session.neg_pool_json, list):
                    logger.warning(f"Nieprawidłowy format neg_pool_json w sesji {session.id}")
                    raise ValueError("Nieprawidłowy format neg_pool_json")
                
                # Sprawdź, czy obrazy mają wymagane pola
                for pool_name, pool in [("pozytywna", session.pos_pool_json), ("negatywna", session.neg_pool_json)]:
                    for i, item in enumerate(pool):
                        if not isinstance(item, dict):
                            logger.error(f"Obraz {i} w {pool_name} puli nie jest słownikiem: {type(item)}")
                            raise ValueError(f"Obraz {i} w {pool_name} puli nie jest słownikiem")
                        
                        if "id" not in item:
                            logger.error(f"Obraz {i} w {pool_name} puli nie ma pola 'id'")
                            raise ValueError(f"Obraz {i} w {pool_name} puli nie ma pola 'id'")
                
                logger.info(f"Pola JSON w sesji {session.id} są prawidłowo sformatowane")
                
                session.status = "ACTIVE"
                session.started_at = datetime.utcnow()
                session.session_profit_factor = 1.0
                
                # Sprawdź liczbę par w pulach
                pos_count = len([item for item in session.pos_pool_json if item.get("failures", 0) == 0])
                neg_count = len([item for item in session.neg_pool_json if item.get("failures", 0) == 0])
                
                if pos_count < 1 or neg_count < 1:
                    logger.warning(f"Zbyt mało dostępnych par w sesji {session.id}: pozytywnych={pos_count}, negatywnych={neg_count}")
                    raise ValueError("Zbyt mało dostępnych par w pulach")
                
                session.remaining_pairs = min(pos_count, neg_count)
                
                db.commit()
                db.refresh(session)
                return session
                
            except ValueError as e:
                logger.error(f"Błąd walidacji pól JSON w sesji {session.id}: {str(e)}")
                # Jeśli pule są nieprawidłowe, generujemy nową pulę
                logger.info(f"Generowanie nowej puli dla sesji {session.id}")
                pos_pool_json, neg_pool_json = get_random_pool(db, 6)
                session.pos_pool_json = pos_pool_json
                session.neg_pool_json = neg_pool_json
                session.remaining_pairs = 6
                
                session.status = "ACTIVE"
                session.started_at = datetime.utcnow()
                session.session_profit_factor = 1.0
                
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


@router.get("/sessions/{session_id}/pool-info", response_model=dict)
def get_pool_info(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Sprawdza status sesji i zwraca informacje o sesji PENDING oraz statystyki puli.
    """
    try:
        # Sprawdź czy istnieje sesja PENDING
        pending_session = db.query(SessionModel).filter(
            SessionModel.user_id == current_user.id,
            SessionModel.status == "PENDING"
        ).order_by(SessionModel.id.desc()).first()
        
        if pending_session:
            logger.info(f"Znaleziono sesję PENDING {pending_session.id} dla użytkownika {current_user.id}")
            
            # Sprawdź, czy sesja ma wygenerowane pule
            has_generated_pools = False
            pool_stats = None
            
            if pending_session.pos_pool_json and pending_session.neg_pool_json:
                try:
                    # Bezpieczne sprawdzenie pól JSON
                    if isinstance(pending_session.pos_pool_json, list) and isinstance(pending_session.neg_pool_json, list):
                        has_generated_pools = True
                        logger.info(f"Sesja {pending_session.id} ma wygenerowane pule")
                        
                        # Oblicz statystyki puli
                        pool_stats = {
                            "pos_pool": {
                                "total": len(pending_session.pos_pool_json),
                                "bought": sum(1 for item in pending_session.pos_pool_json if item.get("origin", "random") == "bought"),
                                "children": sum(1 for item in pending_session.pos_pool_json if item.get("origin", "").startswith("child_of_")),
                                "random": sum(1 for item in pending_session.pos_pool_json if item.get("origin", "random") == "random"),
                                "random_fallback": sum(1 for item in pending_session.pos_pool_json if item.get("origin", "").startswith("random_fallback_for_")),
                                "images": [{
                                    "id": item["id"],
                                    "origin": item.get("origin", "random"),
                                    "successes": item.get("successes", 0),
                                    "failures": item.get("failures", 0)
                                } for item in pending_session.pos_pool_json]
                            },
                            "neg_pool": {
                                "total": len(pending_session.neg_pool_json),
                                "bought": sum(1 for item in pending_session.neg_pool_json if item.get("origin", "random") == "bought"),
                                "children": sum(1 for item in pending_session.neg_pool_json if item.get("origin", "").startswith("child_of_")),
                                "random": sum(1 for item in pending_session.neg_pool_json if item.get("origin", "random") == "random"),
                                "random_fallback": sum(1 for item in pending_session.neg_pool_json if item.get("origin", "").startswith("random_fallback_for_")),
                                "images": [{
                                    "id": item["id"],
                                    "origin": item.get("origin", "random"),
                                    "successes": item.get("successes", 0),
                                    "failures": item.get("failures", 0)
                                } for item in pending_session.neg_pool_json]
                            },
                            "total_images": len(pending_session.pos_pool_json) + len(pending_session.neg_pool_json)
                        }
                except Exception as e:
                    logger.error(f"Błąd podczas sprawdzania pól JSON: {str(e)}")
                    has_generated_pools = False
            
            return {
                "has_pending_session": True,
                "pending_session_id": pending_session.id,
                "has_generated_pools": has_generated_pools,
                "pool_stats": pool_stats
            }
        else:
            return {
                "has_pending_session": False,
                "pending_session_id": None,
                "has_generated_pools": False,
                "pool_stats": None
            }
            
    except Exception as e:
        logger.error(f"Błąd podczas sprawdzania statusu puli: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sessions/generate-pending", response_model=schemas.Message)
def generate_pending_session(
    request: schemas.GenerateNewPoolRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Generuje nową sesję w stanie PENDING na podstawie poprzedniej sesji.
    """
    try:
        logger.info(f"Rozpoczynam generowanie nowej puli dla użytkownika {current_user.id}")
        
        # Pobierz poprzednią sesję
        previous_session = db.query(SessionModel).filter(
            SessionModel.id == request.previous_session_id,
            SessionModel.user_id == current_user.id
        ).first()
        
        if not previous_session:
            raise HTTPException(status_code=404, detail="Poprzednia sesja nie znaleziona")
        
        # Sprawdź czy poprzednia sesja jest zakończona
        if previous_session.status != "COMPLETED":
            raise HTTPException(status_code=400, detail="Poprzednia sesja nie jest zakończona")

        # Parsuj JSON puli obrazów
        try:
            pos_pool_json = previous_session.pos_pool_json
            neg_pool_json = previous_session.neg_pool_json
            
            logger.info(f"Pomyślnie sparsowano JSON pozytywnej puli: {len(pos_pool_json)} elementów")
            logger.info(f"Pomyślnie sparsowano JSON negatywnej puli: {len(neg_pool_json)} elementów")
        except Exception as e:
            logger.error(f"Błąd parsowania JSON puli: {str(e)}")
            raise HTTPException(status_code=500, detail="Błąd parsowania JSON puli")
        
        # Generuj nową pulę na podstawie poprzedniej sesji
        try:
            # Generuj nową pulę
            logger.info(f"Rozpoczynam generowanie nowej puli na podstawie sesji {previous_session.id}")
            
            # Wywołaj funkcję process_pool_generation z modułu genetic_pool
            new_pos_pool, new_neg_pool = generate_pool_with_genetic_algorithm(previous_session, db)
            
            logger.info(f"Wygenerowano nową pulę: {len(new_pos_pool)} pozytywnych, {len(new_neg_pool)} negatywnych")
        except Exception as e:
            logger.error(f"Błąd generowania nowej puli: {str(e)}")
            logger.error(traceback.format_exc())
            raise HTTPException(status_code=500, detail="Błąd generowania nowej puli")
        
        # Utwórz nową sesję w stanie PENDING
        new_session = SessionModel(
            user_id=current_user.id,
            status="PENDING",
            pos_pool_json=new_pos_pool,
            neg_pool_json=new_neg_pool,
            session_profit_factor=1.0,
            remaining_pairs=6  # Stała liczba par, zgodnie z resztą kodu
        )
        
        db.add(new_session)
        db.commit()
        db.refresh(new_session)
        
        logger.info(f"Utworzono nową sesję PENDING (id={new_session.id}) dla użytkownika {current_user.id}")
        
        return {"message": "Utworzono nową sesję PENDING"}
        
    except HTTPException as e:
        # Przekaż wyjątek HTTPException dalej
        raise e
    except Exception as e:
        logger.error(f"Błąd podczas generowania sesji PENDING: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


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
        
        # Sprawdź czy istnieje sesja PENDING
        existing_pending = db.query(SessionModel).filter(
            SessionModel.user_id == current_user.id,
            SessionModel.status == "PENDING"
        ).first()
        
        if existing_pending:
            logger.info(f"Istnieje już sesja PENDING (id={existing_pending.id}) dla użytkownika {current_user.id}")
            return {"message": f"Istnieje już sesja PENDING (id={existing_pending.id})"}
        
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
