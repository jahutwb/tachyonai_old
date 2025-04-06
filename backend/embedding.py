import os
import logging
import torch
import numpy as np
from PIL import Image
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
import json
import faiss
import time
from torchvision import transforms
from io import BytesIO
from tqdm import tqdm

from .database import SessionLocal, engine
from .models import Image as ImageModel, ImageTypeEnum
from . import models

# Konfiguracja loggera
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Globalne zmienne dla CLIP i indeksu FAISS
clip_model = None
clip_preprocess = None
faiss_index_pos = None
faiss_index_neg = None
image_ids_pos = []
image_ids_neg = []

# Maksymalna liczba obrazów każdego typu
MAX_POSITIVE_IMAGES = 2000
MAX_NEGATIVE_IMAGES = 2000


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


def build_faiss_index(db: Session) -> Tuple[int, int]:
    """
    Buduje indeksy FAISS dla pozytywnych i negatywnych obrazów.
    
    Args:
        db: Sesja bazy danych
    
    Returns:
        Tuple z liczbą obrazów w indeksie pozytywnym i negatywnym
    """
    global faiss_index_pos, faiss_index_neg, image_ids_pos, image_ids_neg
    
    # Pobierz obrazy z embeddingami
    pos_images = db.query(ImageModel).filter(
        ImageModel.type == ImageTypeEnum.POSITIVE,
        ImageModel.embedding.isnot(None)
    ).all()
    
    neg_images = db.query(ImageModel).filter(
        ImageModel.type == ImageTypeEnum.NEGATIVE,
        ImageModel.embedding.isnot(None)
    ).all()
    
    logger.info(f"Budowanie indeksu FAISS dla {len(pos_images)} obrazów pozytywnych...")
    
    # Przygotuj dane dla indeksu pozytywnego
    pos_embeddings = np.array([img.embedding for img in pos_images], dtype=np.float32)
    image_ids_pos = [img.id for img in pos_images]
    
    if len(pos_embeddings) > 0:
        dim = pos_embeddings.shape[1]  # Wymiar embeddingów
        faiss_index_pos = faiss.IndexFlatL2(dim)  # Indeks L2 (Euclidean distance)
        faiss_index_pos.add(pos_embeddings)
    
    logger.info(f"Budowanie indeksu FAISS dla {len(neg_images)} obrazów negatywnych...")
    
    # Przygotuj dane dla indeksu negatywnego
    neg_embeddings = np.array([img.embedding for img in neg_images], dtype=np.float32)
    image_ids_neg = [img.id for img in neg_images]
    
    if len(neg_embeddings) > 0:
        dim = neg_embeddings.shape[1]  # Wymiar embeddingów
        faiss_index_neg = faiss.IndexFlatL2(dim)  # Indeks L2 (Euclidean distance)
        faiss_index_neg.add(neg_embeddings)
    
    logger.info(f"Zakończono budowanie indeksów FAISS: {len(pos_images)} pozytywnych, {len(neg_images)} negatywnych.")
    
    return len(pos_images), len(neg_images)


def find_nearest_image(
    embedding: List[float],
    positive: bool = True,
    exclude_ids: List[int] = None,
    k: int = 5
) -> Optional[int]:
    """
    Znajduje najbliższy obraz do podanego embeddingu.
    
    Args:
        embedding: Embedding obrazu
        positive: Czy szukać w indeksie obrazów pozytywnych
        exclude_ids: Lista ID obrazów do wykluczenia z wyszukiwania
        k: Liczba najbliższych sąsiadów do znalezienia
    
    Returns:
        ID najbliższego obrazu lub None, jeśli nie znaleziono
    """
    global faiss_index_pos, faiss_index_neg, image_ids_pos, image_ids_neg
    
    if exclude_ids is None:
        exclude_ids = []
    
    # Wybierz odpowiedni indeks
    faiss_index = faiss_index_pos if positive else faiss_index_neg
    image_ids = image_ids_pos if positive else image_ids_neg
    
    if faiss_index is None or len(image_ids) == 0:
        logger.warning(f"Indeks FAISS nie jest dostępny dla {'pozytywnych' if positive else 'negatywnych'} obrazów.")
        return None
    
    try:
        # Konwersja embeddingu na numpy array
        query_embedding = np.array([embedding], dtype=np.float32)
        
        # Wyszukiwanie k najbliższych sąsiadów
        distances, indices = faiss_index.search(query_embedding, k)
        
        # Znajdź pierwszy wynik, który nie jest w exclude_ids
        for idx in indices[0]:
            if idx < len(image_ids) and image_ids[idx] not in exclude_ids:
                return image_ids[idx]
        
        # Jeśli wszystkie wyniki są w exclude_ids, zwróć None
        return None
    
    except Exception as e:
        logger.error(f"Błąd podczas wyszukiwania najbliższego obrazu: {str(e)}")
        return None


