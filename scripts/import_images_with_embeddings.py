import os
import sys
import logging
import numpy as np
from PIL import Image
from pathlib import Path
from tqdm import tqdm
import torch
import json
import random
import time
import argparse
import shutil
import sqlite3

# Dodanie katalogu głównego projektu do ścieżki Pythona
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import SessionLocal, engine
from backend.models import Image as ImageModel, ImageTypeEnum, Base
from backend import models

# Konfiguracja parsera argumentów
parser = argparse.ArgumentParser(description='Import obrazów z embeddingami do bazy danych')
parser.add_argument('--reset', action='store_true', help='Reset bazy danych przed importem')
parser.add_argument('--pos', type=int, default=1000, help='Liczba obrazów pozytywnych do dodania')
parser.add_argument('--neg', type=int, default=1000, help='Liczba obrazów negatywnych do dodania')
args = parser.parse_args()

# Konfiguracja loggera
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Inicjalizacja modelu CLIP
try:
    import clip
    device = "cuda" if torch.cuda.is_available() else "cpu"
    logger.info(f"Ładowanie modelu CLIP na urządzeniu: {device}")
    model, preprocess = clip.load("ViT-B/32", device=device)
    model.eval()
    logger.info("Model CLIP załadowany pomyślnie")
except ImportError:
    logger.error("Błąd: Moduł CLIP nie jest zainstalowany.")
    print("Instalowanie CLIP: pip install git+https://github.com/openai/CLIP.git")
    sys.exit(1)

# Stałe
NUM_POS_IMAGES = args.pos
NUM_NEG_IMAGES = args.neg
EMBEDDING_DIM = 512  # Wymiar embeddingów dla modelu CLIP ViT-B/32
DATA_DIR = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) / "data"
POS_DIR = DATA_DIR / "pos"
NEG_DIR = DATA_DIR / "neg"
DB_FILE = "tachyonai.db"

def reset_database():
    """Resetuje bazę danych."""
    logger.info("Resetowanie bazy danych...")
    
    # Tworzenie kopii zapasowej na wszelki wypadek
    if os.path.exists(DB_FILE):
        backup_name = f"{DB_FILE}.bak_{int(time.time())}"
        logger.info(f"Tworzenie kopii zapasowej: {backup_name}")
        shutil.copy2(DB_FILE, backup_name)
        
        # Usunięcie tabeli images
        logger.info("Usuwanie danych z tabeli 'images'...")
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM images")
        conn.commit()
        conn.close()
        
    # Odtworzenie tabel
    logger.info("Odtwarzanie struktury bazy danych...")
    Base.metadata.drop_all(bind=engine, tables=[models.Image.__table__])
    Base.metadata.create_all(bind=engine, tables=[models.Image.__table__])
    logger.info("Baza danych zresetowana pomyślnie.")

def generate_embedding(image_path):
    """Generuje embedding dla obrazu za pomocą CLIP."""
    try:
        # Wczytaj i przetwórz obraz
        image = Image.open(image_path).convert("RGB")
        image_input = preprocess(image).unsqueeze(0).to(device)
        
        # Generuj embedding
        with torch.no_grad():
            image_features = model.encode_image(image_input)
            image_features = image_features / image_features.norm(dim=-1, keepdim=True)
        
        # Konwersja do listy float (serializowalna do JSON)
        embedding = image_features.cpu().numpy()[0].tolist()
        return embedding
    except Exception as e:
        logger.error(f"Błąd podczas generowania embeddingu dla {image_path}: {str(e)}")
        return None

def get_positive_image_files(limit=1000):
    """Pobiera ścieżki do prawdziwych obrazów pozytywnych."""
    image_files = []
    
    # Sprawdź katalog rule34
    rule34_dir = POS_DIR / "rule34"
    if rule34_dir.exists():
        logger.info(f"Szukanie obrazów w {rule34_dir}...")
        rule34_files = list(rule34_dir.glob("*.jpg"))
        logger.info(f"Znaleziono {len(rule34_files)} obrazów w katalogu rule34")
        image_files.extend(rule34_files)
    
    # Sprawdź katalog freeones
    freeones_dir = POS_DIR / "freeones"
    if freeones_dir.exists() and len(image_files) < limit:
        logger.info(f"Szukanie obrazów w {freeones_dir}...")
        
        # Przeszukaj wszystkie podkatalogi
        for gallery_dir in freeones_dir.iterdir():
            if gallery_dir.is_dir():
                gallery_files = list(gallery_dir.glob("*.jpg"))
                logger.info(f"Znaleziono {len(gallery_files)} obrazów w galerii {gallery_dir.name}")
                image_files.extend(gallery_files)
                
                if len(image_files) >= limit:
                    break
    
    # Ogranicz do limitu i pomieszaj
    if len(image_files) > limit:
        random.shuffle(image_files)
        image_files = image_files[:limit]
    
    logger.info(f"Wybrano łącznie {len(image_files)} obrazów pozytywnych")
    return image_files

