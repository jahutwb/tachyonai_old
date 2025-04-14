"""
Pydantic schemas for TachyonAI.

This module defines the Pydantic schemas used for request and response validation
throughout the application. These schemas are used to validate incoming requests
and to serialize outgoing responses.
"""
from pydantic import BaseModel, Field, validator, root_validator
from typing import Optional, List, Dict, Any, Union, Literal
from datetime import datetime
from enum import Enum


class UserRoleEnum(str, Enum):
    """
    Enum for user roles.

    Attributes:
        USER: Regular user role
        ADMIN: Administrator role with elevated privileges
    """
    USER = "USER"
    ADMIN = "ADMIN"


class SessionStatusEnum(str, Enum):
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


class RoundResultEnum(str, Enum):
    """
    Enum for round result.

    Attributes:
        SUCCESS: Round was successful
        FAILURE: Round was a failure
    """
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"


class SideEnum(str, Enum):
    """
    Enum for side selection.

    Attributes:
        LEFT: Left side selected
        RIGHT: Right side selected
    """
    LEFT = "LEFT"
    RIGHT = "RIGHT"


class ActionEnum(str, Enum):
    """
    Enum for trading actions.

    Attributes:
        BUY: Buy action
        SELL: Sell action
    """
    BUY = "BUY"
    SELL = "SELL"


class ImageTypeEnum(str, Enum):
    """
    Enum for image types.

    Attributes:
        POSITIVE: Positive stimulus image
        NEGATIVE: Negative stimulus image
    """
    POSITIVE = "POSITIVE"
    NEGATIVE = "NEGATIVE"


class UserBase(BaseModel):
    """
    Base schema for user data.

    Attributes:
        username: User's username
    """
    username: str


class UserCreate(BaseModel):
    """
    Schema for creating a new user.

    Attributes:
        username: User's username
        password: User's password (will be hashed)
    """
    username: str
    password: str


class UserLogin(UserBase):
    """
    Schema for user login.

    Attributes:
        password: User's password
    """
    password: str


class UserResponse(BaseModel):
    """
    Schema for user data returned from the API.

    Attributes:
        id: User's unique identifier
        username: User's username
        created_at: Timestamp when the user was created
    """
    id: int
    username: str
    created_at: datetime

    class Config:
        from_attributes = True


class UserProfile(UserResponse):
    """
    Schema for user profile data.

    Attributes:
        session_count: Total number of sessions
        completed_session_count: Number of completed sessions
        round_count: Total number of rounds
        success_count: Number of successful rounds
        failure_count: Number of failed rounds
        total_profit_factor: Cumulative profit factor
    """
    session_count: int
    completed_session_count: int
    round_count: int
    success_count: int
    failure_count: int
    total_profit_factor: float


class ImageBase(BaseModel):
    """
    Base schema for image data.

    Attributes:
        path: Path to the image file
        type: Image type (POSITIVE or NEGATIVE)
    """
    path: str
    type: ImageTypeEnum
    img_metadata: Optional[Dict[str, Any]] = None


class ImageCreate(ImageBase):
    """
    Schema for creating a new image.

    Attributes:
        embedding: Vector embedding of the image
    """
    embedding: Optional[List[float]] = None


class ImageUpdate(BaseModel):
    """
    Schema for updating an image.

    Attributes:
        total_successes: Total number of successful rounds with this image
        total_failures: Total number of failed rounds with this image
        total_profit_factor: Cumulative profit factor for this image
    """
    total_successes: Optional[int] = None
    total_failures: Optional[int] = None
    total_profit_factor: Optional[float] = None


class ImageResponse(ImageBase):
    """
    Schema for image data returned from the API.

    Attributes:
        id: Image's unique identifier
        embedding: Vector embedding of the image
        total_successes: Total number of successful rounds with this image
        total_failures: Total number of failed rounds with this image
        total_profit_factor: Cumulative profit factor for this image
        created_at: Timestamp when the image was created
        updated_at: Timestamp when the image was last updated
    """
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
    """
    Base schema for session data.

    Attributes:
        user_id: ID of the user who owns this session
    """
    user_id: int


