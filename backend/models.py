"""
Database models for TachyonAI.

This module defines the SQLAlchemy ORM models used throughout the application.
These models represent the database schema and provide methods for interacting with the data.
"""
from sqlalchemy import Column, Integer, String, Float, ForeignKey, Enum, DateTime, JSON, Text
from sqlalchemy.ext.mutable import MutableList
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from enum import Enum as PyEnum
from datetime import datetime
from typing import List as TypeList, Optional, Dict, Any

from .database import Base


class UserRoleEnum(PyEnum):
    """
    Enum for user roles.

    Attributes:
        USER: Regular user role
        ADMIN: Administrator role with elevated privileges
    """
    USER = "USER"
    ADMIN = "ADMIN"


class SessionStatusEnum(PyEnum):
    """
    Enum for session status.

    Attributes:
        ACTIVE: Session is currently active
        COMPLETED: Session has been completed
        ABANDONED: Session was abandoned before completion
        PENDING: Session is pending activation
    """
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    ABANDONED = "ABANDONED"
    PENDING = "PENDING"


class RoundResultEnum(PyEnum):
    """
    Enum for round result.

    Attributes:
        SUCCESS: Round was successful
        FAILURE: Round was a failure
    """
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"


class SideEnum(PyEnum):
    """
    Enum for side selection.

    Attributes:
        LEFT: Left side selected
        RIGHT: Right side selected
    """
    LEFT = "LEFT"
    RIGHT = "RIGHT"


class ActionEnum(PyEnum):
    """
    Enum for trading actions.

    Attributes:
        BUY: Buy action
        SELL: Sell action
    """
    BUY = "BUY"
    SELL = "SELL"


class ImageTypeEnum(str, PyEnum):
    """
    Enum for image types.

    Attributes:
        POSITIVE: Positive stimulus image
        NEGATIVE: Negative stimulus image
    """
    POSITIVE = "POSITIVE"
    NEGATIVE = "NEGATIVE"


class NotificationTypeEnum(str, PyEnum):
    """
    Enum for notification types.

    Attributes:
        INFO: Informational notification
        WARNING: Warning notification
        ERROR: Error notification
        SUCCESS: Success notification
    """
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    SUCCESS = "SUCCESS"


