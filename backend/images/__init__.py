"""Moduł do obsługi obrazów."""
import os
import logging
from PIL import Image
import io

logger = logging.getLogger(__name__)

def get_image_thumbnail(image_path):
    """
    Pobiera miniaturę obrazu.
    
    Args:
        image_path: Ścieżka do obrazu.
        
    Returns:
        Binarne dane miniatury obrazu.
    """
    try:
        if not os.path.exists(image_path):
            logger.warning(f"Plik nie istnieje: {image_path}")
            # Zwróć testowe dane PNG
            return b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDAT\x08\x99c\xf8\x0f\x00\x01\x01\x01\x00\x1b\x0c\x1b\x00\x00\x00\x00IEND\xaeB`\x82'
        
        # Otwórz obraz za pomocą PIL
        img = Image.open(image_path)
        
        # Stwórz miniaturę, zachowując proporcje
        max_size = (300, 300)
        img.thumbnail(max_size, Image.LANCZOS)
        
        # Zapisz obraz do bufora w formacie PNG
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        
        # Zwróć binarne dane obrazu
        return buffer.getvalue()
        
    except Exception as e:
        logger.error(f"Błąd podczas generowania miniatury dla {image_path}: {str(e)}")
        # Zwróć testowe dane PNG jako fallback
        return b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDAT\x08\x99c\xf8\x0f\x00\x01\x01\x01\x00\x1b\x0c\x1b\x00\x00\x00\x00IEND\xaeB`\x82'


def get_full_image(image_path):
    """
    Pobiera obraz w pełnej rozdzielczości.
    
    Args:
        image_path: Ścieżka do obrazu.
        
    Returns:
        Binarne dane obrazu w pełnej rozdzielczości.
    """
    try:
        if not os.path.exists(image_path):
            logger.warning(f"Plik nie istnieje: {image_path}")
            # Zwróć testowe dane PNG
            return b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDAT\x08\x99c\xf8\x0f\x00\x01\x01\x01\x00\x1b\x0c\x1b\x00\x00\x00\x00IEND\xaeB`\x82'
        
        # Otwórz obraz za pomocą PIL
        img = Image.open(image_path)
        
        # Konwertuj do bufora
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        
        # Zwróć binarne dane obrazu
        return buffer.getvalue()
        
    except Exception as e:
        logger.error(f"Błąd podczas ładowania obrazu dla {image_path}: {str(e)}")
        # Zwróć testowe dane PNG jako fallback
        return b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDAT\x08\x99c\xf8\x0f\x00\x01\x01\x01\x00\x1b\x0c\x1b\x00\x00\x00\x00IEND\xaeB`\x82'