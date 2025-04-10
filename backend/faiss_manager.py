import faiss
import numpy as np
import threading
import time
import pickle
import os
import logging
import traceback
from datetime import datetime
from pathlib import Path
from typing import Dict, Tuple, List, Any, Optional

from sqlalchemy.orm import Session
from .database import SessionLocal
from .models import Image as ImageModel, ImageTypeEnum

# Konfiguracja loggera
logger = logging.getLogger(__name__)


def build_faiss_index_from_images(images: List[ImageModel]) -> Tuple[faiss.Index, Dict[int, int], Dict[int, int]]:
    """
    Buduje indeks FAISS z listy obrazów z embeddingami.
    
    Args:
        images: Lista obrazów ImageModel z embeddingami
        
    Returns:
        Tuple (index, id_to_index, index_to_id)
    """
    logger.info(f"Budowanie indeksu FAISS z {len(images)} obrazów...")
    
    # Filtruj obrazy bez embeddingów
    images_with_embeddings = [img for img in images if img.embedding]
    
    if not images_with_embeddings:
        logger.warning("Brak obrazów z embeddingami")
        return None, {}, {}
    
    # Określ wymiar embeddingów na podstawie pierwszego obrazu
    sample_embedding = images_with_embeddings[0].embedding
    dim = len(sample_embedding)
    
    # Utwórz indeks FAISS
    index = faiss.IndexFlatIP(dim)  # Używamy Inner Product jako miary podobieństwa
    
    # Przygotuj embeddingi i mapowania
    embeddings = []
    id_to_index = {}  # Mapowanie ID obrazu -> indeks w FAISS
    index_to_id = {}  # Mapowanie indeks w FAISS -> ID obrazu
    
    for i, img in enumerate(images_with_embeddings):
        embeddings.append(img.embedding)
        id_to_index[img.id] = i
        index_to_id[i] = img.id
    
    # Konwertuj embeddingi na array numpy i dodaj do indeksu
    embeddings_array = np.array(embeddings, dtype=np.float32)
    
    # Normalizuj embeddingi (opcjonalne, ale poprawia wyniki)
    faiss.normalize_L2(embeddings_array)
    
    # Dodaj do indeksu
    index.add(embeddings_array)
    
    logger.info(f"Zbudowano indeks FAISS z {index.ntotal} wektorami o wymiarze {dim}")
    
    return index, id_to_index, index_to_id


def _find_nearest_image(index: faiss.Index, id_to_index: Dict[int, int], index_to_id: Dict[int, int], 
                       query_embedding: List[float]) -> Tuple[Optional[int], Optional[float]]:
    """
    Znajduje najbliższy obraz do podanego embeddingu.
    
    Args:
        index: Indeks FAISS
        id_to_index: Mapowanie ID obrazu -> indeks w FAISS
        index_to_id: Mapowanie indeks w FAISS -> ID obrazu
        query_embedding: Embedding zapytania
        
    Returns:
        Tuple (ID obrazu, odległość) lub (None, None) w przypadku błędu
    """
    if index.ntotal == 0 or not id_to_index or not index_to_id:
        logger.warning("Pusty indeks FAISS lub brak mapowań ID")
        return None, None
    
    try:
        # Przygotuj embedding zapytania
        query = np.array([query_embedding], dtype=np.float32)
        
        # Normalizuj zapytanie (jeśli embeddingi były normalizowane)
        faiss.normalize_L2(query)
        
        # Znajdź najbliższy wektor
        distances, indices = index.search(query, 1)
        
        if len(indices) == 0 or len(indices[0]) == 0:
            logger.warning("Nie znaleziono żadnego wektora")
            return None, None
        
        nearest_index = indices[0][0]
        distance = distances[0][0]
        
        # Mapuj indeks na ID obrazu
        if nearest_index in index_to_id:
            nearest_id = index_to_id[nearest_index]
            return nearest_id, distance
        else:
            logger.warning(f"Nie znaleziono ID dla indeksu {nearest_index}")
            return None, None
    
    except Exception as e:
        logger.error(f"Błąd podczas wyszukiwania najbliższego obrazu: {str(e)}")
        logger.error(traceback.format_exc())
        return None, None


