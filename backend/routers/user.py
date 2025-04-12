from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from ..database import get_db
from ..models import User, Session as SessionModel, Round
from .. import schemas
from ..auth import get_current_user
from ..schemas import RoundResultEnum
from ..pool_image_item import PoolImageItem

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
    if type not in ['positive', 'negative']:
        raise HTTPException(status_code=400, detail="Nieprawidłowy typ bodźca. Dozwolone: 'positive' lub 'negative'")
    
    # Pobierz sesje użytkownika, posortowane od najnowszej do najstarszej
    sessions = db.query(SessionModel).filter(
        SessionModel.user_id == current_user.id,
        SessionModel.status == "COMPLETED"
    ).order_by(SessionModel.ended_at.desc()).limit(20).all()
    
    if not sessions:
        return []
    
    # Słownik do przechowywania unikalnych węzłów genealogii
    genealogy_nodes = {}
    
    # Iteruj przez sesje od najstarszej do najnowszej
    for session in reversed(sessions):
        # Wybierz odpowiednią pulę w zależności od typu
        pool_json = session.pos_pool_json if type == 'positive' else session.neg_pool_json
        
        if not pool_json:
            continue
        
        for item in pool_json:
            # Przygotuj obiekt PoolImageItem dla łatwiejszej analizy
            pool_item = PoolImageItem.from_dict(item)
            
            # Jeśli węzeł już istnieje, zaktualizuj jego statystyki
            if pool_item.id in genealogy_nodes:
                node = genealogy_nodes[pool_item.id]
                node['successes'] += pool_item.successes
                node['failures'] += pool_item.failures
            else:
                # Określ rodzica na podstawie origin
                parent = None
                if pool_item.is_child():
                    parents = pool_item.get_parents()
                    if parents:
                        parent = parents[0]  # Pierwszy rodzic jako główny
                
                # Dodaj nowy węzeł
                genealogy_nodes[pool_item.id] = {
                    "id": pool_item.id,
                    "successes": pool_item.successes,
                    "failures": pool_item.failures,
                    "profit_factor": 1.0,  # Zostanie zaktualizowane później
                    "parent": parent,
                    "origin": "child" if pool_item.is_child() else pool_item.origin
                }
    
    # Oblicz czynnik zysku dla każdego węzła
    for node_id, node in genealogy_nodes.items():
        if node['successes'] > 0 or node['failures'] > 0:
            total = node['successes'] + node['failures']
            success_rate = node['successes'] / total if total > 0 else 0
            # Prosty model zysku: 1.0 + (proporcja sukcesów * 0.2)
            node['profit_factor'] = 1.0 + (success_rate * 0.2)
    
    # Zwróć listę węzłów
    return list(genealogy_nodes.values()) 