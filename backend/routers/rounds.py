"""
Rounds router module for TachyonAI.
This module provides endpoints for managing game rounds, including creation, retrieval, and processing user choices.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import random
import logging
import traceback
import json
from sqlalchemy.sql import func
from typing import Dict, List, Optional
from datetime import datetime

from ..database import get_db
from ..models import User, Session as SessionModel, Round, Image, ImageTypeEnum
from .. import schemas
from ..auth import get_current_user
from ..routers.sessions import generate_pool_with_genetic_algorithm

# Initialize router and logger
router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/rounds/next", response_model=schemas.RoundCreate)
async def get_next_round(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get the next round for a session by ID.

    Args:
        session_id: ID of the session to get the next round for
        current_user: Current authenticated user
        db: Database session

    Returns:
        Next round data or a new round if there are no unfinished rounds

    Raises:
        HTTPException: If the session doesn't exist, isn't active, or has no available pairs
    """
    try:
        logger.info(f"Getting next round for session {session_id}")

        # Check if the session exists and belongs to the current user
        session = db.query(SessionModel).filter(
            SessionModel.id == session_id,
            SessionModel.user_id == current_user.id
        ).first()

        if not session:
            logger.warning(f"Session {session_id} not found or access denied")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found or access denied")

        logger.info(f"Session {session_id} state after retrieval:")
        logger.info(f"Status: {session.status}")
        logger.info(f"Remaining pairs: {session.remaining_pairs}")

        try:
            # Direct use of JSON fields from the model
            pos_pool_json = session.pos_pool_json
            neg_pool_json = session.neg_pool_json

            # Guard against None values
            if pos_pool_json is None:
                pos_pool_json = []
            if neg_pool_json is None:
                neg_pool_json = []

            logger.info(f"Pos pool: {[item['id'] for item in pos_pool_json]}")
            logger.info(f"Neg pool: {[item['id'] for item in neg_pool_json]}")
        except Exception as json_error:
            logger.error(f"Error processing JSON: {str(json_error)}")
            pos_pool_json = []
            neg_pool_json = []

        # Check if the session is active
        if session.status != "ACTIVE":
            logger.warning(f"Session {session_id} is not active - status: {session.status}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Session is not active")

        # Check if there are still pairs available to play
        if session.remaining_pairs <= 0:
            logger.warning(f"No available pairs in session {session_id}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No available pairs in session")

        # Check if there is an unfinished round
        unfinished_round = db.query(Round).filter(
            Round.session_id == session_id,
            Round.result == None
        ).order_by(Round.id.desc()).first()

        if unfinished_round:
            logger.info(f"Found unfinished round {unfinished_round.id} for session {session_id}")
            return unfinished_round

        # Get the number of rounds in the session to determine the round number
        round_count = db.query(Round).filter(Round.session_id == session_id).count()
        round_number = round_count + 1
        logger.info(f"Creating round number {round_number} for session {session_id}")

        try:
            # Filter image pools - only items with failures=0
            valid_pos_pool = [item for item in pos_pool_json if item.get("failures", 0) == 0]
            valid_neg_pool = [item for item in neg_pool_json if item.get("failures", 0) == 0]

            logger.info(f"Pool state after filtering (only failures=0):")
            logger.info(f"Positive: {[item['id'] for item in valid_pos_pool]}")
            logger.info(f"Negative: {[item['id'] for item in valid_neg_pool]}")

            # Check if there are available image pairs
            if not valid_pos_pool or not valid_neg_pool:
                logger.warning(f"No available image pairs in session {session_id}")
                # End the session if there are no available pairs
                session.status = "COMPLETED"
                session.remaining_pairs = 0
                session.ended_at = func.now()
                db.commit()
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No available image pairs in session. Session has been completed."
                )

            # Choose a random image from the filtered pools
            pos_item = random.choice(valid_pos_pool)
            neg_item = random.choice(valid_neg_pool)

            # Retrieve image objects from the database
            pos_image = db.query(Image).filter(Image.id == pos_item["id"]).first()
            neg_image = db.query(Image).filter(Image.id == neg_item["id"]).first()

            if not pos_image or not neg_image:
                logger.error(f"Images not found in database: pos_id={pos_item['id']}, neg_id={neg_item['id']}")
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Invalid image references in pool")

            logger.info(f"Selected images from pool (failures=0): pos_id={pos_image.id}, neg_id={neg_image.id}")
            logger.info(f"Image paths: pos_path={pos_image.path}, neg_path={neg_image.path}")

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error selecting images from pool: {str(e)}")
            logger.error(traceback.format_exc())
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error selecting images: {str(e)}")

        # Randomly determine which side is buy (BUY) and which is sell (SELL)
        left_action = random.choice(["BUY", "SELL"])
        right_action = "SELL" if left_action == "BUY" else "BUY"
        logger.info(f"Assigned actions: left={left_action}, right={right_action}")

        # Create a new round
        try:
            new_round = Round(
                session_id=session_id,
                round_number=round_number,
                pos_image_id=pos_image.id,
                neg_image_id=neg_image.id,
                start_price=50000.0,  # Example value
                left_action=left_action,
                right_action=right_action
            )

            db.add(new_round)
            db.commit()
            db.refresh(new_round)
            logger.info(f"Created new round id={new_round.id} for session {session_id}")

            return {
                "id": new_round.id,
                "session_id": new_round.session_id,
                "round_number": new_round.round_number,
                "pos_image_id": new_round.pos_image_id,
                "neg_image_id": new_round.neg_image_id,
                "start_price": new_round.start_price,
                "left_action": new_round.left_action,
                "right_action": new_round.right_action,
                "created_at": new_round.created_at
            }
        except Exception as db_error:
            logger.error(f"Database error while creating round: {str(db_error)}")
            logger.error(traceback.format_exc())
            db.rollback()
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Database error: {str(db_error)}")

    except HTTPException:
        # Pass through HTTPException to preserve their details
        raise
    except Exception as e:
        logger.error(f"Unexpected error in get_next_round: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Unexpected error: {str(e)}")


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
    import time
    start_time = time.time()

    try:
        logger.info(f"[TIMING] Starting to process choice for round {choice.round_id}, session {choice.session_id}")

        # Check if the round exists
        query_start = time.time()
        round_obj = db.query(Round).filter(Round.id == choice.round_id).first()
        logger.info(f"[TIMING] Round retrieval: {time.time() - query_start:.3f}s")

        if not round_obj:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Round not found")

        # Check if the session belongs to the current user
        query_start = time.time()
        session = db.query(SessionModel).filter(SessionModel.id == round_obj.session_id).first()
        logger.info(f"[TIMING] Session retrieval: {time.time() - query_start:.3f}s")

        if not session or session.user_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to this round")

        # Determine user action
        user_action = round_obj.left_action if choice.side == schemas.SideEnum.LEFT else round_obj.right_action

        # Simulate price change
        price_change = random.uniform(-0.01, 0.01)
        end_price = round_obj.start_price * (1 + price_change)

        # Prepare copies of JSON pools
        json_start = time.time()
        try:
            pos_pool = json.loads(session.pos_pool_json) if isinstance(session.pos_pool_json, str) else session.pos_pool_json
            neg_pool = json.loads(session.neg_pool_json) if isinstance(session.neg_pool_json, str) else session.neg_pool_json

            # Guard against None values
            if pos_pool is None:
                pos_pool = []
            if neg_pool is None:
                neg_pool = []

            logger.info(f"[TIMING] JSON processing: {time.time() - json_start:.3f}s")

        except Exception as e:
            logger.error(f"Error reading JSON pool: {str(e)}")
            pos_pool = []
            neg_pool = []

        # Calculate result and update pools
        update_start = time.time()
        if (user_action == schemas.ActionEnum.BUY and price_change > 0) or (user_action == schemas.ActionEnum.SELL and price_change < 0):
            result = schemas.RoundResultEnum.SUCCESS
            profit_fraction = abs(price_change)
            stimulus_id = round_obj.pos_image_id

            # Update successes for both images in pools
            for item in pos_pool:
                if item["id"] == round_obj.pos_image_id:
                    item["successes"] = item.get("successes", 0) + 1
                    logger.info(f"SUCCESS: Increasing successes for pos_image {item['id']}: {item['successes']}")

            for item in neg_pool:
                if item["id"] == round_obj.neg_image_id:
                    item["successes"] = item.get("successes", 0) + 1
                    logger.info(f"SUCCESS: Increasing successes for neg_image {item['id']}: {item['successes']}")
        else:
            result = schemas.RoundResultEnum.FAILURE
            profit_fraction = -abs(price_change)
            stimulus_id = round_obj.neg_image_id

            # Update failures for both images in pools
            for item in pos_pool:
                if item["id"] == round_obj.pos_image_id:
                    item["failures"] = item.get("failures", 0) + 1
                    logger.info(f"FAILURE: Increasing failures for pos_image {item['id']}: {item['failures']}")

            for item in neg_pool:
                if item["id"] == round_obj.neg_image_id:
                    item["failures"] = item.get("failures", 0) + 1
                    logger.info(f"FAILURE: Increasing failures for neg_image {item['id']}: {item['failures']}")

        logger.info(f"[TIMING] Pool updates: {time.time() - update_start:.3f}s")

        # Update session - force detection of changes in JSON fields
        session.session_profit_factor *= (1 + profit_fraction)

        # Update JSON fields in session - direct assignment
        session.pos_pool_json = pos_pool
        session.neg_pool_json = neg_pool

        # Mark fields as modified
        from sqlalchemy.orm import attributes
        attributes.flag_modified(session, "pos_pool_json")
        attributes.flag_modified(session, "neg_pool_json")

        # Check number of available pairs (number of images with failures=0)
        pairs_start = time.time()
        valid_pos_pool = [item for item in pos_pool if item.get("failures", 0) == 0]
        valid_neg_pool = [item for item in neg_pool if item.get("failures", 0) == 0]

        available_pairs = min(len(valid_pos_pool), len(valid_neg_pool))
        logger.info(f"[TIMING] Available pairs calculation: {time.time() - pairs_start:.3f}s")
        logger.info(f"Available pairs after update: {available_pairs} (valid_pos: {len(valid_pos_pool)}, valid_neg: {len(valid_neg_pool)})")

        # Update remaining_pairs based on actual number of available pairs
        session.remaining_pairs = available_pairs

        # End session only if there are no available pairs
        if available_pairs <= 0:
            session.status = schemas.SessionStatusEnum.COMPLETED
            session.ended_at = func.now()
            logger.info(f"Ending session {session.id} - no available pairs")

            # New pool will be generated only after clicking the "Session Summary" button
            # according to the specification, not automatically after session completion

        # Save all changes in one transaction
        commit_start = time.time()
        db.commit()
        logger.info(f"[TIMING] Saving changes to database: {time.time() - commit_start:.3f}s")

        # Refresh all objects
        db.refresh(session)
        db.refresh(round_obj)

        # Update image statistics in the database
        images_start = time.time()
        pos_image = db.query(Image).filter(Image.id == round_obj.pos_image_id).first()
        neg_image = db.query(Image).filter(Image.id == round_obj.neg_image_id).first()

        if result == schemas.RoundResultEnum.SUCCESS:
            pos_image.total_successes += 1
            neg_image.total_successes += 1
        else:
            pos_image.total_failures += 1
            neg_image.total_failures += 1

        pos_image.total_profit_factor *= (1 + profit_fraction)
        neg_image.total_profit_factor *= (1 + profit_fraction)

        # Save changes to images
        db.commit()
        logger.info(f"[TIMING] Image update: {time.time() - images_start:.3f}s")

        # Update round object
        round_obj.user_choice_side = str(choice.side)  # Set the user's choice side
        round_obj.user_action = user_action
        round_obj.end_price = end_price
        round_obj.profit_fraction = profit_fraction
        round_obj.result = result
        round_obj.stimulus_id = stimulus_id
        round_obj.processed_at = func.now()

        logger.info(f"Updated round {round_obj.id} with user_choice_side={round_obj.user_choice_side}")

        db.commit()
        logger.info(f"[TIMING] Total choice processing time: {time.time() - start_time:.3f}s")

        # Get stimulus image URL for full resolution
        stimulus = db.query(Image).filter(Image.id == stimulus_id).first()

        # Use full URL with token so the image is accessible without additional authorization
        from ..auth import create_access_token
        from starlette.config import Config

        # Create token for the image
        token_data = {"sub": current_user.username}
        access_token = create_access_token(token_data)

        # Create full URL
        host_url = "http://127.0.0.1:8000"  # Can be retrieved from configuration or environment variables
        stimulus_url = f"{host_url}/api/images/{stimulus_id}/full?token={access_token}" if stimulus else None

        # Add stimulus path logging
        if stimulus:
            logger.info(f"Displayed stimulus: {stimulus.path}")

        return {
            "round_id": round_obj.id,
            "session_id": session.id,
            "start_price": round_obj.start_price,
            "end_price": end_price,
            "profit_fraction": profit_fraction,
            "result": result,
            "session_status": session.status,
            "remaining_pairs": session.remaining_pairs,
            "session_profit_factor": session.session_profit_factor,
            "stimulus_url": stimulus_url
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in submit_round_choice: {str(e)}")
        logger.error(traceback.format_exc())
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error processing choice: {str(e)}")