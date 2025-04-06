import os
import json
import logging
import csv
from pathlib import Path
from sqlalchemy.orm import Session
import numpy as np
from typing import List, Dict, Any, Optional
from PIL import Image

from .database import SessionLocal, engine
from .models import Image as ImageModel, ImageTypeEnum
from . import models

# Konfiguracja loggera
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Ścieżki do katalogów z danymi
DATA_DIR = Path("/home/jahu/PycharmProjects/tachyonai/data")
POS_DIR = DATA_DIR / "pos"
NEG_DIR = DATA_DIR / "neg"

# Ścieżki do plików metadanych z Open Images
OPEN_IMAGES_CLASSES_FILE = NEG_DIR / "metadata" / "classes.csv"
OPEN_IMAGES_IMAGE_IDS_FILE = NEG_DIR / "metadata" / "image_ids.csv"
OPEN_IMAGES_DETECTIONS_FILE = NEG_DIR / "labels" / "detections.csv"
OPEN_IMAGES_CLASSIFICATIONS_FILE = NEG_DIR / "labels" / "classifications.csv"


def load_metadata_from_freeones(gallery_path: Path) -> Dict[str, Any]:
    """Ładuje metadane z pliku metadata.json dla galerii z freeones."""
    metadata_file = gallery_path / "metadata.json"
    if not metadata_file.exists():
        return {}
    
    try:
        with open(metadata_file, "r", encoding="utf-8") as f:
            metadata = json.load(f)
        return metadata
    except json.JSONDecodeError:
        logger.error(f"Błąd parsowania JSON w pliku {metadata_file}")
        return {}
    except Exception as e:
        logger.error(f"Błąd podczas ładowania metadanych z {metadata_file}: {str(e)}")
        return {}


def process_pos_images(db: Session) -> int:
    """Przetwarza obrazy pozytywne i zapisuje je do bazy danych."""
    processed_count = 0
    
    # Przetwarzanie obrazów z freeones
    freeones_dir = POS_DIR / "freeones"
    if freeones_dir.exists():
        for gallery_dir in freeones_dir.iterdir():
            if gallery_dir.is_dir():
                metadata = load_metadata_from_freeones(gallery_dir)
                
                for img_file in gallery_dir.glob("*.jpg"):
                    # Sprawdź, czy obraz już istnieje w bazie
                    existing_image = db.query(ImageModel).filter(
                        ImageModel.path == str(img_file)
                    ).first()
                    
                    if existing_image:
                        logger.info(f"Obraz {img_file} już istnieje w bazie, pomijam.")
                        continue
                    
                    try:
                        # Stwórz nowy rekord obrazu
                        image = ImageModel(
                            path=str(img_file),
                            type=ImageTypeEnum.POSITIVE,
                            img_metadata=metadata,
                            embedding=None,  # Embedding będzie dodany później
                        )
                        db.add(image)
                        processed_count += 1
                        
                        # Co 10 obrazów commituj do bazy
                        if processed_count % 10 == 0:
                            db.commit()
                            logger.info(f"Zapisano {processed_count} obrazów pozytywnych.")
                    
                    except Exception as e:
                        logger.error(f"Błąd podczas przetwarzania obrazu {img_file}: {str(e)}")
    
    # Przetwarzanie obrazów z rule34
    rule34_dir = POS_DIR / "rule34"
    if rule34_dir.exists():
        for img_file in rule34_dir.glob("*.jpg"):
            # Sprawdź, czy obraz już istnieje w bazie
            existing_image = db.query(ImageModel).filter(
                ImageModel.path == str(img_file)
            ).first()
            
            if existing_image:
                logger.info(f"Obraz {img_file} już istnieje w bazie, pomijam.")
                continue
            
            try:
                # Stwórz nowy rekord obrazu
                image = ImageModel(
                    path=str(img_file),
                    type=ImageTypeEnum.POSITIVE,
                    img_metadata={},  # Brak metadanych dla rule34
                    embedding=None,  # Embedding będzie dodany później
                )
                db.add(image)
                processed_count += 1
                
                # Co 10 obrazów commituj do bazy
                if processed_count % 10 == 0:
                    db.commit()
                    logger.info(f"Zapisano {processed_count} obrazów pozytywnych.")
            
            except Exception as e:
                logger.error(f"Błąd podczas przetwarzania obrazu {img_file}: {str(e)}")
    
    # Końcowy commit
    db.commit()
    logger.info(f"Zakończono przetwarzanie obrazów pozytywnych. Zapisano {processed_count} obrazów.")
    
    return processed_count


def load_open_images_classes() -> Dict[str, str]:
    """Ładuje mapowanie ID klas na nazwy z pliku classes.csv."""
    class_map = {}
    try:
        with open(OPEN_IMAGES_CLASSES_FILE, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader)  # Pomijamy nagłówek
            for row in reader:
                if len(row) >= 2:
                    class_id, class_name = row[0], row[1]
                    class_map[class_id] = class_name
    except Exception as e:
        logger.error(f"Błąd podczas ładowania klas Open Images: {str(e)}")
    
    return class_map


