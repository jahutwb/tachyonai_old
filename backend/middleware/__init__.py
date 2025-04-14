"""
Middleware package for TachyonAI.
This package contains middleware for the FastAPI application.
"""

from .error_handler import ErrorHandlerMiddleware, add_error_handlers

__all__ = ["ErrorHandlerMiddleware", "add_error_handlers"]
