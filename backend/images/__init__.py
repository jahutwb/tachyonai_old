"""Moduł do obsługi obrazów."""

def get_image_thumbnail(image_path):
    """
    Pobiera miniaturę obrazu.
    
    Args:
        image_path: Ścieżka do obrazu.
        
    Returns:
        Binarne dane miniatury obrazu.
    """
    # Ta implementacja jest mockiem - w rzeczywistej aplikacji odczytywałaby obrazek
    # z dysku i generowała miniaturę
    return b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDAT\x08\x99c\xf8\x0f\x00\x01\x01\x01\x00\x1b\x0c\x1b\x00\x00\x00\x00IEND\xaeB`\x82' 