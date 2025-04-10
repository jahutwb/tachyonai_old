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
    
    def __init__(self, image_id: int, origin: str = "random", successes: int = 0, failures: int = 0):
        self.id = image_id
        self.origin = origin
        self.successes = successes
        self.failures = failures
    
    def to_dict(self) -> Dict[str, Any]:
        """Konwertuje obiekt na słownik."""
        return {
            "id": self.id,
            "origin": self.origin,
            "successes": self.successes,
            "failures": self.failures
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PoolImageItem':
        """Tworzy obiekt z słownika."""
        return cls(
            image_id=data.get("id"),
            origin=data.get("origin", "random"),
            successes=data.get("successes", 0),
            failures=data.get("failures", 0)
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
        return [PoolImageItem(img.id, origin="random", successes=0, failures=0) for img in images]
    
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
        parent_items: Lista rodziców (PoolImageItem) posortowana od najlepszego
        difference_vector: Wektor różnicy
        count: Liczba dzieci do wygenerowania
        is_positive: Czy to dzieci obrazów pozytywnych
        exclude_ids: Lista ID obrazów do wykluczenia
        previous_pool_ids: Lista ID obrazów z poprzedniej puli
    
    Returns:
        Lista dzieci (PoolImageItem)
    """
    if not parent_items:
        logger.warning("Brak rodziców do generowania dzieci.")
        return []
    
    # Pobierz embeddingi rodziców
    parent_ids = [item.id for item in parent_items]
    parent_embeddings = get_image_embeddings(db, parent_ids)
    
    # Przygotuj listę ID do wykluczenia
    if exclude_ids is None:
        exclude_ids = []
    
    if previous_pool_ids is not None:
        exclude_ids.extend(previous_pool_ids)
    
    # Dodaj ID rodziców do wykluczenia
    exclude_ids.extend(parent_ids)
    
    # Lista dzieci
    children = []
    
    # Rozdzielenie dzieci między rodziców zgodnie ze specyfikacją
    num_parents = len(parent_items)
    if num_parents == 0:
        return []
    
    # Każdy rodzic dostaje count // num_parents dzieci
    children_per_parent = count // num_parents
    
    # Reszta dzieci idzie do najlepszych rodziców
    remainder = count % num_parents
    
    logger.info(f"Generowanie {count} dzieci od {num_parents} rodziców.")
    logger.info(f"Każdy rodzic dostaje {children_per_parent} dzieci, a {remainder} najlepszych rodziców dostaje po 1 dodatkowym dziecku.")
    
    # Przydziel dzieci rodzicom
    for i, parent_item in enumerate(parent_items):
        parent_id = parent_item.id
        
        # Liczba dzieci dla tego rodzica
        num_children = children_per_parent + (1 if i < remainder else 0)
        
        if num_children == 0:
            continue
        
        logger.info(f"Rodzic {parent_id} (pozycja {i+1} w rankingu) generuje {num_children} dzieci.")
        
        # Pobierz embedding rodzica
        if parent_id not in parent_embeddings:
            logger.warning(f"Brak embeddingu dla rodzica {parent_id}.")
            continue
        
        parent_embedding = parent_embeddings[parent_id]
        
        # Generuj dzieci dla tego rodzica
        for _ in range(num_children):
            # Generuj dziecko
            found_child = False
            attempts = 0
            max_attempts = 5  # Maksymalna liczba prób z różnymi długościami wektora
            
            # Początkowy wektor różnicy
            current_direction = difference_vector.copy()
            
            logger.info(f"Początkowa długość wektora różnicy: {np.linalg.norm(current_direction):.2f}")
            logger.info(f"Początkowy kierunek wektora: {current_direction[:3]}...")
            
            while not found_child and attempts < max_attempts:
                # Dodaj losowy szum do wektora
                noise = np.random.randn(len(current_direction)) * 0.1
                current_direction += noise
                
                logger.info(f"Próba {attempts+1}: Dodano szum do wektora")
                logger.info(f"  - Długość wektora po dodaniu szumu: {np.linalg.norm(current_direction):.2f}")
                logger.info(f"  - Kierunek wektora po szumie: {current_direction[:3]}...")
                
                # Przesuń się o wektor kierunku od wektora rodzica
                candidate_embedding = np.array(parent_embedding) + current_direction
                
                logger.info(f"Próba {attempts+1}: Wygenerowano kandydata do dziecka")
                logger.info(f"  - Odległość kandydata od rodzica: {np.linalg.norm(candidate_embedding - np.array(parent_embedding)):.2f}")
                
                # Szukaj najbliższego obrazu
                from .embedding import find_nearest_image
                result, distance = find_nearest_image(db, candidate_embedding.tolist())
                
                if result is not None:
                    # Sprawdź czy wynik nie jest na liście exclude_ids
                    if result["id"] not in exclude_ids:
                        # Znaleziono obraz spoza exclude_ids
                        found_child = True
                        child_id = result["id"]
                        
                        logger.info(f"Próba {attempts+1}: Znaleziono nowe dziecko!")
                        logger.info(f"  - ID dziecka: {child_id}")
                        logger.info(f"  - Odległość od kandydata: {distance:.2f}")
                        logger.info(f"  - Długość wektora różnicy: {np.linalg.norm(current_direction):.2f}")
                        
                        # Dodaj dziecko do listy
                        child = PoolImageItem(
                            image_id=child_id,
                            origin=f"child_of_{parent_id}",
                            successes=0,  # Resetujemy licznik sukcesów
                            failures=0    # Resetujemy licznik porażek
                        )
                        children.append(child)
                        
                        # Dodaj dziecko do wykluczeń
                        exclude_ids.append(child_id)
                        break
                    else:
                        # Znaleziono obraz z exclude_ids - dostosuj wektor kierunku
                        ratio = 1 + (distance / np.linalg.norm(current_direction))
                        current_direction *= ratio
                        
                        logger.info(f"Próba {attempts+1}: Znaleziono obraz z exclude_ids")
                        logger.info(f"  - Odległość: {distance:.2f}")
                        logger.info(f"  - Ratio: {ratio:.2f}")
                        logger.info(f"  - Nowa długość wektora: {np.linalg.norm(current_direction):.2f}")
                        logger.info(f"  - Nowy kierunek wektora: {current_direction[:3]}...")
                else:
                    logger.info(f"Próba {attempts+1}: Nie znaleziono żadnego obrazu")
                    logger.info(f"  - Długość wektora: {np.linalg.norm(current_direction):.2f}")
                    logger.info(f"  - Kierunek wektora: {current_direction[:3]}...")
                attempts += 1
                
            if not found_child:
                logger.warning(f"Nie udało się wygenerować dziecka dla rodzica {parent_id} po {max_attempts} próbach z różnymi skalami przesunięcia.")
                # Jeśli nie udało się wygenerować dziecka po wszystkich próbach, użyj losowego obrazu
                random_image = get_random_images_as_pool_items(db, 1, is_positive, exclude_ids)
                if random_image:
                    logger.info(f"Użyto losowego obrazu jako dziecka dla rodzica {parent_id}.")
                    random_image[0].origin = f"random_fallback_for_{parent_id}"
                    children.append(random_image[0])
    
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
    logger.info(f"Dane wejściowe: {len(successful_sorted)} obrazów z sukcesami, suma sukcesów: {total_successes}, liczba par: {num_pairs}")
    
    # Wyświetl szczegóły obrazów z sukcesami
    for idx, item in enumerate(successful_sorted):
        logger.info(f"Obraz {idx+1} z sukcesami: id={item['id']}, successes={item.get('successes', 0)}")
    
    # Inicjalizuj nową pulę
    new_pool = []
    
    # Wykluczenia dla losowych obrazów
    exclude_ids = []
    
    # Przypadek A: Jeśli mamy więcej sukcesów niż potrzebujemy par
    if total_successes > num_pairs:
        logger.info(f"Przypadek A: {total_successes} sukcesów > {num_pairs} par.")
        
        # Obliczamy dostępne punkty
        points = total_successes - num_pairs
        logger.info(f"Dostępne punkty: {points}")
        
        # "Kupujemy" obrazy z rankingu
        bought_count = 0
        for item in successful_sorted:
            success_count = item.get("successes", 0)
            
            # Kupujemy obraz, nawet jeśli nie mamy wystarczająco punktów
            new_pool.append(PoolImageItem(
                image_id=item["id"],
                origin="bought",
                successes=0,  # Resetujemy licznik sukcesów
                failures=0    # Resetujemy licznik porażek
            ))
            exclude_ids.append(item["id"])
            bought_count += 1
            
            # Odejmujemy punkty
            points -= success_count
            logger.info(f"Kupiono obraz id={item['id']} za {success_count} punktów. Pozostało: {points} punktów.")
            
            # Jeśli wyczerpaliśmy punkty lub zapełniliśmy pulę, kończymy
            if points <= 0 or bought_count >= num_pairs:
                break
        
        logger.info(f"Kupiono {bought_count} obrazów.")
        
        # Jeśli nie zapełniliśmy puli, generujemy dzieci
        if len(new_pool) < num_pairs:
            children_count = num_pairs - len(new_pool)
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
    
    # Przypadek B: Jeśli mamy mniej lub tyle samo sukcesów co par
    else:
        logger.info(f"Przypadek B: {total_successes} sukcesów <= {num_pairs} par.")
        
        # Generujemy dokładnie S dzieci
        if successful_sorted and total_successes > 0:
            logger.info(f"Generowanie {total_successes} dzieci.")
            
            children = generate_children(
                db=db,
                parent_items=[PoolImageItem.from_dict(item) for item in successful_sorted],
                difference_vector=difference_vector,
                count=total_successes,
                is_positive=is_positive,
                exclude_ids=exclude_ids,
                previous_pool_ids=previous_ids
            )
            
            for child in children:
                exclude_ids.append(child.id)
                child.successes = 0  # Resetujemy licznik sukcesów
                child.failures = 0  # Resetujemy licznik porażek
                
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