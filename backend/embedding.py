import os
import logging
import torch
import numpy as np
from PIL import Image
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Union
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
logger = logging.getLogger(__name__)

# Katalog danych - ustawiony bezpośrednio
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

def get_logger(name):
    """Pomocnicza funkcja do uzyskania loggera."""
    return logging.getLogger(name)

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


def build_faiss_index(db: Session) -> tuple[int, int]:
    """
    Tworzy indeks FAISS dla wszystkich obrazów w bazie danych, które mają embeddingi.
    Zwraca liczbę obrazów pozytywnych i negatywnych użytych do budowy indeksu.
    """
    logger = get_logger("backend.embedding")
    
    # Pobierz wszystkie pozytywne obrazy z embeddingami
    logger.info(f"Budowanie indeksu FAISS dla {count_images_with_embeddings(db, True)} obrazów pozytywnych...")
    pos_images = get_images_with_embeddings(db, True)
    
    # Pobierz wszystkie negatywne obrazy z embeddingami
    logger.info(f"Budowanie indeksu FAISS dla {count_images_with_embeddings(db, False)} obrazów negatywnych...")
    neg_images = get_images_with_embeddings(db, False)
    
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
    
    # Zapisz indeks
    index_path = os.path.join(DATA_DIR, "index", "faiss_index.idx")
    os.makedirs(os.path.dirname(index_path), exist_ok=True)
    faiss.write_index(index, index_path)
    
    logger.info(f"Indeks FAISS zbudowany i zapisany. "
                f"Zawiera {len(pos_embeddings)} obrazów pozytywnych i {len(neg_embeddings)} obrazów negatywnych.")
    
    # Zapisz mapowanie id
    id_mapping = []
    for i, img in enumerate(pos_images):
        if i < len(pos_embeddings):  # Upewnij się, że indeks nie wychodzi poza zakres
            id_mapping.append((img.id, True))
    
    for i, img in enumerate(neg_images):
        if i < len(neg_embeddings):  # Upewnij się, że indeks nie wychodzi poza zakres
            id_mapping.append((img.id, False))
    
    # Zapisz mapowanie ID
    with open(os.path.join(DATA_DIR, "index", "id_mapping.json"), "w") as f:
        json.dump(id_mapping, f)
    
    logger.info(f"Mapowanie ID zapisane.")
    return len(pos_embeddings), len(neg_embeddings)


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


def count_images_with_embeddings(db: Session, is_positive: bool) -> int:
    """
    Zlicza ilość obrazów z embeddingami w bazie danych.
    
    Args:
        db: Sesja bazy danych
        is_positive: Czy liczyć obrazy pozytywne (True) czy negatywne (False)
    
    Returns:
        Liczba obrazów z embeddingami
    """
    image_type = ImageTypeEnum.POSITIVE if is_positive else ImageTypeEnum.NEGATIVE
    return db.query(ImageModel).filter(
        ImageModel.type == image_type,
        ImageModel.embedding.isnot(None)
    ).count()


def get_images_with_embeddings(db: Session, is_positive: bool) -> List[ImageModel]:
    """
    Pobiera obrazy z embeddingami z bazy danych.
    
    Args:
        db: Sesja bazy danych
        is_positive: Czy pobrać obrazy pozytywne (True) czy negatywne (False)
    
    Returns:
        Lista obrazów z embeddingami
    """
    image_type = ImageTypeEnum.POSITIVE if is_positive else ImageTypeEnum.NEGATIVE
    return db.query(ImageModel).filter(
        ImageModel.type == image_type,
        ImageModel.embedding.isnot(None)
    ).all()


