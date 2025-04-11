from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from ..database import get_db
from ..models import User, Session as SessionModel, Round
from .. import schemas
from ..auth import get_current_user
from ..schemas import RoundResultEnum

router = APIRouter()


@router.get("/user/sessions", response_model=List[schemas.SessionSummary])
def get_user_sessions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Pobiera wszystkie sesje użytkownika."""
    sessions = db.query(SessionModel).filter(SessionModel.user_id == current_user.id).all()
    
    # Przygotuj szczegółowe podsumowania sesji
    session_summaries = []
    for session in sessions:
        # Oblicz liczbę sukcesów i porażek
        success_count = db.query(Round).filter(
            Round.session_id == session.id,
            Round.result == RoundResultEnum.SUCCESS.value
        ).count()
        
        failure_count = db.query(Round).filter(
            Round.session_id == session.id,
            Round.result == RoundResultEnum.FAILURE.value
        ).count()
        
        round_count = success_count + failure_count
        
        # Użyj SessionResponse jako podstawy
        session_summary = schemas.SessionSummary(
            id=session.id,
            status=session.status,
            started_at=session.started_at,
            session_profit_factor=session.session_profit_factor,
            remaining_pairs=session.remaining_pairs,
            success_count=success_count,
            failure_count=failure_count,
            round_count=round_count
        )
        
        session_summaries.append(session_summary)
    
    return session_summaries


@router.get("/user/profile", response_model=schemas.UserProfile)
def get_user_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Pobiera profil użytkownika z dodatkowymi statystykami."""
    # Pobierz wszystkie sesje użytkownika
    sessions = db.query(SessionModel).filter(SessionModel.user_id == current_user.id).all()
    
    # Oblicz łączny czynnik zysku ze wszystkich sesji
    total_profit_factor = 1.0
    session_count = 0
    completed_session_count = 0
    for session in sessions:
        session_count += 1
        if session.status == "COMPLETED":
            completed_session_count += 1
            total_profit_factor *= session.session_profit_factor
    
    # Oblicz łączną liczbę rund
    round_count = db.query(SessionModel).filter(
        SessionModel.user_id == current_user.id
    ).join(
        SessionModel.rounds
    ).count()
    
    # Policz sukcesy i porażki
    success_count = db.query(SessionModel).filter(
        SessionModel.user_id == current_user.id
    ).join(
        SessionModel.rounds
    ).filter(
        SessionModel.rounds.any(Round.result == RoundResultEnum.SUCCESS.value)
    ).count()
    
    failure_count = round_count - success_count
    
    return {
        "id": current_user.id,
        "username": current_user.username,
        "created_at": current_user.created_at,
        "session_count": session_count,
        "completed_session_count": completed_session_count,
        "round_count": round_count,
        "success_count": success_count,
        "failure_count": failure_count,
        "total_profit_factor": total_profit_factor
    }


@router.get("/genealogy/{type}", response_model=List[schemas.GenealogyNode])
def get_genealogy(
    type: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Pobiera dane genealogii bodźców dla danego typu."""
    # Uproszczona implementacja - w rzeczywistej aplikacji pobierałaby prawdziwe dane genealogii
    # Zwracamy testowe dane
    genealogy_nodes = []
    for i in range(5):
        # Dodaj węzeł główny
        genealogy_nodes.append({
            "id": i + 1,
            "successes": 10 - i,
            "failures": i,
            "profit_factor": 1.1,
            "parent": None,
            "origin": "random"
        })
        
        # Dodaj dzieci
        for j in range(2):
            child_id = 100 + (i * 10) + j
            genealogy_nodes.append({
                "id": child_id,
                "successes": 5 - j,
                "failures": j,
                "profit_factor": 1.05,
                "parent": i + 1,
                "origin": "child"
            })
    
    return genealogy_nodes 