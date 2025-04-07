from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Any
from sqlalchemy.orm import Session
import traceback

from ..database import get_db
from ..models import User, Session as SessionModel, Round, Image
from .. import schemas
from ..auth import get_current_user

router = APIRouter()


@router.post("/sessions", response_model=schemas.Session, status_code=status.HTTP_201_CREATED)
def create_session(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Tworzy nową sesję dla zalogowanego użytkownika."""
    # Ta implementacja jest uproszczona - w prawdziwej aplikacji należy zaimplementować logikę wybierania puli obrazów
    session = SessionModel(
        user_id=current_user.id,
        status="ACTIVE",
        pos_pool_json=[],
        neg_pool_json=[],
        session_profit_factor=1.0,
        remaining_pairs=6
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


@router.get("/sessions/{session_id}", response_model=schemas.Session)
def get_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Pobiera szczegóły sesji o podanym ID."""
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Sesja nie znaleziona")
    if session.user_id != current_user.id:
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
        if not session:
            raise HTTPException(status_code=404, detail="Sesja nie znaleziona")
        if session.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Brak dostępu do tej sesji")
        
        # Pobierz liczbę sukcesów i porażek
        success_count = db.query(Round).filter(
            Round.session_id == session_id, Round.result == "SUCCESS"
        ).count()
        
        failure_count = db.query(Round).filter(
            Round.session_id == session_id, Round.result == "FAILURE"
        ).count()
        
        # Przygotuj listy rankingowe obrazów
        pos_ranking = []
        neg_ranking = []
        
        # Jeśli mamy dane w pos_pool_json, przygotuj ranking obrazów pozytywnych
        if session.pos_pool_json:
            # Pobierz IDs obrazów z puli
            pos_ids = [item["id"] for item in session.pos_pool_json]
            
            # Pobierz obrazy z bazy danych
            pos_images = db.query(Image).filter(Image.id.in_(pos_ids)).all()
            
            # Utwórz słownik mapujący ID obrazu na jego dane z puli
            pos_pool_dict = {item["id"]: item for item in session.pos_pool_json}
            
            # Tworzenie rankingu obrazów pozytywnych
            for img in pos_images:
                pool_data = pos_pool_dict.get(img.id, {})
                successes = pool_data.get("successes", 0)
                
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
            
            # Sortuj ranking według liczby sukcesów (malejąco)
            pos_ranking = sorted(pos_ranking, key=lambda x: x["total_successes"], reverse=True)
        
        # Jeśli mamy dane w neg_pool_json, przygotuj ranking obrazów negatywnych
        if session.neg_pool_json:
            # Pobierz IDs obrazów z puli
            neg_ids = [item["id"] for item in session.neg_pool_json]
            
            # Pobierz obrazy z bazy danych
            neg_images = db.query(Image).filter(Image.id.in_(neg_ids)).all()
            
            # Utwórz słownik mapujący ID obrazu na jego dane z puli
            neg_pool_dict = {item["id"]: item for item in session.neg_pool_json}
            
            # Tworzenie rankingu obrazów negatywnych
            for img in neg_images:
                pool_data = neg_pool_dict.get(img.id, {})
                successes = pool_data.get("successes", 0)
                
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
            
            # Sortuj ranking według liczby sukcesów (malejąco)
            neg_ranking = sorted(neg_ranking, key=lambda x: x["total_successes"], reverse=True)
        
        return {
            "id": session.id,
            "status": session.status,
            "started_at": session.started_at,
            "session_profit_factor": session.session_profit_factor,
            "remaining_pairs": session.remaining_pairs,
            "success_count": success_count,
            "failure_count": failure_count,
            "round_count": success_count + failure_count,
            "pos_stimuli": session.pos_pool_json,
            "neg_stimuli": session.neg_pool_json,
            "pos_ranking": pos_ranking,
            "neg_ranking": neg_ranking
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Błąd podczas pobierania podsumowania sesji: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Błąd serwera: {str(e)}")


@router.get("/sessions/{session_id}/rounds", response_model=List[schemas.RoundCreate])
def get_rounds_for_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Pobiera listę rund dla sesji o podanym ID."""
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Sesja nie znaleziona")
    if session.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Brak dostępu do tej sesji")
    
    rounds = db.query(Round).filter(Round.session_id == session_id).order_by(Round.round_number).all()
    return rounds 