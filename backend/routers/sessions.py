from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Any
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User, Session as SessionModel, Round
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
    
    return {
        "id": session.id,
        "status": session.status,
        "started_at": session.created_at,
        "session_profit_factor": session.session_profit_factor,
        "remaining_pairs": session.remaining_pairs,
        "success_count": success_count,
        "failure_count": failure_count,
        "round_count": success_count + failure_count,
        "positive_stimuli": session.pos_pool_json,
        "negative_stimuli": session.neg_pool_json
    }


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