def force_generate_embeddings(db: Session, limit_pos: int = 20, limit_neg: int = 20) -> Dict[str, int]:
    """
    Wymusza generowanie embeddingów dla obrazów, nawet jeśli w bazie danych jest informacja,
    że obrazy już mają embeddingi. Przydatne, gdy embeddingi są puste lub nieprawidłowe.
    
    Args:
        db: Sesja bazy danych
        limit_pos: Maksymalna liczba obrazów pozytywnych do przetworzenia
        limit_neg: Maksymalna liczba obrazów negatywnych do przetworzenia
        
    Returns:
        Słownik zawierający liczbę zaktualizowanych obrazów każdego typu
    """
    file_logger = logging.getLogger(__name__)
    
    # Ładowanie modelu CLIP
    load_clip_model()
    if clip_model is None:
        file_logger.error("Nie można zaktualizować embeddingów - model CLIP nie jest dostępny.")
        return {"positive": 0, "negative": 0}
    
    # Liczniki zaktualizowanych obrazów
    updated_pos = 0
    updated_neg = 0
    
    # Aktualizacja obrazów pozytywnych
    file_logger.info(f"Pobieranie obrazów pozytywnych do wygenerowania embeddingów (limit: {limit_pos})...")
    pos_images = db.query(ImageModel).filter(
        ImageModel.type == ImageTypeEnum.POSITIVE
    ).limit(limit_pos).all()
    file_logger.info(f"Pobrano {len(pos_images)} obrazów pozytywnych.")
    
    if pos_images:
        file_logger.info("Rozpoczynam generowanie embeddingów dla obrazów pozytywnych...")
        for image in tqdm(pos_images, desc="Obrazy pozytywne"):
            # Sprawdź, czy plik istnieje
            if not os.path.exists(image.path):
                file_logger.warning(f"Plik {image.path} nie istnieje, pomijam.")
                continue
            
            # Generuj embedding
            embedding = generate_embedding(image.path)
            if embedding is None:
                file_logger.warning(f"Nie udało się wygenerować embeddingu dla {image.path}, pomijam.")
                continue
            
            # Aktualizuj obiekt w bazie
            image.embedding = embedding
            updated_pos += 1
            
            # Co 5 obrazów commituj zmiany
            if updated_pos % 5 == 0:
                db.commit()
                file_logger.info(f"Zapisano {updated_pos} embeddingów dla obrazów pozytywnych.")
        
        # Końcowy commit dla obrazów pozytywnych
        db.commit()
        file_logger.info(f"Zakończono generowanie embeddingów dla {updated_pos} obrazów pozytywnych.")
    
    # Aktualizacja obrazów negatywnych
    file_logger.info(f"Pobieranie obrazów negatywnych do wygenerowania embeddingów (limit: {limit_neg})...")
    neg_images = db.query(ImageModel).filter(
        ImageModel.type == ImageTypeEnum.NEGATIVE
    ).limit(limit_neg).all()
    file_logger.info(f"Pobrano {len(neg_images)} obrazów negatywnych.")
    
    if neg_images:
        file_logger.info("Rozpoczynam generowanie embeddingów dla obrazów negatywnych...")
        for image in tqdm(neg_images, desc="Obrazy negatywne"):
            # Sprawdź, czy plik istnieje
            if not os.path.exists(image.path):
                file_logger.warning(f"Plik {image.path} nie istnieje, pomijam.")
                continue
            
            # Generuj embedding
            embedding = generate_embedding(image.path)
            if embedding is None:
                file_logger.warning(f"Nie udało się wygenerować embeddingu dla {image.path}, pomijam.")
                continue
            
            # Aktualizuj obiekt w bazie
            image.embedding = embedding
            updated_neg += 1
            
            # Co 5 obrazów commituj zmiany
            if updated_neg % 5 == 0:
                db.commit()
                file_logger.info(f"Zapisano {updated_neg} embeddingów dla obrazów negatywnych.")
        
        # Końcowy commit dla obrazów negatywnych
        db.commit()
        file_logger.info(f"Zakończono generowanie embeddingów dla {updated_neg} obrazów negatywnych.")
    
    total_updated = updated_pos + updated_neg
    file_logger.info(f"Zakończono aktualizację embeddingów. Zaktualizowano {total_updated} obrazów "
                f"({updated_pos} pozytywnych, {updated_neg} negatywnych).")
    
    return {"positive": updated_pos, "negative": updated_neg}


