#!/usr/bin/env python
"""
Skrypt do generowania embeddingów dla obrazów w bazie danych.
Wykorzystuje moduł CLIP do generowania embeddingów i moduł FAISS do tworzenia indeksu.
"""
import os
import sys
import logging
import argparse
from pathlib import Path
import time

# Dodajemy katalog główny projektu do ścieżki Pythona
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.database import SessionLocal
from backend.embedding import update_embeddings, build_faiss_index, MAX_POSITIVE_IMAGES, MAX_NEGATIVE_IMAGES

# Konfiguracja loggera
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    """Główna funkcja skryptu."""
    parser = argparse.ArgumentParser(description="Generowanie embeddingów dla obrazów w bazie danych.")
    parser.add_argument(
        "--limit-pos", 
        type=int, 
        default=MAX_POSITIVE_IMAGES,
        help=f"Maksymalna liczba obrazów pozytywnych do przetworzenia (domyślnie: {MAX_POSITIVE_IMAGES})"
    )
    parser.add_argument(
        "--limit-neg", 
        type=int, 
        default=MAX_NEGATIVE_IMAGES,
        help=f"Maksymalna liczba obrazów negatywnych do przetworzenia (domyślnie: {MAX_NEGATIVE_IMAGES})"
    )
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
        # Aktualizacja embeddingów
        logger.info(f"Rozpoczynam generowanie embeddingów (limit pozytywnych: {args.limit_pos}, limit negatywnych: {args.limit_neg})...")
        result = update_embeddings(db, limit_pos=args.limit_pos, limit_neg=args.limit_neg)
        logger.info(f"Zaktualizowano {result['positive']} obrazów pozytywnych i {result['negative']} obrazów negatywnych.")
        
        # Tworzenie indeksu FAISS, jeśli nie zostało pominięte
        if not args.skip_faiss:
            logger.info("Rozpoczynam tworzenie indeksu FAISS...")
            pos_count, neg_count = build_faiss_index(db)
            logger.info(f"Utworzono indeks FAISS dla {pos_count} obrazów pozytywnych i {neg_count} obrazów negatywnych.")
        else:
            logger.info("Pomijam tworzenie indeksu FAISS zgodnie z parametrem --skip-faiss.")
        
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