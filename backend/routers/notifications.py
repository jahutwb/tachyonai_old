"""
Notifications router module for TachyonAI.
This module provides endpoints for managing user notifications.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
import logging
from datetime import datetime

from ..database import get_db
from ..models import User, Notification, NotificationTypeEnum
from .. import schemas
from ..auth import get_current_user

# Initialize router and logger
router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/notifications", response_model=List[schemas.Notification])
async def get_notifications(
    unread_only: bool = Query(False, description="Get only unread notifications"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get notifications for the current user.

    Args:
        unread_only: If True, return only unread notifications
        current_user: Current authenticated user
        db: Database session

    Returns:
        List of notifications for the current user
    """
    logger.info(f"Getting notifications for user {current_user.username}")
    
    # Build the query
    query = db.query(Notification).filter(Notification.user_id == current_user.id)
    
    # Filter by read status if requested
    if unread_only:
        query = query.filter(Notification.read == 0)
    
    # Order by creation date (newest first)
    query = query.order_by(Notification.created_at.desc())
    
    # Execute the query
    notifications = query.all()
    
    # Convert to schema
    result = []
    for notification in notifications:
        result.append(schemas.Notification(
            type=notification.type,
            message=notification.message,
            title=notification.title,
            timestamp=notification.created_at,
            read=notification.read == 1,
            data=notification.data
        ))
    
    return result


@router.post("/notifications/mark-read/{notification_id}", response_model=schemas.Message)
async def mark_notification_read(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Mark a notification as read.

    Args:
        notification_id: ID of the notification to mark as read
        current_user: Current authenticated user
        db: Database session

    Returns:
        Success message

    Raises:
        HTTPException: If the notification doesn't exist or doesn't belong to the user
    """
    logger.info(f"Marking notification {notification_id} as read for user {current_user.username}")
    
    # Get the notification
    notification = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.user_id == current_user.id
    ).first()
    
    # Check if the notification exists
    if not notification:
        logger.warning(f"Notification {notification_id} not found or doesn't belong to user {current_user.username}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found or access denied"
        )
    
    # Mark as read
    notification.read = 1
    notification.updated_at = datetime.now()
    
    # Commit changes
    db.commit()
    
    return {"message": "Notification marked as read"}


@router.post("/notifications/mark-all-read", response_model=schemas.Message)
async def mark_all_notifications_read(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Mark all notifications as read for the current user.

    Args:
        current_user: Current authenticated user
        db: Database session

    Returns:
        Success message
    """
    logger.info(f"Marking all notifications as read for user {current_user.username}")
    
    # Update all unread notifications
    db.query(Notification).filter(
        Notification.user_id == current_user.id,
        Notification.read == 0
    ).update({
        "read": 1,
        "updated_at": datetime.now()
    })
    
    # Commit changes
    db.commit()
    
    return {"message": "All notifications marked as read"}


@router.delete("/notifications/{notification_id}", response_model=schemas.Message)
async def delete_notification(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Delete a notification.

    Args:
        notification_id: ID of the notification to delete
        current_user: Current authenticated user
        db: Database session

    Returns:
        Success message

    Raises:
        HTTPException: If the notification doesn't exist or doesn't belong to the user
    """
    logger.info(f"Deleting notification {notification_id} for user {current_user.username}")
    
    # Get the notification
    notification = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.user_id == current_user.id
    ).first()
    
    # Check if the notification exists
    if not notification:
        logger.warning(f"Notification {notification_id} not found or doesn't belong to user {current_user.username}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found or access denied"
        )
    
    # Delete the notification
    db.delete(notification)
    
    # Commit changes
    db.commit()
    
    return {"message": "Notification deleted"}


@router.delete("/notifications", response_model=schemas.Message)
async def delete_all_notifications(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Delete all notifications for the current user.

    Args:
        current_user: Current authenticated user
        db: Database session

    Returns:
        Success message
    """
    logger.info(f"Deleting all notifications for user {current_user.username}")
    
    # Delete all notifications for the user
    db.query(Notification).filter(
        Notification.user_id == current_user.id
    ).delete()
    
    # Commit changes
    db.commit()
    
    return {"message": "All notifications deleted"}


# Helper function to create a notification
def create_notification(
    db: Session,
    user_id: int,
    type: NotificationTypeEnum,
    message: str,
    title: Optional[str] = None,
    data: Optional[Dict[str, Any]] = None,
):
    """
    Create a new notification for a user.

    Args:
        db: Database session
        user_id: ID of the user to create the notification for
        type: Notification type (INFO, WARNING, ERROR, SUCCESS)
        message: Notification message text
        title: Optional notification title
        data: Optional additional data for the notification

    Returns:
        Created notification
    """
    logger.info(f"Creating {type} notification for user {user_id}")
    
    # Create the notification
    notification = Notification(
        user_id=user_id,
        type=type,
        message=message,
        title=title,
        data=data,
        read=0,
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    
    # Add to database
    db.add(notification)
    db.commit()
    db.refresh(notification)
    
    return notification
