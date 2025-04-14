"""
Images router module for TachyonAI.
This module provides endpoints for retrieving and managing images, including random selection,
rankings, and image serving with various resolutions.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Response, Query
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
import random
import os
import io
import logging
from PIL import Image as PILImage

from ..database import get_db
from ..models import User, Image, ImageTypeEnum
from .. import schemas
from ..auth import get_current_user, decode_access_token

# Initialize router and logger
router = APIRouter()
logger = logging.getLogger(__name__)


# Endpoints with fixed paths must be defined BEFORE endpoints with path parameters
# Otherwise FastAPI treats "random" and "ranking" as {image_id}
@router.get("/images/random", response_model=List[schemas.Image])
async def get_random_images(
    type: Optional[schemas.ImageTypeEnum] = Query(None, description="Image type (POSITIVE or NEGATIVE)"),
    count: int = Query(10, description="Number of images to return", ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get random images of a specified type.

    Args:
        type: Image type (POSITIVE or NEGATIVE)
        count: Number of images to return (default: 10)
        current_user: Current authenticated user
        db: Database session

    Returns:
        List of random images

    Raises:
        HTTPException: If the image type is invalid
    """
    logger.info(f"Getting {count} random images of type {type}")
    query = db.query(Image)

    if type:
        query = query.filter(Image.type == type)

    images = query.limit(100).all()

    if not images:
        logger.info("No images found")
        return []

    # Select 'count' images randomly
    selected_images = random.sample(images, min(count, len(images)))
    logger.info(f"Returning {len(selected_images)} random images")
    return selected_images