class SessionCreate(SessionBase):
    """
    Schema for creating a new session.

    Attributes:
        pos_pool_json: JSON data for the positive image pool
        neg_pool_json: JSON data for the negative image pool
        remaining_pairs: Number of remaining image pairs in this session
    """
    pos_pool_json: List[PoolImageItem]
    neg_pool_json: List[PoolImageItem]
    remaining_pairs: int = 6


class SessionUpdate(BaseModel):
    """
    Schema for updating a session.

    Attributes:
        status: Session status
        session_profit_factor: Cumulative profit factor for this session
        remaining_pairs: Number of remaining image pairs in this session
        ended_at: Timestamp when the session was ended
    """
    status: Optional[SessionStatusEnum] = None
    session_profit_factor: Optional[float] = None
    remaining_pairs: Optional[int] = None
    ended_at: Optional[datetime] = None


class SessionResponse(SessionBase):
    """
    Schema for session data returned from the API.

    Attributes:
        id: Session's unique identifier
        status: Session status
        pos_pool_json: JSON data for the positive image pool
        neg_pool_json: JSON data for the negative image pool
        session_profit_factor: Cumulative profit factor for this session
        remaining_pairs: Number of remaining image pairs in this session
        started_at: Timestamp when the session was started
        ended_at: Timestamp when the session was ended
    """
    id: int
    status: SessionStatusEnum
    pos_pool_json: Any
    neg_pool_json: Any
    session_profit_factor: float
    remaining_pairs: int
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None

    class Config:
        from_attributes = True
        arbitrary_types_allowed = True


class RoundBase(BaseModel):
    """
    Base schema for round data.

    Attributes:
        session_id: ID of the session this round belongs to
        round_number: Sequence number of this round within the session
        pos_image_id: ID of the positive image used in this round
        neg_image_id: ID of the negative image used in this round
        user_choice_side: Side chosen by the user (LEFT or RIGHT)
    """
    session_id: int
    round_number: int
    pos_image_id: int
    neg_image_id: int
    user_choice_side: Optional[str] = None


class RoundCreate(BaseModel):
    """
    Schema for round data returned when creating a new round.

    Attributes:
        id: Round's unique identifier
        session_id: ID of the session this round belongs to
        round_number: Sequence number of this round within the session
        pos_image_id: ID of the positive image used in this round
        neg_image_id: ID of the negative image used in this round
        start_price: Starting price for this round
        left_action: Action assigned to the left side (BUY or SELL)
        right_action: Action assigned to the right side (BUY or SELL)
        created_at: Timestamp when the round was created
    """
    id: int
    session_id: int
    round_number: int
    pos_image_id: int
    neg_image_id: int
    start_price: float
    left_action: ActionEnum
    right_action: ActionEnum
    created_at: datetime

    class Config:
        from_attributes = True


class RoundUpdate(BaseModel):
    """
    Schema for updating a round.

    Attributes:
        end_price: Ending price for this round
        profit_fraction: Profit fraction for this round
        result: Result of this round (SUCCESS or FAILURE)
        completed_at: Timestamp when the round was completed
    """
    end_price: Optional[float] = None
    profit_fraction: Optional[float] = None
    result: Optional[RoundResultEnum] = None
    completed_at: Optional[datetime] = None


class RoundResponse(RoundBase):
    """
    Schema for round data returned from the API.

    Attributes:
        id: Round's unique identifier
        user_action: Action chosen by the user (BUY or SELL)
        start_price: Starting price for this round
        end_price: Ending price for this round
        profit_fraction: Profit fraction for this round
        result: Result of this round (SUCCESS or FAILURE)
        response_time: Time taken by the user to respond
        created_at: Timestamp when the round was created
        completed_at: Timestamp when the round was completed
    """
    id: int
    user_action: Optional[ActionEnum] = None
    start_price: float
    end_price: Optional[float] = None
    profit_fraction: Optional[float] = None
    result: Optional[RoundResultEnum] = None
    response_time: Optional[float] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class TokenTypeEnum(str, Enum):
    """
    Enum for token types.

    Attributes:
        BEARER: Bearer token
    """
    BEARER = "bearer"