def calculate_centroid(embeddings: List[List[float]], weights: List[float] = None) -> List[float]:
    """
    Oblicza centroid (średnią ważoną) zbioru embeddingów.
    
    Args:
        embeddings: Lista embeddingów
        weights: Lista wag dla każdego embeddingu (opcjonalne)
    
    Returns:
        Centroid jako lista float
    """
    if not embeddings:
        return []
    
    # Konwersja na numpy arrays
    embedding_array = np.array(embeddings, dtype=np.float32)
    
    if weights is not None:
        # Normalizacja wag
        weights_array = np.array(weights, dtype=np.float32)
        weights_sum = np.sum(weights_array)
        if weights_sum > 0:
            normalized_weights = weights_array / weights_sum
        else:
            normalized_weights = np.ones(len(weights_array)) / len(weights_array)
        
        # Obliczenie średniej ważonej
        centroid = np.sum(embedding_array * normalized_weights[:, np.newaxis], axis=0)
    else:
        # Obliczenie prostej średniej
        centroid = np.mean(embedding_array, axis=0)
    
    # Normalizacja wektora
    norm = np.linalg.norm(centroid)
    if norm > 0:
        centroid = centroid / norm
    
    return centroid.tolist()


def get_image_embeddings(db: Session, image_ids: List[int]) -> Dict[int, List[float]]:
    """
    Pobiera embeddingi obrazów o podanych ID.
    
    Args:
        db: Sesja bazy danych
        image_ids: Lista ID obrazów
    
    Returns:
        Słownik {image_id: embedding}
    """
    embeddings = {}
    images = db.query(ImageModel).filter(ImageModel.id.in_(image_ids)).all()
    
    for img in images:
        if img.embedding is not None:
            embeddings[img.id] = img.embedding
    
    return embeddings


def main():
    """Główna funkcja do testowania generowania embeddingów."""
    # Utworzenie sesji bazy danych
    db = SessionLocal()
    try:
        # Aktualizacja embeddingów
        updated_count = update_embeddings(db, limit_pos=MAX_POSITIVE_IMAGES, limit_neg=MAX_NEGATIVE_IMAGES)
        logger.info(f"Zaktualizowano {updated_count['positive']} obrazów pozytywnych i {updated_count['negative']} obrazów negatywnych.")
        
        # Budowa indeksu FAISS
        pos_count, neg_count = build_faiss_index(db)
        logger.info(f"Zbudowano indeks FAISS dla {pos_count} obrazów pozytywnych i {neg_count} obrazów negatywnych.")
        
        if pos_count > 0 and neg_count > 0:
            # Test znajdowania najbliższego obrazu
            test_image = db.query(ImageModel).filter(ImageModel.embedding.isnot(None)).first()
            if test_image:
                nearest_id = find_nearest_image(
                    test_image.embedding,
                    positive=(test_image.type == ImageTypeEnum.POSITIVE),
                    exclude_ids=[test_image.id]
                )
                if nearest_id:
                    logger.info(f"Najbliższy obraz do {test_image.id}: {nearest_id}")
                else:
                    logger.warning("Nie znaleziono najbliższego obrazu.")
    
    except Exception as e:
        logger.error(f"Błąd podczas przetwarzania embeddingów: {str(e)}")
    finally:
        db.close()


if __name__ == "__main__":
    main() 