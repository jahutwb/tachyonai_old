"""
Error handling utilities for TachyonAI.
This module provides functions for standardized error handling.
"""
import logging
import json
from datetime import datetime
from typing import Dict, Any, Optional, Type

from fastapi import HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from ..schemas import ErrorCodeEnum, ErrorResponse

# Initialize logger
logger = logging.getLogger(__name__)


class CustomJSONEncoder(json.JSONEncoder):
    """
    Custom JSON encoder that can handle datetime objects.
    """
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


class CustomJSONResponse(JSONResponse):
    """
    Custom JSONResponse that uses the CustomJSONEncoder.
    """
    def render(self, content: Any) -> bytes:
        return json.dumps(
            content,
            ensure_ascii=False,
            allow_nan=False,
            indent=None,
            separators=(",", ":"),
            cls=CustomJSONEncoder,
        ).encode("utf-8")

# Mapping from HTTP status codes to error codes
STATUS_TO_ERROR_CODE = {
    status.HTTP_400_BAD_REQUEST: ErrorCodeEnum.BAD_REQUEST,
    status.HTTP_401_UNAUTHORIZED: ErrorCodeEnum.AUTHENTICATION_ERROR,
    status.HTTP_403_FORBIDDEN: ErrorCodeEnum.AUTHORIZATION_ERROR,
    status.HTTP_404_NOT_FOUND: ErrorCodeEnum.NOT_FOUND,
    status.HTTP_409_CONFLICT: ErrorCodeEnum.CONFLICT,
    status.HTTP_422_UNPROCESSABLE_ENTITY: ErrorCodeEnum.VALIDATION_ERROR,
    status.HTTP_429_TOO_MANY_REQUESTS: ErrorCodeEnum.RATE_LIMIT,
    status.HTTP_500_INTERNAL_SERVER_ERROR: ErrorCodeEnum.SERVER_ERROR,
    status.HTTP_503_SERVICE_UNAVAILABLE: ErrorCodeEnum.SERVICE_UNAVAILABLE,
}

# Mapping from error codes to HTTP status codes
ERROR_CODE_TO_STATUS = {
    ErrorCodeEnum.BAD_REQUEST: status.HTTP_400_BAD_REQUEST,
    ErrorCodeEnum.AUTHENTICATION_ERROR: status.HTTP_401_UNAUTHORIZED,
    ErrorCodeEnum.AUTHORIZATION_ERROR: status.HTTP_403_FORBIDDEN,
    ErrorCodeEnum.NOT_FOUND: status.HTTP_404_NOT_FOUND,
    ErrorCodeEnum.CONFLICT: status.HTTP_409_CONFLICT,
    ErrorCodeEnum.VALIDATION_ERROR: status.HTTP_422_UNPROCESSABLE_ENTITY,
    ErrorCodeEnum.RATE_LIMIT: status.HTTP_429_TOO_MANY_REQUESTS,
    ErrorCodeEnum.SERVER_ERROR: status.HTTP_500_INTERNAL_SERVER_ERROR,
    ErrorCodeEnum.SERVICE_UNAVAILABLE: status.HTTP_503_SERVICE_UNAVAILABLE,
}


def create_error_response(
    status_code: int,
    message: str,
    details: Optional[Dict[str, Any]] = None,
    error_code: Optional[ErrorCodeEnum] = None,
) -> ErrorResponse:
    """
    Create a standardized error response.

    Args:
        status_code: HTTP status code
        message: Human-readable error message
        details: Optional additional error details
        error_code: Optional error code (if not provided, will be derived from status_code)

    Returns:
        Standardized error response
    """
    if error_code is None:
        error_code = STATUS_TO_ERROR_CODE.get(
            status_code, ErrorCodeEnum.SERVER_ERROR
        )

    return ErrorResponse(
        code=error_code,
        message=message,
        details=details,
        timestamp=datetime.now(),
    )


def raise_http_exception(
    status_code: int,
    message: str,
    details: Optional[Dict[str, Any]] = None,
    error_code: Optional[ErrorCodeEnum] = None,
    headers: Optional[Dict[str, str]] = None,
) -> None:
    """
    Raise an HTTPException with a standardized error response.

    Args:
        status_code: HTTP status code
        message: Human-readable error message
        details: Optional additional error details
        error_code: Optional error code (if not provided, will be derived from status_code)
        headers: Optional HTTP headers

    Raises:
        HTTPException: With the standardized error response
    """
    error_response = create_error_response(
        status_code=status_code,
        message=message,
        details=details,
        error_code=error_code,
    )

    # Log the error
    logger.error(
        f"HTTP Exception: {status_code} - {message}",
        extra={
            "status_code": status_code,
            "error_code": error_response.code,
            "details": details,
        },
    )

    # Raise the exception
    raise HTTPException(
        status_code=status_code,
        detail=error_response.dict(),
        headers=headers,
    )


def handle_validation_error(
    exc: ValidationError,
    message: str = "Validation error",
) -> HTTPException:
    """
    Handle a Pydantic ValidationError and convert it to an HTTPException.

    Args:
        exc: Pydantic ValidationError
        message: Human-readable error message

    Returns:
        HTTPException with the standardized error response
    """
    details = {"errors": exc.errors()}
    error_response = create_error_response(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        message=message,
        details=details,
        error_code=ErrorCodeEnum.VALIDATION_ERROR,
    )

    # Log the error
    logger.error(
        f"Validation Error: {message}",
        extra={
            "status_code": status.HTTP_422_UNPROCESSABLE_ENTITY,
            "error_code": ErrorCodeEnum.VALIDATION_ERROR,
            "details": details,
        },
    )

    # Return the exception
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=error_response.dict(),
    )


def handle_exception(
    exc: Exception,
    message: str = "An unexpected error occurred",
    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
    error_code: Optional[ErrorCodeEnum] = None,
) -> HTTPException:
    """
    Handle a generic exception and convert it to an HTTPException.

    Args:
        exc: Exception to handle
        message: Human-readable error message
        status_code: HTTP status code
        error_code: Optional error code (if not provided, will be derived from status_code)

    Returns:
        HTTPException with the standardized error response
    """
    details = {"error": str(exc)}
    error_response = create_error_response(
        status_code=status_code,
        message=message,
        details=details,
        error_code=error_code,
    )

    # Log the error
    logger.error(
        f"Exception: {message} - {str(exc)}",
        extra={
            "status_code": status_code,
            "error_code": error_response.code,
            "details": details,
            "exception_type": type(exc).__name__,
        },
        exc_info=True,
    )

    # Return the exception
    return HTTPException(
        status_code=status_code,
        detail=error_response.dict(),
    )
