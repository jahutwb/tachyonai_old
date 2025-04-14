# Type Safety Improvements

This document outlines specific opportunities to improve type safety in the TachyonAI codebase, prioritized by impact and implementation effort.

## High Priority Improvements

### 1. Convert User Action String Literals to ActionEnum

**Location**: `backend/routers/rounds.py`

**Current Implementation**:
```python
user_action = round_obj.left_action if choice.side == "LEFT" else round_obj.right_action
```

**Proposed Change**:
```python
user_action = round_obj.left_action if choice.side == schemas.SideEnum.LEFT else round_obj.right_action
```

**Impact**: High - This is a core part of the application logic that determines the outcome of a round.

**Effort**: Low - The ActionEnum already exists, and the change is straightforward.

### 2. Convert Side String Literals to SideEnum

**Location**: `backend/schemas.py` - RoundChoice schema

**Current Implementation**:
```python
class RoundChoice(BaseModel):
    session_id: int
    round_id: int
    side: str  # LEFT or RIGHT
```

**Proposed Change**:
```python
class RoundChoice(BaseModel):
    session_id: int
    round_id: int
    side: SideEnum  # LEFT or RIGHT
```

**Impact**: High - This ensures that only valid side values are accepted by the API.

**Effort**: Medium - This requires updating the frontend to handle the enum values correctly.

### 3. Convert Session Status String Literals to SessionStatusEnum

**Location**: `backend/routers/sessions.py`

**Current Implementation**:
```python
session.status = "COMPLETED"
```

**Proposed Change**:
```python
session.status = schemas.SessionStatusEnum.COMPLETED
```

**Impact**: High - Session status is used throughout the application to determine user flow.

**Effort**: Low - The SessionStatusEnum already exists, and the change is straightforward.

## Medium Priority Improvements

### 4. Convert Image Type String Literals to ImageTypeEnum

**Location**: `backend/routers/images.py`

**Current Implementation**:
```python
@router.get("/images/random", response_model=List[schemas.Image])
async def get_random_images(
    type: Optional[str] = Query(None, description="Image type (POSITIVE or NEGATIVE)"),
    # ...
):
```

**Proposed Change**:
```python
@router.get("/images/random", response_model=List[schemas.Image])
async def get_random_images(
    type: Optional[schemas.ImageTypeEnum] = Query(None, description="Image type (POSITIVE or NEGATIVE)"),
    # ...
):
```

**Impact**: Medium - This ensures that only valid image types are accepted by the API.

**Effort**: Medium - This requires updating the API documentation and potentially the frontend.

### 5. Create TokenTypeEnum for Authentication

**Location**: `backend/schemas.py` - Token schema

**Current Implementation**:
```python
class Token(BaseModel):
    access_token: str
    token_type: str
```

**Proposed Change**:
```python
class TokenTypeEnum(str, Enum):
    """
    Enum for token types.

    Attributes:
        BEARER: Bearer token
    """
    BEARER = "bearer"

class Token(BaseModel):
    access_token: str
    token_type: TokenTypeEnum
```

**Impact**: Medium - This ensures that only valid token types are used.

**Effort**: Medium - This requires creating a new enum and updating the authentication logic.

### 6. Create NotificationTypeEnum for User Notifications

**Location**: `backend/schemas.py` - Notification schema (if it exists)

**Proposed Change**:
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

class Notification(BaseModel):
    type: NotificationTypeEnum
    message: str
    # ...
```

**Impact**: Medium - This ensures that only valid notification types are used.

**Effort**: Medium - This requires creating a new enum and updating the notification logic.

## Low Priority Improvements

### 7. Create ErrorCodeEnum for API Error Responses

**Location**: `backend/main.py` - Error handling middleware

**Proposed Change**:
```python
class ErrorCodeEnum(str, Enum):
    """
    Enum for error codes.

    Attributes:
        AUTHENTICATION_ERROR: Authentication error
        AUTHORIZATION_ERROR: Authorization error
        VALIDATION_ERROR: Validation error
        NOT_FOUND: Resource not found
        SERVER_ERROR: Server error
    """
    AUTHENTICATION_ERROR = "AUTHENTICATION_ERROR"
    AUTHORIZATION_ERROR = "AUTHORIZATION_ERROR"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    NOT_FOUND = "NOT_FOUND"
    SERVER_ERROR = "SERVER_ERROR"

# Update error handling middleware to use the enum
```

**Impact**: Low - This improves error handling consistency but doesn't affect core functionality.

**Effort**: High - This requires updating the error handling middleware and potentially the frontend.

### 8. Create ConfigSettingEnum for Application Configuration

**Location**: `backend/config.py` (if it exists)

**Proposed Change**:
```python
class ConfigSettingEnum(str, Enum):
    """
    Enum for configuration settings.

    Attributes:
        DEBUG: Debug mode
        ENVIRONMENT: Application environment
        LOG_LEVEL: Logging level
    """
    DEBUG = "DEBUG"
    ENVIRONMENT = "ENVIRONMENT"
    LOG_LEVEL = "LOG_LEVEL"

# Update configuration logic to use the enum
```

**Impact**: Low - This improves configuration consistency but doesn't affect core functionality.

**Effort**: High - This requires updating the configuration logic throughout the application.

## Implementation Plan

1. **Phase 1**: Implement high-priority improvements
   - Convert User Action String Literals to ActionEnum
   - Convert Side String Literals to SideEnum
   - Convert Session Status String Literals to SessionStatusEnum

2. **Phase 2**: Implement medium-priority improvements
   - Convert Image Type String Literals to ImageTypeEnum
   - Create TokenTypeEnum for Authentication
   - Create NotificationTypeEnum for User Notifications

3. **Phase 3**: Implement low-priority improvements
   - Create ErrorCodeEnum for API Error Responses
   - Create ConfigSettingEnum for Application Configuration

## Testing Strategy

For each improvement:

1. Update the code to use the enum
2. Update tests to use the enum
3. Verify that the API still works correctly
4. Verify that the frontend still works correctly
5. Update documentation to reflect the changes

## Conclusion

These improvements will enhance the type safety of the TachyonAI codebase, making it more robust and maintainable. By implementing them in phases, we can minimize disruption to ongoing development while gradually improving the codebase.
