import pytest
from unittest.mock import patch, MagicMock, mock_open
import json
import os
from pathlib import Path

from backend import import_data


@pytest.fixture
def mock_db_session():
    """Mock sesji bazy danych do testów."""
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    return db


def test_load_metadata_from_freeones():
    """Test ładowania metadanych z pliku freeones."""
    mock_metadata = {
        "Gallery URL": "https://test.com",
        "Cast": ["Test Person"],
        "Categories": ["Test Category"],
        "Tags": ["Test Tag"],
        "Number of Photos": 5
    }
    
    # Przypadek 1: Plik metadanych istnieje i ma poprawną zawartość
    with patch("pathlib.Path.exists", return_value=True), \
         patch("builtins.open", mock_open(read_data=json.dumps(mock_metadata))):
        result = import_data.load_metadata_from_freeones(Path("/fake/path"))
        assert result == mock_metadata
    
    # Przypadek 2: Plik metadanych nie istnieje
    with patch("pathlib.Path.exists", return_value=False):
        result = import_data.load_metadata_from_freeones(Path("/fake/path"))
        assert result == {}
    
    # Przypadek 3: Plik metadanych ma niepoprawny format JSON
    with patch("pathlib.Path.exists", return_value=True), \
         patch("builtins.open", mock_open(read_data="{invalid json")), \
         patch("backend.import_data.logger.error") as mock_logger:
        result = import_data.load_metadata_from_freeones(Path("/fake/path"))
        assert result == {}
        mock_logger.assert_called_once()


def test_check_image_contains_person():
    """Test sprawdzania, czy obraz zawiera osobę."""
    # Dane testowe
    class_map = {
        "1": "Person",
        "2": "Dog",
        "3": "Human face",
        "4": "Car"
    }
    
    detections_map = {
        "img1": ["1"],  # Zawiera osobę
        "img2": ["2", "4"],  # Nie zawiera osoby
        "img3": ["3"],  # Zawiera twarz człowieka
        "img4": ["4", "1"]  # Zawiera osobę i samochód
    }
    
    # Przypadek 1: Obraz zawiera osobę
    assert import_data.check_image_contains_person("img1", detections_map, class_map) == True
    
    # Przypadek 2: Obraz nie zawiera osoby
    assert import_data.check_image_contains_person("img2", detections_map, class_map) == False
    
    # Przypadek 3: Obraz zawiera część ciała człowieka
    assert import_data.check_image_contains_person("img3", detections_map, class_map) == True
    
    # Przypadek 4: Obraz zawiera osobę i inny obiekt
    assert import_data.check_image_contains_person("img4", detections_map, class_map) == True
    
    # Przypadek 5: Obraz nie istnieje w mapie detekcji
    assert import_data.check_image_contains_person("img5", detections_map, class_map) == False


def test_get_image_metadata():
    """Test tworzenia metadanych dla obrazu."""
    # Dane testowe
    class_map = {
        "1": "Person",
        "2": "Dog",
        "3": "Human face",
        "4": "Car"
    }
    
    detections_map = {
        "img1": ["2", "4"]  # Pies i samochód
    }
    
    classifications_map = {
        "img1": ["2", "4"]  # Pies i samochód
    }
    
    # Przypadek 1: Obraz z detekcjami i klasyfikacjami
    metadata = import_data.get_image_metadata("img1", class_map, detections_map, classifications_map)
    assert "Categories" in metadata
    assert "Tags" in metadata
    assert "Dog" in metadata["Categories"]
    assert "Car" in metadata["Categories"]
    assert "Dog" in metadata["Tags"]
    assert "Car" in metadata["Tags"]
    
    # Przypadek 2: Obraz bez detekcji i klasyfikacji
    metadata = import_data.get_image_metadata("img2", class_map, detections_map, classifications_map)
    assert "Categories" in metadata
    assert "Tags" in metadata
    assert len(metadata["Categories"]) == 0
    assert len(metadata["Tags"]) == 0


