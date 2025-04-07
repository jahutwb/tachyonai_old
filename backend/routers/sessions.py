from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Any, Dict, Tuple
from sqlalchemy.orm import Session
import traceback
import logging
from sqlalchemy import func
import numpy as np
import random

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
        # Sprawdź, czy użytkownik ma już sesję w stanie INACTIVE (wygenerowaną przez algorytm quasi-genetyczny)
        inactive_session = db.query(SessionModel).filter(
            SessionModel.user_id == current_user.id,
            SessionModel.status == "INACTIVE"
        ).order_by(SessionModel.id.desc()).first()
        
        if inactive_session:
            logger.info(f"Znaleziono sesję w stanie INACTIVE (id={inactive_session.id}) dla użytkownika {current_user.id}, aktywuję ją")
            inactive_session.status = "ACTIVE"
            db.commit()
            db.refresh(inactive_session)
            return inactive_session
            
        # Sprawdź, czy użytkownik ma poprzednią zakończoną sesję
        previous_session = db.query(SessionModel).filter(
            SessionModel.user_id == current_user.id,
            SessionModel.status == "COMPLETED"
        ).order_by(SessionModel.id.desc()).first()
        
        pos_pool_json = []
        neg_pool_json = []
        
        if previous_session:
            logger.info(f"Znaleziono poprzednią zakończoną sesję id={previous_session.id} dla użytkownika {current_user.id}, generowanie puli metodą quasi-genetyczną")
            # Uruchom algorytm quasi-genetyczny do generowania nowej puli
            pos_pool_json, neg_pool_json = generate_pool_with_genetic_algorithm(previous_session, db)
            logger.info(f"Wygenerowano nową pulę: {len(pos_pool_json)} pozytywnych i {len(neg_pool_json)} negatywnych bodźców")
        else:
            logger.info(f"Brak poprzedniej zakończonej sesji dla użytkownika {current_user.id}, generowanie losowej puli")
            # Brak poprzedniej sesji - wygeneruj losową pulę
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
            
            logger.info(f"Wygenerowano losową pulę: {len(pos_pool_json)} pozytywnych i {len(neg_pool_json)} negatywnych bodźców")
            
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
):
    """Pobiera statystyki puli dla następnej sesji, która może być w trakcie generowania."""
    try:
        logger.info(f"Pobieranie statystyk puli dla następnej sesji, na podstawie sesji {session_id}")
        
        # Sprawdź, czy sesja istnieje i należy do bieżącego użytkownika
        session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
        if not session or session.user_id != current_user.id:
            raise HTTPException(status_code=404, detail="Sesja nie znaleziona lub brak dostępu")
            
        # Sprawdź, czy istnieje już wygenerowana ale nieużyta sesja dla użytkownika
        next_session = db.query(SessionModel).filter(
            SessionModel.user_id == current_user.id,
            SessionModel.status == "PENDING"
        ).order_by(SessionModel.id.desc()).first()
        
        # Jeśli nie ma jeszcze wygenerowanej sesji PENDING, generujemy nową w tle
        if not next_session:
            # Rozpocznij generowanie w tle (nie czekaj na zakończenie)
            # W tym przypadku zwracamy informację, że pula nie jest jeszcze gotowa
            return {
                "is_ready": False,
                "session_id": None,
                "total_count": 0,
                "random_count": 0,
                "bought_count": 0,
                "child_count": 0,
                "message": "Generowanie puli w toku"
            }
            
        # Jeśli sesja istnieje, przygotuj statystyki
        pos_pool = next_session.pos_pool_json or []
        neg_pool = next_session.neg_pool_json or []
        
        # Zlicz bodźce według pochodzenia
        origins = {"random": 0, "bought": 0, "child": 0}
        
        for item in pos_pool + neg_pool:
            origin = item.get("origin", "unknown")
            if origin in origins:
                origins[origin] += 1
                
        total_count = len(pos_pool) + len(neg_pool)
                
        return {
            "is_ready": True,
            "session_id": next_session.id,
            "total_count": total_count,
            "random_count": origins["random"],
            "bought_count": origins["bought"],
            "child_count": origins["child"],
            "message": "Pula gotowa do użycia"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Błąd podczas pobierania statystyk puli: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Błąd serwera: {str(e)}")


def calculate_centroid(embeddings: List[List[float]], weights: List[float] = None) -> List[float]:
    """Oblicza centroid (średnią ważoną) wektorów embeddingów."""
    if not embeddings:
        return []
        
    if weights is None:
        weights = [1.0] * len(embeddings)
        
    # Konwersja na numpy arrays
    embeddings_array = np.array(embeddings)
    weights_array = np.array(weights)
    
    # Normalizacja wag
    weights_sum = np.sum(weights_array)
    if weights_sum > 0:
        normalized_weights = weights_array / weights_sum
    else:
        normalized_weights = np.ones(len(weights_array)) / len(weights_array)
    
    # Obliczenie średniej ważonej
    centroid = np.average(embeddings_array, axis=0, weights=normalized_weights)
    
    return centroid.tolist()


def find_nearest_embedding(target_embedding: List[float], all_embeddings: List[Tuple[int, List[float]]], exclude_ids: List[int] = None) -> Tuple[int, float]:
    """
    Znajduje obraz o najbliższym embeddingu do podanego.
    
    Args:
        target_embedding: Wektor embedingu, dla którego szukamy najbliższego sąsiada
        all_embeddings: Lista krotek (id, embedding) wszystkich obrazów
        exclude_ids: Lista ID obrazów do wykluczenia z wyszukiwania
        
    Returns:
        Tuple (id, distance) - ID najbliższego obrazu i odległość
    """
    if exclude_ids is None:
        exclude_ids = []
        
    min_distance = float('inf')
    nearest_id = None
    
    target_array = np.array(target_embedding)
    
    for img_id, embedding in all_embeddings:
        if img_id in exclude_ids:
            continue
            
        # Oblicz odległość euklidesową
        distance = np.linalg.norm(np.array(embedding) - target_array)
        
        if distance < min_distance:
            min_distance = distance
            nearest_id = img_id
    
    return nearest_id, min_distance


def generate_pool_with_genetic_algorithm(previous_session: SessionModel, db: Session) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Implementacja algorytmu quasi-genetycznego do generowania nowej puli obrazów.
    
    Args:
        previous_session: Obiekt poprzedniej sesji
        db: Obiekt sesji bazy danych
        
    Returns:
        Tuple (pos_pool_json, neg_pool_json) zawierające nowe pule obrazów
    """
    try:
        num_pairs = 6  # Liczba par obrazów w puli
        logger.info(f"===== ROZPOCZĘCIE GENEROWANIA PULI QUASI-GENETYCZNEJ =====")
        logger.info(f"Przetwarzam sesję id={previous_session.id}, status={previous_session.status}")
        
        # 1. Pobranie danych z poprzedniej sesji
        pos_pool_prev = previous_session.pos_pool_json
        neg_pool_prev = previous_session.neg_pool_json
        
        if not pos_pool_prev or not neg_pool_prev:
            logger.warning(f"[BŁĄD GENETYCZNY] Brak danych w puli poprzedniej sesji {previous_session.id}")
            logger.warning(f"Pos pool: {pos_pool_prev}")
            logger.warning(f"Neg pool: {neg_pool_prev}")
            logger.warning(f"Fallback do losowej puli")
            return generate_random_pool(db, num_pairs)
            
        # 2. Pobierz embeddingi obrazów
        pos_ids = [item["id"] for item in pos_pool_prev if "id" in item]
        neg_ids = [item["id"] for item in neg_pool_prev if "id" in item]
        
        logger.info(f"Bodźce w poprzedniej sesji: {len(pos_ids)} pozytywnych, {len(neg_ids)} negatywnych")
        
        pos_images = db.query(Image).filter(Image.id.in_(pos_ids)).all()
        neg_images = db.query(Image).filter(Image.id.in_(neg_ids)).all()
        
        logger.info(f"Znaleziono obrazy w bazie: {len(pos_images)}/{len(pos_ids)} pozytywnych, {len(neg_images)}/{len(neg_ids)} negatywnych")
        
        # Sprawdź, czy mamy dostęp do embeddingów
        missing_embeddings = []
        for img in pos_images + neg_images:
            if not img.embedding:
                missing_embeddings.append(img.id)
                
        if missing_embeddings:
            logger.warning(f"[BŁĄD GENETYCZNY] Brak embeddingów dla obrazów: {missing_embeddings}")
            logger.warning(f"Fallback do losowej puli")
            return generate_random_pool(db, num_pairs)
        
        logger.info(f"Wszystkie embeddingów są dostępne, kontynuuję algorytm genetyczny")
        
        # 3. Przygotowanie danych do obliczeń
        pos_embeddings = [(img.id, img.embedding) for img in pos_images]
        neg_embeddings = [(img.id, img.embedding) for img in neg_images]
        
        # Mapowanie id->embedding i id->item z puli
        pos_embeddings_dict = {img.id: img.embedding for img in pos_images}
        neg_embeddings_dict = {img.id: img.embedding for img in neg_images}
        
        pos_pool_dict = {item["id"]: item for item in pos_pool_prev if "id" in item}
        neg_pool_dict = {item["id"]: item for item in neg_pool_prev if "id" in item}
        
        # 4. Obliczanie centroidów
        # 4.1 Centroid startowy - średnia wszystkich embeddingów z puli
        pos_start_centroid = calculate_centroid([embedding for _, embedding in pos_embeddings])
        neg_start_centroid = calculate_centroid([embedding for _, embedding in neg_embeddings])
        
        logger.info(f"Obliczono centroidy startowe")
        
        # 4.2 Centroid końcowy - średnia ważona z liczbą sukcesów jako wagami
        pos_weights = [pos_pool_dict.get(img_id, {}).get("successes", 0) for img_id, _ in pos_embeddings]
        neg_weights = [neg_pool_dict.get(img_id, {}).get("successes", 0) for img_id, _ in neg_embeddings]
        
        logger.info(f"Wagi (sukcesy) dla pozytywnych: {pos_weights}")
        logger.info(f"Wagi (sukcesy) dla negatywnych: {neg_weights}")
        
        pos_end_centroid = calculate_centroid([embedding for _, embedding in pos_embeddings], pos_weights)
        neg_end_centroid = calculate_centroid([embedding for _, embedding in neg_embeddings], neg_weights)
        
        logger.info(f"Obliczono centroidy końcowe")
        
        # 4.3 Wektor różnicy
        if pos_start_centroid and pos_end_centroid:
            pos_difference_vector = np.array(pos_end_centroid) - np.array(pos_start_centroid)
            logger.info(f"Obliczono wektor różnicy dla pozytywnych, norma: {np.linalg.norm(pos_difference_vector):.6f}")
        else:
            logger.warning(f"[BŁĄD GENETYCZNY] Brak centroidów dla pozytywnych, używam wektora zerowego")
            pos_difference_vector = np.zeros(len(pos_embeddings[0][1]) if pos_embeddings else 0)
            
        if neg_start_centroid and neg_end_centroid:
            neg_difference_vector = np.array(neg_end_centroid) - np.array(neg_start_centroid)
            logger.info(f"Obliczono wektor różnicy dla negatywnych, norma: {np.linalg.norm(neg_difference_vector):.6f}")
        else:
            logger.warning(f"[BŁĄD GENETYCZNY] Brak centroidów dla negatywnych, używam wektora zerowego")
            neg_difference_vector = np.zeros(len(neg_embeddings[0][1]) if neg_embeddings else 0)
            
        # 5. Ranking bodźców
        # 5.1 Dla pozytywnych - sortuj wg liczby sukcesów (malejąco)
        pos_ranking = sorted(
            [(img_id, pos_pool_dict.get(img_id, {}).get("successes", 0)) 
             for img_id, _ in pos_embeddings if pos_pool_dict.get(img_id, {}).get("successes", 0) > 0],
            key=lambda x: x[1],
            reverse=True
        )
        
        # 5.2 Dla negatywnych - sortuj wg liczby przetrwań (malejąco)
        neg_ranking = sorted(
            [(img_id, neg_pool_dict.get(img_id, {}).get("successes", 0)) 
             for img_id, _ in neg_embeddings if neg_pool_dict.get(img_id, {}).get("successes", 0) > 0],
            key=lambda x: x[1],
            reverse=True
        )
        
        logger.info(f"Utworzono ranking: {len(pos_ranking)} pozytywnych, {len(neg_ranking)} negatywnych")
        if pos_ranking:
            logger.info(f"Najlepsze bodźce pozytywne: {pos_ranking[:3]}")
        if neg_ranking:
            logger.info(f"Najlepsze bodźce negatywne: {neg_ranking[:3]}")
        
        # 6. Generowanie nowej puli
        new_pos_pool = []
        new_neg_pool = []
        
        # 6.1 Pozytywne bodźce
        # Łączna liczba sukcesów
        pos_total_successes = sum(successes for _, successes in pos_ranking)
        logger.info(f"Łączna liczba sukcesów pozytywnych: {pos_total_successes}")
        
        # Strategia zależna od liczby sukcesów
        if pos_total_successes > num_pairs:
            logger.info(f"Przypadek A (pos): S > num_pairs, kupuję najlepsze bodźce")
            # Przypadek A: S > num_pairs
            # "Kupujemy" bodźce z rankingu
            points = pos_total_successes - num_pairs
            bought_pos = []
            
            for img_id, successes in pos_ranking:
                bought_pos.append(img_id)
                points -= successes
                if points <= 0:
                    break
            
            logger.info(f"Kupiono {len(bought_pos)} bodźców pozytywnych: {bought_pos}")
            
            # Dodajemy kupione bodźce do nowej puli
            for img_id in bought_pos:
                new_pos_pool.append({
                    "id": img_id,
                    "successes": 0,
                    "failures": 0,
                    "origin": "bought"
                })
                
            # Jeśli nie zapełniliśmy puli, generujemy dzieci
            num_children_needed = num_pairs - len(bought_pos)
            if num_children_needed > 0 and bought_pos:
                # Generowanie dzieci od najlepszych rodziców
                pos_children = generate_children(
                    bought_pos, 
                    pos_embeddings_dict, 
                    pos_difference_vector, 
                    num_children_needed, 
                    db,
                    "POSITIVE",
                    exclude_ids=pos_ids + [item["id"] for item in new_pos_pool]
                )
                
                new_pos_pool.extend(pos_children)
                
            # Jeśli wciąż brakuje obrazów, uzupełniamy losowymi
            if len(new_pos_pool) < num_pairs:
                random_count = num_pairs - len(new_pos_pool)
                random_pos = get_random_images(db, "POSITIVE", random_count, exclude_ids=pos_ids + [item["id"] for item in new_pos_pool])
                
                for img_id in random_pos:
                    new_pos_pool.append({
                        "id": img_id,
                        "successes": 0,
                        "failures": 0,
                        "origin": "random"
                    })
        else:
            # Przypadek B: S <= num_pairs
            # Generujemy tyle dzieci, ile wynosi S
            # Najpierw dodajemy wszystkie obrazy z rankingu jako "bought"
            for img_id, _ in pos_ranking:
                new_pos_pool.append({
                    "id": img_id,
                    "successes": 0,
                    "failures": 0,
                    "origin": "bought"
                })
            
            # Generujemy dzieci na podstawie obrazów z rankingu
            num_children = pos_total_successes if pos_ranking else 0
            if num_children > 0:
                parent_ids = [img_id for img_id, _ in pos_ranking]
                pos_children = generate_children(
                    parent_ids, 
                    pos_embeddings_dict, 
                    pos_difference_vector, 
                    num_children, 
                    db,
                    "POSITIVE",
                    exclude_ids=pos_ids + [item["id"] for item in new_pos_pool]
                )
                
                new_pos_pool.extend(pos_children)
            
            # Jeśli wciąż brakuje obrazów, uzupełniamy losowymi
            if len(new_pos_pool) < num_pairs:
                random_count = num_pairs - len(new_pos_pool)
                random_pos = get_random_images(db, "POSITIVE", random_count, exclude_ids=pos_ids + [item["id"] for item in new_pos_pool])
                
                for img_id in random_pos:
                    new_pos_pool.append({
                        "id": img_id,
                        "successes": 0,
                        "failures": 0,
                        "origin": "random"
                    })
        
        # 6.2 Negatywne bodźce - analogicznie jak dla pozytywnych
        # Łączna liczba sukcesów (przetrwań)
        neg_total_successes = sum(successes for _, successes in neg_ranking)
        
        # Strategia zależna od liczby sukcesów
        if neg_total_successes > num_pairs:
            logger.info(f"Przypadek A (neg): S > num_pairs, kupuję najlepsze bodźce")
            # Przypadek A: S > num_pairs
            # "Kupujemy" bodźce z rankingu
            points = neg_total_successes - num_pairs
            bought_neg = []
            
            for img_id, successes in neg_ranking:
                bought_neg.append(img_id)
                points -= successes
                if points <= 0:
                    break
            
            logger.info(f"Kupiono {len(bought_neg)} bodźców negatywnych: {bought_neg}")
            
            # Dodajemy kupione bodźce do nowej puli
            for img_id in bought_neg:
                new_neg_pool.append({
                    "id": img_id,
                    "successes": 0,
                    "failures": 0,
                    "origin": "bought"
                })
                
            # Jeśli nie zapełniliśmy puli, generujemy dzieci
            num_children_needed = num_pairs - len(bought_neg)
            if num_children_needed > 0 and bought_neg:
                # Generowanie dzieci od najlepszych rodziców
                neg_children = generate_children(
                    bought_neg, 
                    neg_embeddings_dict, 
                    neg_difference_vector, 
                    num_children_needed, 
                    db,
                    "NEGATIVE",
                    exclude_ids=neg_ids + [item["id"] for item in new_neg_pool]
                )
                
                new_neg_pool.extend(neg_children)
                
            # Jeśli wciąż brakuje obrazów, uzupełniamy losowymi
            if len(new_neg_pool) < num_pairs:
                random_count = num_pairs - len(new_neg_pool)
                random_neg = get_random_images(db, "NEGATIVE", random_count, exclude_ids=neg_ids + [item["id"] for item in new_neg_pool])
                
                for img_id in random_neg:
                    new_neg_pool.append({
                        "id": img_id,
                        "successes": 0,
                        "failures": 0,
                        "origin": "random"
                    })
        else:
            # Przypadek B: S <= num_pairs
            # Generujemy tyle dzieci, ile wynosi S
            # Najpierw dodajemy wszystkie obrazy z rankingu jako "bought"
            for img_id, _ in neg_ranking:
                new_neg_pool.append({
                    "id": img_id,
                    "successes": 0,
                    "failures": 0,
                    "origin": "bought"
                })
            
            # Generujemy dzieci na podstawie obrazów z rankingu
            num_children = neg_total_successes if neg_ranking else 0
            if num_children > 0:
                parent_ids = [img_id for img_id, _ in neg_ranking]
                neg_children = generate_children(
                    parent_ids, 
                    neg_embeddings_dict, 
                    neg_difference_vector, 
                    num_children, 
                    db,
                    "NEGATIVE",
                    exclude_ids=neg_ids + [item["id"] for item in new_neg_pool]
                )
                
                new_neg_pool.extend(neg_children)
            
            # Jeśli wciąż brakuje obrazów, uzupełniamy losowymi
            if len(new_neg_pool) < num_pairs:
                random_count = num_pairs - len(new_neg_pool)
                random_neg = get_random_images(db, "NEGATIVE", random_count, exclude_ids=neg_ids + [item["id"] for item in new_neg_pool])
                
                for img_id in random_neg:
                    new_neg_pool.append({
                        "id": img_id,
                        "successes": 0,
                        "failures": 0,
                        "origin": "random"
                    })
        
        # Upewnij się, że mamy dokładnie num_pairs obrazów w każdej puli
        if len(new_pos_pool) > num_pairs:
            new_pos_pool = new_pos_pool[:num_pairs]
        
        if len(new_neg_pool) > num_pairs:
            new_neg_pool = new_neg_pool[:num_pairs]
            
        # Jeśli nie udało się wygenerować wystarczającej liczby obrazów, uzupełnij losowymi
        if len(new_pos_pool) < num_pairs:
            random_pos = get_random_images(db, "POSITIVE", num_pairs - len(new_pos_pool), exclude_ids=[item["id"] for item in new_pos_pool])
            for img_id in random_pos:
                new_pos_pool.append({
                    "id": img_id,
                    "successes": 0,
                    "failures": 0,
                    "origin": "random"
                })
                
        if len(new_neg_pool) < num_pairs:
            random_neg = get_random_images(db, "NEGATIVE", num_pairs - len(new_neg_pool), exclude_ids=[item["id"] for item in new_neg_pool])
            for img_id in random_neg:
                new_neg_pool.append({
                    "id": img_id,
                    "successes": 0,
                    "failures": 0,
                    "origin": "random"
                })
                
        logger.info(f"Zakończono generowanie puli metodą quasi-genetyczną: "
                   f"{len(new_pos_pool)} pozytywnych bodźców, {len(new_neg_pool)} negatywnych bodźców")
                
        return new_pos_pool, new_neg_pool
    
    except Exception as e:
        logger.error(f"Błąd podczas generowania puli quasi-genetyczną: {str(e)}")
        logger.error(traceback.format_exc())
        # Fallback - wygeneruj losową pulę
        return generate_random_pool(db, num_pairs)


def generate_children(
    parent_ids: List[int], 
    embeddings_dict: Dict[int, List[float]], 
    difference_vector: np.ndarray, 
    num_children: int,
    db: Session,
    image_type: str,
    exclude_ids: List[int] = None
) -> List[Dict[str, Any]]:
    """
    Generuje dzieci na podstawie rodziców i wektora różnicy.
    
    Args:
        parent_ids: Lista ID obrazów-rodziców
        embeddings_dict: Słownik mapujący ID na embedding
        difference_vector: Wektor różnicy (kierunek ewolucji)
        num_children: Liczba dzieci do wygenerowania
        db: Obiekt sesji bazy danych
        image_type: Typ obrazu (POSITIVE/NEGATIVE)
        exclude_ids: Lista ID obrazów do wykluczenia
        
    Returns:
        Lista słowników opisujących dzieci
    """
    if exclude_ids is None:
        exclude_ids = []
        
    logger.info(f"Generowanie {num_children} dzieci typu {image_type} z {len(parent_ids)} rodziców")
    
    # Jeśli brak rodziców lub dzieci do wygenerowania, zwróć pustą listę
    if not parent_ids or num_children <= 0:
        logger.warning(f"[BŁĄD DZIECI] Brak rodziców ({len(parent_ids)}) lub liczba dzieci <= 0 ({num_children})")
        return []
    
    # Pobierz wszystkie obrazy danego typu z bazy danych
    all_images = db.query(Image).filter(Image.type == image_type).all()
    all_embeddings = []
    for img in all_images:
        if img.embedding:
            all_embeddings.append((img.id, img.embedding))
        else:
            logger.warning(f"[BŁĄD DZIECI] Obraz {img.id} nie ma embeddingu, pomijam")
            
    if not all_embeddings:
        logger.warning(f"[BŁĄD DZIECI] Brak obrazów z embeddingami typu {image_type}")
        return []
        
    logger.info(f"Znaleziono {len(all_embeddings)} potencjalnych kandydatów na dzieci typu {image_type}")
    
    # Rozdziel dzieci pomiędzy rodziców
    children_per_parent = num_children // len(parent_ids)
    extra_children = num_children % len(parent_ids)
    
    logger.info(f"Rozdzielam dzieci: {children_per_parent} na rodzica + {extra_children} extra dla najlepszych")
    
    children = []
    
    # Dla każdego rodzica wygeneruj przydzieloną liczbę dzieci
    for i, parent_id in enumerate(parent_ids):
        # Liczba dzieci dla tego rodzica
        num_parent_children = children_per_parent
        if i < extra_children:
            num_parent_children += 1
            
        logger.info(f"Generuję {num_parent_children} dzieci dla rodzica {parent_id}")
        
        # Embedding rodzica
        parent_vec = np.array(embeddings_dict[parent_id])
        
        # Wygeneruj dzieci
        for _ in range(num_parent_children):
            # Oblicz embedding dziecka
            child_vec = parent_vec + difference_vector
            
            # Znajdź najbliższy obraz
            child_id, distance = find_nearest_embedding(
                child_vec.tolist(), 
                all_embeddings, 
                exclude_ids + [item["id"] for item in children] + parent_ids
            )
            
            if child_id is None:
                logger.warning(f"[BŁĄD DZIECI] Nie znaleziono odpowiedniego dziecka dla rodzica {parent_id}")
                # Jeśli nie znaleziono odpowiedniego dziecka, spróbuj z modyfikacją wektora
                for alpha in [1.5, 2.0, 3.0]:
                    logger.info(f"Próba z modyfikacją alpha={alpha}")
                    # Wydłuż wektor różnicy
                    modified_child_vec = parent_vec + alpha * difference_vector
                    # Dodaj losowy szum
                    noise = np.random.normal(0, 0.1, size=modified_child_vec.shape)
                    modified_child_vec += noise
                    
                    child_id, distance = find_nearest_embedding(
                        modified_child_vec.tolist(), 
                        all_embeddings, 
                        exclude_ids + [item["id"] for item in children] + parent_ids
                    )
                    
                    if child_id is not None:
                        logger.info(f"Znaleziono dziecko {child_id} dla rodzica {parent_id} z alpha={alpha}, odległość={distance:.6f}")
                        break
                        
                # Jeśli wciąż nie znaleziono, wybierz losowy obraz
                if child_id is None:
                    logger.warning(f"[BŁĄD DZIECI] Nie znaleziono dziecka nawet z modyfikacją, próbuję losowo")
                    remaining_ids = set(img_id for img_id, _ in all_embeddings) - set(exclude_ids) - set([item["id"] for item in children]) - set(parent_ids)
                    if remaining_ids:
                        child_id = random.choice(list(remaining_ids))
                        logger.info(f"Wybrano losowe dziecko {child_id} dla rodzica {parent_id}")
            else:
                logger.info(f"Znaleziono dziecko {child_id} dla rodzica {parent_id}, odległość={distance:.6f}")
            
            if child_id is not None:
                children.append({
                    "id": child_id,
                    "successes": 0,
                    "failures": 0,
                    "origin": "child",
                    "parent": parent_id
                })
                
    logger.info(f"Wygenerowano {len(children)} dzieci typu {image_type}")
    return children


def get_random_images(db: Session, image_type: str, count: int, exclude_ids: List[int] = None) -> List[int]:
    """
    Pobiera losowe obrazy z bazy danych.
    
    Args:
        db: Obiekt sesji bazy danych
        image_type: Typ obrazu (POSITIVE/NEGATIVE)
        count: Liczba obrazów do pobrania
        exclude_ids: Lista ID obrazów do wykluczenia
        
    Returns:
        Lista ID obrazów
    """
    if count <= 0:
        return []
        
    if exclude_ids is None:
        exclude_ids = []
        
    query = db.query(Image.id).filter(Image.type == image_type)
    
    if exclude_ids:
        query = query.filter(~Image.id.in_(exclude_ids))
        
    query = query.order_by(func.random()).limit(count)
    results = query.all()
    
    return [img_id for img_id, in results]


def generate_random_pool(db: Session, num_pairs: int) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Generuje losową pulę obrazów.
    
    Args:
        db: Obiekt sesji bazy danych
        num_pairs: Liczba par obrazów w puli
        
    Returns:
        Tuple (pos_pool_json, neg_pool_json) z losowymi pulami obrazów
    """
    pos_ids = get_random_images(db, "POSITIVE", num_pairs)
    neg_ids = get_random_images(db, "NEGATIVE", num_pairs)
    
    pos_pool_json = []
    for img_id in pos_ids:
        pos_pool_json.append({
            "id": img_id,
            "successes": 0,
            "failures": 0,
            "origin": "random"
        })
        
    neg_pool_json = []
    for img_id in neg_ids:
        neg_pool_json.append({
            "id": img_id,
            "successes": 0,
            "failures": 0,
            "origin": "random"
        })
        
    return pos_pool_json, neg_pool_json


@router.post("/sessions/generate-new-pool")
def generate_new_pool_for_session(
    request: schemas.GenerateNewPoolRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Rozpoczyna generowanie nowej puli dla użytkownika na podstawie poprzedniej sesji."""
    try:
        logger.info(f"Rozpoczynam generowanie nowej puli dla użytkownika {current_user.id}")
        
        # Sprawdzamy, czy istnieje już sesja PENDING dla tego użytkownika
        existing_pending = db.query(SessionModel).filter(
            SessionModel.user_id == current_user.id,
            SessionModel.status == "PENDING"
        ).first()
        
        if existing_pending:
            logger.info(f"Istnieje już sesja PENDING (id={existing_pending.id}) dla użytkownika {current_user.id}")
            return {"status": "success", "message": "Sesja PENDING już istnieje"}
        
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
            previous_session = db.query(SessionModel).filter(
                SessionModel.user_id == current_user.id,
                SessionModel.status == "COMPLETED"
            ).order_by(SessionModel.ended_at.desc()).first()
        
        # Jeśli brak poprzedniej sesji, zwracamy błąd
        if not previous_session:
            logger.warning(f"Brak poprzedniej sesji dla użytkownika {current_user.id}")
            raise HTTPException(status_code=404, detail="Brak poprzedniej sesji")
        
        # Generujemy nowe pule na podstawie poprzedniej sesji
        pos_pool_json, neg_pool_json = generate_pool_with_genetic_algorithm(previous_session, db)
        
        # Tworzymy nową sesję w stanie PENDING
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