class NotificationTypeEnum(str, Enum):
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


class ErrorCodeEnum(str, Enum):
    """
    Enum for error codes used in API error responses.

    Attributes:
        AUTHENTICATION_ERROR: Authentication error (401)
        AUTHORIZATION_ERROR: Authorization error (403)
        VALIDATION_ERROR: Validation error (422)
        NOT_FOUND: Resource not found (404)
        CONFLICT: Resource conflict (409)
        SERVER_ERROR: Server error (500)
        BAD_REQUEST: Bad request (400)
        RATE_LIMIT: Rate limit exceeded (429)
        SERVICE_UNAVAILABLE: Service unavailable (503)
    """
    AUTHENTICATION_ERROR = "AUTHENTICATION_ERROR"
    AUTHORIZATION_ERROR = "AUTHORIZATION_ERROR"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    NOT_FOUND = "NOT_FOUND"
    CONFLICT = "CONFLICT"
    SERVER_ERROR = "SERVER_ERROR"
    BAD_REQUEST = "BAD_REQUEST"
    RATE_LIMIT = "RATE_LIMIT"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"


class Token(BaseModel):
    """
    Schema for authentication token.

    Attributes:
        access_token: JWT access token
        token_type: Token type (Bearer)
    """
    access_token: str
    token_type: TokenTypeEnum


class TokenData(BaseModel):
    """
    Schema for token data.

    Attributes:
        username: Username extracted from the token
    """
    username: Optional[str] = None


class NearestImage(BaseModel):
    """
    Schema for nearest image data.

    Attributes:
        id: Image's unique identifier
        distance: Distance to the reference image
    """
    id: int
    distance: float


class ImageEmbedding(BaseModel):
    """
    Schema for image embedding data.

    Attributes:
        id: Image's unique identifier
        embedding: Vector embedding of the image
    """
    id: int
    embedding: List[float]


class NextPoolStats(BaseModel):
    is_ready: bool
    session_id: Optional[int] = None
    total_count: int
    random_count: int
    bought_count: int
    child_count: int
    message: str

    # Dodatkowe statystyki z podziałem na pozytywne i negatywne
    pos_total: int = 0
    pos_random: int = 0
    pos_bought: int = 0
    pos_child: int = 0

    neg_total: int = 0
    neg_random: int = 0
    neg_bought: int = 0
    neg_child: int = 0


class Image(BaseModel):
    id: int
    path: str
    type: ImageTypeEnum
    total_successes: int
    total_failures: int
    total_profit_factor: float
    parent_id: Optional[int] = None

    class Config:
        from_attributes = True


class Session(BaseModel):
    id: int
    user_id: int
    status: str
    created_at: datetime = None
    session_profit_factor: float
    remaining_pairs: int
    pos_pool_json: Optional[List[Any]] = Field(default_factory=list)
    neg_pool_json: Optional[List[Any]] = Field(default_factory=list)

    class Config:
        from_attributes = True


class GenealogyNode(BaseModel):
    id: int
    successes: int
    failures: int
    profit_factor: float
    parent: Optional[int] = None
    origin: str  # "random", "child", "bought"


class StimulusRanking(BaseModel):
    id: int
    successes: int
    failures: int
    cumulative_factor: float
    origin: str  # "random", "child", "bought"
    parent: Optional[int] = None


class SessionSummary(BaseModel):
    id: int
    status: SessionStatusEnum
    started_at: Optional[datetime] = None
    session_profit_factor: float
    remaining_pairs: int
    success_count: int
    failure_count: int
    round_count: int
    pos_stimuli: Optional[List[Any]] = None
    neg_stimuli: Optional[List[Any]] = None
    pos_ranking: Optional[List[StimulusRanking]] = None
    neg_ranking: Optional[List[StimulusRanking]] = None

    class Config:
        from_attributes = True


