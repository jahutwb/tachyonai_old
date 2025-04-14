import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.main import app
from backend.database import get_db
from backend.models import User, Image, ImageTypeEnum


@pytest.fixture
def test_user_in_db(test_db: Session):
    """Fixture zwracający testowego użytkownika."""
    # Użytkownik został już utworzony w fixture test_db
    user = test_db.query(User).filter(User.username == "test_user").first()
    return user


@pytest.fixture
def test_images(test_db: Session):
    """Fixture zwracający testowe obrazy."""
    # Obrazy zostały już utworzone w fixture test_db
    pos_images = test_db.query(Image).filter(Image.type == ImageTypeEnum.POSITIVE).all()
    neg_images = test_db.query(Image).filter(Image.type == ImageTypeEnum.NEGATIVE).all()
    return {"positive": pos_images, "negative": neg_images}


@pytest.fixture
def test_token(test_client, test_user):
    """Fixture zwracający token testowego użytkownika."""
    response = test_client.post(
        "/token",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "username": test_user.username,
            "password": "test_password"
        }
    )
    assert response.status_code == 200
    token_data = response.json()
    return token_data["access_token"]


@pytest.fixture
def authorized_client(test_client, test_token):
    """Fixture zwracający autoryzowanego klienta testowego."""
    test_client.headers = {"Authorization": f"Bearer {test_token}"}
    return test_client


def test_get_image(authorized_client, test_images, monkeypatch):
    """Test pobierania obrazu w pełnej rozdzielczości."""
    test_image = test_images["positive"][0]

    # Musimy zamockować funkcję, która mogłaby odczytywać prawdziwy obraz z dysku
    def mock_open(*args, **kwargs):
        from io import BytesIO
        from PIL import Image

        # Tworzymy mały obrazek testowy 1x1
        im = Image.new('RGB', (1, 1))
        buffer = BytesIO()
        im.save(buffer, format="PNG")
        buffer.seek(0)
        return buffer.getvalue()

    # Podmieniamy funkcje używane do odczytu obrazów
    import os
    monkeypatch.setattr(os.path, "exists", lambda x: True)
    monkeypatch.setattr("PIL.Image.open", lambda x: Image.new('RGB', (1, 1)))

    response = authorized_client.get(f"/api/images/{test_image.id}")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    # Testujemy, że odpowiedź to dane binarne PNG
    assert response.content.startswith(b'\x89PNG')


def test_get_image_with_token(test_client, test_images, test_token, monkeypatch):
    """Test pobierania obrazu przy użyciu tokena zamiast pełnej autoryzacji."""
    test_image = test_images["positive"][0]

    # Musimy zamockować funkcję, która mogłaby odczytywać prawdziwy obraz z dysku
    def mock_open(*args, **kwargs):
        from io import BytesIO
        from PIL import Image

        # Tworzymy mały obrazek testowy 1x1
        im = Image.new('RGB', (1, 1))
        buffer = BytesIO()
        im.save(buffer, format="PNG")
        buffer.seek(0)
        return buffer.getvalue()

    # Podmieniamy funkcje używane do odczytu obrazów
    import os
    monkeypatch.setattr(os.path, "exists", lambda x: True)
    monkeypatch.setattr("PIL.Image.open", lambda x: Image.new('RGB', (1, 1)))

    # Używamy URL z tokenem
    response = test_client.get(f"/api/images/{test_image.id}?token={test_token}")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    # Testujemy, że odpowiedź to dane binarne PNG
    assert response.content.startswith(b'\x89PNG')


