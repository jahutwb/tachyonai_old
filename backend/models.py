from sqlalchemy import Column, Integer, String, Float, ForeignKey, Enum, DateTime, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from datetime import datetime

from .database import Base


class UserRoleEnum(enum.Enum):
    USER = "USER"
    ADMIN = "ADMIN"


class SessionStatusEnum(enum.Enum):
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    ABANDONED = "ABANDONED"


class RoundResultEnum(enum.Enum):
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"


class SideEnum(enum.Enum):
    LEFT = "LEFT"
    RIGHT = "RIGHT"


class ActionEnum(enum.Enum):
    BUY = "BUY"
    SELL = "SELL"


class ImageTypeEnum(enum.Enum):
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
    path = Column(String, unique=True)
    type = Column(Enum(ImageTypeEnum))
    embedding = Column(JSON, nullable=True)
    img_metadata = Column(JSON, nullable=True)
    total_successes = Column(Integer, default=0)
    total_failures = Column(Integer, default=0)
    total_profit_factor = Column(Float, default=1.0)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    pos_rounds = relationship("Round", foreign_keys="Round.pos_image_id", back_populates="pos_image")
    neg_rounds = relationship("Round", foreign_keys="Round.neg_image_id", back_populates="neg_image")


class Session(Base):
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    status = Column(Enum(SessionStatusEnum), default=SessionStatusEnum.ACTIVE)
    pos_pool_json = Column(JSON)
    neg_pool_json = Column(JSON)
    session_profit_factor = Column(Float, default=1.0)
    remaining_pairs = Column(Integer, default=6)
    started_at = Column(DateTime, default=func.now())
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
    user_choice_side = Column(Enum(SideEnum))
    user_action = Column(Enum(ActionEnum))
    start_price = Column(Float)
    end_price = Column(Float, nullable=True)
    profit_fraction = Column(Float, nullable=True)
    result = Column(Enum(RoundResultEnum), nullable=True)
    response_time = Column(Float, nullable=True)
    created_at = Column(DateTime, default=func.now())
    completed_at = Column(DateTime, nullable=True)

    session = relationship("Session", back_populates="rounds")
    pos_image = relationship("Image", foreign_keys=[pos_image_id], back_populates="pos_rounds")
    neg_image = relationship("Image", foreign_keys=[neg_image_id], back_populates="neg_rounds") 