# Statystyki puli bodźców generowanej przez algorytm quasi-genetyczny
class PoolStatistics(BaseModel):
    random_count: int  # Liczba losowych bodźców
    bought_count: int  # Liczba kupionych bodźców
    child_count: int   # Liczba dzieci
    total_count: int   # Łączna liczba bodźców
    is_ready: bool = True  # Czy pula jest gotowa
    session_id: Optional[int] = None  # ID nowo utworzonej sesji


class RoundChoice(BaseModel):
    """
    Schema for submitting a choice for a round.

    Attributes:
        session_id: ID of the session this round belongs to
        round_id: ID of the round to submit a choice for
        side: Side chosen by the user (LEFT or RIGHT)
    """
    session_id: int
    round_id: int
    side: SideEnum  # LEFT or RIGHT


class RoundResult(BaseModel):
    """
    Schema for round result data returned after a user submits a choice.

    This schema encapsulates all the information needed to display the result of a round
    to the user, including the financial outcome, session status, and feedback stimulus.

    Attributes:
        round_id: Unique identifier of the completed round
        session_id: ID of the session this round belongs to
        start_price: Initial price at the beginning of the round
        end_price: Final price at the end of the round after market movement
        profit_fraction: Calculated profit/loss factor (values > 1 indicate profit, < 1 indicate loss)
        result: Outcome of the round (SUCCESS or FAILURE) based on user's choice
        remaining_pairs: Number of image pairs remaining in the current session
        session_profit_factor: Cumulative profit factor for the entire session
        stimulus_url: URL of the feedback stimulus image shown after the round
        session_status: Current status of the session (ACTIVE, COMPLETED, etc.)
    """
    round_id: int  # Unique identifier for the round
    session_id: int  # Reference to the parent session
    start_price: float  # Initial price at the beginning of the round
    end_price: float  # Final price after market movement
    profit_fraction: float  # Profit/loss factor (>1 = profit, <1 = loss)
    result: RoundResultEnum  # Outcome: SUCCESS or FAILURE
    remaining_pairs: int  # Number of image pairs left in the session
    session_profit_factor: float  # Cumulative profit factor for the entire session
    stimulus_url: Optional[str] = None  # URL of the feedback stimulus image
    session_status: Optional[SessionStatusEnum] = None  # Current status of the session

    class Config:
        from_attributes = True


class GenerateNewPoolRequest(BaseModel):
    previous_session_id: Optional[int] = None


# Modele dla API zewnętrznego
class UserCredentials(BaseModel):
    username: str
    password: str

# Prosty model dla odpowiedzi z wiadomością
class Message(BaseModel):
    """
    Schema for simple message response.

    Attributes:
        message: Message text
    """
    message: str


class ErrorResponse(BaseModel):
    """
    Schema for standardized error responses.

    Attributes:
        code: Error code from ErrorCodeEnum
        message: Human-readable error message
        details: Optional additional error details
        timestamp: Timestamp when the error occurred
    """
    code: ErrorCodeEnum
    message: str
    details: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.now)


class Notification(BaseModel):
    """
    Schema for user notifications.

    Attributes:
        type: Type of notification (INFO, WARNING, ERROR, SUCCESS)
        message: Notification message text
        title: Optional notification title
        timestamp: Timestamp when the notification was created
        read: Whether the notification has been read by the user
        data: Optional additional data for the notification
    """
    type: NotificationTypeEnum
    message: str
    title: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)
    read: bool = False
    data: Optional[Dict[str, Any]] = None


# Nowe modele do obsługi zarządzania sesją
class SessionStats(BaseModel):
    success_count: int
    failure_count: int
    success_rate: float
    profit_factor: float
    remaining_pairs: int


class PoolOriginStats(BaseModel):
    pos_origins: Dict[str, int]
    neg_origins: Dict[str, int]
    total_pairs: int


class SessionCreateResponse(BaseModel):
    session_exists: bool
    session_status: str
    session_id: int
    has_unfinished_round: bool
    unfinished_round_id: Optional[int] = None
    session_stats: Optional[SessionStats] = None
    new_pool_stats: Optional[PoolOriginStats] = None