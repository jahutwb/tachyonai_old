"""Moduł do obsługi embeddingów obrazów."""

import os
import logging
import numpy as np
import traceback
import torch
import json
import faiss
import time
from typing import Dict, List, Optional, Any, Tuple
from torchvision import transforms
from io import BytesIO
from tqdm import tqdm
from PIL import Image
from pathlib import Path
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import SessionLocal, engine
from ..models import Image as ImageModel, ImageTypeEnum
from .. import models
from ..faiss_manager import get_faiss_index_manager

# Konfiguracja loggera
logger = logging.getLogger(__name__)

# Katalog danych - ustawiony bezpośrednio
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data")

def get_logger(name):
    """Pomocnicza funkcja do uzyskania loggera."""
    return logging.getLogger(name)

# Globalne zmienne dla CLIP i indeksu FAISS
clip_model = None
clip_preprocess = None
faiss_manager = None
faiss_index_pos = None
faiss_index_neg = None
image_ids_pos = []
image_ids_neg = []

# Maksymalna liczba obrazów każdego typu
MAX_POSITIVE_IMAGES = 2000
MAX_NEGATIVE_IMAGES = 2000


def _initialize_faiss_manager():
    """
    Inicjalizuje FAISS Manager przy pierwszym użyciu
    """
    global faiss_manager
    if faiss_manager is None:
        try:
            faiss_manager = get_faiss_index_manager()
            if faiss_manager is None:
                logger.error("Nie udało się zainicjalizować FAISS Managera")
        except Exception as e:
            logger.error(f"Błąd podczas inicjalizacji FAISS Managera: {str(e)}")
            logger.error(traceback.format_exc())
            faiss_manager = None


def get_faiss_index(image_type: ImageTypeEnum):
    """
    Pobiera indeks FAISS dla danego typu obrazu
    """
    _initialize_faiss_manager()
    if faiss_manager is None:
        return None, {}, {}
    
    return faiss_manager.get_index(image_type)


def load_clip_model() -> None:
    """Ładuje model CLIP do generowania embeddingów."""
    global clip_model, clip_preprocess
    
    if clip_model is not None:
        return  # Model już załadowany
    
    try:
        import clip
        device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"Ładowanie modelu CLIP na urządzeniu: {device}")
        
        clip_model, clip_preprocess = clip.load("ViT-B/32", device=device)
        clip_model.eval()  # Przełączenie modelu w tryb ewaluacji
        
        logger.info("Model CLIP załadowany pomyślnie.")
    except Exception as e:
        logger.error(f"Błąd podczas ładowania modelu CLIP: {str(e)}")
        clip_model, clip_preprocess = None, None


def generate_embedding(image_path: str) -> Optional[List[float]]:
    """Generuje embedding dla obrazu za pomocą CLIP."""
    global clip_model, clip_preprocess
    
    if clip_model is None or clip_preprocess is None:
        load_clip_model()
        if clip_model is None or clip_preprocess is None:
            logger.error("Nie można wygenerować embeddingu - model CLIP nie jest dostępny.")
            return None
    
    try:
        # Wczytaj i przetwórz obraz
        image = Image.open(image_path).convert("RGB")
        image_input = clip_preprocess(image).unsqueeze(0).to(
            "cuda" if torch.cuda.is_available() else "cpu"
        )
        
        # Generuj embedding
        with torch.no_grad():
            image_features = clip_model.encode_image(image_input)
            image_features = image_features / image_features.norm(dim=-1, keepdim=True)
        
        # Konwersja do listy float (serializowalna do JSON)
        embedding = image_features.cpu().numpy()[0].tolist()
        return embedding
    
    except Exception as e:
        logger.error(f"Błąd podczas generowania embeddingu dla {image_path}: {str(e)}")
        return None


