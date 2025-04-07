from datetime import datetime, timedelta
from typing import Optional
import os
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from dotenv import load_dotenv

from .database import get_db
from . import models, schemas

load_dotenv()

# Konfiguracja JWT
SECRET_KEY = os.getenv("JWT_SECRET", "tajny_klucz_dla_jwt_token")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = 1440  # 24 godziny zamiast 30 minut

# Konfiguracja haszowania hasła
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Bearer token
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


def verify_password(plain_password, hashed_password):
    """Weryfikuje, czy hasło jest zgodne z hashem."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    """Generuje hash hasła."""
    return pwd_context.hash(password)


def get_user(db: Session, username: str) -> Optional[models.User]:
    """Pobiera użytkownika z bazy danych."""
    return db.query(models.User).filter(models.User.username == username).first()


def authenticate_user(db: Session, username: str, password: str):
    """Autentykuje użytkownika na podstawie nazwy użytkownika i hasła."""
    user = db.query(models.User).filter(models.User.username == username).first()
    if not user:
        return False
    if not verify_password(password, user.password_hash):
        return False
    return user


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Tworzy token JWT."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    """Pobiera bieżącego użytkownika na podstawie tokenu JWT."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Nieprawidłowe poświadczenia",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = schemas.TokenData(username=username)
    except JWTError:
        raise credentials_exception
    user = db.query(models.User).filter(models.User.username == token_data.username).first()
    if user is None:
        raise credentials_exception
    return user


def get_current_active_user(current_user: models.User = Depends(get_current_user)):
    """Pobiera bieżącego aktywnego użytkownika."""
    return current_user 