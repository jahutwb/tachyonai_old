from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from enum import Enum


class UserRoleEnum(str, Enum):
    USER = "USER"
    ADMIN = "ADMIN"


class SessionStatusEnum(str, Enum):
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    ABANDONED = "ABANDONED"


class RoundResultEnum(str, Enum):
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"


class SideEnum(str, Enum):
    LEFT = "LEFT"
    RIGHT = "RIGHT"


class ActionEnum(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class ImageTypeEnum(str, Enum):
    POSITIVE = "POSITIVE"
    NEGATIVE = "NEGATIVE"


class UserBase(BaseModel):
    username: str


class UserCreate(UserBase):
    password: str


class UserLogin(UserBase):
    password: str


class UserResponse(UserBase):
    id: int
    role: UserRoleEnum
    created_at: datetime

    class Config:
        from_attributes = True


class ImageBase(BaseModel):
    path: str
    type: ImageTypeEnum
    img_metadata: Optional[Dict[str, Any]] = None


class ImageCreate(ImageBase):
    embedding: Optional[List[float]] = None


class ImageUpdate(BaseModel):
    total_successes: Optional[int] = None
    total_failures: Optional[int] = None
    total_profit_factor: Optional[float] = None


class ImageResponse(ImageBase):
    id: int
    embedding: Optional[List[float]] = None
    total_successes: int
    total_failures: int
    total_profit_factor: float
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PoolImageItem(BaseModel):
    id: int
    successes: int = 0
    failures: int = 0
    origin: Optional[str] = None
    parent: Optional[int] = None


class SessionBase(BaseModel):
    user_id: int


class SessionCreate(SessionBase):
    pos_pool_json: List[PoolImageItem]
    neg_pool_json: List[PoolImageItem]
    remaining_pairs: int = 6


class SessionUpdate(BaseModel):
    status: Optional[SessionStatusEnum] = None
    session_profit_factor: Optional[float] = None
    remaining_pairs: Optional[int] = None
    ended_at: Optional[datetime] = None


class SessionResponse(SessionBase):
    id: int
    status: SessionStatusEnum
    pos_pool_json: List[Dict[str, Any]]
    neg_pool_json: List[Dict[str, Any]]
    session_profit_factor: float
    remaining_pairs: int
    started_at: datetime
    ended_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class RoundBase(BaseModel):
    session_id: int
    round_number: int
    pos_image_id: int
    neg_image_id: int
    user_choice_side: SideEnum


class RoundCreate(RoundBase):
    user_action: ActionEnum
    start_price: float
    response_time: Optional[float] = None


class RoundUpdate(BaseModel):
    end_price: Optional[float] = None
    profit_fraction: Optional[float] = None
    result: Optional[RoundResultEnum] = None
    completed_at: Optional[datetime] = None


class RoundResponse(RoundBase):
    id: int
    user_action: ActionEnum
    start_price: float
    end_price: Optional[float] = None
    profit_fraction: Optional[float] = None
    result: Optional[RoundResultEnum] = None
    response_time: Optional[float] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: Optional[str] = None 