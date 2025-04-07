from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Any
from sqlalchemy.orm import Session
import traceback
import logging
from sqlalchemy import func

from ..database import get_db
from ..models import User, Session as SessionModel, Round, Image
from .. import schemas
from ..auth import get_current_user

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/sessions", response_model=schemas.Session, status_code=status.HTTP_201_CREATED)
def create_session(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Tworzy nową sesję dla zalogowanego użytkownika."""
    try:
        # Pobierz losowe obrazy pozytywne i negatywne do puli
        pos_images = db.query(Image).filter(Image.type == "POSITIVE").order_by(func.random()).limit(6).all()
        neg_images = db.query(Image).filter(Image.type == "NEGATIVE").order_by(func.random()).limit(6).all()
        
        if len(pos_images) < 6 or len(neg_images) < 6:
            logger.error(f"Niewystarczająca liczba obrazów w bazie danych. Znaleziono: {len(pos_images)} pozytywnych, {len(neg_images)} negatywnych")
            raise HTTPException(status_code=500, detail="Niewystarczająca liczba obrazów w bazie danych")
            
        # Przygotuj struktury JSON dla pul obrazów
        pos_pool_json = []
        for img in pos_images:
            pos_pool_json.append({
                "id": img.id,
                "successes": 0,
                "failures": 0,
                "origin": "random"
            })
            
        neg_pool_json = []
        for img in neg_images:
            neg_pool_json.append({
                "id": img.id,
                "successes": 0,
                "failures": 0,
                "origin": "random"
            })
            
        # Utwórz sesję z przygotowanymi pulami obrazów
        session = SessionModel(
            user_id=current_user.id,
            status="ACTIVE",
            pos_pool_json=pos_pool_json,
            neg_pool_json=neg_pool_json,
            session_profit_factor=1.0,
            remaining_pairs=6
        )
        
        db.add(session)
        db.commit()
        db.refresh(session)
        logger.info(f"Utworzono nową sesję id={session.id} dla użytkownika {current_user.id} z pulą {len(pos_pool_json)} pozytywnych i {len(neg_pool_json)} negatywnych obrazów")
        return session
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Błąd podczas tworzenia sesji: {str(e)}")
        logger.error(traceback.format_exc())
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Błąd serwera: {str(e)}")


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
                    
                    # Utwórz słownik mapujący ID obrazu na jego dane z puli
                    pos_pool_dict = {item["id"]: item for item in session.pos_pool_json if "id" in item}
                    
                    # Tworzenie rankingu obrazów pozytywnych
                    for img in pos_images:
                        pool_data = pos_pool_dict.get(img.id, {})
                        successes = pool_data.get("successes", 0)
                        
                        logger.info(f"Obraz pozytywny id={img.id}: successes={successes}, total_successes={img.total_successes}, total_failures={img.total_failures}, total_profit_factor={img.total_profit_factor:.6f}")
                        
                        # Dodaj tylko obrazy, które miały conajmniej jeden sukces
                        if successes > 0:
                            pos_ranking.append({
                                "id": img.id,
                                "total_successes": img.total_successes,
                                "total_failures": img.total_failures,
                                "total_profit_factor": img.total_profit_factor,
                                "origin": pool_data.get("origin", "random"),
                                "parent": pool_data.get("parent") if pool_data.get("origin") == "child" else None
                            })
                            logger.info(f"Dodano obraz id={img.id} do rankingu pozytywnego")
                
                # Sortuj ranking według liczby sukcesów (malejąco)
                pos_ranking = sorted(pos_ranking, key=lambda x: x["total_successes"], reverse=True)
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
                    
                    # Utwórz słownik mapujący ID obrazu na jego dane z puli
                    neg_pool_dict = {item["id"]: item for item in session.neg_pool_json if "id" in item}
                    
                    # Tworzenie rankingu obrazów negatywnych
                    for img in neg_images:
                        pool_data = neg_pool_dict.get(img.id, {})
                        successes = pool_data.get("successes", 0)
                        
                        logger.info(f"Obraz negatywny id={img.id}: successes={successes}, total_successes={img.total_successes}, total_failures={img.total_failures}, total_profit_factor={img.total_profit_factor:.6f}")
                        
                        # Dodaj tylko obrazy, które miały conajmniej jeden sukces (przetrwanie)
                        if successes > 0:
                            neg_ranking.append({
                                "id": img.id,
                                "total_successes": img.total_successes,
                                "total_failures": img.total_failures,
                                "total_profit_factor": img.total_profit_factor,
                                "origin": pool_data.get("origin", "random"),
                                "parent": pool_data.get("parent") if pool_data.get("origin") == "child" else None
                            })
                            logger.info(f"Dodano obraz id={img.id} do rankingu negatywnego")
                
                # Sortuj ranking według liczby sukcesów (malejąco)
                neg_ranking = sorted(neg_ranking, key=lambda x: x["total_successes"], reverse=True)
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