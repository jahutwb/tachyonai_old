from backend.database import SessionLocal
from backend.models import Session as SessionModel, Round as RoundModel

def clear_tables():
    """Usuwa wszystkie dane z tabel sessions i rounds."""
    db = SessionLocal()
    try:
        # Usuń najpierw rekordy z rundy, ponieważ mają one zależności do sesji
        print("Usuwanie danych z tabeli rounds...")
        db.query(RoundModel).delete()
        
        # Następnie usuń rekordy z sesji
        print("Usuwanie danych z tabeli sessions...")
        db.query(SessionModel).delete()
        
        # Zatwierdź zmiany
        db.commit()
        print("Dane zostały usunięte pomyślnie!")
    except Exception as e:
        db.rollback()
        print(f"Wystąpił błąd podczas usuwania danych: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    clear_tables()
