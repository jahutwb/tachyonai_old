"""Moduł do obsługi sesji."""

def get_initial_pool():
    """Pobiera początkową pulę obrazów dla nowej sesji."""
    return {
        "pos_pool": [],
        "neg_pool": []
    } 