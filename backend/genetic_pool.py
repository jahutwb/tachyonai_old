import logging
import random
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
import json
from datetime import datetime

from .database import SessionLocal, engine
from .models import Image as ImageModel, ImageTypeEnum, Session as SessionModel, SessionStatusEnum
from .embedding import (
    build_faiss_index, get_image_embeddings, calculate_centroid, 
    find_nearest_image
)
from . import models

# Konfiguracja loggera
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class PoolImageItem:
    """Reprezentacja pojedynczego elementu w puli obrazów."""
    def __init__(
        self, 
        image_id: int, 
        successes: int = 0, 
        failures: int = 0,
        origin: Optional[str] = None,
        parent: Optional[int] = None
    ):
        self.id = image_id
        self.successes = successes
        self.failures = failures
        self.origin = origin  # "child", "bought", "random"
        self.parent = parent  # ID rodzica, jeśli origin="child"
    
    def to_dict(self) -> Dict[str, Any]:
        """Konwertuje obiekt na słownik."""
        result = {
            "id": self.id,
            "successes": self.successes,
            "failures": self.failures
        }
        if self.origin:
            result["origin"] = self.origin
        if self.parent:
            result["parent"] = self.parent
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PoolImageItem':
        """Tworzy obiekt ze słownika."""
        return cls(
            image_id=data["id"],
            successes=data.get("successes", 0),
            failures=data.get("failures", 0),
            origin=data.get("origin"),
            parent=data.get("parent")
        )


def create_initial_pool(
    db: Session, 
    positive_count: int = 6, 
    negative_count: int = 6
) -> Tuple[List[PoolImageItem], List[PoolImageItem]]:
    """
    Tworzy początkową pulę obrazów.
    
    Args:
        db: Sesja bazy danych
        positive_count: Liczba obrazów pozytywnych
        negative_count: Liczba obrazów negatywnych
    
    Returns:
        Tuple zawierające listy PoolImageItem dla obrazów pozytywnych i negatywnych
    """
    # Pobierz wszystkie obrazy pozytywne z embeddingami
    pos_images = db.query(ImageModel).filter(
        ImageModel.type == ImageTypeEnum.POSITIVE,
        ImageModel.embedding.isnot(None)
    ).all()
    
    # Pobierz wszystkie obrazy negatywne z embeddingami
    neg_images = db.query(ImageModel).filter(
        ImageModel.type == ImageTypeEnum.NEGATIVE,
        ImageModel.embedding.isnot(None)
    ).all()
    
    logger.info(f"Znaleziono {len(pos_images)} obrazów pozytywnych i {len(neg_images)} obrazów negatywnych z embeddingami.")
    
    # Sprawdź, czy mamy wystarczającą liczbę obrazów
    if len(pos_images) < positive_count:
        logger.warning(f"Za mało obrazów pozytywnych: {len(pos_images)}/{positive_count}.")
        positive_count = len(pos_images)
    
    if len(neg_images) < negative_count:
        logger.warning(f"Za mało obrazów negatywnych: {len(neg_images)}/{negative_count}.")
        negative_count = len(neg_images)
    
    # Losowo wybierz obrazy do początkowej puli
    pos_pool = [PoolImageItem(img.id, origin="random") for img in random.sample(pos_images, positive_count)]
    neg_pool = [PoolImageItem(img.id, origin="random") for img in random.sample(neg_images, negative_count)]
    
    return pos_pool, neg_pool


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
        SessionModel.status == SessionStatusEnum.COMPLETED
    ).order_by(SessionModel.ended_at.desc()).first()


def get_active_session(db: Session, user_id: int) -> Optional[SessionModel]:
    """
    Pobiera aktywną sesję użytkownika.
    
    Args:
        db: Sesja bazy danych
        user_id: ID użytkownika
    
    Returns:
        Aktywna sesja lub None, jeśli nie ma żadnej
    """
    return db.query(SessionModel).filter(
        SessionModel.user_id == user_id,
        SessionModel.status == SessionStatusEnum.ACTIVE
    ).first()


