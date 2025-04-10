from sqlalchemy import Column, Integer, String, Float, ForeignKey, Enum, DateTime, JSON, Text
from sqlalchemy.ext.mutable import MutableList
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from enum import Enum as PyEnum
from datetime import datetime
from typing import List as TypeList, Optional

from .database import Base


class UserRoleEnum(PyEnum):
    USER = "USER"
    ADMIN = "ADMIN"


class SessionStatusEnum(PyEnum):
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    ABANDONED = "ABANDONED"


class RoundResultEnum(PyEnum):
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"


class SideEnum(PyEnum):
    LEFT = "LEFT"
    RIGHT = "RIGHT"


class ActionEnum(PyEnum):
    BUY = "BUY"
    SELL = "SELL"


class ImageTypeEnum(str, PyEnum):
    POSITIVE = "POSITIVE"
    NEGATIVE = "NEGATIVE"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    password_hash = Column(String)
    role = Column(Enum(UserRoleEnum), default=UserRoleEnum.USER)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    sessions = relationship("Session", back_populates="user")


class Image(Base):
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


class Round(Base):
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