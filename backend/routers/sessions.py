from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
import traceback
import logging
from datetime import datetime

from ..database import get_db
from ..models import User, Session as SessionModel, Round, Image
from .. import schemas
from ..auth import get_current_user
from ..schemas import SessionResponse
from ..genetic_pool import generate_pool_with_genetic_algorithm, get_random_pool
from ..embedding import find_nearest_image
from ..pool_image_item import PoolImageItem  # 👈 Zmiana: import klasy PoolImageItem

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
                        if "id" not in item:
                            logger.error(f"Obraz {i} w {pool_name} puli nie ma pola 'id'")
                
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
        session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
        if not session or session.user_id != current_user.id:
            raise HTTPException(
                status_code=404 if not session else 403,
                detail="Sesja nie znaleziona lub brak dostępu"
            )

        rounds = db.query(Round).filter(Round.session_id == session_id).all()
        success_count = sum(1 for r in rounds if r.result == "SUCCESS")
        failure_count = sum(1 for r in rounds if r.result == "FAILURE")

        pos_items = {item["id"]: PoolImageItem.from_dict(item) for item in (session.pos_pool_json or [])}
        neg_items = {item["id"]: PoolImageItem.from_dict(item) for item in (session.neg_pool_json or [])}

        pos_cumulative = {id_: 1.0 for id_ in pos_items}
        neg_cumulative = {id_: 1.0 for id_ in neg_items}

        for r in rounds:
            if r.result == "SUCCESS":
                if r.pos_image_id in pos_cumulative:
                    pos_cumulative[r.pos_image_id] *= (1 + r.profit_fraction)
                if r.neg_image_id in neg_cumulative:
                    neg_cumulative[r.neg_image_id] *= (1 + r.profit_fraction)

        def build_ranking(items: dict[int, PoolImageItem], cumulative: dict[int, float]):
            return sorted([
                {
                    "id": id_,
                    "successes": item.successes,
                    "failures": item.failures,
                    "cumulative_factor": cumulative.get(id_, 1.0),
                    "origin": item.origin,
                    "parent": item.parent if item.origin == "child" else None
                }
                for id_, item in items.items()
            ], key=lambda x: x["successes"], reverse=True)

        summary = {
            "id": session.id,
            "status": session.status,
            "started_at": session.started_at,
            "session_profit_factor": session.session_profit_factor,
            "remaining_pairs": session.remaining_pairs,
            "success_count": success_count,
            "failure_count": failure_count,
            "round_count": success_count + failure_count,
            "pos_stimuli": [item.to_dict() for item in pos_items.values()],
            "neg_stimuli": [item.to_dict() for item in neg_items.values()],
            "pos_ranking": build_ranking(pos_items, pos_cumulative),
            "neg_ranking": build_ranking(neg_items, neg_cumulative)
        }

        return summary
    except Exception as e:
        logger.error(f"Błąd podczas podsumowania sesji: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


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
        
        previous_session = db.query(SessionModel).filter(
            SessionModel.id == request.previous_session_id,
            SessionModel.user_id == current_user.id
        ).first()
        
        if not previous_session:
            raise HTTPException(status_code=404, detail="Poprzednia sesja nie znaleziona")
        
        if previous_session.status != "COMPLETED":
            raise HTTPException(status_code=400, detail="Poprzednia sesja nie jest zakończona")

        try:
            pos_pool_json = previous_session.pos_pool_json or []
            neg_pool_json = previous_session.neg_pool_json or []

            logger.info(f"Pomyślnie sparsowano JSON pozytywnej puli: {len(pos_pool_json)} elementów")
            logger.info(f"Pomyślnie sparsowano JSON negatywnej puli: {len(neg_pool_json)} elementów")
        except Exception as e:
            logger.error(f"Błąd parsowania JSON puli: {str(e)}")
            raise HTTPException(status_code=500, detail="Błąd parsowania JSON puli")

        try:
            logger.info(f"Rozpoczynam generowanie nowej puli na podstawie sesji {previous_session.id}")
            
            new_pos_pool, new_neg_pool = generate_pool_with_genetic_algorithm(previous_session, db)

            # Upewnij się, że każdy element to instancja PoolImageItem
            new_pos_pool_json = [
                item.to_dict() if isinstance(item, PoolImageItem) else PoolImageItem.from_dict(item).to_dict()
                for item in new_pos_pool
            ]
            new_neg_pool_json = [
                item.to_dict() if isinstance(item, PoolImageItem) else PoolImageItem.from_dict(item).to_dict()
                for item in new_neg_pool
            ]

            logger.info(f"Wygenerowano nową pulę: {len(new_pos_pool_json)} pozytywnych, {len(new_neg_pool_json)} negatywnych")
        except Exception as e:
            logger.error(f"Błąd generowania nowej puli: {str(e)}")
            logger.error(traceback.format_exc())
            raise HTTPException(status_code=500, detail="Błąd generowania nowej puli")

        new_session = SessionModel(
            user_id=current_user.id,
            status="PENDING",
            pos_pool_json=new_pos_pool_json,
            neg_pool_json=new_neg_pool_json,
            session_profit_factor=1.0,
            remaining_pairs=6
        )
        
        db.add(new_session)
        db.commit()
        db.refresh(new_session)
        
        logger.info(f"Utworzono nową sesję PENDING (id={new_session.id}) dla użytkownika {current_user.id}")
        
        return schemas.Message(message="Utworzono nową sesję PENDING")
        
    except HTTPException:
        raise
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
