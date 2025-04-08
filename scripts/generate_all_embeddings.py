#!/usr/bin/env python
"""
Skrypt do generowania embeddingów dla wszystkich obrazów w bazie danych.
Wykorzystuje moduł CLIP do generowania embeddingów i moduł FAISS do tworzenia indeksu.
"""
import os
import sys
import logging
import argparse
from pathlib import Path
import time
from tqdm import tqdm

# Dodajemy katalog główny projektu do ścieżki Pythona
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.database import SessionLocal
from backend.models import Image, ImageTypeEnum
from backend.embedding import force_generate_embeddings, build_faiss_index, generate_embedding

# Konfiguracja loggera
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    """Główna funkcja skryptu."""
    parser = argparse.ArgumentParser(description="Generowanie embeddingów dla wszystkich obrazów w bazie danych.")
    parser.add_argument(
        "--skip-faiss", 
        action="store_true",
        help="Pomiń tworzenie indeksu FAISS po wygenerowaniu embeddingów"
    )
    args = parser.parse_args()
    
    logger.info("Rozpoczynanie procesu generowania embeddingów i tworzenia indeksu FAISS...")
    
    # Początek pomiaru czasu
    start_time = time.time()
    
    # Utworzenie sesji bazy danych
    db = SessionLocal()
    try:
        # Pokaż informacje o obecnym stanie bazy danych
        pos_count = db.query(Image).filter(
            Image.type == ImageTypeEnum.POSITIVE
        ).count()
        
        neg_count = db.query(Image).filter(
            Image.type == ImageTypeEnum.NEGATIVE
        ).count()
        
        logger.info(f"W bazie danych znajduje się {pos_count} obrazów pozytywnych i {neg_count} obrazów negatywnych.")
        
        # Wymuszenie generowania embeddingów dla wszystkich obrazów
        logger.info(f"Wymuszanie generowania embeddingów dla wszystkich obrazów...")
        
        # Pobierz wszystkie obrazy
        pos_images = db.query(Image).filter(
            Image.type == ImageTypeEnum.POSITIVE
        ).all()
        
        neg_images = db.query(Image).filter(
            Image.type == ImageTypeEnum.NEGATIVE
        ).all()
        
        # Liczniki zaktualizowanych obrazów
        updated_pos = 0
        updated_neg = 0
        
        # Aktualizacja obrazów pozytywnych
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
        
        result = {"positive": updated_pos, "negative": updated_neg}
        logger.info(f"Zaktualizowano {result['positive']} obrazów pozytywnych i {result['negative']} obrazów negatywnych.")
        
        # Tworzenie indeksu FAISS, jeśli nie zostało pominięte i coś zostało zaktualizowane
        if not args.skip_faiss and (result['positive'] > 0 or result['negative'] > 0):
            logger.info("Rozpoczynam tworzenie indeksu FAISS...")
            pos_count, neg_count = build_faiss_index(db)
            logger.info(f"Utworzono indeks FAISS dla {pos_count} obrazów pozytywnych i {neg_count} obrazów negatywnych.")
        elif args.skip_faiss:
            logger.info("Pomijam tworzenie indeksu FAISS zgodnie z parametrem --skip-faiss.")
        else:
            logger.info("Pomijam tworzenie indeksu FAISS - nie zaktualizowano żadnych embeddingów.")
        
    finally:
        # Zamknięcie sesji bazy danych
        db.close()
    
    # Koniec pomiaru czasu
    end_time = time.time()
    elapsed_time = end_time - start_time
    hours, remainder = divmod(elapsed_time, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    logger.info(f"Zakończono cały proces w czasie: {int(hours)}h {int(minutes)}m {int(seconds)}s.")


if __name__ == "__main__":
    main() 