from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import random
import logging

from ..database import get_db
from ..models import User
from ..auth import get_current_user

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/price/current")
def get_current_price(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Zwraca aktualną cenę BTC."""
    try:
        # Dla uproszczenia, generujemy losową cenę wokół 50000
        price = 50000.0 * (1 + random.uniform(-0.01, 0.01))
        logger.info(f"Zwracam aktualną cenę: {price}")
        return {"price": price}
    except Exception as e:
        logger.error(f"Błąd podczas pobierania ceny: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Błąd podczas pobierania ceny: {str(e)}") 