def check_image_contains_person(image_id: str, detections_map: Dict[str, List[str]], class_map: Dict[str, str]) -> bool:
    """Sprawdza, czy obraz zawiera osobę (człowieka)."""
    if image_id not in detections_map:
        return False
    
    person_related_classes = [
        "Person", "Man", "Woman", "Boy", "Girl", "Human body", "Human face", "Human head",
        "Human arm", "Human hand", "Human leg", "Human foot", "Human eye", "Human ear",
        "Human nose", "Human mouth", "Human beard", "Human hair"
    ]
    
    # Normalizacja nazw klas do małych liter dla łatwiejszego porównania
    person_related_classes_lower = {c.lower() for c in person_related_classes}
    
    # Sprawdź, czy któraś z wykrytych klas wskazuje na obecność człowieka
    for class_id in detections_map[image_id]:
        if class_id in class_map:
            class_name = class_map[class_id]
            if class_name.lower() in person_related_classes_lower:
                return True
    
    return False


def load_open_images_detections() -> Dict[str, List[str]]:
    """Ładuje mapowanie ID obrazów na listy wykrytych klas obiektów."""
    detections_map = {}
    try:
        with open(OPEN_IMAGES_DETECTIONS_FILE, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader)  # Pomijamy nagłówek
            for row in reader:
                if len(row) >= 2:
                    image_id, class_id = row[0], row[2]
                    if image_id not in detections_map:
                        detections_map[image_id] = []
                    detections_map[image_id].append(class_id)
    except Exception as e:
        logger.error(f"Błąd podczas ładowania detekcji Open Images: {str(e)}")
    
    return detections_map


def load_open_images_classifications() -> Dict[str, List[str]]:
    """Ładuje mapowanie ID obrazów na listy sklasyfikowanych klas."""
    classifications_map = {}
    try:
        with open(OPEN_IMAGES_CLASSIFICATIONS_FILE, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader)  # Pomijamy nagłówek
            for row in reader:
                if len(row) >= 3:
                    image_id, class_id, is_positive = row[0], row[2], row[3] == "1"
                    if is_positive:  # Tylko pozytywne klasyfikacje
                        if image_id not in classifications_map:
                            classifications_map[image_id] = []
                        classifications_map[image_id].append(class_id)
    except Exception as e:
        logger.error(f"Błąd podczas ładowania klasyfikacji Open Images: {str(e)}")
    
    return classifications_map


def get_image_metadata(
    image_id: str, 
    class_map: Dict[str, str], 
    detections_map: Dict[str, List[str]], 
    classifications_map: Dict[str, List[str]]
) -> Dict[str, Any]:
    """Tworzy metadane dla obrazu na podstawie danych Open Images."""
    metadata = {"Categories": [], "Tags": []}
    
    # Dodawanie kategorii z detekcji
    if image_id in detections_map:
        for class_id in detections_map[image_id]:
            if class_id in class_map:
                metadata["Categories"].append(class_map[class_id])
    
    # Dodawanie tagów z klasyfikacji
    if image_id in classifications_map:
        for class_id in classifications_map[image_id]:
            if class_id in class_map:
                metadata["Tags"].append(class_map[class_id])
    
    return metadata


def map_filename_to_image_id(filename: str, image_ids_map: Dict[str, str]) -> Optional[str]:
    """Mapuje nazwę pliku na ID obrazu z Open Images."""
    # Usunięcie rozszerzenia
    base_name = os.path.splitext(os.path.basename(filename))[0]
    
    # Sprawdzenie, czy nazwa pliku jest bezpośrednio w mapie
    if base_name in image_ids_map:
        return image_ids_map[base_name]
    
    # Przeszukiwanie mapy (może być wolniejsze, ale bardziej elastyczne)
    for file_name, image_id in image_ids_map.items():
        if base_name in file_name or file_name in base_name:
            return image_id
    
    return None


def load_image_ids_map() -> Dict[str, str]:
    """Ładuje mapowanie nazw plików na ID obrazów z Open Images."""
    image_ids_map = {}
    try:
        with open(OPEN_IMAGES_IMAGE_IDS_FILE, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader)  # Pomijamy nagłówek
            for row in reader:
                if len(row) >= 2:
                    image_id, file_name = row[0], row[1]
                    # Usunięcie rozszerzenia
                    base_name = os.path.splitext(file_name)[0]
                    image_ids_map[base_name] = image_id
    except Exception as e:
        logger.error(f"Błąd podczas ładowania mapowania ID obrazów Open Images: {str(e)}")
    
    return image_ids_map