def update_embeddings(db: Session, limit_pos: int = MAX_POSITIVE_IMAGES, limit_neg: int = MAX_NEGATIVE_IMAGES) -> Dict[str, int]:
    """
    Aktualizuje embeddingi dla obrazów w bazie danych, które ich nie mają.
    Ogranicza liczbę obrazów do podanych limitów dla każdego typu.
    
    Args:
        db: Sesja bazy danych
        limit_pos: Maksymalna liczba obrazów pozytywnych do zaktualizowania
        limit_neg: Maksymalna liczba obrazów negatywnych do zaktualizowania
    
    Returns:
        Słownik zawierający liczbę zaktualizowanych obrazów każdego typu
    """
    # Ładowanie modelu CLIP
    load_clip_model()
    if clip_model is None:
        logger.error("Nie można zaktualizować embeddingów - model CLIP nie jest dostępny.")
        return {"positive": 0, "negative": 0}
    
    # Liczniki zaktualizowanych obrazów
    updated_pos = 0
    updated_neg = 0
    
    # Aktualizacja obrazów pozytywnych
    logger.info(f"Wyszukiwanie obrazów pozytywnych bez embeddingów (limit: {limit_pos})...")
    pos_images = db.query(ImageModel).filter(
        ImageModel.type == ImageTypeEnum.POSITIVE,
        ImageModel.embedding.is_(None)
    ).limit(limit_pos).all()
    logger.info(f"Znaleziono {len(pos_images)} obrazów pozytywnych bez embeddingów.")
    
    if pos_images:
        logger.info("Rozpoczynam generowanie embeddingów dla obrazów pozytywnych...")
        for image in tqdm(pos_images, desc="Obrazy pozytywne"):
            # Sprawdź, czy plik istnieje
            if not os.path.exists(image.path):
                logger.warning(f"Plik {image.path} nie istnieje, pomijam.")
                continue
            
            # Generuj embedding
            embedding = generate_embedding(image.path)
            if embedding is None:
                logger.warning(f"Nie udało się wygenerować embeddingu dla {image.path}, pomijam.")
                continue
            
            # Aktualizuj obiekt w bazie
            image.embedding = embedding
            updated_pos += 1
            
            # Co 10 obrazów commituj zmiany
            if updated_pos % 10 == 0:
                db.commit()
        
        # Końcowy commit dla obrazów pozytywnych
        db.commit()
        logger.info(f"Zakończono generowanie embeddingów dla {updated_pos} obrazów pozytywnych.")
    
    # Aktualizacja obrazów negatywnych
    logger.info(f"Wyszukiwanie obrazów negatywnych bez embeddingów (limit: {limit_neg})...")
    neg_images = db.query(ImageModel).filter(
        ImageModel.type == ImageTypeEnum.NEGATIVE,
        ImageModel.embedding.is_(None)
    ).limit(limit_neg).all()
    logger.info(f"Znaleziono {len(neg_images)} obrazów negatywnych bez embeddingów.")
    
    if neg_images:
        logger.info("Rozpoczynam generowanie embeddingów dla obrazów negatywnych...")
        for image in tqdm(neg_images, desc="Obrazy negatywne"):
            # Sprawdź, czy plik istnieje
            if not os.path.exists(image.path):
                logger.warning(f"Plik {image.path} nie istnieje, pomijam.")
                continue
            
            # Generuj embedding
            embedding = generate_embedding(image.path)
            if embedding is None:
                logger.warning(f"Nie udało się wygenerować embeddingu dla {image.path}, pomijam.")
                continue
            
            # Aktualizuj obiekt w bazie
            image.embedding = embedding
            updated_neg += 1
            
            # Co 10 obrazów commituj zmiany
            if updated_neg % 10 == 0:
                db.commit()
        
        # Końcowy commit dla obrazów negatywnych
        db.commit()
        logger.info(f"Zakończono generowanie embeddingów dla {updated_neg} obrazów negatywnych.")
    
    total_updated = updated_pos + updated_neg
    logger.info(f"Zakończono aktualizację embeddingów. Zaktualizowano {total_updated} obrazów "
                f"({updated_pos} pozytywnych, {updated_neg} negatywnych).")
    
    return {"positive": updated_pos, "negative": updated_neg}


