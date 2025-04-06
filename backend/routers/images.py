from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.orm import Session
from typing import List, Optional
import random

from ..database import get_db
from ..models import User, Image, ImageTypeEnum
from .. import schemas
from ..auth import get_current_user

router = APIRouter()


@router.get("/images/{image_id}", response_model=schemas.Image)
def get_image(
    image_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Pobiera informacje o obrazie o podanym ID."""
    image = db.query(Image).filter(Image.id == image_id).first()
    if not image:
        raise HTTPException(status_code=404, detail="Obraz nie znaleziony")
    return image


@router.get("/images/{image_id}/thumbnail")
def get_image_thumbnail(
    image_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Pobiera miniaturę obrazu o podanym ID."""
    image = db.query(Image).filter(Image.id == image_id).first()
    if not image:
        raise HTTPException(status_code=404, detail="Obraz nie znaleziony")
    
    # Uproszczona implementacja - w rzeczywistej aplikacji odczytywałaby obrazek z dysku i generowała miniaturę
    # Zwracamy testowe dane PNG
    test_png_data = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDAT\x08\x99c\xf8\x0f\x00\x01\x01\x01\x00\x1b\x0c\x1b\x00\x00\x00\x00IEND\xaeB`\x82'
    
    return Response(content=test_png_data, media_type="image/png")


@router.get("/images/random", response_model=List[schemas.Image])
def get_random_images(
    type: Optional[str] = None,
    count: int = 10,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Pobiera losowe obrazy określonego typu."""
    query = db.query(Image)
    
    if type:
        try:
            image_type = ImageTypeEnum(type)
            query = query.filter(Image.type == image_type)
        except ValueError:
            raise HTTPException(status_code=400, detail="Nieprawidłowy typ obrazu")
    
    images = query.limit(100).all()
    
    if not images:
        return []
    
    # Wybierz losowo 'count' obrazów
    selected_images = random.sample(images, min(count, len(images)))
    return selected_images


@router.get("/images/ranking", response_model=List[schemas.Image])
def get_images_ranking(
    type: Optional[str] = None,
    limit: int = 10,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Pobiera ranking obrazów według liczby sukcesów."""
    query = db.query(Image)
    
    if type:
        try:
            image_type = ImageTypeEnum(type)
            query = query.filter(Image.type == image_type)
        except ValueError:
            raise HTTPException(status_code=400, detail="Nieprawidłowy typ obrazu")
    
    # Sortuj według liczby sukcesów (malejąco)
    images = query.order_by(Image.total_successes.desc()).limit(limit).all()
    return images


@router.get("/images/{image_id}/embedding", response_model=schemas.ImageEmbedding)
def get_image_embedding(
    image_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Pobiera embedding obrazu o podanym ID."""
    image = db.query(Image).filter(Image.id == image_id).first()
    if not image:
        raise HTTPException(status_code=404, detail="Obraz nie znaleziony")
    
    if not image.embedding:
        raise HTTPException(status_code=404, detail="Brak embeddingu dla tego obrazu")
    
    return {"id": image.id, "embedding": image.embedding}


@router.get("/images/{image_id}/nearest", response_model=List[schemas.NearestImage])
def get_nearest_images(
    image_id: int,
    count: int = 10,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Pobiera obrazy najbliższe do obrazu o podanym ID w przestrzeni embeddingów."""
    image = db.query(Image).filter(Image.id == image_id).first()
    if not image:
        raise HTTPException(status_code=404, detail="Obraz nie znaleziony")
    
    if not image.embedding:
        raise HTTPException(status_code=404, detail="Brak embeddingu dla tego obrazu")
    
    # Uproszczona implementacja - w rzeczywistej aplikacji obliczałaby odległości między embeddingami
    # Zwracamy testowe dane
    nearest_images = []
    for i in range(count):
        nearest_images.append({
            "id": i + 1,
            "distance": 0.1 * (i + 1)
        })
    
    return nearest_images 