def process_neg_images(db: Session) -> int:
    """Przetwarza obrazy negatywne (bez ludzi) i zapisuje je do bazy danych."""
    processed_count = 0
    
    # Ładowanie danych pomocniczych
    class_map = load_open_images_classes()
    detections_map = load_open_images_detections()
    classifications_map = load_open_images_classifications()
    image_ids_map = load_image_ids_map()
    
    # Przetwarzanie obrazów z katalogu test/data
    test_data_dir = NEG_DIR / "test" / "data"
    if test_data_dir.exists():
        for img_file in test_data_dir.glob("*.jpg"):
            # Sprawdź, czy obraz już istnieje w bazie
            existing_image = db.query(ImageModel).filter(
                ImageModel.path == str(img_file)
            ).first()
            
            if existing_image:
                logger.info(f"Obraz {img_file} już istnieje w bazie, pomijam.")
                continue
            
            # Mapuj nazwę pliku na ID obrazu
            image_id = map_filename_to_image_id(str(img_file), image_ids_map)
            
            # Jeśli nie znaleziono ID lub obraz zawiera osobę, pomijamy
            if not image_id or check_image_contains_person(image_id, detections_map, class_map):
                logger.info(f"Pomijam obraz {img_file}: brak ID lub zawiera osobę.")
                continue
            
            try:
                # Pobierz metadane
                metadata = get_image_metadata(
                    image_id, class_map, detections_map, classifications_map
                )
                
                # Stwórz nowy rekord obrazu
                image = ImageModel(
                    path=str(img_file),
                    type=ImageTypeEnum.NEGATIVE,
                    img_metadata=metadata,
                    embedding=None,  # Embedding będzie dodany później
                )
                db.add(image)
                processed_count += 1
                
                # Co 10 obrazów commituj do bazy
                if processed_count % 10 == 0:
                    db.commit()
                    logger.info(f"Zapisano {processed_count} obrazów negatywnych.")
            
            except Exception as e:
                logger.error(f"Błąd podczas przetwarzania obrazu {img_file}: {str(e)}")
    
    # Przetwarzanie obrazów z katalogu validation/data
    validation_data_dir = NEG_DIR / "validation" / "data"
    if validation_data_dir.exists():
        for img_file in validation_data_dir.glob("*.jpg"):
            # Sprawdź, czy obraz już istnieje w bazie
            existing_image = db.query(ImageModel).filter(
                ImageModel.path == str(img_file)
            ).first()
            
            if existing_image:
                logger.info(f"Obraz {img_file} już istnieje w bazie, pomijam.")
                continue
            
            # Mapuj nazwę pliku na ID obrazu
            image_id = map_filename_to_image_id(str(img_file), image_ids_map)
            
            # Jeśli nie znaleziono ID lub obraz zawiera osobę, pomijamy
            if not image_id or check_image_contains_person(image_id, detections_map, class_map):
                logger.info(f"Pomijam obraz {img_file}: brak ID lub zawiera osobę.")
                continue
            
            try:
                # Pobierz metadane
                metadata = get_image_metadata(
                    image_id, class_map, detections_map, classifications_map
                )
                
                # Stwórz nowy rekord obrazu
                image = ImageModel(
                    path=str(img_file),
                    type=ImageTypeEnum.NEGATIVE,
                    img_metadata=metadata,
                    embedding=None,  # Embedding będzie dodany później
                )
                db.add(image)
                processed_count += 1
                
                # Co 10 obrazów commituj do bazy
                if processed_count % 10 == 0:
                    db.commit()
                    logger.info(f"Zapisano {processed_count} obrazów negatywnych.")
            
            except Exception as e:
                logger.error(f"Błąd podczas przetwarzania obrazu {img_file}: {str(e)}")
    
    # Końcowy commit
    db.commit()
    logger.info(f"Zakończono przetwarzanie obrazów negatywnych. Zapisano {processed_count} obrazów.")
    
    return processed_count


def main():
    """Główna funkcja importująca dane."""
    # Sprawdzenie, czy katalog danych istnieje
    if not DATA_DIR.exists():
        logger.error(f"Katalog danych {DATA_DIR} nie istnieje.")
        return
    
    # Utworzenie sesji bazy danych
    db = SessionLocal()
    try:
        # Przetwarzanie obrazów pozytywnych
        pos_count = process_pos_images(db)
        logger.info(f"Zaimportowano {pos_count} obrazów pozytywnych.")
        
        # Przetwarzanie obrazów negatywnych
        neg_count = process_neg_images(db)
        logger.info(f"Zaimportowano {neg_count} obrazów negatywnych.")
        
        logger.info(f"Import zakończony. Łącznie zaimportowano {pos_count + neg_count} obrazów.")
    except Exception as e:
        logger.error(f"Błąd podczas importu danych: {str(e)}")
    finally:
        db.close()


if __name__ == "__main__":
    main() 