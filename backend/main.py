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
from .routers import sessions_router, rounds_router, images_router, user_router, price_router

# Inicjalizacja loggera
log_path = os.path.join("logs", "app.log")
os.makedirs(os.path.dirname(log_path), exist_ok=True)  # Upewniamy się, że katalog istnieje

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s - %(pathname)s:%(lineno)d",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_path, mode='a')  # Tryb 'a' (append) zamiast domyślnego 'w' (write)
    ]
)
logger = logging.getLogger(__name__)

# Testujemy zapis do logu
logger.debug("Test zapisu do logu")
logger.info("Konfiguracja loggera zakończona")

# Dodatkowa konfiguracja loggerów
logging.getLogger("uvicorn").setLevel(logging.INFO)
logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)

# Logowanie uruchomienia aplikacji
logger.info("Aplikacja uruchomiona")

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

# Rejestracja routerów API
app.include_router(sessions_router, prefix="/api", tags=["sessions"])
app.include_router(rounds_router, prefix="/api", tags=["rounds"])
app.include_router(images_router, prefix="/api", tags=["images"])
app.include_router(user_router, prefix="/api", tags=["users"])
app.include_router(price_router, prefix="/api", tags=["price"])


@app.get("/")
async def read_root(request: Request):
    """Strona główna."""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/game")
async def game_page(request: Request):
    """Strona z grą."""
    return templates.TemplateResponse("game.html", {"request": request})


@app.get("/summary")
async def summary_page(request: Request):
    """Strona z podsumowaniem sesji."""
    return templates.TemplateResponse("summary.html", {"request": request})


@app.get("/stats")
async def stats_page(request: Request):
    """Strona ze statystykami globalnymi."""
    return templates.TemplateResponse("stats.html", {"request": request})


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


@app.get("/signup")
async def signup_page(request: Request):
    """Strona z formularzem rejestracji."""
    return templates.TemplateResponse("signup.html", {"request": request})


@app.get("/login")
async def login_page(request: Request):
    """Strona z formularzem logowania."""
    return templates.TemplateResponse("login.html", {"request": request})


@app.get("/users/me", response_model=schemas.UserResponse)
async def read_users_me(current_user: models.User = Depends(auth.get_current_user)):
    """Endpoint zwracający dane aktualnie zalogowanego użytkownika."""
    return current_user


@app.get("/health")
async def health_check():
    """Endpoint sprawdzający stan aplikacji."""
    return {"status": "ok"}


@app.get("/ping")
async def ping():
    """Prosty endpoint sprawdzający czy serwer działa."""
    return {"ping": "pong"}


# Uruchomienie serwera gdy skrypt jest wywoływany bezpośrednio
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 