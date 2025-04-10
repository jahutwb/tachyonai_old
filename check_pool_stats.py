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

def check_pool_stats():
    # Inicjalizacja bazy danych
    init_db()
    
    # Pobierz sesję bazy danych
    db = next(get_db())
    
    try:
        # Pobierz ostatnią sesję PENDING
        pending_session = db.query(SessionModel).filter(
            SessionModel.status == "PENDING"
        ).order_by(SessionModel.id.desc()).first()
        
        if not pending_session:
            logger.info("Brak sesji PENDING")
            return
        
        logger.info(f"Znaleziono sesję PENDING o ID: {pending_session.id}")
        
        # Pobierz pule obrazów
        pos_pool = pending_session.pos_pool_json
        neg_pool = pending_session.neg_pool_json
        
        # Zlicz statystyki dla puli pozytywnej
        pos_origins = {"bought": 0, "child": 0, "random": 0, "other": 0}
        for item in pos_pool:
            origin = item.get("origin", "random")
            if origin == "bought":
                pos_origins["bought"] += 1
            elif origin.startswith("child_of_"):
                pos_origins["child"] += 1
            elif origin.startswith("random_fallback_for_"):
                pos_origins["random"] += 1
            elif origin == "random":
                pos_origins["random"] += 1
            else:
                pos_origins["other"] += 1
        
        # Zlicz statystyki dla puli negatywnej
        neg_origins = {"bought": 0, "child": 0, "random": 0, "other": 0}
        for item in neg_pool:
            origin = item.get("origin", "random")
            if origin == "bought":
                neg_origins["bought"] += 1
            elif origin.startswith("child_of_"):
                neg_origins["child"] += 1
            elif origin.startswith("random_fallback_for_"):
                neg_origins["random"] += 1
            elif origin == "random":
                neg_origins["random"] += 1
            else:
                neg_origins["other"] += 1
        
        # Wyświetl statystyki
        logger.info("Statystyki dla puli pozytywnej:")
        logger.info(f"Kupione: {pos_origins['bought']}")
        logger.info(f"Dzieci: {pos_origins['child']}")
        logger.info(f"Losowe: {pos_origins['random']}")
        logger.info(f"Inne: {pos_origins['other']}")
        
        logger.info("Statystyki dla puli negatywnej:")
        logger.info(f"Kupione: {neg_origins['bought']}")
        logger.info(f"Dzieci: {neg_origins['child']}")
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
    check_pool_stats()