def create_new_session(
    db: Session, 
    user_id: int, 
    pos_pool: List[PoolImageItem], 
    neg_pool: List[PoolImageItem]
) -> SessionModel:
    """
    Tworzy nową sesję z podanymi pulami obrazów.
    
    Args:
        db: Sesja bazy danych
        user_id: ID użytkownika
        pos_pool: Lista PoolImageItem dla obrazów pozytywnych
        neg_pool: Lista PoolImageItem dla obrazów negatywnych
    
    Returns:
        Nowa sesja
    """
    # Konwersja pul do JSON
    pos_pool_json = [item.to_dict() for item in pos_pool]
    neg_pool_json = [item.to_dict() for item in neg_pool]
    
    # Utwórz nową sesję
    session = SessionModel(
        user_id=user_id,
        status=SessionStatusEnum.ACTIVE,
        pos_pool_json=pos_pool_json,
        neg_pool_json=neg_pool_json,
        session_profit_factor=1.0,
        remaining_pairs=min(len(pos_pool), len(neg_pool)),
        started_at=datetime.now()
    )
    
    db.add(session)
    db.commit()
    db.refresh(session)
    
    return session


def generate_pool_from_last_session(
    db: Session, 
    user_id: int, 
    num_pairs: int = 6
) -> Tuple[List[PoolImageItem], List[PoolImageItem]]:
    """
    Generuje nową pulę obrazów na podstawie ostatniej zakończonej sesji.
    
    Args:
        db: Sesja bazy danych
        user_id: ID użytkownika
        num_pairs: Liczba par obrazów w nowej puli
    
    Returns:
        Tuple zawierające listy PoolImageItem dla obrazów pozytywnych i negatywnych
    """
    # Pobierz ostatnią zakończoną sesję
    last_session = get_last_completed_session(db, user_id)
    
    if not last_session:
        logger.info(f"Brak zakończonej sesji dla użytkownika {user_id}. Tworzenie początkowej puli.")
        return create_initial_pool(db, num_pairs, num_pairs)
    
    # Odtwórz pule z ostatniej sesji
    last_pos_pool = [PoolImageItem.from_dict(item) for item in last_session.pos_pool_json]
    last_neg_pool = [PoolImageItem.from_dict(item) for item in last_session.neg_pool_json]
    
    # Algorytm quasi-genetyczny dla pozytywnych obrazów
    pos_pool = generate_new_pool(db, last_pos_pool, is_positive=True, num_pairs=num_pairs)
    
    # Algorytm quasi-genetyczny dla negatywnych obrazów
    neg_pool = generate_new_pool(db, last_neg_pool, is_positive=False, num_pairs=num_pairs)
    
    return pos_pool, neg_pool


