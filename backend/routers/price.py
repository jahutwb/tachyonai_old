"""
Price router module for TachyonAI.
This module provides endpoints for retrieving BTC price information.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import random
import logging
from typing import Dict

from ..database import get_db
from ..models import User
from ..auth import get_current_user

# Initialize router and logger
router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/price/current", response_model=Dict[str, float])
async def get_current_price(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get current BTC price.

    For simplicity, this endpoint generates a random price around 50000.
    In a production environment, this would connect to a real price API.

    Args:
        current_user: Current authenticated user
        db: Database session

    Returns:
        Dictionary containing the current price

    Raises:
        HTTPException: If there's an error retrieving the price
    """
    try:
        # For simplicity, generate a random price around 50000
        price = 50000.0 * (1 + random.uniform(-0.01, 0.01))
        logger.info(f"Returning current price: {price}")
        return {"price": price}
    except Exception as e:
        logger.error(f"Error retrieving price: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving price: {str(e)}"
        )