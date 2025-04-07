"""
Moduł do obsługi ceny BTC - rzeczywistej (z Binance) lub symulowanej
"""
import os
import requests
import logging
from dotenv import load_dotenv
from .price_simulator import BtcPriceSimulator

# Załaduj zmienne środowiskowe
load_dotenv()

# Konfiguracja loggera
logger = logging.getLogger(__name__)

# Tryb ceny BTC (rzeczywisty lub symulowany)
REAL_BTC_PRICE = os.environ.get("REAL_BTC_PRICE", "false").lower() == "true"

class BtcPriceService:
    """
    Serwis do pobierania aktualnej ceny BTC.
    Może korzystać z rzeczywistej ceny z Binance lub symulowanej.
    """
    def __init__(self):
        logger.info(f"Inicjalizacja BtcPriceService. Tryb rzeczywisty: {REAL_BTC_PRICE}")
        self.simulator = BtcPriceSimulator()
        
    def get_current_price(self):
        """
        Pobiera aktualną cenę BTC.
        
        Returns:
            float: Aktualna cena BTC w USD
        """
        if REAL_BTC_PRICE:
            return self._get_binance_price()
        else:
            return self._get_simulated_price()
            
    def _get_binance_price(self):
        """
        Pobiera aktualną cenę BTC z API Binance.
        
        Returns:
            float: Aktualna cena BTC w USD
        """
        try:
            logger.debug("Pobieranie ceny BTC z API Binance")
            response = requests.get("https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT", timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                price = float(data["price"])
                logger.debug(f"Pobrano cenę BTC z Binance: {price} USD")
                return price
            else:
                logger.error(f"Błąd pobierania ceny BTC z Binance: {response.status_code} - {response.text}")
                # Fallback do symulatora
                logger.warning("Używanie symulowanej ceny jako fallback")
                return self._get_simulated_price()
        except Exception as e:
            logger.exception(f"Wyjątek podczas pobierania ceny BTC z Binance: {e}")
            # Fallback do symulatora
            logger.warning("Używanie symulowanej ceny jako fallback")
            return self._get_simulated_price()
            
    def _get_simulated_price(self):
        """
        Pobiera symulowaną cenę BTC.
        
        Returns:
            float: Symulowana cena BTC
        """
        price = self.simulator.get_current_price()
        logger.debug(f"Pobrano symulowaną cenę BTC: {price} USD")
        return price
        
    def wait_for_price_change(self, min_change_percent=0.0001):
        """
        Czeka na zmianę ceny BTC.
        
        Args:
            min_change_percent (float): Minimalny % zmiany ceny
            
        Returns:
            float: Nowa cena BTC po zmianie
        """
        if REAL_BTC_PRICE:
            # W trybie rzeczywistym czekamy na zmianę ceny z API Binance
            logger.info(f"Oczekiwanie na rzeczywistą zmianę ceny BTC (min {min_change_percent*100:.4f}%)")
            current_price = self._get_binance_price()
            
            # Maksymalnie 50 prób (około 2 minuty przy opóźnieniu 2.5s)
            for _ in range(50):
                try:
                    # Krótkie opóźnienie, aby nie przekroczyć limitu zapytań API
                    import time
                    time.sleep(2.5)
                    
                    new_price = self._get_binance_price()
                    change_percent = abs((new_price - current_price) / current_price)
                    
                    logger.debug(f"Sprawdzanie zmiany ceny: {current_price} -> {new_price} (zmiana: {change_percent*100:.4f}%)")
                    
                    if change_percent >= min_change_percent:
                        logger.info(f"Wykryto rzeczywistą zmianę ceny BTC: {current_price} -> {new_price} (zmiana: {change_percent*100:.4f}%)")
                        return new_price
                except Exception as e:
                    logger.error(f"Błąd podczas oczekiwania na zmianę ceny: {e}")
            
            logger.warning("Nie wykryto rzeczywistej zmiany ceny BTC, używanie symulatora")
            # Fallback do symulatora, jeśli nie wykryto zmiany w rzeczywistej cenie
            self.simulator.generate_price_change()
            return self.simulator.get_current_price()
        else:
            # W trybie symulacji używamy symulatora
            logger.info(f"Oczekiwanie na symulowaną zmianę ceny BTC (min {min_change_percent*100:.4f}%)")
            if self.simulator.wait_for_price_change(min_change_percent):
                return self.simulator.get_current_price()
            else:
                # Jeśli nie udało się wygenerować wystarczającej zmiany, wymuś zmianę
                logger.info("Wymuszenie symulowanej zmiany ceny")
                self.simulator.generate_price_change()
                return self.simulator.get_current_price()

# Singletonowa instancja serwisu
btc_price_service = BtcPriceService() 