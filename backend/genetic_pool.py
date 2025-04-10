import logging
import random
import numpy as np
from typing import List, Dict, Any, Optional, Tuple, Union
from sqlalchemy.orm import Session
import json
from datetime import datetime
import traceback

from .database import SessionLocal, engine
from .models import Image as ImageModel, Session as SessionModel, ImageTypeEnum, SessionStatusEnum
from .embedding import (
    build_faiss_index, get_image_embeddings, find_nearest_image
)
from . import models
from sqlalchemy import func

# Konfiguracja loggera
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class PoolImageItem:
    """Reprezentuje obraz w puli genetycznej."""
    
    def __init__(self, image_id: int, origin: str = "random", successes: int = 0):
        self.id = image_id
        self.origin = origin
        self.successes = successes
    
    def to_dict(self) -> Dict[str, Any]:
        """Konwertuje obiekt na słownik."""
        return {
            "id": self.id,
            "origin": self.origin,
            "successes": self.successes
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PoolImageItem':
        """Tworzy obiekt z słownika."""
        return cls(
            image_id=data.get("id"),
            origin=data.get("origin", "random"),
            successes=data.get("successes", 0)
        )


def get_random_images(
    db: Session, 
    count: int, 
    is_positive: bool, 
    exclude_ids: List[int] = None,
    as_pool_items: bool = False
) -> Union[List[ImageModel], List[PoolImageItem]]:
    """
    Pobiera losowe obrazy z bazy danych.
    
    Args:
        db: Sesja bazy danych
        count: Liczba obrazów do pobrania
        is_positive: Czy to obrazy pozytywne
        exclude_ids: Lista ID obrazów do wykluczenia
        as_pool_items: Czy zwrócić jako obiekty PoolImageItem (True) czy jako obiekty ImageModel (False)
    
    Returns:
        Lista obrazów (ImageModel lub PoolImageItem)
    """
    # Przygotuj zapytanie
    query = db.query(ImageModel).filter(
        ImageModel.type == (ImageTypeEnum.POSITIVE if is_positive else ImageTypeEnum.NEGATIVE)
    )
    
    # Wyklucz obrazy, jeśli podano
    if exclude_ids:
        query = query.filter(~ImageModel.id.in_(exclude_ids))
    
    # Pobierz losowe obrazy
    images = query.order_by(func.random()).limit(count).all()
    
    # Jeśli potrzebujemy PoolImageItem, konwertuj
    if as_pool_items:
        return [PoolImageItem(img.id, origin="random") for img in images]
    
    return images


def get_random_images_as_pool_items(
    db: Session, 
    count: int, 
    is_positive: bool, 
    exclude_ids: List[int] = None
) -> List[PoolImageItem]:
    """
    Pobiera losowe obrazy i konwertuje je na PoolImageItem.
    
    Args:
        db: Sesja bazy danych
        count: Liczba obrazów do pobrania
        is_positive: Czy to obrazy pozytywne
        exclude_ids: Lista ID obrazów do wykluczenia
    
    Returns:
        Lista PoolImageItem dla losowych obrazów
    """
    return get_random_images(db, count, is_positive, exclude_ids, as_pool_items=True)


def get_random_pool(db: Session, num_pairs: int = 6) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Tworzy losową pulę obrazów.
    
    Args:
        db: Sesja bazy danych
        num_pairs: Liczba par obrazów w puli
    
    Returns:
        Tuple zawierające listy słowników dla obrazów pozytywnych i negatywnych
    """
    # Pobierz losowe obrazy pozytywne i negatywne
    pos_images = get_random_images_as_pool_items(db, num_pairs, is_positive=True)
    neg_images = get_random_images_as_pool_items(db, num_pairs, is_positive=False)
    
    # Konwersja na słowniki
    pos_pool_dict = [item.to_dict() for item in pos_images]
    neg_pool_dict = [item.to_dict() for item in neg_images]
    
    return pos_pool_dict, neg_pool_dict


def generate_children(
    db: Session,
    parent_items: List[PoolImageItem],
    difference_vector: np.ndarray,
    count: int,
    is_positive: bool,
    exclude_ids: List[int] = None,
    previous_pool_ids: List[int] = None
) -> List[PoolImageItem]:
    """
    Generuje dzieci na podstawie rodziców i wektora różnicy.
    
    Args:
        db: Sesja bazy danych
        parent_items: Lista rodziców (PoolImageItem)
        difference_vector: Wektor różnicy (np.ndarray)
        count: Liczba dzieci do wygenerowania
        is_positive: Czy to dzieci pozytywne
        exclude_ids: Lista ID obrazów do wykluczenia
        previous_pool_ids: Lista ID obrazów z poprzedniej puli
    
    Returns:
        Lista PoolImageItem dla dzieci
    """
    # Jeśli brak rodziców, zwróć pustą listę
    if not parent_items:
        logger.warning("Brak rodziców do generowania dzieci.")
        return []
    
    # Pobierz embeddingi dla rodziców
    parent_ids = [item.id for item in parent_items]
    parent_embeddings = get_image_embeddings(db, parent_ids)
    
    # Jeśli brak embeddingów, zwróć pustą listę
    if not parent_embeddings:
        logger.warning("Brak embeddingów dla rodziców.")
        return []
    
    # Inicjalizuj listę dzieci
    children = []
    
    # Przygotuj listę ID do wykluczenia
    if exclude_ids is None:
        exclude_ids = []
    
    if previous_pool_ids is not None:
        exclude_ids.extend(previous_pool_ids)
    
    # Dodaj ID rodziców do wykluczenia
    exclude_ids.extend(parent_ids)
    
    # Generuj dzieci
    for i in range(count):
        # Wybierz losowego rodzica
        parent_item = random.choice(parent_items)
        parent_id = parent_item.id
        
        # Pobierz embedding rodzica
        if parent_id not in parent_embeddings:
            logger.warning(f"Brak embeddingu dla rodzica {parent_id}.")
            continue
        
        parent_embedding = parent_embeddings[parent_id]
        
        # Generuj dziecko
        found_child = False
        attempts = 0
        max_attempts = 10
        
        while not found_child and attempts < max_attempts:
            # Dodaj losowy szum do wektora różnicy
            noise = np.random.randn(len(difference_vector)) * 0.1
            child_direction = difference_vector + noise
            
            # Normalizacja wektora
            norm = np.linalg.norm(child_direction)
            if norm > 0:
                child_direction = child_direction / norm
            
            # Oblicz embedding dziecka (przesunięcie w kierunku wektora różnicy)
            shift_scale = random.uniform(0.1, 0.3)
            child_embedding = np.array(parent_embedding) + child_direction * shift_scale
            
            # Normalizacja embeddingu dziecka
            norm = np.linalg.norm(child_embedding)
            if norm > 0:
                child_embedding = child_embedding / norm
            
            # Znajdź najbliższy obraz do embeddingu dziecka
            child_id = find_nearest_image(
                db, 
                child_embedding.tolist(), 
                exclude_ids=exclude_ids
            )
            
            if child_id:
                # Dodaj dziecko do listy
                child = PoolImageItem(
                    image_id=child_id,
                    origin=f"child_of_{parent_id}"
                )
                children.append(child)
                
                # Dodaj ID dziecka do wykluczenia
                exclude_ids.append(child_id)
                
                found_child = True
                logger.info(f"Wygenerowano dziecko {child_id} z rodzica {parent_id}.")
            else:
                attempts += 1
        
        # Jeśli nie znaleziono dziecka po próbach z losowym szumem, 
        # spróbuj z większym przesunięciem
        if not found_child:
            logger.warning(f"Nie znaleziono dziecka dla rodzica {parent_id} po {max_attempts} próbach.")
            
            # Spróbuj z większym przesunięciem
            shift_scale = random.uniform(0.3, 0.5)
            child_embedding = np.array(parent_embedding) + difference_vector * shift_scale
            
            # Normalizacja embeddingu dziecka
            norm = np.linalg.norm(child_embedding)
            if norm > 0:
                child_embedding = child_embedding / norm
            
            # Znajdź najbliższy obraz do embeddingu dziecka
            child_id = find_nearest_image(
                db, 
                child_embedding.tolist(), 
                exclude_ids=exclude_ids
            )
            
            if child_id:
                # Dodaj dziecko do listy
                child = PoolImageItem(
                    image_id=child_id,
                    origin=f"child_of_{parent_id}_large_shift"
                )
                children.append(child)
                
                # Dodaj ID dziecka do wykluczenia
                exclude_ids.append(child_id)
                
                logger.info(f"Wygenerowano dziecko {child_id} z rodzica {parent_id} z większym przesunięciem.")
    
    # Jeśli nie udało się wygenerować wystarczającej liczby dzieci, uzupełnij losowymi obrazami
    if len(children) < count:
        missing_count = count - len(children)
        logger.warning(f"Wygenerowano tylko {len(children)}/{count} dzieci. Uzupełniam {missing_count} losowymi obrazami.")
        
        # Pobierz losowe obrazy
        random_items = get_random_images_as_pool_items(
            db, missing_count, is_positive, exclude_ids
        )
        children.extend(random_items)
    
    return children


def calculate_centroids(
    pool_items: List[Dict[str, Any]], 
    embeddings_dict: Dict[int, List[float]]
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Oblicza centroidy początkowe i końcowe oraz wektor różnicy.
    
    Args:
        pool_items: Lista elementów puli
        embeddings_dict: Słownik embeddingów {id obrazu: embedding}
    
    Returns:
        Tuple zawierające centroid początkowy, końcowy i wektor różnicy
    """
    # Pobierz embeddingi dla wszystkich obrazów
    all_embeddings = []
    for item in pool_items:
        img_id = item["id"]
        if img_id in embeddings_dict:
            all_embeddings.append(embeddings_dict[img_id])
    
    # Jeśli brak embeddingów, zwróć puste wektory
    if not all_embeddings:
        logger.warning("Brak embeddingów dla obrazów w puli.")
        return np.zeros(512), np.zeros(512), np.zeros(512)
    
    # Oblicz centroid początkowy (średnia wszystkich embeddingów)
    if len(all_embeddings) == 1:
        centroid = calculate_centroid(all_embeddings)
        return centroid, centroid, np.zeros(len(centroid))
    
    start_centroid = calculate_centroid(all_embeddings)
    
    # Pobierz embeddingi dla obrazów z sukcesami
    successful_embeddings = []
    weights = []
    
    for item in pool_items:
        img_id = item["id"]
        successes = item.get("successes", 0)
        if successes > 0 and img_id in embeddings_dict:
            successful_embeddings.append(embeddings_dict[img_id])
            weights.append(successes)
    
    # Jeśli brak obrazów z sukcesami, użyj centroidu początkowego jako końcowego
    if not successful_embeddings:
        logger.warning("Brak obrazów z sukcesami.")
        return start_centroid, start_centroid, np.zeros(len(start_centroid))
    
    # Oblicz centroid końcowy (średnia ważona embeddingów obrazów z sukcesami)
    end_centroid = calculate_centroid(successful_embeddings, weights)
    
    # Oblicz wektor różnicy (kierunek ewolucji)
    difference_vector = np.array(end_centroid) - np.array(start_centroid)
    
    # Normalizacja wektora różnicy
    norm = np.linalg.norm(difference_vector)
    if norm > 0:
        difference_vector = difference_vector / norm
    
    logger.info("Obliczono centroidy i wektor różnicy")
    
    return start_centroid, end_centroid, difference_vector


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


def process_pool_generation(
    db: Session,
    successful_sorted: List[Dict[str, Any]],
    difference_vector: np.ndarray,
    total_successes: int,
    num_pairs: int,
    is_positive: bool,
    previous_ids: List[int]
) -> List[PoolImageItem]:
    """
    Generuje pulę obrazów (pozytywną lub negatywną) na podstawie sukcesów i historii.
    
    Args:
        db: Sesja bazy danych
        successful_sorted: Posortowana lista obrazów z sukcesami
        difference_vector: Wektor różnicy
        total_successes: Suma sukcesów
        num_pairs: Liczba par obrazów w nowej puli
        is_positive: Czy to pula obrazów pozytywnych
        previous_ids: Lista ID obrazów z poprzedniej puli
    
    Returns:
        Lista PoolImageItem dla nowej puli obrazów
    """
    pool_type = "pozytywnych" if is_positive else "negatywnych"
    logger.info(f"Generowanie puli {pool_type} obrazów.")
    
    # Inicjalizuj nową pulę
    new_pool = []
    
    # Wykluczenia dla losowych obrazów
    exclude_ids = []
    
    # Strategia 1: Jeśli mamy więcej sukcesów niż potrzebujemy par
    if total_successes >= num_pairs:
        logger.info(f"Strategia 1: {total_successes} sukcesów >= {num_pairs} par.")
        
        # "Kupujemy" obrazy z rankingu (zachowujemy najlepsze)
        for item in successful_sorted[:num_pairs]:
            new_pool.append(PoolImageItem(
                image_id=item["id"],
                origin="bought",
                successes=0  # Resetujemy licznik sukcesów
            ))
            exclude_ids.append(item["id"])
            
        logger.info(f"Zachowano {len(new_pool)} najlepszych obrazów.")
    
    # Strategia 2: Jeśli mamy mniej sukcesów niż potrzebujemy par
    else:
        logger.info(f"Strategia 2: {total_successes} sukcesów < {num_pairs} par.")
        
        # Zachowaj wszystkie obrazy z sukcesami
        for item in successful_sorted:
            new_pool.append(PoolImageItem(
                image_id=item["id"],
                origin="bought",
                successes=0  # Resetujemy licznik sukcesów
            ))
            exclude_ids.append(item["id"])
            
        logger.info(f"Zachowano {len(new_pool)} obrazów z sukcesami.")
        
        # Generuj dzieci na podstawie obrazów z sukcesami
        if successful_sorted and len(new_pool) < num_pairs:
            children_count = min(len(successful_sorted), num_pairs - len(new_pool))
            logger.info(f"Generowanie {children_count} dzieci.")
            
            children = generate_children(
                db=db,
                parent_items=[PoolImageItem.from_dict(item) for item in successful_sorted],
                difference_vector=difference_vector,
                count=children_count,
                is_positive=is_positive,
                exclude_ids=exclude_ids,
                previous_pool_ids=previous_ids
            )
            
            for child in children:
                exclude_ids.append(child.id)
                
            new_pool.extend(children)
            logger.info(f"Wygenerowano {len(children)} dzieci.")
        
        # Uzupełnij pulę losowymi obrazami, jeśli potrzeba
        if len(new_pool) < num_pairs:
            remaining = num_pairs - len(new_pool)
            logger.info(f"Uzupełnianie puli {remaining} losowymi obrazami.")
            
            random_items = get_random_images_as_pool_items(
                db=db,
                count=remaining,
                is_positive=is_positive,
                exclude_ids=exclude_ids
            )
            
            for random_item in random_items:
                logger.info(f"Dodano losowy obraz id={random_item.id}")
            
            new_pool.extend(random_items)
            logger.info(f"Dodano {len(random_items)} losowych obrazów do puli {pool_type}")
    
    return new_pool


def generate_pool_with_genetic_algorithm(
    previous_session: SessionModel,
    db: Session,
    num_pairs: int = 6
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Implementacja algorytmu quasi-genetycznego do generowania nowej puli obrazów.
    
    Args:
        previous_session: Poprzednia sesja, na podstawie której generowana jest nowa pula
        db: Sesja bazy danych
        num_pairs: Liczba par obrazów w nowej puli
        
    Returns:
        Tuple zawierające listy słowników dla obrazów pozytywnych i negatywnych
    """
    try:
        logger.info(f"Generowanie nowej puli na podstawie sesji {previous_session.id}")
        
        # Pobierz pule obrazów z poprzedniej sesji
        previous_pos_pool = previous_session.pos_pool_json
        previous_neg_pool = previous_session.neg_pool_json
        
        # Pobierz ID obrazów z poprzednich pul
        previous_pos_ids = [item["id"] for item in previous_pos_pool]
        previous_neg_ids = [item["id"] for item in previous_neg_pool]
        
        # Pobierz embeddingi dla obrazów
        pos_embeddings = get_image_embeddings(db, previous_pos_ids)
        neg_embeddings = get_image_embeddings(db, previous_neg_ids)
        
        # Jeśli brak embeddingów, generuj losową pulę
        if not pos_embeddings or not neg_embeddings:
            logger.warning("Brak embeddingów dla obrazów z poprzedniej sesji. Generowanie losowej puli.")
            return get_random_pool(db, num_pairs)
        
        # Funkcja pomocnicza do przetwarzania puli
        def process_pool(pool_items, embeddings, is_positive):
            # Oblicz centroidy i wektor różnicy
            start_centroid, end_centroid, difference_vector = calculate_centroids(pool_items, embeddings)
            
            # Sortowanie obrazów według liczby sukcesów (malejąco)
            successful_items = [item for item in pool_items if item.get("successes", 0) > 0]
            successful_sorted = sorted(successful_items, key=lambda x: x.get("successes", 0), reverse=True)
            
            # Oblicz sumę sukcesów
            total_successes = sum(item.get("successes", 0) for item in pool_items)
            
            # Pobierz ID obrazów z poprzedniej puli
            previous_ids = [item["id"] for item in pool_items]
            
            # Generuj nową pulę
            return process_pool_generation(
                db=db,
                successful_sorted=successful_sorted,
                difference_vector=difference_vector,
                total_successes=total_successes,
                num_pairs=num_pairs,
                is_positive=is_positive,
                previous_ids=previous_ids
            )
        
        # Generuj nowe pule
        new_pos_pool = process_pool(previous_pos_pool, pos_embeddings, True)
        new_neg_pool = process_pool(previous_neg_pool, neg_embeddings, False)
        
        # Konwersja na słowniki
        pos_pool_dict = [item.to_dict() for item in new_pos_pool]
        neg_pool_dict = [item.to_dict() for item in new_neg_pool]
        
        logger.info(f"Wygenerowano nową pulę: {len(pos_pool_dict)} pozytywnych, {len(neg_pool_dict)} negatywnych")
        
        return pos_pool_dict, neg_pool_dict
        
    except Exception as e:
        logger.error(f"Błąd podczas generowania puli: {str(e)}")
        logger.error(traceback.format_exc())
        return get_random_pool(db, num_pairs)