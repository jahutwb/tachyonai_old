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

logger = logging.getLogger(__name__)


def build_faiss_index_from_images(images: List[ImageModel]) -> Tuple[faiss.Index, Dict[int, int], Dict[int, int]]:
    logger.info(f"Budowanie indeksu FAISS z {len(images)} obrazów...")
    images_with_embeddings = [img for img in images if img.embedding]

    if not images_with_embeddings:
        logger.warning("Brak obrazów z embeddingami")
        return None, {}, {}

    sample_embedding = images_with_embeddings[0].embedding
    dim = len(sample_embedding)
    index = faiss.IndexFlatIP(dim)

    embeddings = []
    id_to_index = {}
    index_to_id = {}

    for i, img in enumerate(images_with_embeddings):
        embeddings.append(img.embedding)
        id_to_index[img.id] = i
        index_to_id[i] = img.id

    embeddings_array = np.array(embeddings, dtype=np.float32)
    faiss.normalize_L2(embeddings_array)
    index.add(embeddings_array)

    logger.info(f"Zbudowano indeks FAISS z {index.ntotal} wektorami o wymiarze {dim}")
    return index, id_to_index, index_to_id

def _find_k_nearest_images(
    index: faiss.Index,
    id_to_index: Dict[int, int],
    index_to_id: Dict[int, int],
    query_embedding: List[float],
    k: int = 5
) -> Tuple[List[int], List[float]]:
    if index is None or index.ntotal == 0:
        logger.warning("Indeks FAISS pusty lub niezainicjalizowany.")
        return [], []

    try:
        query = np.array([query_embedding], dtype=np.float32)
        faiss.normalize_L2(query)
        distances, indices = index.search(query, k)

        nearest_ids = []
        nearest_distances = []
        for idx, dist in zip(indices[0], distances[0]):
            if idx in index_to_id:
                nearest_ids.append(index_to_id[idx])
                nearest_distances.append(dist)

        return nearest_ids, nearest_distances

    except Exception as e:
        logger.error(f"Błąd w _find_k_nearest_images: {str(e)}")
        logger.error(traceback.format_exc())
        return [], []


def _find_nearest_image(index: faiss.Index, id_to_index: Dict[int, int], index_to_id: Dict[int, int], 
                       query_embedding: List[float]) -> Tuple[Optional[int], Optional[float]]:
    if index is None or index.ntotal == 0 or not id_to_index or not index_to_id:
        logger.warning("Pusty lub niewłaściwie zainicjalizowany indeks FAISS lub brak mapowań ID")
        return None, None

    try:
        query = np.array([query_embedding], dtype=np.float32)
        faiss.normalize_L2(query)
        distances, indices = index.search(query, 1)

        if len(indices) == 0 or len(indices[0]) == 0:
            logger.warning("Nie znaleziono żadnego wektora w indeksie")
            return None, None

        nearest_index = indices[0][0]
        distance = distances[0][0]

        if nearest_index in index_to_id:
            nearest_id = index_to_id[nearest_index]
            return nearest_id, distance
        else:
            logger.warning(f"Brak ID dla indeksu {nearest_index}")
            return None, None

    except Exception as e:
        logger.error(f"Błąd podczas wyszukiwania najbliższego obrazu: {str(e)}")
        logger.error(traceback.format_exc())
        return None, None

def _find_nearest_image_excluding(
    index: faiss.Index,
    id_to_index: Dict[int, int],
    index_to_id: Dict[int, int],
    query_embedding: List[float],
    exclude_ids: Optional[set] = None,
    top_k: int = 10
) -> Tuple[Optional[int], Optional[float]]:
    if index is None or index.ntotal == 0:
        logger.warning("Indeks FAISS pusty lub niezainicjalizowany.")
        return None, None

    try:
        query = np.array([query_embedding], dtype=np.float32)
        faiss.normalize_L2(query)
        distances, indices = index.search(query, top_k)

        for idx, dist in zip(indices[0], distances[0]):
            if idx < 0:
                continue
            img_id = index_to_id.get(idx)
            if img_id is not None and (exclude_ids is None or img_id not in exclude_ids):
                return img_id, dist
        return None, None

    except Exception as e:
        logger.error(f"Błąd w _find_nearest_image_excluding: {str(e)}")
        logger.error(traceback.format_exc())
        return None, None