class User(Base):
    """
    User model representing application users.

    Attributes:
        id: Unique identifier
        username: Unique username
        password_hash: Hashed password for authentication
        role: User role (USER or ADMIN)
        created_at: Timestamp when the user was created
        updated_at: Timestamp when the user was last updated
        sessions: Relationship to user's sessions
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    password_hash = Column(String)
    role = Column(Enum(UserRoleEnum), default=UserRoleEnum.USER)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    sessions = relationship("Session", back_populates="user")
    notifications = relationship("Notification", back_populates="user")


class Image(Base):
    """
    Image model representing stimulus images.

    Attributes:
        id: Unique identifier
        path: Path to the image file
        type: Image type (POSITIVE or NEGATIVE)
        embedding: Vector embedding of the image for similarity calculations
        img_metadata: Additional metadata for the image
        total_successes: Total number of successful rounds with this image
        total_failures: Total number of failed rounds with this image
        total_profit_factor: Cumulative profit factor for this image
        created_at: Timestamp when the image was created
        updated_at: Timestamp when the image was last updated
        parent_id: ID of the parent image (for child images)
        parent: Relationship to the parent image
        children: Relationship to child images
        pos_rounds: Relationship to rounds where this image is the positive stimulus
        neg_rounds: Relationship to rounds where this image is the negative stimulus
    """
    __tablename__ = "images"

    id = Column(Integer, primary_key=True, index=True)
    path = Column(String, unique=True, index=True)
    type = Column(Enum(ImageTypeEnum), index=True)
    embedding = Column(MutableList.as_mutable(JSON), nullable=True)
    img_metadata = Column(JSON, nullable=True)
    total_successes = Column(Integer, default=0)
    total_failures = Column(Integer, default=0)
    total_profit_factor = Column(Float, default=1.0)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    parent_id = Column(Integer, ForeignKey("images.id"), nullable=True)

    parent = relationship("Image", remote_side=[id], backref="children")
    pos_rounds = relationship("Round", foreign_keys="Round.pos_image_id", back_populates="pos_image")
    neg_rounds = relationship("Round", foreign_keys="Round.neg_image_id", back_populates="neg_image")


class Session(Base):
    """
    Session model representing user trading sessions.

    Attributes:
        id: Unique identifier
        user_id: ID of the user who owns this session
        status: Session status (ACTIVE, COMPLETED, ABANDONED, PENDING)
        pos_pool_json: JSON data for the positive image pool
        neg_pool_json: JSON data for the negative image pool
        session_profit_factor: Cumulative profit factor for this session
        remaining_pairs: Number of remaining image pairs in this session
        started_at: Timestamp when the session was started
        ended_at: Timestamp when the session was ended
        user: Relationship to the user who owns this session
        rounds: Relationship to the rounds in this session
    """
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    status = Column(String, index=True)
    pos_pool_json = Column(JSON, nullable=True)
    neg_pool_json = Column(JSON, nullable=True)
    session_profit_factor = Column(Float, default=1.0)
    remaining_pairs = Column(Integer, default=6)
    started_at = Column(DateTime, nullable=True)
    ended_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="sessions")
    rounds = relationship("Round", back_populates="session")


class Notification(Base):
    """
    Notification model representing user notifications.

    Attributes:
        id: Unique identifier
        user_id: ID of the user who owns this notification
        type: Notification type (INFO, WARNING, ERROR, SUCCESS)
        title: Optional notification title
        message: Notification message text
        data: Optional additional data for the notification
        read: Whether the notification has been read by the user
        created_at: Timestamp when the notification was created
        updated_at: Timestamp when the notification was last updated
        user: Relationship to the user who owns this notification
    """
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    type = Column(Enum(NotificationTypeEnum), index=True)
    title = Column(String, nullable=True)
    message = Column(Text, nullable=False)
    data = Column(JSON, nullable=True)
    read = Column(Integer, default=0)  # 0 = unread, 1 = read
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="notifications")


class Round(Base):
    """
    Round model representing individual trading rounds within a session.

    Attributes:
        id: Unique identifier
        session_id: ID of the session this round belongs to
        round_number: Sequence number of this round within the session
        pos_image_id: ID of the positive image used in this round
        neg_image_id: ID of the negative image used in this round
        user_choice_side: Side chosen by the user (LEFT or RIGHT)
        user_action: Action chosen by the user (BUY or SELL)
        left_action: Action assigned to the left side (BUY or SELL)
        right_action: Action assigned to the right side (BUY or SELL)
        start_price: Starting price for this round
        end_price: Ending price for this round
        profit_fraction: Profit fraction for this round
        result: Result of this round (SUCCESS or FAILURE)
        response_time: Time taken by the user to respond
        created_at: Timestamp when the round was created
        completed_at: Timestamp when the round was completed
        session: Relationship to the session this round belongs to
        pos_image: Relationship to the positive image used in this round
        neg_image: Relationship to the negative image used in this round
    """
    __tablename__ = "rounds"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id"))
    round_number = Column(Integer)
    pos_image_id = Column(Integer, ForeignKey("images.id"))
    neg_image_id = Column(Integer, ForeignKey("images.id"))
    user_choice_side = Column(String, nullable=True)
    user_action = Column(String, nullable=True)
    left_action = Column(String, nullable=True)
    right_action = Column(String, nullable=True)
    start_price = Column(Float)
    end_price = Column(Float, nullable=True)
    profit_fraction = Column(Float, nullable=True)
    result = Column(String, nullable=True)
    response_time = Column(Float, nullable=True)
    created_at = Column(DateTime, default=func.now())
    completed_at = Column(DateTime, nullable=True)

    session = relationship("Session", back_populates="rounds")
    pos_image = relationship("Image", foreign_keys=[pos_image_id], back_populates="pos_rounds")
    neg_image = relationship("Image", foreign_keys=[neg_image_id], back_populates="neg_rounds")