def force_generate_embeddings(db: Session, limit_pos: int = 20, limit_neg: int = 20) -> Dict[str, int]:
    """
    Wymusza generowanie embeddingów dla obrazów w bazie danych, nawet jeśli już je mają.
    Ogranicza liczbę obrazów do podanych limitów dla każdego typu.
    
    Args:
        db: Sesja bazy danych
        limit_pos: Maksymalna liczba obrazów pozytywnych do zaktualizowania
        limit_neg: Maksymalna liczba obrazów negatywnych do zaktualizowania
    
    Returns:
        Słownik zawierający liczbę zaktualizowanych obrazów każdego typu
    """
    # Ładowanie modelu CLIP
    load_clip_model()
    if clip_model is None:
        logger.error("Nie można zaktualizować embeddingów - model CLIP nie jest dostępny.")
        return {"positive": 0, "negative": 0}
    
    # Liczniki zaktualizowanych obrazów
    updated_pos = 0
    updated_neg = 0
    
    # Aktualizacja obrazów pozytywnych
    logger.info(f"Wyszukiwanie obrazów pozytywnych (limit: {limit_pos})...")
    pos_images = db.query(ImageModel).filter(
        ImageModel.type == ImageTypeEnum.POSITIVE
    ).limit(limit_pos).all()
    logger.info(f"Znaleziono {len(pos_images)} obrazów pozytywnych.")
    
    if pos_images:
        logger.info("Rozpoczynam generowanie embeddingów dla obrazów pozytywnych...")
        for image in tqdm(pos_images, desc="Obrazy pozytywne"):
            # Sprawdź, czy plik istnieje
            if not os.path.exists(image.path):
                logger.warning(f"Plik {image.path} nie istnieje, pomijam.")
                continue
            
            # Generuj embedding
            embedding = generate_embedding(image.path)
            if embedding is None:
                logger.warning(f"Nie udało się wygenerować embeddingu dla {image.path}, pomijam.")
                continue
            
            # Aktualizuj obiekt w bazie
            image.embedding = embedding
            updated_pos += 1
            
            # Co 10 obrazów commituj zmiany
            if updated_pos % 10 == 0:
                db.commit()
        
        # Końcowy commit dla obrazów pozytywnych
        db.commit()
        logger.info(f"Zakończono generowanie embeddingów dla {updated_pos} obrazów pozytywnych.")
    
    # Aktualizacja obrazów negatywnych
    logger.info(f"Wyszukiwanie obrazów negatywnych (limit: {limit_neg})...")
    neg_images = db.query(ImageModel).filter(
        ImageModel.type == ImageTypeEnum.NEGATIVE
    ).limit(limit_neg).all()
    logger.info(f"Znaleziono {len(neg_images)} obrazów negatywnych.")
    
    if neg_images:
        logger.info("Rozpoczynam generowanie embeddingów dla obrazów negatywnych...")
        for image in tqdm(neg_images, desc="Obrazy negatywne"):
            # Sprawdź, czy plik istnieje
            if not os.path.exists(image.path):
                logger.warning(f"Plik {image.path} nie istnieje, pomijam.")
                continue
            
            # Generuj embedding
            embedding = generate_embedding(image.path)
            if embedding is None:
                logger.warning(f"Nie udało się wygenerować embeddingu dla {image.path}, pomijam.")
                continue
            
            # Aktualizuj obiekt w bazie
            image.embedding = embedding
            updated_neg += 1
            
            # Co 10 obrazów commituj zmiany
            if updated_neg % 10 == 0:
                db.commit()
        
        # Końcowy commit dla obrazów negatywnych
        db.commit()
        logger.info(f"Zakończono generowanie embeddingów dla {updated_neg} obrazów negatywnych.")
    
    total_updated = updated_pos + updated_neg
    logger.info(f"Zakończono aktualizację embeddingów. Zaktualizowano {total_updated} obrazów "
                f"({updated_pos} pozytywnych, {updated_neg} negatywnych).")
    
    return {"positive": updated_pos, "negative": updated_neg}


