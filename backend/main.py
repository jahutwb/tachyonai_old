"""
Main application module for TachyonAI.
This module initializes the FastAPI application, sets up logging, database, and routes.
"""
import os
import logging
import contextlib
from pathlib import Path
from datetime import timedelta
from typing import AsyncGenerator

from fastapi import FastAPI, Depends, HTTPException, status, Request, Form
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import Session

from .database import get_db, engine
from . import models, schemas, auth
from .init_db import init_db
from .routers import sessions_router, rounds_router, images_router, user_router, price_router, notifications_router
from .faiss_manager import get_faiss_index_manager
from .middleware import ErrorHandlerMiddleware, add_error_handlers
from .utils.errors import create_error_response, raise_http_exception, CustomJSONResponse
from .config import Config, ConfigSettingEnum, EnvironmentEnum, LogLevelEnum

# Initialize logger
def setup_logging():
    """Set up application logging configuration."""
    log_path = os.path.join("logs", "app.log")
    os.makedirs(os.path.dirname(log_path), exist_ok=True)

    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s - %(pathname)s:%(lineno)d",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_path, mode='a')
        ]
    )

    # Configure specific loggers
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.ERROR)

    return logging.getLogger(__name__)

# Set up logger
logger = setup_logging()
logger.info("Logger configuration completed")

# Create FastAPI application
app = FastAPI(
    title="TachyonAI",
    version="0.1.0",
    description="Application for hidden BTC price prediction using a quasi-genetic algorithm"
)

# Lifespan context manager for startup and shutdown events
@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Lifespan context manager for application startup and shutdown events.

    Args:
        app: FastAPI application instance
    """
    # Startup
    logger.info("Application starting up")

    # Initialize database
    init_db()
    logger.info("Database initialized")

    # Initialize FAISS index manager
    logger.info("Initializing FAISS index manager")
    faiss_manager = get_faiss_index_manager()
    logger.info("FAISS index manager initialized")

    yield

    # Shutdown
    logger.info("Application shutting down")

# Set lifespan
app.router.lifespan_context = lifespan

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=Config.get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add error handling middleware
app.add_middleware(ErrorHandlerMiddleware)

# Add error handlers
add_error_handlers(app)

# Add custom exception handler for HTTPException
@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    """
    Custom exception handler for HTTPException.
    This ensures that HTTPExceptions are handled correctly and not converted to 500 errors.
    """
    # Create a standardized error response
    error_code = schemas.ErrorCodeEnum.AUTHENTICATION_ERROR if exc.status_code == status.HTTP_401_UNAUTHORIZED else None
    error_response = create_error_response(
        status_code=exc.status_code,
        message=str(exc.detail),
        error_code=error_code
    )

    return CustomJSONResponse(
        status_code=exc.status_code,
        content=error_response.dict(),
        headers=exc.headers,
    )

# Set up static files and templates
frontend_dir = Path(__file__).parent.parent
templates_dir = frontend_dir / Config.get_templates_dir()
static_dir = frontend_dir / Config.get_static_dir()
templates = Jinja2Templates(directory=str(templates_dir))
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Register API routers
app.include_router(sessions_router, prefix="/api", tags=["sessions"])
app.include_router(rounds_router, prefix="/api", tags=["rounds"])
app.include_router(images_router, prefix="/api", tags=["images"])
app.include_router(user_router, prefix="/api", tags=["users"])
app.include_router(price_router, prefix="/api", tags=["price"])
app.include_router(notifications_router, prefix="/api", tags=["notifications"])


# Page routes
@app.get("/")
async def read_root(request: Request):
    """Home page."""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/game")
async def game_page(request: Request):
    """Game page."""
    return templates.TemplateResponse("game.html", {"request": request})


@app.get("/summary")
async def summary_page(request: Request):
    """Session summary page."""
    return templates.TemplateResponse("summary.html", {"request": request})


@app.get("/stats")
async def stats_page(request: Request):
    """Global statistics page."""
    return templates.TemplateResponse("stats.html", {"request": request})


# Authentication routes
@app.post("/token", response_model=schemas.Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)
):
    """Login endpoint for JWT token generation.

    Args:
        form_data: Username and password form data
        db: Database session

    Returns:
        JWT access token

    Raises:
        HTTPException: If authentication fails
    """
    user = auth.authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise_http_exception(
            status_code=status.HTTP_401_UNAUTHORIZED,
            message="Invalid username or password",
            error_code=schemas.ErrorCodeEnum.AUTHENTICATION_ERROR,
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=Config.get_access_token_expire_minutes())
    access_token = auth.create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": schemas.TokenTypeEnum.BEARER}


@app.post("/signup", response_model=schemas.UserResponse)
async def signup(user: schemas.UserCreate, db: Session = Depends(get_db)):
    """Register a new user.

    Args:
        user: User creation data
        db: Database session

    Returns:
        Created user data

    Raises:
        HTTPException: If username already exists
    """
    db_user = db.query(models.User).filter(models.User.username == user.username).first()
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already exists",
        )
    hashed_password = auth.get_password_hash(user.password)
    db_user = models.User(username=user.username, password_hash=hashed_password)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


# Authentication pages
@app.get("/signup")
async def signup_page(request: Request):
    """Registration form page."""
    return templates.TemplateResponse("signup.html", {"request": request})


@app.get("/login")
async def login_page(request: Request):
    """Login form page."""
    return templates.TemplateResponse("login.html", {"request": request})


# User routes
@app.get("/users/me", response_model=schemas.UserResponse)
async def read_users_me(current_user: models.User = Depends(auth.get_current_user)):
    """Get current authenticated user data.

    Args:
        current_user: Current authenticated user

    Returns:
        User data
    """
    return current_user


# Health check routes
@app.get("/health")
async def health_check():
    """Application health check endpoint."""
    return {"status": "ok"}


@app.get("/ping")
async def ping():
    """Simple ping endpoint to check if server is running."""
    return {"ping": "pong"}


# Run server when script is called directly
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=True)