class FaissIndexManager:
    """Menedżer indeksów FAISS dla różnych typów obrazów"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(FaissIndexManager, cls).__new__(cls)
                cls._instance._initialize()
            return cls._instance
    
    def _initialize(self):
        """Inicjalizacja menedżera indeksów"""
        self.indexes = {
            ImageTypeEnum.POSITIVE: None,
            ImageTypeEnum.NEGATIVE: None
        }
        self.id_mappings = {
            ImageTypeEnum.POSITIVE: (None, None),  # (id_to_index, index_to_id)
            ImageTypeEnum.NEGATIVE: (None, None)
        }
        self.last_updated = {
            ImageTypeEnum.POSITIVE: None,
            ImageTypeEnum.NEGATIVE: None
        }
        self.cache_dir = Path("cache/faiss_indexes")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Wczytaj istniejące indeksy przy starcie
        self._load_all_indexes()
        
        # Uruchom wątek odświeżający indeksy
        self.refresh_thread = threading.Thread(target=self._periodic_refresh, daemon=True)
        self.refresh_thread.start()
    
    def get_index(self, image_type: ImageTypeEnum) -> Tuple[faiss.Index, Dict[int, int], Dict[int, int]]:
        """
        Pobierz indeks dla określonego typu obrazu
        """
        with self._lock:
            if not self._initialize():
                return None, {}, {}
                
            if image_type not in self.indexes:
                logger.error(f"Nieznany typ obrazu: {image_type}")
                return None, {}, {}
                
            if self.last_updated[image_type] is None or not self._load_index(image_type):
                # Jeśli nie udało się wczytać z dysku, przebuduj indeks
                self._build_index(image_type)
                
            if image_type in self.indexes:
                return self.indexes[image_type], self.id_mappings[image_type]["id_to_index"], self.id_mappings[image_type]["index_to_id"]
            
            return None, {}, {}

    def get_filtered_index(self, image_type: ImageTypeEnum, exclude_ids: List[int]):
        """
        Pobierz indeks z filtrowaną listą ID (usuwając wykluczone ID)
        
        To nie tworzy nowego indeksu, tylko zwraca istniejący z przefiltrowanymi mapowaniami
        aby pominąć konkretne obrazy podczas wyszukiwania.
        """
        with self._lock:
            # Upewnij się, że indeks istnieje
            if self.indexes[image_type] is None:
                self._build_index(image_type)
            
            index = self.indexes[image_type]
            id_to_index, index_to_id = self.id_mappings[image_type]
            
            if not id_to_index or not index_to_id:
                logger.warning(f"Brak mapowań indeksu dla typu {image_type}")
                return index, {}, {}
            
            # Filtruj mapowania, aby usunąć wykluczone ID
            filtered_id_to_index = {k: v for k, v in id_to_index.items() if k not in exclude_ids}
            filtered_index_to_id = {k: v for k, v in index_to_id.items() if v not in exclude_ids}
            
            logger.info(f"Zwracam filtrowany indeks: usunięto {len(exclude_ids)} ID, pozostało {len(filtered_id_to_index)}")
            
            return index, filtered_id_to_index, filtered_index_to_id
    
    def _build_index(self, image_type: ImageTypeEnum, db=None):
        """Zbuduj indeks FAISS dla danego typu obrazu"""
        should_close_db = False
        if db is None:
            db = SessionLocal()
            should_close_db = True
        
        try:
            # Sprawdź, czy możemy załadować istniejący indeks z dysku
            index_path = self.cache_dir / f"index_{image_type.value}.faiss"
            if index_path.exists() and self.indexes[image_type] is None:
                logger.info(f"Próba załadowania istniejącego indeksu dla typu {image_type}...")
                loaded = self._load_index(image_type)
                if loaded:
                    logger.info(f"Pomyślnie załadowano istniejący indeks dla typu {image_type}")
                    return

            # Jeśli nie załadowano indeksu, budujemy go od nowa
            logger.info(f"Budowanie indeksu FAISS dla obrazów typu {image_type}...")
            
            # Dodajemy limit i optymalizujemy zapytanie
            images = db.query(ImageModel).filter(
                ImageModel.type == image_type,
                ImageModel.embedding.isnot(None)
            ).limit(10000).all()  # Dodajemy limit, aby uniknąć przetwarzania zbyt wielu obrazów naraz
            
            if not images:
                logger.warning(f"Brak obrazów typu {image_type} z embeddingami")
                return
                
            logger.info(f"Znaleziono {len(images)} obrazów typu {image_type} z embeddingami")
            
            # Budowanie indeksu z naszej własnej implementacji
            index, id_to_index, index_to_id = build_faiss_index_from_images(images)
            
            # Zapisz indeks i mapowania
            self.indexes[image_type] = index
            self.id_mappings[image_type] = {"id_to_index": id_to_index, "index_to_id": index_to_id}
            self.last_updated[image_type] = datetime.now()
            
            # Zapisz indeks na dysku
            self._save_index(image_type)
            
            logger.info(f"Indeks FAISS dla obrazów typu {image_type} zbudowany i zapisany.")
        except Exception as e:
            logger.error(f"Błąd podczas budowania indeksu FAISS: {str(e)}")
            logger.error(traceback.format_exc())
        finally:
            if should_close_db:
                db.close()
    
    def build_full_index(self, image_type: ImageTypeEnum, batch_size: int = 1000):
        """
        Buduje pełny indeks FAISS dla wszystkich obrazów danego typu, podzielony na partie.
        
        Args:
            image_type: Typ obrazu (ImageTypeEnum.POSITIVE lub ImageTypeEnum.NEGATIVE)
            batch_size: Rozmiar partii przy przetwarzaniu
        """
        should_close_db = False
        db = SessionLocal()
        should_close_db = True
        
        try:
            # Sprawdź, czy możemy załadować istniejący indeks z dysku
            index_path = self.cache_dir / f"index_{image_type.value}.faiss"
            if index_path.exists() and self.indexes[image_type] is None:
                logger.info(f"Próba załadowania istniejącego indeksu dla typu {image_type}...")
                loaded = self._load_index(image_type)
                if loaded:
                    logger.info(f"Pomyślnie załadowano istniejący indeks dla typu {image_type}")
                    return

            # Pobierz liczbę wszystkich obrazów
            total_images = db.query(ImageModel).filter(
                ImageModel.type == image_type,
                ImageModel.embedding.isnot(None)
            ).count()
            
            logger.info(f"Budowanie pełnego indeksu FAISS dla {total_images} obrazów typu {image_type}...")
            
            # Pobierz pierwszą partię obrazów, aby określić wymiar embeddingu
            first_batch = db.query(ImageModel).filter(
                ImageModel.type == image_type,
                ImageModel.embedding.isnot(None)
            ).limit(batch_size).all()
            
            if not first_batch:
                logger.warning(f"Brak obrazów typu {image_type} z embeddingami")
                return
                
            # Określ wymiar embeddingów
            sample_embedding = first_batch[0].embedding
            dim = len(sample_embedding)
            logger.info(f"Ustalono wymiar embeddingu: {dim}")
            
            # Utwórz nowy indeks FAISS
            index = faiss.IndexFlatIP(dim)
            
            # Przygotuj mapowania ID
            id_to_index = {}
            index_to_id = {}
            
            # Statystyki
            total_processed = 0
            total_skipped = 0
            
            # Przetwarzaj obrazy partiami
            offset = 0
            while offset < total_images:
                logger.info(f"Przetwarzanie partii {offset // batch_size + 1}...")
                
                # Pobierz partię obrazów
                batch = db.query(ImageModel).filter(
                    ImageModel.type == image_type,
                    ImageModel.embedding.isnot(None)
                ).offset(offset).limit(batch_size).all()
                
                if not batch:
                    break
                
                # Przygotuj embeddingi i mapowania dla partii
                valid_embeddings = []
                for i, img in enumerate(batch):
                    if img.embedding is None:
                        logger.warning(f"Pominięto obraz {img.id} - brak embeddingu")
                        total_skipped += 1
                        continue
                        
                    # Sprawdź wymiar embeddingu
                    if len(img.embedding) == dim:
                        # Konwertuj listę na numpy array
                        embedding = np.array(img.embedding, dtype=np.float32)
                        valid_embeddings.append(embedding)
                        id_to_index[img.id] = offset + total_processed
                        index_to_id[offset + total_processed] = img.id
                        total_processed += 1
                    else:
                        logger.warning(f"Pominięto obraz {img.id} - niezgodny wymiar embeddingu ({len(img.embedding)} != {dim})")
                        total_skipped += 1
                
                if valid_embeddings:
                    # Konwertuj listę numpy array na pojedynczy numpy array
                    embeddings_array = np.stack(valid_embeddings)
                    faiss.normalize_L2(embeddings_array)
                    index.add(embeddings_array)
                
                offset += batch_size
                
            logger.info(f"Statystyki przetwarzania:")
            logger.info(f"  - Przetworzono obrazów: {total_processed}")
            logger.info(f"  - Pominięto obrazów: {total_skipped}")
            logger.info(f"  - W sumie: {total_processed + total_skipped}")
            logger.info(f"  - Współczynnik pominiętych: {total_skipped / (total_processed + total_skipped) * 100:.2f}%")
            logger.info(f"Zbudowano pełny indeks FAISS z {index.ntotal} wektorami o wymiarze {dim}")
            
            # Zapisz indeks i mapowania
            self.indexes[image_type] = index
            self.id_mappings[image_type] = {"id_to_index": id_to_index, "index_to_id": index_to_id}
            self.last_updated[image_type] = datetime.now()
            
            # Zapisz na dysku
            self._save_index(image_type)
            
            logger.info(f"Pełny indeks FAISS dla obrazów typu {image_type} zbudowany i zapisany.")
            
        except Exception as e:
            logger.error(f"Błąd podczas budowania pełnego indeksu FAISS: {str(e)}")
            logger.error(traceback.format_exc())
        finally:
            if should_close_db:
                db.close()
    
    def get_index_size(self, image_type: ImageTypeEnum) -> Tuple[int, int]:
        """
        Zwraca rozmiar indeksu (liczbę wektorów i ich wymiar).
        
        Args:
            image_type: Typ obrazu (ImageTypeEnum.POSITIVE lub ImageTypeEnum.NEGATIVE)
            
        Returns:
            Tuple (liczba wektorów, wymiar wektorów)
        """
        with self._lock:
            index, _, _ = self.get_index(image_type)
            if index is None:
                return 0, 0
            return index.ntotal, index.d
    
    def _save_index(self, image_type: ImageTypeEnum):
        """Zapisz indeks na dysku"""
        try:
            index_path = self.cache_dir / f"index_{image_type.value}.faiss"
            mapping_path = self.cache_dir / f"mapping_{image_type.value}.pkl"
            
            # Zapisz indeks FAISS
            logger.info(f"Zapisuję indeks FAISS dla typu {image_type} do pliku {index_path}")
            faiss.write_index(self.indexes[image_type], str(index_path))
            
            # Zapisz mapowania ID
            logger.info(f"Zapisuję mapowania ID dla typu {image_type} do pliku {mapping_path}")
            with open(mapping_path, 'wb') as f:
                pickle.dump(self.id_mappings[image_type], f)
                
            logger.info(f"Indeks i mapowania dla typu {image_type} zapisane na dysku")
        except Exception as e:
            logger.error(f"Błąd podczas zapisywania indeksu FAISS: {str(e)}")
            logger.error(traceback.format_exc())
    
    def _load_index(self, image_type: ImageTypeEnum):
        """Wczytaj indeks z dysku"""
        try:
            index_path = self.cache_dir / f"index_{image_type.value}.faiss"
            mapping_path = self.cache_dir / f"mapping_{image_type.value}.pkl"
            
            if not index_path.exists() or not mapping_path.exists():
                logger.info(f"Nie znaleziono zapisanych indeksów dla typu {image_type}")
                logger.info(f"  - Ścieżka indeksu: {index_path}")
                logger.info(f"  - Ścieżka mapowania: {mapping_path}")
                return False
                
            # Wczytaj indeks FAISS
            logger.info(f"Wczytywanie indeksu FAISS dla typu {image_type} z {index_path}")
            self.indexes[image_type] = faiss.read_index(str(index_path))
            
            # Wczytaj mapowania ID
            logger.info(f"Wczytywanie mapowania ID dla typu {image_type} z {mapping_path}")
            with open(mapping_path, 'rb') as f:
                self.id_mappings[image_type] = pickle.load(f)
                
            self.last_updated[image_type] = datetime.fromtimestamp(index_path.stat().st_mtime)
            
            # Sprawdź rozmiar indeksu po wczytaniu
            if self.indexes[image_type] is not None:
                logger.info(f"Wczytano indeks z {self.indexes[image_type].ntotal} wektorami o wymiarze {self.indexes[image_type].d}")
            else:
                logger.warning(f"Indeks po wczytaniu jest None")
                
            logger.info(f"Wczytano indeks i mapowania dla typu {image_type} z dysku")
            return True
        except Exception as e:
            logger.error(f"Błąd podczas wczytywania indeksu FAISS: {str(e)}")
            logger.error(traceback.format_exc())
            return False
    
    def _load_all_indexes(self):
        """Wczytaj wszystkie indeksy z dysku"""
        for image_type in self.indexes.keys():
            self._load_index(image_type)
    
    def invalidate_index(self, image_type: ImageTypeEnum = None):
        """Oznacz indeks jako nieaktualny, wymuszając przebudowanie"""
        with self._lock:
            if image_type is None:
                # Oznacz wszystkie indeksy jako nieaktualne
                for type_enum in self.indexes.keys():
                    self.last_updated[type_enum] = None
            else:
                self.last_updated[image_type] = None
    
    def rebuild_all_indexes(self, db=None):
        """Przebuduj wszystkie indeksy"""
        should_close_db = False
        if db is None:
            db = SessionLocal()
            should_close_db = True
        
        try:
            for image_type in self.indexes.keys():
                self._build_index(image_type, db)
        finally:
            if should_close_db:
                db.close()
    
    def _periodic_refresh(self):
        """Periodyczne odświeżanie indeksów w tle"""
        while True:
            try:
                for image_type in self.indexes.keys():
                    # Jeśli indeks nie był aktualizowany od co najmniej 24 godzin
                    if (self.last_updated[image_type] is None or 
                        (datetime.now() - self.last_updated[image_type]).total_seconds() > 86400):
                        logger.info(f"Rozpoczęcie okresowego odświeżania indeksu dla typu {image_type}")
                        self._build_index(image_type)
                
                # Odczekaj 12 godzin przed kolejnym sprawdzeniem
                time.sleep(43200)
            except Exception as e:
                logger.error(f"Błąd w wątku odświeżania indeksu: {str(e)}")
                time.sleep(3600)  # W przypadku błędu, odczekaj godzinę


# Inicjalizacja singletona przy imporcie modułu
faiss_index_manager = FaissIndexManager()

def get_faiss_index_manager() -> FaissIndexManager:
    """Funkcja dostępowa do singletona FaissIndexManager"""
    return faiss_index_manager