class FaissIndexManager:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(FaissIndexManager, cls).__new__(cls)
                cls._instance._initialize()
            return cls._instance

    def _initialize(self):
        self.indexes = {ImageTypeEnum.POSITIVE: None, ImageTypeEnum.NEGATIVE: None}
        self.id_mappings = {ImageTypeEnum.POSITIVE: {"id_to_index": None, "index_to_id": None},  
                            ImageTypeEnum.NEGATIVE: {"id_to_index": None, "index_to_id": None}}
        self.last_updated = {ImageTypeEnum.POSITIVE: None, ImageTypeEnum.NEGATIVE: None}
        self.cache_dir = Path("cache/faiss_indexes")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._load_all_indexes()

    def get_index(self, image_type: ImageTypeEnum) -> Tuple[Optional[faiss.Index], Dict[int, int], Dict[int, int]]:
        with self._lock:
            if image_type not in self.indexes:
                logger.error(f"Nieznany typ obrazu: {image_type}")
                return None, {}, {}

            if self.indexes[image_type] is None:
                logger.info(f"Indeks dla {image_type} niezaładowany, próba wczytania z dysku...")
                success = self._load_index(image_type)
                if not success:
                    logger.warning(f"Nie udało się wczytać indeksu FAISS dla {image_type}, próbuję go zbudować...")
                    self._build_index(image_type)

            index = self.indexes[image_type]
            id_to_index = self.id_mappings[image_type]["id_to_index"] or {}
            index_to_id = self.id_mappings[image_type]["index_to_id"] or {}

            if index is None:
                logger.error(f"Indeks FAISS typu {image_type} jest nadal None po wczytaniu/przebudowie")
            else:
                logger.info(f"Indeks FAISS dla {image_type} zawiera {index.ntotal} wektorów")

            return index, id_to_index, index_to_id

    def _build_index(self, image_type: ImageTypeEnum, db: Session = None):
        with self._lock:
            try:
                logger.info(f"Rozpoczynanie przebudowy indeksu dla typu {image_type}")
                if db is None:
                    db = SessionLocal()
                images = db.query(ImageModel).filter(ImageModel.type == image_type, ImageModel.embedding.isnot(None)).all()
                if db:
                    db.close()

                if not images:
                    logger.warning(f"Brak obrazów typu {image_type} z embeddingami w bazie danych")
                    return

                index, id_to_index, index_to_id = build_faiss_index_from_images(images)
                if index is None:
                    logger.error(f"Nie udało się utworzyć indeksu FAISS dla typu {image_type}")
                    return

                self.indexes[image_type] = index
                self.id_mappings[image_type] = {"id_to_index": id_to_index, "index_to_id": index_to_id}
                self.last_updated[image_type] = datetime.now()
                self._save_index(image_type, index, id_to_index, index_to_id)
            except Exception as e:
                logger.error(f"Błąd podczas przebudowy indeksu FAISS: {str(e)}")
                logger.error(traceback.format_exc())

    def _save_index(self, image_type: ImageTypeEnum, index: faiss.Index, id_to_index: Dict[int, int], index_to_id: Dict[int, int]):
        try:
            index_path = self.cache_dir / f"index_{image_type.value}.faiss"
            mapping_path = self.cache_dir / f"mapping_{image_type.value}.pkl"
            faiss.write_index(index, str(index_path))
            with open(mapping_path, 'wb') as f:
                pickle.dump({"id_to_index": id_to_index, "index_to_id": index_to_id}, f)
            logger.info(f"Indeks i mapowania FAISS zapisane dla typu {image_type}")
        except Exception as e:
            logger.error(f"Błąd zapisu indeksu FAISS: {str(e)}")
            logger.error(traceback.format_exc())

    def _load_index(self, image_type: ImageTypeEnum) -> bool:
        try:
            index_path = self.cache_dir / f"index_{image_type.value}.faiss"
            mapping_path = self.cache_dir / f"mapping_{image_type.value}.pkl"

            if not index_path.exists() or not mapping_path.exists():
                logger.warning(f"Brak plików indeksu FAISS dla typu {image_type}")
                return False

            self.indexes[image_type] = faiss.read_index(str(index_path))
            with open(mapping_path, 'rb') as f:
                self.id_mappings[image_type] = pickle.load(f)
            self.last_updated[image_type] = datetime.fromtimestamp(index_path.stat().st_mtime)
            logger.info(f"Wczytano indeks i mapowania FAISS dla typu {image_type}")
            return True
        except Exception as e:
            logger.error(f"Błąd wczytywania indeksu FAISS: {str(e)}")
            logger.error(traceback.format_exc())
            return False

    def _load_all_indexes(self):
        for image_type in self.indexes.keys():
            self._load_index(image_type)


def get_faiss_index_manager():
    try:
        return FaissIndexManager()
    except Exception as e:
        logger.error(f"Błąd inicjalizacji FaissIndexManager: {str(e)}")
        logger.error(traceback.format_exc())
        return None