def build_faiss_index(db: Session) -> tuple[int, int]:
    """
    Tworzy indeks FAISS dla wszystkich obrazów w bazie danych, które mają embeddingi.
    Zwraca liczbę obrazów pozytywnych i negatywnych użytych do budowy indeksu.
    """
    logger = get_logger("backend.embedding")
    
    # Pobierz wszystkie pozytywne obrazy z embeddingami
    pos_images = db.query(ImageModel).filter(
        ImageModel.type == ImageTypeEnum.POSITIVE,
        ImageModel.embedding.isnot(None)
    ).all()
    
    # Pobierz wszystkie negatywne obrazy z embeddingami
    neg_images = db.query(ImageModel).filter(
        ImageModel.type == ImageTypeEnum.NEGATIVE,
        ImageModel.embedding.isnot(None)
    ).all()
    
    # Sprawdź, czy są jakiekolwiek embeddingi
    if len(pos_images) == 0 and len(neg_images) == 0:
        logger.info("Brak embeddingów do zbudowania indeksu FAISS.")
        return 0, 0
    
    # Przygotuj dane do indeksu
    pos_embeddings = []
    if pos_images:
        pos_embeddings = [img.embedding for img in pos_images if img.embedding]
        
    neg_embeddings = []
    if neg_images:
        neg_embeddings = [img.embedding for img in neg_images if img.embedding]
    
    # Sprawdź czy po filtrowaniu zostały jakieś embeddingi
    if not pos_embeddings and not neg_embeddings:
        logger.info("Brak poprawnych embeddingów do zbudowania indeksu FAISS.")
        return 0, 0
    
    # Ustal wymiar embeddingów
    dim = 512  # Domyślna wartość wymiarowa dla CLIP
    if pos_embeddings:
        sample_embedding = pos_embeddings[0]
        if sample_embedding and len(sample_embedding) > 0:
            dim = len(sample_embedding)
    elif neg_embeddings:
        sample_embedding = neg_embeddings[0]
        if sample_embedding and len(sample_embedding) > 0:
            dim = len(sample_embedding)
    
    logger.info(f"Wymiar embeddingów: {dim}")
    
    # Utwórz indeks FAISS
    index = faiss.IndexFlatIP(dim)
    
    # Konwertuj listy embeddingów na tablice numpy
    if pos_embeddings:
        pos_embeddings_array = np.array(pos_embeddings, dtype=np.float32)
        index.add(pos_embeddings_array)
        logger.info(f"Dodano {len(pos_embeddings)} pozytywnych embeddingów do indeksu")
    
    if neg_embeddings:
        neg_embeddings_array = np.array(neg_embeddings, dtype=np.float32)
        index.add(neg_embeddings_array)
        logger.info(f"Dodano {len(neg_embeddings)} negatywnych embeddingów do indeksu")
    
    # Zapisz indeks do pliku
    faiss.write_index(index, os.path.join(DATA_DIR, "faiss_index.bin"))
    logger.info("Zapisano indeks FAISS do pliku.")
    
    return len(pos_embeddings), len(neg_embeddings)


def find_nearest_images(image_id: str, embedding: List[float], count: int = 10) -> List[Dict[str, Any]]:
    """
    Znajduje obrazy najbliższe do podanego embeddingu.
    
    Args:
        image_id: ID obrazu źródłowego.
        embedding: Embedding obrazu źródłowego.
        count: Liczba najbliższych obrazów do zwrócenia.
        
    Returns:
        Lista obiektów {id, distance} reprezentujących najbliższe obrazy.
    """
    # Ta implementacja jest mockiem - w rzeczywistej aplikacji obliczałaby odległości
    # między embeddingami i zwracała rzeczywiste dane
    return [
        {"id": i + 1, "distance": 0.1 * (i + 1)}
        for i in range(count)
    ] 


def get_image_embeddings(db: Session, image_ids: List[int]) -> Dict[int, List[float]]:
    """
    Pobiera embeddingi dla listy identyfikatorów obrazów.
    
    Args:
        db: Sesja bazy danych
        image_ids: Lista identyfikatorów obrazów
        
    Returns:
        Słownik {id_obrazu: embedding}
    """
    logger.info(f"Pobieranie embeddingów dla {len(image_ids)} obrazów...")
    
    # Pobierz obrazy z bazy danych
    images = db.query(ImageModel).filter(
        ImageModel.id.in_(image_ids),
        ImageModel.embedding.isnot(None)
    ).all()
    
    # Utwórz słownik id -> embedding
    result = {}
    for image in images:
        if image.embedding:
            result[image.id] = image.embedding
    
    logger.info(f"Pobrano embeddingi dla {len(result)}/{len(image_ids)} obrazów.")
    return result


def find_nearest_image(db: Session, image_type: ImageTypeEnum, embedding: List[float]) -> Tuple[Optional[Dict[str, Any]], Optional[float]]:
    """
    Znajduje obraz najbliższy do podanego embeddingu.
    """
    try:
        # Użyj FAISS Managera do znalezienia najbliższego obrazu
        index, id_to_index, index_to_id = get_faiss_index(image_type)
        
        if index is None:
            return None, None
            
        # Znajdź najbliższy obraz
        nearest_id, distance = _find_nearest_image(index, id_to_index, index_to_id, embedding)
        
        if nearest_id is None:
            return None, None
            
        # Pobierz informacje o najbliższym obrazie z bazy danych
        image = db.query(ImageModel).filter(ImageModel.id == nearest_id).first()
        if not image:
            logger.error(f"Nie znaleziono obrazu o ID {nearest_id}")
            return None, None
            
        return {
            "id": image.id,
            "type": image.type,
            "embedding": image.embedding
        }, distance
        
    except Exception as e:
        logger.error(f"Błąd podczas wyszukiwania najbliższego obrazu: {str(e)}")
        logger.error(traceback.format_exc())
        return None, None