def test_map_filename_to_image_id():
    """Test mapowania nazwy pliku na ID obrazu."""
    # Dane testowe
    image_ids_map = {
        "test1": "id1",
        "test2": "id2",
        "test_image3": "id3"
    }
    
    # Przypadek 1: Dokładne dopasowanie
    assert import_data.map_filename_to_image_id("test1.jpg", image_ids_map) == "id1"
    
    # Przypadek 2: Brak dopasowania
    assert import_data.map_filename_to_image_id("nonexistent.jpg", image_ids_map) is None
    
    # Przypadek 3: Częściowe dopasowanie
    assert import_data.map_filename_to_image_id("test_image3_part.jpg", image_ids_map) == "id3"


@patch("backend.import_data.load_metadata_from_freeones")
@patch("pathlib.Path.exists")
@patch("pathlib.Path.iterdir")
@patch("pathlib.Path.glob")
def test_process_pos_images(mock_glob, mock_iterdir, mock_exists, mock_load_metadata, mock_db_session):
    """Test przetwarzania obrazów pozytywnych."""
    # Konfiguracja mocków
    mock_exists.return_value = True
    
    # Mock dla katalogu freeones
    mock_gallery_dir = MagicMock()
    mock_gallery_dir.is_dir.return_value = True
    mock_iterdir.return_value = [mock_gallery_dir]
    
    # Mock dla plików obrazów
    mock_img_file1 = MagicMock()
    mock_img_file1.__str__.return_value = "/fake/path/img1.jpg"
    mock_img_file2 = MagicMock()
    mock_img_file2.__str__.return_value = "/fake/path/img2.jpg"
    mock_glob.return_value = [mock_img_file1, mock_img_file2]
    
    # Mock dla metadanych
    mock_metadata = {"Tags": ["test"]}
    mock_load_metadata.return_value = mock_metadata
    
    # Wywołanie funkcji
    result = import_data.process_pos_images(mock_db_session)
    
    # Sprawdzenie, czy obrazy zostały dodane do bazy
    assert mock_db_session.add.call_count >= 2
    assert mock_db_session.commit.call_count >= 1
    assert result >= 2


@patch("backend.import_data.load_open_images_classes")
@patch("backend.import_data.load_open_images_detections")
@patch("backend.import_data.load_open_images_classifications")
@patch("backend.import_data.load_image_ids_map")
@patch("backend.import_data.map_filename_to_image_id")
@patch("backend.import_data.check_image_contains_person")
@patch("backend.import_data.get_image_metadata")
@patch("pathlib.Path.exists")
@patch("pathlib.Path.glob")
def test_process_neg_images(
    mock_glob, mock_exists, mock_get_metadata, mock_check_person,
    mock_map_id, mock_load_ids, mock_load_class, mock_load_detect, mock_load_classes,
    mock_db_session
):
    """Test przetwarzania obrazów negatywnych."""
    # Konfiguracja mocków
    mock_exists.return_value = True
    
    # Mock dla plików obrazów
    mock_img_file1 = MagicMock()
    mock_img_file1.__str__.return_value = "/fake/path/img1.jpg"
    mock_img_file2 = MagicMock()
    mock_img_file2.__str__.return_value = "/fake/path/img2.jpg"
    mock_glob.return_value = [mock_img_file1, mock_img_file2]
    
    # Mock dla mapowania ID
    mock_map_id.return_value = "test_id"
    
    # Mock dla sprawdzania osób
    mock_check_person.return_value = False  # Brak osób na obrazach
    
    # Mock dla metadanych
    mock_get_metadata.return_value = {"Categories": [], "Tags": []}
    
    # Pomocnicze słowniki
    mock_load_classes.return_value = {}
    mock_load_detect.return_value = {}
    mock_load_class.return_value = {}
    mock_load_ids.return_value = {}
    
    # Wywołanie funkcji
    result = import_data.process_neg_images(mock_db_session)
    
    # Sprawdzenie, czy obrazy zostały dodane do bazy
    assert mock_db_session.add.call_count >= 2
    assert mock_db_session.commit.call_count >= 1
    assert result >= 2 