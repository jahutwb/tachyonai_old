import os
from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import timedelta
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import logging

from .database import get_db, engine
from . import models, schemas, auth
from .init_db import init_db

# Inicjalizacja loggera
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Inicjalizacja bazy danych
init_db()

# Tworzenie aplikacji FastAPI
app = FastAPI(title="TachyonAI", version="0.1.0")

# Middleware CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Statyczne pliki i szablony
frontend_dir = Path(__file__).parent.parent / "frontend"
templates = Jinja2Templates(directory=str(frontend_dir / "templates"))
app.mount("/static", StaticFiles(directory=str(frontend_dir / "static")), name="static")


@app.get("/")
async def read_root(request: Request):
    """Strona główna."""
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/token", response_model=schemas.Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)
):
    """Endpoint logowania i generowania tokenu JWT."""
    user = auth.authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Nieprawidłowa nazwa użytkownika lub hasło",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


@app.post("/signup", response_model=schemas.UserResponse)
async def signup(user: schemas.UserCreate, db: Session = Depends(get_db)):
    """Endpoint rejestracji nowego użytkownika."""
    db_user = db.query(models.User).filter(models.User.username == user.username).first()
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Użytkownik o tej nazwie już istnieje",
        )
    hashed_password = auth.get_password_hash(user.password)
    db_user = models.User(username=user.username, password_hash=hashed_password)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


@app.get("/users/me", response_model=schemas.UserResponse)
async def read_users_me(current_user: models.User = Depends(auth.get_current_user)):
    """Endpoint zwracający dane aktualnie zalogowanego użytkownika."""
    return current_user


# Tutaj dodajemy kolejne routery z endpointami
# Np. app.include_router(users_router)
# Np. app.include_router(sessions_router)
# Np. app.include_router(rounds_router)


@app.get("/health")
async def health_check():
    """Endpoint sprawdzający stan aplikacji."""
    return {"status": "ok"} 