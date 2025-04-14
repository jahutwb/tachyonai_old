# Submit Round Choice Endpoint

## Overview

The `/rounds/choice` endpoint is used to submit a user's choice for a round and receive the result of that choice. This endpoint is a critical part of the application's core gameplay loop.

## Endpoint Details

```
POST /api/rounds/choice
```

## Request

### Headers

- `Authorization`: Bearer token for authentication
- `Content-Type`: application/json

### Request Body

```json
{
  "session_id": 123,
  "round_id": 456,
  "side": "LEFT"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| session_id | integer | Yes | ID of the session this round belongs to |
| round_id | integer | Yes | ID of the round to submit a choice for |
| side | string | Yes | Side chosen by the user (LEFT or RIGHT) |

## Response

### Success Response (200 OK)

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

### Response Fields

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

### Result Enum Values

The `result` field can have the following values:

- `SUCCESS`: The user's choice resulted in a profit
- `FAILURE`: The user's choice resulted in a loss

### Session Status Enum Values

The `session_status` field can have the following values:

- `ACTIVE`: Session is currently active
- `COMPLETED`: Session has been completed
- `ABANDONED`: Session was abandoned before completion
- `PENDING`: Session is pending activation

### Error Responses

#### 401 Unauthorized

```json
{
  "detail": "Not authenticated"
}
```

#### 404 Not Found

```json
{
  "detail": "Round not found"
}
```

or

```json
{
  "detail": "Session not found"
}
```

#### 400 Bad Request

```json
{
  "detail": "Session is not active"
}
```

or

```json
{
  "detail": "Round already completed"
}
```

## Implementation Details

### Processing Logic

1. The endpoint receives the user's choice (LEFT or RIGHT)
2. It retrieves the round and session from the database
3. It determines the user's action (BUY or SELL) based on the chosen side
4. It calculates the price change and determines the result (SUCCESS or FAILURE)
5. It updates the session's profit factor and remaining pairs
6. It returns the result with the appropriate stimulus image URL

### Frontend Integration

The frontend should handle the response as follows:

1. Display the result (SUCCESS or FAILURE) to the user
2. Show the appropriate stimulus image
3. Update the session statistics (remaining pairs, profit factor)
4. If the session is completed, redirect to the summary page

## Code Example

### Frontend

```javascript
async function submitChoice(sessionId, roundId, side) {
  try {
    const response = await fetch('/api/rounds/choice', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${getToken()}`
      },
      body: JSON.stringify({
        session_id: sessionId,
        round_id: roundId,
        side: side
      })
    });

    const result = await response.json();
    
    // Handle result enum (API returns SUCCESS or FAILURE as string)
    if (result.result === 'SUCCESS') {
      // Handle success case
      showSuccessMessage();
    } else if (result.result === 'FAILURE') {
      // Handle failure case
      showFailureMessage();
    } else {
      // Handle unexpected result
      console.error('Unexpected result:', result.result);
    }
    
    // Display stimulus image
    displayStimulus(result.stimulus_url);
    
    // Update session statistics
    updateSessionStats(result.remaining_pairs, result.session_profit_factor);
    
    // Check if session is completed
    if (result.session_status === 'COMPLETED' || result.remaining_pairs === 0) {
      redirectToSummary(result.session_id);
    }
    
    return result;
  } catch (error) {
    console.error('Error submitting choice:', error);
    throw error;
  }
}
```

### Backend

```python
@router.post("/rounds/choice", response_model=schemas.RoundResult)
async def submit_round_choice(
    choice: schemas.RoundChoice,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Process user's choice in a round and return the result.

    Args:
        choice: User's choice data
        current_user: Current authenticated user
        db: Database session

    Returns:
        Round result data

    Raises:
        HTTPException: If the round doesn't exist, the session doesn't belong to the user, or there's an error processing the choice
    """
    try:
        # Retrieve the round
        round_obj = db.query(Round).filter(Round.id == choice.round_id).first()
        if not round_obj:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Round not found")
            
        # Retrieve the session
        session = db.query(SessionModel).filter(
            SessionModel.id == choice.session_id,
            SessionModel.user_id == current_user.id
        ).first()
        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found or access denied")
            
        # Check if session is active
        if session.status != "ACTIVE":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Session is not active")
            
        # Check if round is already completed
        if round_obj.completed_at:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Round already completed")
            
        # Determine user action based on chosen side
        user_action = round_obj.left_action if choice.side == "LEFT" else round_obj.right_action
        
        # Calculate price change
        price_change = random.uniform(-0.01, 0.01)
        
        # Determine result
        if (user_action == "BUY" and price_change > 0) or (user_action == "SELL" and price_change < 0):
            result = schemas.RoundResultEnum.SUCCESS
            profit_fraction = abs(price_change)
        else:
            result = schemas.RoundResultEnum.FAILURE
            profit_fraction = -abs(price_change)
            
        # Update session statistics
        session.session_profit_factor *= (1 + profit_fraction)
        if result == schemas.RoundResultEnum.FAILURE:
            session.remaining_pairs -= 1
            
        # Check if session is completed
        if session.remaining_pairs <= 0:
            session.status = "COMPLETED"
            session.ended_at = datetime.now()
            
        # Update round
        round_obj.user_choice_side = choice.side
        round_obj.user_action = user_action
        round_obj.end_price = round_obj.start_price * (1 + price_change)
        round_obj.profit_fraction = profit_fraction
        round_obj.result = result
        round_obj.completed_at = datetime.now()
        
        # Commit changes
        db.commit()
        
        # Generate stimulus URL
        stimulus_id = round_obj.pos_image_id if result == schemas.RoundResultEnum.SUCCESS else round_obj.neg_image_id
        token = auth.create_access_token(data={"sub": current_user.username})
        stimulus_url = f"http://127.0.0.1:8000/api/images/{stimulus_id}/full?token={token}"
        
        # Return result
        return {
            "round_id": round_obj.id,
            "session_id": session.id,
            "start_price": round_obj.start_price,
            "end_price": round_obj.end_price,
            "profit_fraction": profit_fraction,
            "result": result,
            "remaining_pairs": session.remaining_pairs,
            "session_profit_factor": session.session_profit_factor,
            "stimulus_url": stimulus_url,
            "session_status": session.status
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing round choice: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error processing choice: {str(e)}")
```