def generate_new_pool(
    db: Session, 
    last_pool: List[PoolImageItem], 
    is_positive: bool, 
    num_pairs: int = 6
) -> List[PoolImageItem]:
    """
    Generuje nową pulę obrazów na podstawie poprzedniej puli i wyników.
    
    Args:
        db: Sesja bazy danych
        last_pool: Poprzednia pula obrazów
        is_positive: Czy to pula obrazów pozytywnych
        num_pairs: Liczba par obrazów w nowej puli
    
    Returns:
        Lista PoolImageItem dla nowej puli obrazów
    """
    # Przebuduj indeks FAISS, jeśli nie jest dostępny
    build_faiss_index(db)
    
    # Pobierz ID obrazów i embeddingi
    image_ids = [item.id for item in last_pool]
    image_embeddings = get_image_embeddings(db, image_ids)
    
    # Jeśli brak embeddingów, utwórz nową pulę losowo
    if not image_embeddings:
        logger.warning(f"Brak embeddingów dla poprzedniej puli {'pozytywnych' if is_positive else 'negatywnych'} obrazów. Tworzenie losowej puli.")
        initial_pos, initial_neg = create_initial_pool(db, num_pairs, num_pairs)
        return initial_pos if is_positive else initial_neg
    
    # Oblicz centroid początkowy (średnia embeddingów wszystkich obrazów z puli)
    start_centroid_embeddings = [embedding for img_id, embedding in image_embeddings.items()]
    start_centroid = calculate_centroid(start_centroid_embeddings)
    
    # Stwórz ranking obrazów (tylko te z co najmniej 1 sukcesem)
    success_images = [item for item in last_pool if item.successes >= 1]
    success_images.sort(key=lambda x: x.successes, reverse=True)
    
    # Oblicz łączną liczbę sukcesów
    total_successes = sum(item.successes for item in success_images)
    
    # Oblicz centroid końcowy (średnia ważona embeddingów obrazów z co najmniej 1 sukcesem)
    if success_images and total_successes > 0:
        end_centroid_embeddings = []
        weights = []
        
        for item in success_images:
            if item.id in image_embeddings:
                end_centroid_embeddings.append(image_embeddings[item.id])
                weights.append(item.successes)
        
        end_centroid = calculate_centroid(end_centroid_embeddings, weights)
        
        # Oblicz wektor różnicy
        if start_centroid and end_centroid and len(start_centroid) == len(end_centroid):
            difference_vector = np.array(end_centroid) - np.array(start_centroid)
        else:
            logger.warning("Nie można obliczyć wektora różnicy. Używam zerowego wektora.")
            if start_centroid:
                difference_vector = np.zeros_like(np.array(start_centroid))
            else:
                difference_vector = np.zeros(512)  # Domyślny wymiar dla CLIP ViT-B/32
    else:
        logger.warning(f"Brak obrazów z sukcesami w poprzedniej puli {'pozytywnych' if is_positive else 'negatywnych'} obrazów.")
        difference_vector = np.zeros(512)  # Domyślny wymiar dla CLIP ViT-B/32
    
    # Strategia tworzenia nowej puli
    new_pool = []
    
    # Przypadek A: S > num_pairs
    if total_successes > num_pairs:
        points = total_successes - num_pairs
        logger.info(f"Przypadek A: {total_successes} sukcesów > {num_pairs} par. Points: {points}")
        
        # "Kupujemy" obrazy z rankingu
        for item in success_images:
            if points <= 0:
                break
            
            # Kupujemy obraz, płacąc jego liczbą sukcesów
            points -= item.successes
            new_item = PoolImageItem(item.id, origin="bought")
            new_pool.append(new_item)
            logger.info(f"Kupiono obraz {item.id} z {item.successes} sukcesami.")
        
        # Pozostałe sloty wypełniamy dziećmi
        remaining_slots = num_pairs - len(new_pool)
        if remaining_slots > 0:
            logger.info(f"Pozostało {remaining_slots} slotów do wypełnienia dziećmi.")
            children = generate_children(
                db, success_images, difference_vector, 
                count=remaining_slots, is_positive=is_positive,
                exclude_ids=[item.id for item in new_pool]
            )
            new_pool.extend(children)
    
    # Przypadek B: S <= num_pairs
    else:
        logger.info(f"Przypadek B: {total_successes} sukcesów <= {num_pairs} par.")
        
        # Generujemy tyle dzieci, ile mamy sukcesów (lub mniej, jeśli success_images < total_successes)
        children_count = min(len(success_images), total_successes)
        if children_count > 0:
            logger.info(f"Generowanie {children_count} dzieci.")
            children = generate_children(
                db, success_images, difference_vector, 
                count=children_count, is_positive=is_positive
            )
            new_pool.extend(children)
        
        # Pozostałe sloty wypełniamy losowo
        remaining_slots = num_pairs - len(new_pool)
        if remaining_slots > 0:
            logger.info(f"Pozostało {remaining_slots} slotów do wypełnienia losowo.")
            
            # Pobierz obrazy, które nie są już w puli
            exclude_ids = [item.id for item in new_pool]
            random_items = get_random_images(
                db, count=remaining_slots, 
                is_positive=is_positive, 
                exclude_ids=exclude_ids
            )
            new_pool.extend(random_items)
    
    return new_pool


