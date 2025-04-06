"""Moduł do obsługi cen Bitcoin."""

def wait_for_price_change(start_price, action):
    """Symuluje oczekiwanie na zmianę ceny i zwraca nową cenę oraz frakcyjną zmianę."""
    import random
    
    # Symulujemy zmianę ceny
    price_change = random.uniform(-0.01, 0.01)  # +/- 1%
    end_price = start_price * (1 + price_change)
    
    return end_price, price_change 