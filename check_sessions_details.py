import sys
import json
import logging
from sqlalchemy.orm import Session
from backend.models import Session as SessionModel
from backend.database import get_db
from backend.init_db import init_db

# Konfiguracja loggera
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

def check_sessions_details():
    # Inicjalizacja bazy danych
    init_db()
    
    # Pobierz sesję bazy danych
    db = next(get_db())
    
    try:
        # Pobierz sesję 8
        session_8 = db.query(SessionModel).filter(SessionModel.id == 8).first()
        
        if not session_8:
            logger.info("Brak sesji o ID 8")
        else:
            logger.info(f"Sesja 8:")
            logger.info(f"Status: {session_8.status}")
            logger.info(f"Profit factor: {session_8.session_profit_factor}")
            logger.info(f"Remaining pairs: {session_8.remaining_pairs}")
            
            # Pobierz pule obrazów
            pos_pool = session_8.pos_pool_json
            neg_pool = session_8.neg_pool_json
            
            # Zlicz sukcesy
            pos_successes = sum(item.get("successes", 0) for item in pos_pool)
            neg_successes = sum(item.get("successes", 0) for item in neg_pool)
            
            logger.info(f"Suma sukcesów w puli pozytywnej: {pos_successes}")
            logger.info(f"Suma sukcesów w puli negatywnej: {neg_successes}")
            
            # Wyświetl szczegóły obrazów z sukcesami w puli pozytywnej
            logger.info("Obrazy z sukcesami w puli pozytywnej:")
            for i, item in enumerate(pos_pool):
                if item.get("successes", 0) > 0:
                    logger.info(f"{i+1}. ID: {item.get('id')}, Origin: {item.get('origin')}, Successes: {item.get('successes', 0)}")
            
            # Wyświetl szczegóły obrazów z sukcesami w puli negatywnej
            logger.info("Obrazy z sukcesami w puli negatywnej:")
            for i, item in enumerate(neg_pool):
                if item.get("successes", 0) > 0:
                    logger.info(f"{i+1}. ID: {item.get('id')}, Origin: {item.get('origin')}, Successes: {item.get('successes', 0)}")
        
        # Pobierz sesję 9
        session_9 = db.query(SessionModel).filter(SessionModel.id == 9).first()
        
        if not session_9:
            logger.info("Brak sesji o ID 9")
        else:
            logger.info(f"\nSesja 9:")
            logger.info(f"Status: {session_9.status}")
            
            # Pobierz pule obrazów
            pos_pool = session_9.pos_pool_json
            neg_pool = session_9.neg_pool_json
            
            # Zlicz statystyki dla puli pozytywnej
            pos_origins = {"bought": 0, "child": 0, "random": 0, "random_fallback": 0, "other": 0}
            for item in pos_pool:
                origin = item.get("origin", "random")
                if origin == "bought":
                    pos_origins["bought"] += 1
                elif origin.startswith("child_of_"):
                    pos_origins["child"] += 1
                elif origin.startswith("random_fallback_for_"):
                    pos_origins["random_fallback"] += 1
                elif origin == "random":
                    pos_origins["random"] += 1
                else:
                    pos_origins["other"] += 1
            
            # Zlicz statystyki dla puli negatywnej
            neg_origins = {"bought": 0, "child": 0, "random": 0, "random_fallback": 0, "other": 0}
            for item in neg_pool:
                origin = item.get("origin", "random")
                if origin == "bought":
                    neg_origins["bought"] += 1
                elif origin.startswith("child_of_"):
                    neg_origins["child"] += 1
                elif origin.startswith("random_fallback_for_"):
                    neg_origins["random_fallback"] += 1
                elif origin == "random":
                    neg_origins["random"] += 1
                else:
                    neg_origins["other"] += 1
            
            # Wyświetl statystyki
            logger.info("Statystyki dla puli pozytywnej:")
            logger.info(f"Kupione: {pos_origins['bought']}")
            logger.info(f"Dzieci: {pos_origins['child']}")
            logger.info(f"Random fallback: {pos_origins['random_fallback']}")
            logger.info(f"Losowe: {pos_origins['random']}")
            logger.info(f"Inne: {pos_origins['other']}")
            
            logger.info("Statystyki dla puli negatywnej:")
            logger.info(f"Kupione: {neg_origins['bought']}")
            logger.info(f"Dzieci: {neg_origins['child']}")
            logger.info(f"Random fallback: {neg_origins['random_fallback']}")
            logger.info(f"Losowe: {neg_origins['random']}")
            logger.info(f"Inne: {neg_origins['other']}")
            
            # Wyświetl szczegóły obrazów w puli pozytywnej
            logger.info("Szczegóły obrazów w puli pozytywnej:")
            for i, item in enumerate(pos_pool):
                logger.info(f"{i+1}. ID: {item.get('id')}, Origin: {item.get('origin')}, Successes: {item.get('successes', 0)}")
            
            # Wyświetl szczegóły obrazów w puli negatywnej
            logger.info("Szczegóły obrazów w puli negatywnej:")
            for i, item in enumerate(neg_pool):
                logger.info(f"{i+1}. ID: {item.get('id')}, Origin: {item.get('origin')}, Successes: {item.get('successes', 0)}")
        
    except Exception as e:
        logger.error(f"Wystąpił błąd: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    check_sessions_details()