def generate_children(
    db: Session,
    parent_items: List[PoolImageItem],
    difference_vector: np.ndarray,
    count: int,
    is_positive: bool,
    exclude_ids: List[int] = None
) -> List[PoolImageItem]:
    """
    Generuje dzieci na podstawie rodziców i wektora różnicy.
    
    Args:
        db: Sesja bazy danych
        parent_items: Lista rodziców (PoolImageItem)
        difference_vector: Wektor różnicy (np.ndarray)
        count: Liczba dzieci do wygenerowania
        is_positive: Czy to pula obrazów pozytywnych
        exclude_ids: Lista ID obrazów do wykluczenia
    
    Returns:
        Lista PoolImageItem dla dzieci
    """
    if not parent_items:
        logger.warning("Brak rodziców do generowania dzieci.")
        return []
    
    if exclude_ids is None:
        exclude_ids = []
    
    # Pobierz embeddingi rodziców
    parent_ids = [item.id for item in parent_items]
    parent_embeddings = get_image_embeddings(db, parent_ids)
    
    # Sprawdź, czy mamy embeddingi
    valid_parents = [item for item in parent_items if item.id in parent_embeddings]
    if not valid_parents:
        logger.warning("Brak embeddingów dla rodziców.")
        return []
    
    # Sortuj rodziców wg liczby sukcesów (malejąco)
    valid_parents.sort(key=lambda x: x.successes, reverse=True)
    
    # Rozdziel dzieci między rodziców
    children_per_parent = count // len(valid_parents)
    extra_children = count % len(valid_parents)
    
    logger.info(f"Generowanie {count} dzieci od {len(valid_parents)} rodziców.")
    logger.info(f"Każdy rodzic dostaje {children_per_parent} dzieci, a {extra_children} najlepszych dostaje po 1 dodatkowym.")
    
    # Wygeneruj dzieci
    children = []
    for i, parent in enumerate(valid_parents):
        # Liczba dzieci dla tego rodzica
        parent_children_count = children_per_parent
        if i < extra_children:
            parent_children_count += 1
        
        parent_embedding = parent_embeddings[parent.id]
        
        for _ in range(parent_children_count):
            # Generuj dziecko
            child_embedding = np.array(parent_embedding) + difference_vector
            
            # Normalizuj wektor
            norm = np.linalg.norm(child_embedding)
            if norm > 0:
                child_embedding = child_embedding / norm
            
            # Znajdź najbliższy obraz
            child_id = find_nearest_image(
                child_embedding.tolist(),
                positive=is_positive,
                exclude_ids=exclude_ids + [parent.id] + [child.id for child in children]
            )
            
            if child_id:
                # Dodaj dziecko do listy
                child = PoolImageItem(
                    image_id=child_id,
                    origin="child",
                    parent=parent.id
                )
                children.append(child)
                logger.info(f"Wygenerowano dziecko {child_id} od rodzica {parent.id}.")
            else:
                # Jeśli nie znaleziono dziecka, spróbuj z większym przesunięciem
                for alpha in [1.5, 2.0, 3.0]:
                    logger.info(f"Próba z większym przesunięciem (alpha={alpha}).")
                    child_embedding = np.array(parent_embedding) + alpha * difference_vector
                    
                    # Normalizuj wektor
                    norm = np.linalg.norm(child_embedding)
                    if norm > 0:
                        child_embedding = child_embedding / norm
                    
                    child_id = find_nearest_image(
                        child_embedding.tolist(),
                        positive=is_positive,
                        exclude_ids=exclude_ids + [parent.id] + [child.id for child in children]
                    )
                    
                    if child_id:
                        child = PoolImageItem(
                            image_id=child_id,
                            origin="child",
                            parent=parent.id
                        )
                        children.append(child)
                        logger.info(f"Wygenerowano dziecko {child_id} od rodzica {parent.id} z alpha={alpha}.")
                        break
                else:
                    # Jeśli nadal nie znaleziono, dodaj losowy obraz
                    logger.warning(f"Nie znaleziono dziecka dla rodzica {parent.id}. Używam losowego obrazu.")
                    random_items = get_random_images(
                        db, count=1, 
                        is_positive=is_positive, 
                        exclude_ids=exclude_ids + [parent.id] + [child.id for child in children]
                    )
                    if random_items:
                        children.extend(random_items)
    
    return children


def get_random_images(
    db: Session, 
    count: int, 
    is_positive: bool, 
    exclude_ids: List[int] = None
) -> List[PoolImageItem]:
    """
    Pobiera losowe obrazy z bazy danych.
    
    Args:
        db: Sesja bazy danych
        count: Liczba obrazów do pobrania
        is_positive: Czy to obrazy pozytywne
        exclude_ids: Lista ID obrazów do wykluczenia
    
    Returns:
        Lista PoolImageItem dla losowych obrazów
    """
    if exclude_ids is None:
        exclude_ids = []
    
    # Pobierz wszystkie obrazy z embeddingami
    query = db.query(ImageModel).filter(
        ImageModel.embedding.isnot(None)
    )
    
    if is_positive:
        query = query.filter(ImageModel.type == ImageTypeEnum.POSITIVE)
    else:
        query = query.filter(ImageModel.type == ImageTypeEnum.NEGATIVE)
    
    if exclude_ids:
        query = query.filter(~ImageModel.id.in_(exclude_ids))
    
    images = query.all()
    
    # Jeśli nie ma wystarczającej liczby obrazów, użyj wszystkich dostępnych
    if len(images) < count:
        logger.warning(f"Za mało obrazów: {len(images)}/{count}. Używam wszystkich dostępnych.")
        count = len(images)
    
    if count == 0:
        return []
    
    # Losowo wybierz obrazy
    selected_images = random.sample(images, count)
    
    # Utwórz PoolImageItem
    return [PoolImageItem(img.id, origin="random") for img in selected_images]


def get_or_create_session(db: Session, user_id: int) -> SessionModel:
    """
    Pobiera aktywną sesję lub tworzy nową.
    
    Args:
        db: Sesja bazy danych
        user_id: ID użytkownika
    
    Returns:
        Aktywna lub nowa sesja
    """
    # Sprawdź, czy jest aktywna sesja
    active_session = get_active_session(db, user_id)
    if active_session:
        logger.info(f"Znaleziono aktywną sesję {active_session.id} dla użytkownika {user_id}.")
        return active_session
    
    # Generuj nową pulę obrazów
    pos_pool, neg_pool = generate_pool_from_last_session(db, user_id)
    
    # Utwórz nową sesję
    new_session = create_new_session(db, user_id, pos_pool, neg_pool)
    logger.info(f"Utworzono nową sesję {new_session.id} dla użytkownika {user_id}.")
    
    return new_session


