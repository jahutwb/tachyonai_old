import logging
from sqlalchemy.orm import Session
from .database import engine, Base, SessionLocal
from . import models

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def init_db() -> None:
    """
    Inicjalizuje bazę danych.
    Tworzy wszystkie tabele zdefiniowane w modelach.
    """
    logger.info("Inicjalizacja bazy danych...")
    Base.metadata.create_all(bind=engine)
    logger.info("Baza danych zainicjalizowana pomyślnie!")


def create_admin_user(db: Session, username: str, password: str) -> None:
    """
    Tworzy administratora w bazie danych, jeśli nie istnieje.
    """
    from .auth import get_password_hash

    admin = db.query(models.User).filter(models.User.username == username).first()
    if not admin:
        hashed_password = get_password_hash(password)
        admin = models.User(
            username=username,
            password_hash=hashed_password,
            role=models.UserRoleEnum.ADMIN
        )
        db.add(admin)
        db.commit()
        logger.info(f"Administrator '{username}' został utworzony.")
    else:
        logger.info(f"Administrator '{username}' już istnieje.")


if __name__ == "__main__":
    init_db()
    # Tworzenie administratora (opcjonalne)
    # with SessionLocal() as db:
    #     create_admin_user(db, "admin", "changeme") 