def get_negative_image_files(limit=1000):
    """Pobiera ścieżki do prawdziwych obrazów negatywnych."""
    image_files = []
    
    # Sprawdź katalog test/data
    test_data_dir = NEG_DIR / "open-images-v7" / "test" / "data"
    if test_data_dir.exists():
        logger.info(f"Szukanie obrazów w {test_data_dir}...")
        test_files = list(test_data_dir.glob("*.jpg"))
        logger.info(f"Znaleziono {len(test_files)} obrazów w katalogu test/data")
        image_files.extend(test_files)
    
    # Sprawdź katalog validation/data
    validation_data_dir = NEG_DIR / "open-images-v7" / "validation" / "data"
    if validation_data_dir.exists() and len(image_files) < limit:
        logger.info(f"Szukanie obrazów w {validation_data_dir}...")
        validation_files = list(validation_data_dir.glob("*.jpg"))
        logger.info(f"Znaleziono {len(validation_files)} obrazów w katalogu validation/data")
        image_files.extend(validation_files)
    
    # Ogranicz do limitu i pomieszaj
    if len(image_files) > limit:
        random.shuffle(image_files)
        image_files = image_files[:limit]
    
    logger.info(f"Wybrano łącznie {len(image_files)} obrazów negatywnych")
    return image_files

def load_metadata_from_freeones(gallery_path):
    """Ładuje metadane z pliku metadata.json dla galerii z freeones."""
    metadata_file = gallery_path / "metadata.json"
    if not metadata_file.exists():
        return {}
    
    try:
        with open(metadata_file, "r", encoding="utf-8") as f:
            metadata = json.load(f)
        return metadata
    except Exception as e:
        logger.error(f"Błąd podczas ładowania metadanych z {metadata_file}: {str(e)}")
        return {}

def import_positive_images(db, image_files):
    """Importuje prawdziwe obrazy pozytywne z generowaniem embeddingów CLIP."""
    logger.info(f"Importowanie {len(image_files)} obrazów pozytywnych...")
    imported_count = 0
    
    for image_path in tqdm(image_files, desc="Obrazy pozytywne"):
        # Sprawdź, czy plik istnieje
        if not os.path.exists(image_path):
            logger.warning(f"Plik {image_path} nie istnieje, pomijam.")
            continue
        
        try:
            # Wczytaj metadane jeśli to obraz z freeones
            metadata = {}
            if "freeones" in str(image_path):
                gallery_path = image_path.parent
                metadata = load_metadata_from_freeones(gallery_path)
            
            # Generuj embedding
            embedding = generate_embedding(image_path)
            if embedding is None:
                logger.warning(f"Nie udało się wygenerować embeddingu dla {image_path}, pomijam.")
                continue
            
            # Dodaj obraz do bazy
            image = ImageModel(
                path=str(image_path),
                type=ImageTypeEnum.POSITIVE,
                img_metadata=metadata,
                embedding=embedding,
                total_successes=0,
                total_failures=0,
                total_profit_factor=1.0
            )
            db.add(image)
            imported_count += 1
            
            # Co 10 obrazów commituj zmiany
            if imported_count % 10 == 0:
                db.commit()
                
        except Exception as e:
            logger.error(f"Błąd podczas importu obrazu {image_path}: {str(e)}")
    
    # Końcowy commit
    db.commit()
    logger.info(f"Zaimportowano {imported_count} obrazów pozytywnych.")
    return imported_count

def import_negative_images(db, image_files):
    """Importuje prawdziwe obrazy negatywne z generowaniem embeddingów CLIP."""
    logger.info(f"Importowanie {len(image_files)} obrazów negatywnych...")
    imported_count = 0
    
    for image_path in tqdm(image_files, desc="Obrazy negatywne"):
        # Sprawdź, czy plik istnieje
        if not os.path.exists(image_path):
            logger.warning(f"Plik {image_path} nie istnieje, pomijam.")
            continue
        
        try:
            # Generuj embedding
            embedding = generate_embedding(image_path)
            if embedding is None:
                logger.warning(f"Nie udało się wygenerować embeddingu dla {image_path}, pomijam.")
                continue
                
            # Dodaj obraz do bazy
            image = ImageModel(
                path=str(image_path),
                type=ImageTypeEnum.NEGATIVE,
                img_metadata={},  # Puste metadane dla obrazów negatywnych
                embedding=embedding,
                total_successes=0,
                total_failures=0,
                total_profit_factor=1.0
            )
            db.add(image)
            imported_count += 1
            
            # Co 10 obrazów commituj zmiany
            if imported_count % 10 == 0:
                db.commit()
                
        except Exception as e:
            logger.error(f"Błąd podczas importu obrazu {image_path}: {str(e)}")
    
    # Końcowy commit
    db.commit()
    logger.info(f"Zaimportowano {imported_count} obrazów negatywnych.")
    return imported_count

def main():
    """Główna funkcja importująca obrazy z prawdziwymi embeddingami."""
    start_time = time.time()
    
    # Resetuj bazę danych jeśli podano argument --reset
    if args.reset:
        reset_database()
    
    # Utworzenie sesji bazy danych
    db = SessionLocal()
    try:
        # Pobierz ścieżki do obrazów
        pos_image_files = get_positive_image_files(NUM_POS_IMAGES)
        neg_image_files = get_negative_image_files(NUM_NEG_IMAGES)
        
        # Importuj obrazy i generuj embeddingi
        pos_count = import_positive_images(db, pos_image_files)
        neg_count = import_negative_images(db, neg_image_files)
        
        # Wyświetl podsumowanie
        elapsed_time = time.time() - start_time
        logger.info(f"\nPodsumowanie importu:")
        logger.info(f"- Czas wykonania: {elapsed_time:.2f} sekund")
        logger.info(f"- Liczba zaimportowanych obrazów pozytywnych: {pos_count}")
        logger.info(f"- Liczba zaimportowanych obrazów negatywnych: {neg_count}")
        logger.info(f"- Łączna liczba zaimportowanych obrazów: {pos_count + neg_count}")
        
    except Exception as e:
        logger.error(f"Błąd podczas importu danych: {str(e)}")
    finally:
        db.close()

if __name__ == "__main__":
    main() 