def process_round_result(
    db: Session, 
    session_id: int, 
    round_id: int, 
    pos_id: int, 
    neg_id: int,
    result: bool,
    profit_fraction: float
) -> SessionModel:
    """
    Przetwarza wynik rundy i aktualizuje sesję.
    
    Args:
        db: Sesja bazy danych
        session_id: ID sesji
        round_id: ID rundy
        pos_id: ID obrazu pozytywnego
        neg_id: ID obrazu negatywnego
        result: Wynik rundy (True = sukces, False = porażka)
        profit_fraction: Część zysku z rundy
    
    Returns:
        Zaktualizowana sesja
    """
    # Pobierz sesję
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        logger.error(f"Nie znaleziono sesji {session_id}.")
        return None
    
    # Pobierz pule obrazów
    pos_pool = [PoolImageItem.from_dict(item) for item in session.pos_pool_json]
    neg_pool = [PoolImageItem.from_dict(item) for item in session.neg_pool_json]
    
    # Zaktualizuj współczynnik zysku sesji
    session.session_profit_factor *= (1 + profit_fraction)
    
    # Zaktualizuj obrazy w bazie danych
    pos_image = db.query(ImageModel).filter(ImageModel.id == pos_id).first()
    neg_image = db.query(ImageModel).filter(ImageModel.id == neg_id).first()
    
    if result:  # Sukces
        # Oba obrazy zostają w puli, zaktualizuj liczniki
        pos_item = next((item for item in pos_pool if item.id == pos_id), None)
        neg_item = next((item for item in neg_pool if item.id == neg_id), None)
        
        if pos_item:
            pos_item.successes += 1
        
        if neg_item:
            pos_item.successes += 1  # Neg też ma sukces, bo przetrwał
        
        # Zaktualizuj liczniki w bazie
        if pos_image:
            pos_image.total_successes += 1
            pos_image.total_profit_factor *= (1 + profit_fraction)
        
        if neg_image:
            neg_image.total_successes += 1
            neg_image.total_profit_factor *= (1 + profit_fraction)
    else:  # Porażka
        # Oba obrazy są usuwane z puli, zaktualizuj liczniki
        pos_pool = [item for item in pos_pool if item.id != pos_id]
        neg_pool = [item for item in neg_pool if item.id != neg_id]
        
        # Zaktualizuj liczniki w bazie
        if pos_image:
            pos_image.total_failures += 1
        
        if neg_image:
            neg_image.total_failures += 1
        
        # Zmniejsz liczbę pozostałych par
        session.remaining_pairs -= 1
    
    # Zaktualizuj pule JSON
    session.pos_pool_json = [item.to_dict() for item in pos_pool]
    session.neg_pool_json = [item.to_dict() for item in neg_pool]
    
    # Jeśli nie ma więcej par, zakończ sesję
    if session.remaining_pairs <= 0:
        session.status = SessionStatusEnum.COMPLETED
        session.ended_at = datetime.now()
    
    # Zapisz zmiany w bazie
    db.commit()
    db.refresh(session)
    
    return session


def get_next_round_images(db: Session, session_id: int) -> Tuple[Optional[int], Optional[int]]:
    """
    Pobiera obrazy na następną rundę.
    
    Args:
        db: Sesja bazy danych
        session_id: ID sesji
    
    Returns:
        Tuple (pos_id, neg_id) lub (None, None), jeśli nie ma więcej obrazów
    """
    # Pobierz sesję
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session or session.status != SessionStatusEnum.ACTIVE or session.remaining_pairs <= 0:
        logger.warning(f"Sesja {session_id} nie jest aktywna lub nie ma więcej par.")
        return None, None
    
    # Pobierz pule obrazów
    pos_pool = [PoolImageItem.from_dict(item) for item in session.pos_pool_json]
    neg_pool = [PoolImageItem.from_dict(item) for item in session.neg_pool_json]
    
    if not pos_pool or not neg_pool:
        logger.warning(f"Sesja {session_id} ma puste pule obrazów.")
        return None, None
    
    # Losowo wybierz jeden obraz z każdej puli
    pos_item = random.choice(pos_pool)
    neg_item = random.choice(neg_pool)
    
    return pos_item.id, neg_item.id 