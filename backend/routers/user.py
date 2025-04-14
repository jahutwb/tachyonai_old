"""
User router module for TachyonAI.
This module provides endpoints for retrieving user information, session history,
and genealogy data for stimuli.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
import logging

from ..database import get_db
from ..models import User, Session as SessionModel, Round
from .. import schemas
from ..auth import get_current_user
from ..schemas import RoundResultEnum
from ..pool_image_item import PoolImageItem

# Initialize router and logger
router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/user/sessions", response_model=List[schemas.SessionSummary])
async def get_user_sessions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get all sessions for the current user.

    Args:
        current_user: Current authenticated user
        db: Database session

    Returns:
        List of session summaries with statistics
    """
    logger.info(f"Getting sessions for user {current_user.id}")
    sessions = db.query(SessionModel).filter(SessionModel.user_id == current_user.id).all()
    logger.info(f"Found {len(sessions)} sessions for user {current_user.id}")

    # Prepare detailed session summaries
    session_summaries = []
    for session in sessions:
        # Calculate success and failure counts
        success_count = db.query(Round).filter(
            Round.session_id == session.id,
            Round.result == RoundResultEnum.SUCCESS.value
        ).count()

        failure_count = db.query(Round).filter(
            Round.session_id == session.id,
            Round.result == RoundResultEnum.FAILURE.value
        ).count()

        round_count = success_count + failure_count

        # Use SessionSummary as the base
        session_summary = schemas.SessionSummary(
            id=session.id,
            status=session.status,
            started_at=session.started_at,
            session_profit_factor=session.session_profit_factor,
            remaining_pairs=session.remaining_pairs,
            success_count=success_count,
            failure_count=failure_count,
            round_count=round_count
        )

        session_summaries.append(session_summary)

    logger.info(f"Returning {len(session_summaries)} session summaries")
    return session_summaries


@router.get("/user/profile", response_model=schemas.UserProfile)
async def get_user_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get user profile with additional statistics.

    Args:
        current_user: Current authenticated user
        db: Database session

    Returns:
        User profile with statistics
    """
    logger.info(f"Getting profile for user {current_user.id}")
    # Get all user sessions
    sessions = db.query(SessionModel).filter(SessionModel.user_id == current_user.id).all()

    # Calculate total profit factor from all sessions
    total_profit_factor = 1.0
    session_count = 0
    completed_session_count = 0
    for session in sessions:
        session_count += 1
        if session.status == schemas.SessionStatusEnum.COMPLETED:
            completed_session_count += 1
            total_profit_factor *= session.session_profit_factor

    # Calculate total number of rounds
    round_count = db.query(SessionModel).filter(
        SessionModel.user_id == current_user.id
    ).join(
        SessionModel.rounds
    ).count()

    # Count successes and failures
    success_count = db.query(SessionModel).filter(
        SessionModel.user_id == current_user.id
    ).join(
        SessionModel.rounds
    ).filter(
        SessionModel.rounds.any(Round.result == RoundResultEnum.SUCCESS.value)
    ).count()

    failure_count = round_count - success_count

    logger.info(f"User {current_user.id} statistics: {session_count} sessions, {round_count} rounds")
    return {
        "id": current_user.id,
        "username": current_user.username,
        "created_at": current_user.created_at,
        "session_count": session_count,
        "completed_session_count": completed_session_count,
        "round_count": round_count,
        "success_count": success_count,
        "failure_count": failure_count,
        "total_profit_factor": total_profit_factor
    }


@router.get("/genealogy/{type}", response_model=List[schemas.GenealogyNode])
async def get_genealogy(
    type: schemas.ImageTypeEnum,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get stimulus genealogy data for a given type.

    Args:
        type: Type of stimuli (POSITIVE or NEGATIVE)
        current_user: Current authenticated user
        db: Database session

    Returns:
        List of genealogy nodes for visualization

    Raises:
        HTTPException: If the type is invalid
    """
    logger.info(f"Getting genealogy for type: {type}")

    # Get user sessions, sorted from newest to oldest
    sessions = db.query(SessionModel).filter(
        SessionModel.user_id == current_user.id,
        SessionModel.status == schemas.SessionStatusEnum.COMPLETED
    ).order_by(SessionModel.ended_at.desc()).limit(20).all()

    if not sessions:
        logger.info("No completed sessions found")
        return []

    # Dictionary to store unique genealogy nodes
    genealogy_nodes = {}

    # Iterate through sessions from oldest to newest
    for session in reversed(sessions):
        # Select the appropriate pool based on type
        pool_json = session.pos_pool_json if type == schemas.ImageTypeEnum.POSITIVE else session.neg_pool_json

        if not pool_json:
            continue

        for item in pool_json:
            try:
                # Prepare PoolImageItem object for easier analysis
                pool_item = PoolImageItem.from_dict(item)

                # If node already exists, update its statistics
                if pool_item.id in genealogy_nodes:
                    node = genealogy_nodes[pool_item.id]
                    node['successes'] += pool_item.successes
                    node['failures'] += pool_item.failures
                else:
                    # Determine parent based on origin
                    parent = None
                    if pool_item.is_child():
                        parents = pool_item.get_parents()
                        if parents:
                            parent = parents[0]  # First parent as main

                    # Add new node
                    genealogy_nodes[pool_item.id] = {
                        "id": pool_item.id,
                        "successes": pool_item.successes,
                        "failures": pool_item.failures,
                        "profit_factor": 1.0,  # Will be updated later
                        "parent": parent,
                        "origin": "child" if pool_item.is_child() else pool_item.origin
                    }
            except Exception as e:
                logger.warning(f"Error processing pool item: {str(e)}")

    # Calculate profit factor for each node
    for node_id, node in genealogy_nodes.items():
        if node['successes'] > 0 or node['failures'] > 0:
            total = node['successes'] + node['failures']
            success_rate = node['successes'] / total if total > 0 else 0
            # Simple profit model: 1.0 + (success rate * 0.2)
            node['profit_factor'] = 1.0 + (success_rate * 0.2)

    # Convert dictionary to list of nodes
    result = list(genealogy_nodes.values())

    logger.info(f"Returning {len(result)} genealogy nodes for type {type}")
    return result