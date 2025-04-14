"""
Integration tests for the notifications API.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from backend.main import app
from backend.models import User, Notification, NotificationTypeEnum
from backend.auth import create_access_token
from backend.database import get_db
from tests.conftest import create_test_user, get_test_user_token, get_authorized_client


@pytest.fixture
def test_user_in_db(test_db: Session):
    """Fixture creating a test user in the database."""
    return create_test_user(test_db)


@pytest.fixture
def test_token(test_user_in_db):
    """Fixture returning a token for the test user."""
    return get_test_user_token(test_user_in_db)


@pytest.fixture
def authorized_client(test_token):
    """Client with authorization header set."""
    return get_authorized_client(test_token)


@pytest.fixture
def test_notifications(test_db: Session, test_user_in_db):
    """Create test notifications."""
    # Delete existing notifications for the test user
    test_db.query(Notification).filter(Notification.user_id == test_user_in_db.id).delete()

    # Create test notifications
    notifications = [
        Notification(
            user_id=test_user_in_db.id,
            type=NotificationTypeEnum.INFO,
            title="Info Notification",
            message="This is an info notification",
            read=0
        ),
        Notification(
            user_id=test_user_in_db.id,
            type=NotificationTypeEnum.WARNING,
            title="Warning Notification",
            message="This is a warning notification",
            read=0
        ),
        Notification(
            user_id=test_user_in_db.id,
            type=NotificationTypeEnum.ERROR,
            title="Error Notification",
            message="This is an error notification",
            read=1
        ),
        Notification(
            user_id=test_user_in_db.id,
            type=NotificationTypeEnum.SUCCESS,
            title="Success Notification",
            message="This is a success notification",
            read=0
        )
    ]

    for notification in notifications:
        test_db.add(notification)

    test_db.commit()

    for notification in notifications:
        test_db.refresh(notification)

    return notifications


def test_get_notifications(authorized_client, test_notifications):
    """Test getting notifications."""
    response = authorized_client.get("/api/notifications")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 4

    # Check that all notification types are present without assuming order
    notification_types = [notification["type"] for notification in data]
    assert "SUCCESS" in notification_types
    assert "ERROR" in notification_types
    assert "WARNING" in notification_types
    assert "INFO" in notification_types


def test_get_unread_notifications(authorized_client, test_notifications):
    """Test getting unread notifications."""
    response = authorized_client.get("/api/notifications?unread_only=true")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3
    for notification in data:
        assert notification["read"] is False


def test_mark_notification_read(authorized_client, test_notifications, test_db):
    """Test marking a notification as read."""
    # Get an unread notification
    unread_notification = next(n for n in test_notifications if n.read == 0)

    response = authorized_client.post(f"/api/notifications/mark-read/{unread_notification.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Notification marked as read"

    # Verify the notification is marked as read in the database
    test_db.refresh(unread_notification)
    assert unread_notification.read == 1


def test_mark_all_notifications_read(authorized_client, test_notifications, test_db):
    """Test marking all notifications as read."""
    response = authorized_client.post("/api/notifications/mark-all-read")
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "All notifications marked as read"

    # Verify all notifications are marked as read in the database
    for notification in test_notifications:
        test_db.refresh(notification)
        assert notification.read == 1


def test_delete_notification(authorized_client, test_notifications, test_db):
    """Test deleting a notification."""
    notification_to_delete = test_notifications[0]

    response = authorized_client.delete(f"/api/notifications/{notification_to_delete.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Notification deleted"

    # Verify the notification is deleted from the database
    deleted_notification = test_db.query(Notification).filter(Notification.id == notification_to_delete.id).first()
    assert deleted_notification is None


def test_delete_all_notifications(authorized_client, test_notifications, test_db):
    """Test deleting all notifications."""
    response = authorized_client.delete("/api/notifications")
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "All notifications deleted"

    # Verify all notifications are deleted from the database
    user_notifications = test_db.query(Notification).filter(Notification.user_id == test_notifications[0].user_id).all()
    assert len(user_notifications) == 0
