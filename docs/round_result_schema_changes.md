# RoundResult Schema Changes

## Overview

This document describes the changes made to the `RoundResult` schema in the TachyonAI application, specifically the transition from string literals to enum values for the `result` and `session_status` fields.

## Changes Made

### 1. Updated Schema Definition

The `RoundResult` schema has been updated to use enum types instead of string literals for better type safety and consistency:

**Before:**

```python
class RoundResult(BaseModel):
    """
    Schema for round result data.

    Attributes:
        round_id: ID of the round
        session_id: ID of the session this round belongs to
        start_price: Starting price for this round
        end_price: Ending price for this round
        profit_fraction: Profit fraction for this round
        result: Result of this round (SUCCESS or FAILURE)
        remaining_pairs: Number of remaining image pairs in the session
        session_profit_factor: Cumulative profit factor for the session
        stimulus_url: URL of the stimulus image shown after the round
        session_status: Status of the session after this round
    """
    round_id: int
    session_id: int
    start_price: float
    end_price: float
    profit_fraction: float
    result: str
    remaining_pairs: int
    session_profit_factor: float
    stimulus_url: Optional[str] = None
    session_status: Optional[str] = None
```

**After:**

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

### 2. Enum Definitions

The following enum classes have been defined to replace string literals:

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

### 3. Backend Changes

In the backend code, string literals have been replaced with enum values:

**Before:**

```python
if (user_action == "BUY" and price_change > 0) or (user_action == "SELL" and price_change < 0):
    result = "SUCCESS"
    profit_fraction = abs(price_change)
else:
    result = "FAILURE"
    profit_fraction = -abs(price_change)
```

**After:**

```python
if (user_action == "BUY" and price_change > 0) or (user_action == "SELL" and price_change < 0):
    result = schemas.RoundResultEnum.SUCCESS
    profit_fraction = abs(price_change)
else:
    result = schemas.RoundResultEnum.FAILURE
    profit_fraction = -abs(price_change)
```

### 4. Frontend Changes

The frontend code has been updated to handle the enum values:

**Before:**

```javascript
if (result.result === 'SUCCESS') {
    this.data.stats.successes++;
} else {
    this.data.stats.failures++;
}
```

**After:**

```javascript
// Handle result enum (API returns SUCCESS or FAILURE as string)
if (result.result === 'SUCCESS') {
    this.data.stats.successes++;
} else if (result.result === 'FAILURE') {
    this.data.stats.failures++;
} else {
    Logger.error('Nieznany wynik rundy', result.result);
}
```

## Benefits of the Changes

1. **Improved Type Safety**: Using enums instead of string literals provides better type checking and reduces the risk of typos or invalid values.

2. **Better Documentation**: The enum definitions include documentation that explains the meaning of each value, making the code more self-documenting.

3. **Consistent API**: The API now consistently uses enum values for all status and result fields, making it easier to understand and use.

4. **Robust Error Handling**: The frontend code now explicitly checks for both SUCCESS and FAILURE values, with error logging for unexpected values.

## Handling Enum Values in Frontend Code

When working with the API, keep in mind that the enum values are serialized as strings in the JSON response. Here's how to handle them in frontend code:

```javascript
// Example: Processing the result field
function processResult(result) {
    switch (result) {
        case 'SUCCESS':
            // Handle success case
            showSuccessMessage();
            break;
        case 'FAILURE':
            // Handle failure case
            showFailureMessage();
            break;
        default:
            // Handle unexpected values
            console.error('Unexpected result value:', result);
            showErrorMessage();
            break;
    }
}
```

## Testing Enum Values

When writing tests for code that uses the RoundResult schema, make sure to use the enum values instead of string literals:

```python
# Before
assert result["result"] == "SUCCESS"

# After
assert result["result"] == RoundResultEnum.SUCCESS
```

## Conclusion

The changes to the RoundResult schema improve the type safety, documentation, and consistency of the API. By using enum values instead of string literals, we reduce the risk of errors and make the code more maintainable.

When working with the API, remember that the enum values are serialized as strings in the JSON response, so frontend code should handle them accordingly.
