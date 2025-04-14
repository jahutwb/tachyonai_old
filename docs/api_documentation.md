# TachyonAI API Documentation

This document provides detailed information about the TachyonAI API endpoints, request/response formats, and data models.

## Table of Contents

- [Authentication](#authentication)
- [Sessions](#sessions)
- [Rounds](#rounds)
  - [Get Next Round](#get-next-round)
  - [Submit Round Choice](#submit-round-choice)
- [Images](#images)
- [Users](#users)
- [Notifications](#notifications)
  - [Get Notifications](#get-notifications)
  - [Mark Notification Read](#mark-notification-read)
  - [Mark All Notifications Read](#mark-all-notifications-read)
  - [Delete Notification](#delete-notification)
  - [Delete All Notifications](#delete-all-notifications)
- [Error Handling](#error-handling)
  - [Error Response Format](#error-response-format)
  - [Error Codes](#error-codes)
- [Data Models](#data-models)
  - [Enums](#enums)
  - [Schemas](#schemas)

## Authentication

### Login for Access Token

```
POST /token
```

Authenticates a user and returns a JWT access token.

**Request Body:**

```json
{
  "username": "string",
  "password": "string"
}
```

**Response:**

```json
{
  "access_token": "string",
  "token_type": "bearer"
}
```

## Sessions

### Create Session

```
POST /api/sessions
```

Creates a new session or returns information about an existing session.

**Response:**

```json
{
  "session_id": 123,
  "status": "ACTIVE",
  "message": "Session created successfully"
}
```

### Get Session

```
GET /api/sessions/{session_id}
```

Returns information about a specific session.

**Response:**

```json
{
  "id": 123,
  "status": "ACTIVE",
  "session_profit_factor": 1.05,
  "remaining_pairs": 10,
  "started_at": "2023-01-01T12:00:00Z",
  "ended_at": null
}
```

## Rounds

### Get Next Round

```
GET /api/rounds/next?session_id={session_id}
```

Returns the next round for a session.

**Response:**

```json
{
  "id": 456,
  "session_id": 123,
  "round_number": 1,
  "pos_image_id": 789,
  "neg_image_id": 790,
  "start_price": 50000.0,
  "left_action": "BUY",
  "right_action": "SELL",
  "created_at": "2023-01-01T12:01:00Z"
}
```

### Submit Round Choice

```
POST /api/rounds/choice
```

Submits a user's choice for a round and returns the result.

**Request Body:**

```json
{
  "session_id": 123,
  "round_id": 456,
  "side": "LEFT"
}
```

**Response:**

```json
{
  "round_id": 456,
  "session_id": 123,
  "start_price": 50000.0,
  "end_price": 50250.0,
  "profit_fraction": 0.005,
  "result": "SUCCESS",
  "remaining_pairs": 9,
  "session_profit_factor": 1.055,
  "stimulus_url": "http://example.com/api/images/789/full?token=xyz",
  "session_status": "ACTIVE"
}
```

#### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| round_id | integer | Unique identifier of the completed round |
| session_id | integer | ID of the session this round belongs to |
| start_price | float | Initial price at the beginning of the round |
| end_price | float | Final price at the end of the round after market movement |
| profit_fraction | float | Calculated profit/loss factor (values > 0 indicate profit, < 0 indicate loss) |
| result | enum | Outcome of the round (SUCCESS or FAILURE) based on user's choice |
| remaining_pairs | integer | Number of image pairs remaining in the current session |
| session_profit_factor | float | Cumulative profit factor for the entire session |
| stimulus_url | string | URL of the feedback stimulus image shown after the round |
| session_status | enum | Current status of the session (ACTIVE, COMPLETED, etc.) |

#### Result Enum Values

The `result` field can have the following values:

- `SUCCESS`: The user's choice resulted in a profit
- `FAILURE`: The user's choice resulted in a loss

## Images

### Get Image

```
GET /api/images/{image_id}
```

Returns an image by ID.

### Get Image Thumbnail

```
GET /api/images/{image_id}/thumbnail
```

Returns a thumbnail version of an image.

### Get Image Full

```
GET /api/images/{image_id}/full?token={token}
```

Returns a full-size version of an image.

## Users

### Get Current User

```
GET /api/users/me
```

Returns information about the currently authenticated user.

**Response:**

```json
{
  "id": 1,
  "username": "user123",
  "created_at": "2023-01-01T00:00:00Z"
}
```

## Notifications

### Get Notifications

```
GET /api/notifications
```

Returns a list of notifications for the current user.

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| unread_only | boolean | No | If true, returns only unread notifications |

**Response:**

```json
[
  {
    "type": "INFO",
    "message": "This is an informational notification",
    "title": "Information",
    "timestamp": "2023-01-01T12:00:00Z",
    "read": false,
    "data": null
  },
  {
    "type": "SUCCESS",
    "message": "This is a success notification",
    "title": "Success",
    "timestamp": "2023-01-01T12:01:00Z",
    "read": true,
    "data": {
      "additional_info": "Some additional information"
    }
  }
]
```

### Mark Notification Read

```
POST /api/notifications/mark-read/{notification_id}
```

Marks a notification as read.

**Path Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| notification_id | integer | Yes | ID of the notification to mark as read |

**Response:**

```json
{
  "message": "Notification marked as read"
}
```

### Mark All Notifications Read

```
POST /api/notifications/mark-all-read
```

Marks all notifications as read for the current user.

**Response:**

```json
{
  "message": "All notifications marked as read"
}
```

### Delete Notification

```
DELETE /api/notifications/{notification_id}
```

Deletes a notification.

**Path Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| notification_id | integer | Yes | ID of the notification to delete |

**Response:**

```json
{
  "message": "Notification deleted"
}
```

### Delete All Notifications

```
DELETE /api/notifications
```

Deletes all notifications for the current user.

**Response:**

```json
{
  "message": "All notifications deleted"
}
```

## Error Handling

### Error Response Format

All API errors are returned in a standardized format:

```json
{
  "code": "ERROR_CODE",
  "message": "Human-readable error message",
  "details": {
    "additional_info": "Additional error details"
  },
  "timestamp": "2023-01-01T12:00:00Z"
}
```

| Field | Type | Description |
|-------|------|-------------|
| code | string | Error code from ErrorCodeEnum |
| message | string | Human-readable error message |
| details | object | Optional additional error details |
| timestamp | string | Timestamp when the error occurred |

### Error Codes

The API uses the following error codes:

| Code | HTTP Status | Description |
|------|-------------|-------------|
| AUTHENTICATION_ERROR | 401 | Authentication error (e.g., invalid credentials) |
| AUTHORIZATION_ERROR | 403 | Authorization error (e.g., insufficient permissions) |
| VALIDATION_ERROR | 422 | Validation error (e.g., invalid input) |
| NOT_FOUND | 404 | Resource not found |
| CONFLICT | 409 | Resource conflict (e.g., duplicate username) |
| SERVER_ERROR | 500 | Server error |
| BAD_REQUEST | 400 | Bad request (e.g., invalid parameters) |
| RATE_LIMIT | 429 | Rate limit exceeded |
| SERVICE_UNAVAILABLE | 503 | Service unavailable |

## Data Models

### Enums

#### SessionStatusEnum

```python
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
```

#### RoundResultEnum

```python
class RoundResultEnum(str, Enum):
    """
    Enum for round result.

    Attributes:
        SUCCESS: Round was successful
        FAILURE: Round was a failure
    """
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
```

#### SideEnum

```python
class SideEnum(str, Enum):
    """
    Enum for side selection.

    Attributes:
        LEFT: Left side selected
        RIGHT: Right side selected
    """
    LEFT = "LEFT"
    RIGHT = "RIGHT"
```

#### ActionEnum

```python
class ActionEnum(str, Enum):
    """
    Enum for action type.

    Attributes:
        BUY: Buy action
        SELL: Sell action
    """
    BUY = "BUY"
    SELL = "SELL"
```

#### ImageTypeEnum

```python
class ImageTypeEnum(str, Enum):
    """
    Enum for image types.

    Attributes:
        POSITIVE: Positive stimulus image
        NEGATIVE: Negative stimulus image
    """
    POSITIVE = "POSITIVE"
    NEGATIVE = "NEGATIVE"
```

#### NotificationTypeEnum

```python
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
```

#### TokenTypeEnum

```python
class TokenTypeEnum(str, Enum):
    """
    Enum for token types.

    Attributes:
        BEARER: Bearer token
    """
    BEARER = "bearer"
```

#### ErrorCodeEnum

```python
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
```

#### EnvironmentEnum

```python
class EnvironmentEnum(str, Enum):
    """
    Enum for application environments.

    Attributes:
        DEVELOPMENT: Development environment
        TESTING: Testing environment
        STAGING: Staging environment
        PRODUCTION: Production environment
    """
    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"
```

#### LogLevelEnum

```python
class LogLevelEnum(str, Enum):
    """
    Enum for logging levels.

    Attributes:
        DEBUG: Debug level
        INFO: Info level
        WARNING: Warning level
        ERROR: Error level
        CRITICAL: Critical level
    """
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"
```

#### ConfigSettingEnum

```python
class ConfigSettingEnum(str, Enum):
    """
    Enum for configuration settings.

    Attributes:
        DEBUG: Debug mode
        ENVIRONMENT: Application environment
        LOG_LEVEL: Logging level
        DATABASE_URL: Database connection URL
        SECRET_KEY: Secret key for JWT token generation
        ACCESS_TOKEN_EXPIRE_MINUTES: JWT token expiration time in minutes
        CORS_ORIGINS: CORS allowed origins
        STATIC_DIR: Static files directory
        TEMPLATES_DIR: Templates directory
        UPLOAD_DIR: Upload directory for user files
        MAX_UPLOAD_SIZE: Maximum upload size in bytes
        ALLOWED_EXTENSIONS: Allowed file extensions for uploads
    """
    DEBUG = "DEBUG"
    ENVIRONMENT = "ENVIRONMENT"
    LOG_LEVEL = "LOG_LEVEL"
    DATABASE_URL = "DATABASE_URL"
    SECRET_KEY = "SECRET_KEY"
    ACCESS_TOKEN_EXPIRE_MINUTES = "ACCESS_TOKEN_EXPIRE_MINUTES"
    CORS_ORIGINS = "CORS_ORIGINS"
    STATIC_DIR = "STATIC_DIR"
    TEMPLATES_DIR = "TEMPLATES_DIR"
    UPLOAD_DIR = "UPLOAD_DIR"
    MAX_UPLOAD_SIZE = "MAX_UPLOAD_SIZE"
    ALLOWED_EXTENSIONS = "ALLOWED_EXTENSIONS"
```

### Schemas

#### RoundResult

```python
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
```

#### RoundChoice

```python
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
```

#### Notification

```python
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
```

#### ErrorResponse

```python
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
```

#### RoundCreate

```python
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
```