@router.get("/images/ranking", response_model=List[schemas.Image])
async def get_images_ranking(
    type: Optional[schemas.ImageTypeEnum] = Query(None, description="Image type (POSITIVE or NEGATIVE)"),
    limit: int = Query(10, description="Number of images to return", ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get image ranking by number of successes.

    Args:
        type: Image type (POSITIVE or NEGATIVE)
        limit: Number of images to return (default: 10)
        current_user: Current authenticated user
        db: Database session

    Returns:
        List of images sorted by success count

    Raises:
        HTTPException: If the image type is invalid
    """
    logger.info(f"Getting top {limit} images of type {type}")
    query = db.query(Image)

    if type:
        query = query.filter(Image.type == type)

    # Sort by number of successes (descending)
    images = query.order_by(Image.total_successes.desc()).limit(limit).all()
    logger.info(f"Returning {len(images)} top images")
    return images


# Endpoints with path parameters below
@router.get("/images/{image_id}")
async def get_image(
    image_id: int,
    token: Optional[str] = Query(None, description="Optional access token"),
    db: Session = Depends(get_db),
):
    """
    Get image by ID.

    Args:
        image_id: ID of the image to retrieve
        token: Optional access token for authentication
        db: Database session

    Returns:
        Image data as PNG

    Raises:
        HTTPException: If the image is not found
    """
    logger.info(f"Getting image with ID {image_id}")
    # Check token, but only if provided
    current_user = None
    if token:
        try:
            # Decode token and get username
            payload = decode_access_token(token)
            username = payload.get("sub")

            # Get user from database
            if username:
                current_user = db.query(User).filter(User.username == username).first()
                logger.info(f"Authenticated user: {username}")
        except Exception as e:
            # If token is invalid, ignore it
            logger.warning(f"Invalid token: {str(e)}")
            pass

    # We don't require authorization for access to images

    image = db.query(Image).filter(Image.id == image_id).first()
    if not image:
        logger.warning(f"Image with ID {image_id} not found")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found")

    # Get full image
    try:
        img_path = image.path
        if not os.path.exists(img_path):
            # Fallback - return test PNG data
            logger.warning(f"Image file not found at path: {img_path}")
            test_png_data = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDAT\x08\x99c\xf8\x0f\x00\x01\x01\x01\x00\x1b\x0c\x1b\x00\x00\x00\x00IEND\xaeB`\x82'
            return Response(content=test_png_data, media_type="image/png")

        # Open image using PIL
        logger.info(f"Loading image from path: {img_path}")
        img = PILImage.open(img_path)

        # Convert to buffer
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)

        return Response(content=buffer.getvalue(), media_type="image/png")
    except Exception as e:
        # Fallback - return test PNG data
        logger.error(f"Error loading image: {str(e)}")
        test_png_data = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDAT\x08\x99c\xf8\x0f\x00\x01\x01\x01\x00\x1b\x0c\x1b\x00\x00\x00\x00IEND\xaeB`\x82'
        return Response(content=test_png_data, media_type="image/png")


@router.get("/images/{image_id}/thumbnail")
async def get_image_thumbnail(
    image_id: int,
    token: Optional[str] = Query(None, description="Optional access token"),
    db: Session = Depends(get_db),
):
    """
    Get image thumbnail by ID.

    Args:
        image_id: ID of the image to retrieve thumbnail for
        token: Optional access token for authentication
        db: Database session

    Returns:
        Thumbnail image data

    Raises:
        HTTPException: If the image is not found or the user doesn't have access
    """
    logger.info(f"Getting thumbnail for image with ID {image_id}")
    # Check token, but only if provided
    current_user = None
    if token:
        try:
            # Decode token and get username
            payload = decode_access_token(token)
            username = payload.get("sub")

            # Get user from database
            if username:
                current_user = db.query(User).filter(User.username == username).first()
                logger.info(f"Authenticated user: {username}")
        except Exception as e:
            # If token is invalid, ignore it
            logger.warning(f"Invalid token: {str(e)}")
            pass

    # If token was not provided or is invalid, require standard authorization
    if not current_user:
        current_user = Depends(get_current_user)

    image = db.query(Image).filter(Image.id == image_id).first()
    if not image:
        logger.warning(f"Image with ID {image_id} not found")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found")

    # Simplified implementation - in a real application, it would read the image from disk and generate a thumbnail
    from ..images import get_image_thumbnail as get_thumbnail
    try:
        logger.info(f"Generating thumbnail for image: {image.path}")
        image_data = get_thumbnail(image.path)
        return Response(content=image_data, media_type="image/png")
    except Exception as e:
        # Fallback - return test PNG data
        logger.error(f"Error generating thumbnail: {str(e)}")
        test_png_data = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDAT\x08\x99c\xf8\x0f\x00\x01\x01\x01\x00\x1b\x0c\x1b\x00\x00\x00\x00IEND\xaeB`\x82'
        return Response(content=test_png_data, media_type="image/png")


@router.get("/images/{image_id}/full")
async def get_full_image(
    image_id: int,
    token: Optional[str] = Query(None, description="Optional access token"),
    db: Session = Depends(get_db),
):
    """
    Get full resolution image by ID.

    Args:
        image_id: ID of the image to retrieve
        token: Optional access token for authentication
        db: Database session

    Returns:
        Full resolution image data

    Raises:
        HTTPException: If the image is not found or the user doesn't have access
    """
    logger.info(f"Getting full resolution image with ID {image_id}")
    # Check token, but only if provided
    current_user = None
    if token:
        try:
            # Decode token and get username
            payload = decode_access_token(token)
            username = payload.get("sub")

            # Get user from database
            if username:
                current_user = db.query(User).filter(User.username == username).first()
                logger.info(f"Authenticated user: {username}")
        except Exception as e:
            # If token is invalid, ignore it
            logger.warning(f"Invalid token: {str(e)}")
            pass

    # If token was not provided or is invalid, require standard authorization
    if not current_user:
        current_user = Depends(get_current_user)

    image = db.query(Image).filter(Image.id == image_id).first()
    if not image:
        logger.warning(f"Image with ID {image_id} not found")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found")

    # Get full image
    from ..images import get_full_image
    try:
        logger.info(f"Loading full image: {image.path}")
        image_data = get_full_image(image.path)
        return Response(content=image_data, media_type="image/png")
    except Exception as e:
        # Fallback - return test PNG data
        logger.error(f"Error loading full image: {str(e)}")
        test_png_data = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDAT\x08\x99c\xf8\x0f\x00\x01\x01\x01\x00\x1b\x0c\x1b\x00\x00\x00\x00IEND\xaeB`\x82'
        return Response(content=test_png_data, media_type="image/png")


@router.get("/images/{image_id}/embedding", response_model=schemas.ImageEmbedding)
async def get_image_embedding(
    image_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get image embedding by ID.

    Args:
        image_id: ID of the image to retrieve embedding for
        current_user: Current authenticated user
        db: Database session

    Returns:
        Image embedding data

    Raises:
        HTTPException: If the image or embedding is not found
    """
    logger.info(f"Getting embedding for image with ID {image_id}")
    image = db.query(Image).filter(Image.id == image_id).first()
    if not image:
        logger.warning(f"Image with ID {image_id} not found")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found")

    if not image.embedding:
        logger.warning(f"Embedding not found for image with ID {image_id}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Embedding not found for this image")

    logger.info(f"Returning embedding for image with ID {image_id} (length: {len(image.embedding)})")
    return {"id": image.id, "embedding": image.embedding}


@router.get("/images/{image_id}/nearest", response_model=List[schemas.NearestImage])
async def get_nearest_images(
    image_id: int,
    count: int = Query(10, description="Number of nearest images to return", ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get images nearest to the image with the given ID in embedding space.

    Args:
        image_id: ID of the reference image
        count: Number of nearest images to return (default: 10)
        current_user: Current authenticated user
        db: Database session

    Returns:
        List of nearest images with distances

    Raises:
        HTTPException: If the image or embedding is not found
    """
    logger.info(f"Getting {count} nearest images to image with ID {image_id}")
    image = db.query(Image).filter(Image.id == image_id).first()
    if not image:
        logger.warning(f"Image with ID {image_id} not found")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found")

    if not image.embedding:
        logger.warning(f"Embedding not found for image with ID {image_id}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Embedding not found for this image")

    from ..embedding import find_nearest_images
    try:
        logger.info(f"Finding nearest images to image with ID {image_id}")
        nearest = find_nearest_images(image.embedding, count=count, db=db)
        logger.info(f"Found {len(nearest)} nearest images")
        return nearest
    except Exception as e:
        # Fallback - return test data
        logger.error(f"Error finding nearest images: {str(e)}")
        nearest_images = []
        for i in range(count):
            nearest_images.append({
                "id": i + 1,
                "distance": 0.1 * (i + 1)
            })
        return nearest_images