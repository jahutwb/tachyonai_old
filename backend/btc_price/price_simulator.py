"""
Moduł symulujący zmianę ceny BTC dla trybu symulacji
"""
import random
import time
import logging

logger = logging.getLogger(__name__)

class BtcPriceSimulator:
    """
    Symulator ceny BTC. Generuje losowe zmiany ceny dla trybu symulacji.
    """
    def __init__(self, start_price=50000.0, volatility=0.005):
        self.current_price = start_price
        self.volatility = volatility  # Zmienność (max % zmiany ceny na skok)
        logger.info(f"Inicjalizacja symulatora ceny BTC: cena początkowa={start_price}, zmienność={volatility}")

    def get_current_price(self):
        """
        Zwraca aktualną cenę BTC.
        """
        logger.debug(f"Pobieranie aktualnej ceny: {self.current_price}")
        return self.current_price

    def update_price(self):
        """
        Aktualizuje cenę BTC o losową zmianę.
        """
        # Generuj losową zmianę ceny
        change_percent = random.uniform(-self.volatility, self.volatility)
        old_price = self.current_price
        self.current_price = self.current_price * (1 + change_percent)
        
        logger.debug(f"Aktualizacja ceny: {old_price} -> {self.current_price} (zmiana: {change_percent*100:.4f}%)")
        return self.current_price

    def generate_price_change(self, direction=None, min_change=0.001, max_change=0.003):
        """
        Generuje zmianę ceny w określonym kierunku (jeśli podano).
        
        Args:
            direction (str, optional): 'up' lub 'down'. Jeśli None, losowy kierunek.
            min_change (float): Minimalna procentowa zmiana (default: 0.1%)
            max_change (float): Maksymalna procentowa zmiana (default: 0.3%)
            
        Returns:
            float: Aktualizowana cena BTC
        """
        if direction is None:
            direction = random.choice(['up', 'down'])
            
        logger.info(f"Generowanie zmiany ceny. Kierunek: {direction}, min={min_change}, max={max_change}")
            
        if direction == 'up':
            change_percent = random.uniform(min_change, max_change)
        else:  # 'down'
            change_percent = random.uniform(-max_change, -min_change)
            
        old_price = self.current_price
        self.current_price = self.current_price * (1 + change_percent)
        
        logger.info(f"Wygenerowana zmiana ceny: {old_price} -> {self.current_price} (zmiana: {change_percent*100:.4f}%)")
        return self.current_price
        
    def wait_for_price_change(self, min_change_percent=0.0001, max_attempts=10, sleep_time=0.5):
        """
        Czeka na zmianę ceny o określony procent. Zwraca True, gdy cena się zmieni.
        
        Args:
            min_change_percent (float): Minimalna procentowa zmiana dla uznania zmiany (default: 0.01%)
            max_attempts (int): Maksymalna liczba prób (default: 10)
            sleep_time (float): Czas oczekiwania między próbami w sekundach (default: 0.5)
            
        Returns:
            bool: True, jeśli cena się zmieniła o min_change_percent, False w przeciwnym przypadku
        """
        logger.info(f"Oczekiwanie na zmianę ceny (min {min_change_percent*100:.4f}%, max prób: {max_attempts}, czas oczekiwania: {sleep_time}s)")
        start_price = self.current_price
        
        for attempt in range(max_attempts):
            self.update_price()
            current_price = self.current_price
            
            percent_change = abs((current_price - start_price) / start_price)
            logger.debug(f"Próba {attempt+1}/{max_attempts}: zmiana {percent_change*100:.4f}% (wymagane: {min_change_percent*100:.4f}%)")
            
            if percent_change >= min_change_percent:
                logger.info(f"Wykryto zmianę ceny: {start_price} -> {current_price} (zmiana: {percent_change*100:.4f}%)")
                return True
                
            time.sleep(sleep_time)
            
        logger.warning(f"Nie wykryto wystarczającej zmiany ceny po {max_attempts} próbach")
        return False 