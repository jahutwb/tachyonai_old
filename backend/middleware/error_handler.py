"""
Error handling middleware for TachyonAI.
This module provides middleware for handling exceptions and returning standardized error responses.
"""
import logging
import traceback
from typing import Callable, Dict, Any

from fastapi import FastAPI, Request, Response, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from starlette.middleware.base import BaseHTTPMiddleware

from ..schemas import ErrorCodeEnum
from ..utils.errors import create_error_response, handle_validation_error, handle_exception, CustomJSONResponse

# Initialize logger
logger = logging.getLogger(__name__)


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """
    Middleware for handling exceptions and returning standardized error responses.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Dispatch the request and handle any exceptions.

        Args:
            request: FastAPI request
            call_next: Next middleware or endpoint handler

        Returns:
            Response with standardized error format if an exception occurs
        """
        try:
            return await call_next(request)
        except Exception as exc:
            # Log the exception
            logger.error(
                f"Unhandled exception in request: {request.url.path}",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "exception_type": type(exc).__name__,
                },
                exc_info=True,
            )

            # Handle different types of exceptions
            if isinstance(exc, RequestValidationError):
                return self._handle_request_validation_error(exc)
            elif isinstance(exc, ValidationError):
                return self._handle_validation_error(exc)
            else:
                return self._handle_generic_exception(exc)

    def _handle_request_validation_error(self, exc: RequestValidationError) -> JSONResponse:
        """
        Handle FastAPI RequestValidationError.

        Args:
            exc: RequestValidationError

        Returns:
            JSONResponse with standardized error format
        """
        details = {"errors": exc.errors()}
        error_response = create_error_response(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            message="Request validation error",
            details=details,
            error_code=ErrorCodeEnum.VALIDATION_ERROR,
        )

        return CustomJSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=error_response.dict(),
        )

    def _handle_validation_error(self, exc: ValidationError) -> JSONResponse:
        """
        Handle Pydantic ValidationError.

        Args:
            exc: ValidationError

        Returns:
            JSONResponse with standardized error format
        """
        http_exc = handle_validation_error(exc)
        return CustomJSONResponse(
            status_code=http_exc.status_code,
            content=http_exc.detail,
        )

    def _handle_generic_exception(self, exc: Exception) -> JSONResponse:
        """
        Handle generic exceptions.

        Args:
            exc: Exception

        Returns:
            JSONResponse with standardized error format
        """
        http_exc = handle_exception(exc)
        return CustomJSONResponse(
            status_code=http_exc.status_code,
            content=http_exc.detail,
        )


def add_error_handlers(app: FastAPI) -> None:
    """
    Add exception handlers to the FastAPI application.

    Args:
        app: FastAPI application
    """
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        """
        Handle FastAPI RequestValidationError.

        Args:
            request: FastAPI request
            exc: RequestValidationError

        Returns:
            JSONResponse with standardized error format
        """
        details = {"errors": exc.errors()}
        error_response = create_error_response(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            message="Request validation error",
            details=details,
            error_code=ErrorCodeEnum.VALIDATION_ERROR,
        )

        return CustomJSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=error_response.dict(),
        )

    @app.exception_handler(ValidationError)
    async def pydantic_validation_exception_handler(request: Request, exc: ValidationError) -> JSONResponse:
        """
        Handle Pydantic ValidationError.

        Args:
            request: FastAPI request
            exc: ValidationError

        Returns:
            JSONResponse with standardized error format
        """
        http_exc = handle_validation_error(exc)
        return CustomJSONResponse(
            status_code=http_exc.status_code,
            content=http_exc.detail,
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """
        Handle generic exceptions.

        Args:
            request: FastAPI request
            exc: Exception

        Returns:
            JSONResponse with standardized error format
        """
        # Log the exception
        logger.error(
            f"Unhandled exception in request: {request.url.path}",
            extra={
                "method": request.method,
                "path": request.url.path,
                "exception_type": type(exc).__name__,
            },
            exc_info=True,
        )

        http_exc = handle_exception(exc)
        return CustomJSONResponse(
            status_code=http_exc.status_code,
            content=http_exc.detail,
        )