def test_get_image_thumbnail(authorized_client, test_images, monkeypatch):
    """Test pobierania miniatury obrazu."""
    test_image = test_images["positive"][0]

    # Musimy zamockować funkcję, która ładuje obraz z dysku
    def mock_get_image_thumbnail(*args, **kwargs):
        # Zwracamy binarną reprezentację małego obrazka
        return b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDAT\x08\x99c\xf8\x0f\x00\x01\x01\x01\x00\x1b\x0c\x1b\x00\x00\x00\x00IEND\xaeB`\x82'

    import backend.images
    monkeypatch.setattr(backend.images, "get_image_thumbnail", mock_get_image_thumbnail)

    response = authorized_client.get(f"/api/images/{test_image.id}/thumbnail")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"


def test_get_random_images(authorized_client, test_images):
    """Test pobierania losowych obrazów."""
    response = authorized_client.get("/api/images/random?type=POSITIVE&count=2")
    assert response.status_code == 200

    images_data = response.json()
    assert len(images_data) == 2
    assert all(img["type"] == "POSITIVE" for img in images_data)

    response = authorized_client.get("/api/images/random?type=NEGATIVE&count=2")
    assert response.status_code == 200

    images_data = response.json()
    assert len(images_data) == 2
    assert all(img["type"] == "NEGATIVE" for img in images_data)


def test_get_images_ranking(authorized_client, test_images):
    """Test pobierania rankingu obrazów."""
    response = authorized_client.get("/api/images/ranking?type=POSITIVE&limit=3")
    assert response.status_code == 200

    ranking_data = response.json()
    assert len(ranking_data) == 3

    # Sprawdź, czy ranking jest posortowany według total_successes (malejąco)
    assert ranking_data[0]["total_successes"] >= ranking_data[1]["total_successes"]
    assert ranking_data[1]["total_successes"] >= ranking_data[2]["total_successes"]

    # Sprawdź ranking dla obrazów negatywnych
    response = authorized_client.get("/api/images/ranking?type=NEGATIVE&limit=3")
    assert response.status_code == 200

    ranking_data = response.json()
    assert len(ranking_data) == 3
    assert all(img["type"] == "NEGATIVE" for img in ranking_data)


def test_get_images_with_embedding(authorized_client, test_images):
    """Test pobierania obrazów z embeddingami."""
    test_image = test_images["positive"][0]

    response = authorized_client.get(f"/api/images/{test_image.id}/embedding")
    assert response.status_code == 200

    embedding_data = response.json()
    assert "embedding" in embedding_data
    assert isinstance(embedding_data["embedding"], list)
    # The embedding length can vary, so we just check that it's a non-empty list
    assert len(embedding_data["embedding"]) > 0


def test_get_nearest_images(authorized_client, test_images, monkeypatch):
    """Test pobierania najbliższych obrazów w przestrzeni embeddingów."""
    test_image = test_images["positive"][0]

    # Musimy zamockować funkcję, która zwraca najbliższe obrazy
    def mock_find_nearest_images(*args, **kwargs):
        return [
            {"id": test_images["positive"][1].id, "distance": 0.1},
            {"id": test_images["positive"][2].id, "distance": 0.2},
            {"id": test_images["positive"][3].id, "distance": 0.3}
        ]

    import backend.embedding
    monkeypatch.setattr(backend.embedding, "find_nearest_images", mock_find_nearest_images)

    response = authorized_client.get(f"/api/images/{test_image.id}/nearest?count=3")
    assert response.status_code == 200

    nearest_data = response.json()
    assert len(nearest_data) == 3
    assert "id" in nearest_data[0]
    assert "distance" in nearest_data[0]
    assert nearest_data[0]["distance"] <= nearest_data[1]["distance"]  # Sprawdź sortowanie


def test_get_image_full_resolution(authorized_client, test_images, monkeypatch):
    """Test pobierania obrazu w pełnej rozdzielczości."""
    test_image = test_images["positive"][0]

    # Musimy zamockować funkcję, która ładuje obraz z dysku
    def mock_get_full_image(*args, **kwargs):
        # Zwracamy binarną reprezentację małego obrazka
        return b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDAT\x08\x99c\xf8\x0f\x00\x01\x01\x01\x00\x1b\x0c\x1b\x00\x00\x00\x00IEND\xaeB`\x82'

    import backend.images
    monkeypatch.setattr(backend.images, "get_full_image", mock_get_full_image)

    response = authorized_client.get(f"/api/images/{test_image.id}/full")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    # Sprawdzamy, czy dane zawierają sygnaturę PNG
    assert response.content.startswith(b'\x89PNG')