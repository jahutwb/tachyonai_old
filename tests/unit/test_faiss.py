import pytest
import numpy as np
from unittest.mock import patch, MagicMock, Mock
import faiss

from backend.embedding import find_nearest_image, build_faiss_index
from backend.models import ImageTypeEnum


@pytest.fixture
def sample_embeddings():
    """Przykładowe embeddingi do testów."""
    # Tworzenie przykładowych embeddingów - wektory 3D
    return np.array([
        [0.1, 0.2, 0.3],  # id 0
        [0.4, 0.5, 0.6],  # id 1
        [0.7, 0.8, 0.9],  # id 2
        [0.2, 0.3, 0.4],  # id 3
        [0.5, 0.6, 0.7],  # id 4
    ], dtype=np.float32)


@pytest.fixture
def mock_db_session():
    """Mock sesji bazy danych."""
    db = MagicMock()
    return db


def test_find_nearest_image_positive():
    """Test znajdowania najbliższego obrazu pozytywnego."""
    # Przygotowanie danych testowych
    test_embeddings = np.array([
        [0.1, 0.2, 0.3],
        [0.4, 0.5, 0.6],
        [0.7, 0.8, 0.9],
    ], dtype=np.float32)
    
    # Tworzenie indeksu FAISS
    dim = test_embeddings.shape[1]
    index = faiss.IndexFlatL2(dim)
    index.add(test_embeddings)
    
    # Mockowanie globalnych zmiennych
    with patch('backend.embedding.faiss_index_pos', index), \
         patch('backend.embedding.image_ids_pos', [10, 20, 30]):
        
        # Test - szukamy najbliższego embeddingu do [0.15, 0.25, 0.35]
        # Powinien znaleźć pierwszy embedding [0.1, 0.2, 0.3] - indeks 0, id 10
        result = find_nearest_image([0.15, 0.25, 0.35], positive=True)
        assert result == 10
        
        # Test - szukamy najbliższego embeddingu do [0.6, 0.7, 0.8]
        # Powinien znaleźć trzeci embedding [0.7, 0.8, 0.9] - indeks 2, id 30
        result = find_nearest_image([0.6, 0.7, 0.8], positive=True)
        assert result == 30


def test_find_nearest_image_negative():
    """Test znajdowania najbliższego obrazu negatywnego."""
    # Przygotowanie danych testowych
    test_embeddings = np.array([
        [0.1, 0.2, 0.3],
        [0.4, 0.5, 0.6],
        [0.7, 0.8, 0.9],
    ], dtype=np.float32)
    
    # Tworzenie indeksu FAISS
    dim = test_embeddings.shape[1]
    index = faiss.IndexFlatL2(dim)
    index.add(test_embeddings)
    
    # Mockowanie globalnych zmiennych
    with patch('backend.embedding.faiss_index_neg', index), \
         patch('backend.embedding.image_ids_neg', [100, 200, 300]):
        
        # Test - szukamy najbliższego embeddingu do [0.15, 0.25, 0.35]
        # Powinien znaleźć pierwszy embedding [0.1, 0.2, 0.3] - indeks 0, id 100
        result = find_nearest_image([0.15, 0.25, 0.35], positive=False)
        assert result == 100


def test_find_nearest_image_with_exclude():
    """Test znajdowania najbliższego obrazu z wykluczeniem."""
    # Przygotowanie danych testowych
    test_embeddings = np.array([
        [0.1, 0.2, 0.3],
        [0.4, 0.5, 0.6],
        [0.7, 0.8, 0.9],
    ], dtype=np.float32)
    
    # Tworzenie indeksu FAISS
    dim = test_embeddings.shape[1]
    index = faiss.IndexFlatL2(dim)
    index.add(test_embeddings)
    
    # Mockowanie globalnych zmiennych
    with patch('backend.embedding.faiss_index_pos', index), \
         patch('backend.embedding.image_ids_pos', [10, 20, 30]):
        
        # Test - szukamy najbliższego embeddingu do [0.15, 0.25, 0.35] z wykluczeniem id 10
        # Powinien znaleźć drugi najbliższy [0.4, 0.5, 0.6] - indeks 1, id 20
        result = find_nearest_image([0.15, 0.25, 0.35], positive=True, exclude_ids=[10])
        assert result == 20


def test_find_nearest_image_no_index():
    """Test znajdowania najbliższego obrazu gdy indeks nie istnieje."""
    # Mockowanie globalnych zmiennych - brak indeksu
    with patch('backend.embedding.faiss_index_pos', None), \
         patch('backend.embedding.image_ids_pos', []):
        
        # Powinno zwrócić None
        result = find_nearest_image([0.1, 0.2, 0.3], positive=True)
        assert result is None


def test_build_faiss_index(mock_db_session, sample_embeddings):
    """Test budowania indeksu FAISS."""
    # Przygotowanie mockowanych obrazów
    pos_images = []
    neg_images = []
    
    for i in range(3):
        pos_img = MagicMock()
        pos_img.id = i + 1
        pos_img.embedding = sample_embeddings[i].tolist()
        pos_images.append(pos_img)
    
    for i in range(2):
        neg_img = MagicMock()
        neg_img.id = i + 100
        neg_img.embedding = sample_embeddings[i+3].tolist()
        neg_images.append(neg_img)
    
    # Mockowanie query
    mock_db_session.query.return_value.filter.return_value.all.side_effect = [
        pos_images,  # Pierwsze wywołanie - obrazy pozytywne
        neg_images   # Drugie wywołanie - obrazy negatywne
    ]
    
    # Mockowanie faiss.IndexFlatL2
    with patch('faiss.IndexFlatL2') as mock_index_flat:
        mock_index = MagicMock()
        mock_index_flat.return_value = mock_index
        
        # Mockowanie globalnych zmiennych
        with patch('backend.embedding.faiss_index_pos', None), \
             patch('backend.embedding.faiss_index_neg', None), \
             patch('backend.embedding.image_ids_pos', []), \
             patch('backend.embedding.image_ids_neg', []):
            
            # Wywołanie funkcji
            pos_count, neg_count = build_faiss_index(mock_db_session)
            
            # Sprawdzenie wyniku
            assert pos_count == 3
            assert neg_count == 2
            
            # Sprawdzenie czy indeks został utworzony poprawnie
            assert mock_index.add.call_count == 2  # Raz dla pos, raz dla neg 