def main():
    """Główna funkcja do testowania generowania embeddingów."""
    # Konfiguracja loggera dla tego pliku
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    file_logger = logging.getLogger(__name__)
    
    file_logger.info("Rozpoczynam diagnostykę embeddingów")
    
    # Utworzenie sesji bazy danych
    db = SessionLocal()
    try:
        # Sprawdź liczbę obrazów w bazie danych
        pos_count = db.query(ImageModel).filter(
            ImageModel.type == ImageTypeEnum.POSITIVE
        ).count()
        
        neg_count = db.query(ImageModel).filter(
            ImageModel.type == ImageTypeEnum.NEGATIVE
        ).count()
        
        file_logger.info(f"Znaleziono {pos_count} obrazów pozytywnych i {neg_count} obrazów negatywnych w bazie danych.")
        
        # Sprawdź liczbę obrazów z embeddingami
        pos_with_embedding = db.query(ImageModel).filter(
            ImageModel.type == ImageTypeEnum.POSITIVE,
            ImageModel.embedding.isnot(None)
        ).count()
        
        neg_with_embedding = db.query(ImageModel).filter(
            ImageModel.type == ImageTypeEnum.NEGATIVE,
            ImageModel.embedding.isnot(None)
        ).count()
        
        file_logger.info(f"Znaleziono {pos_with_embedding} obrazów pozytywnych i {neg_with_embedding} obrazów negatywnych z embeddingami.")
        
        # Pobierz przykładowy obraz pozytywny i sprawdź jego embedding
        pos_img = db.query(ImageModel).filter(
            ImageModel.type == ImageTypeEnum.POSITIVE
        ).first()
        
        if pos_img:
            file_logger.info(f"Przykładowy obraz pozytywny: ID={pos_img.id}, PATH={pos_img.path}")
            file_logger.info(f"Embedding: {'JEST' if pos_img.embedding is not None else 'BRAK'}")
            if pos_img.embedding:
                file_logger.info(f"Typ embeddingu: {type(pos_img.embedding)}")
                file_logger.info(f"Długość embeddingu: {len(pos_img.embedding) if isinstance(pos_img.embedding, list) else 'N/A'}")
        
        # Pobierz przykładowy obraz negatywny i sprawdź jego embedding
        neg_img = db.query(ImageModel).filter(
            ImageModel.type == ImageTypeEnum.NEGATIVE
        ).first()
        
        if neg_img:
            file_logger.info(f"Przykładowy obraz negatywny: ID={neg_img.id}, PATH={neg_img.path}")
            file_logger.info(f"Embedding: {'JEST' if neg_img.embedding is not None else 'BRAK'}")
            if neg_img.embedding:
                file_logger.info(f"Typ embeddingu: {type(neg_img.embedding)}")
                file_logger.info(f"Długość embeddingu: {len(neg_img.embedding) if isinstance(neg_img.embedding, list) else 'N/A'}")
        
        # Użyj opcji wymuszania generowania embeddingów
        file_logger.info("Rozpoczynam wymuszanie generowania embeddingów...")
        updated_count = force_generate_embeddings(db, limit_pos=10, limit_neg=10)
        file_logger.info(f"Zaktualizowano {updated_count['positive']} obrazów pozytywnych i {updated_count['negative']} obrazów negatywnych.")
        
        # Budowa indeksu FAISS
        if updated_count['positive'] > 0 or updated_count['negative'] > 0:
            file_logger.info("Rozpoczynam budowę indeksu FAISS po aktualizacji embeddingów...")
            pos_count, neg_count = build_faiss_index(db)
            file_logger.info(f"Zbudowano indeks FAISS dla {pos_count} obrazów pozytywnych i {neg_count} obrazów negatywnych.")
        else:
            file_logger.info("Pomijam budowę indeksu FAISS - nie zaktualizowano żadnych embeddingów.")
    
    except Exception as e:
        file_logger.error(f"Błąd podczas przetwarzania embeddingów: {str(e)}", exc_info=True)
    finally:
        db.close()
        file_logger.info("Zakończono diagnostykę embeddingów")


if __name__ == "__main__":
    main() 