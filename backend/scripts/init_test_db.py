#!/usr/bin/env python3
"""
Skrypt inicjalizujący testową bazę danych dla testów E2E.
Tworzy użytkownika testowego oraz przykładowe dane.
"""

import os
import sys
import bcrypt
import json
import random
import numpy as np
from datetime import datetime, timedelta
from sqlalchemy.orm import Session as SQLSession

# Dodaj katalog główny projektu do ścieżki Pythona
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.database import engine
from backend.models import Base, User, Image, Session, Round
from backend.models import ImageTypeEnum, SessionStatusEnum, RoundResultEnum

# Usuń istniejącą bazę danych testową, jeśli istnieje
if os.path.exists('test.db'):
    os.remove('test.db')

# Utwórz nową bazę danych
Base.metadata.create_all(engine)

# Stałe dla testów
TEST_USERNAME = "testuser_3804"
TEST_PASSWORD = "password123"
TEST_IMAGE_COUNT = 30  # po 15 pozytywnych i negatywnych obrazów


def create_test_user():
    """Tworzy testowego użytkownika w bazie danych."""
    with SQLSession(engine) as db:
        # Sprawdź, czy użytkownik już istnieje
        user = db.query(User).filter(User.username == TEST_USERNAME).first()
        if user:
            return user
        
        # Hashuj hasło
        hashed_password = bcrypt.hashpw(TEST_PASSWORD.encode('utf-8'), bcrypt.gensalt())
        
        # Utwórz nowego użytkownika
        new_user = User(
            username=TEST_USERNAME,
            password_hash=hashed_password.decode('utf-8'),
            created_at=datetime.now()
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        return new_user


def create_test_images(user_id):
    """Tworzy testowe obrazy w bazie danych."""
    with SQLSession(engine) as db:
        # Sprawdź, czy już są obrazy
        if db.query(Image).count() > 0:
            return
        
        # Utwórz obrazy pozytywne
        for i in range(TEST_IMAGE_COUNT // 2):
            # Generuj losowy embedding (1-wymiarowy wektor)
            embedding = np.random.rand(512).tolist()
            
            # Metadata w formacie JSON
            metadata = {
                "width": 800,
                "height": 600,
                "format": "jpg",
                "source": "test_data"
            }
            
            new_image = Image(
                path=f"test_positive_{i}.jpg",
                type=ImageTypeEnum.POSITIVE,
                embedding=embedding,
                img_metadata=metadata,
                total_successes=random.randint(0, 10),
                created_at=datetime.now()
            )
            db.add(new_image)
        
        # Utwórz obrazy negatywne
        for i in range(TEST_IMAGE_COUNT // 2):
            # Generuj losowy embedding (1-wymiarowy wektor)
            embedding = np.random.rand(512).tolist()
            
            # Metadata w formacie JSON
            metadata = {
                "width": 800,
                "height": 600,
                "format": "jpg",
                "source": "test_data"
            }
            
            new_image = Image(
                path=f"test_negative_{i}.jpg",
                type=ImageTypeEnum.NEGATIVE,
                embedding=embedding,
                img_metadata=metadata,
                total_successes=random.randint(0, 10),
                created_at=datetime.now()
            )
            db.add(new_image)
        
        db.commit()


def create_test_session(user_id):
    """Tworzy testową sesję z rundami dla użytkownika."""
    with SQLSession(engine) as db:
        # Pobierz obrazy
        pos_images = db.query(Image).filter(Image.type == ImageTypeEnum.POSITIVE).all()
        neg_images = db.query(Image).filter(Image.type == ImageTypeEnum.NEGATIVE).all()
        
        # Wybierz 3 pary obrazów dla sesji
        pos_pool = random.sample(pos_images, min(6, len(pos_images)))
        neg_pool = random.sample(neg_images, min(6, len(neg_images)))
        
        # Utwórz pulę JSON
        pos_pool_json = [{
            "id": img.id,
            "path": img.path,
            "origin": "random"
        } for img in pos_pool]
        
        neg_pool_json = [{
            "id": img.id,
            "path": img.path,
            "origin": "random"
        } for img in neg_pool]
        
        # Utwórz sesję
        session = Session(
            user_id=user_id,
            status=SessionStatusEnum.ACTIVE.value,
            started_at=datetime.now() - timedelta(hours=1),
            pos_pool_json=pos_pool_json,
            neg_pool_json=neg_pool_json,
            session_profit_factor=1.0,
            remaining_pairs=6
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        
        # Utwórz rundy dla sesji (mniej rund niż par, aby pozostały wolne pary)
        for i in range(min(3, len(pos_pool))):
            if i >= len(pos_pool) or i >= len(neg_pool):
                break
                
            result = RoundResultEnum.SUCCESS.value if random.choice([True, False]) else RoundResultEnum.FAILURE.value
            
            # Utwórz rundę
            round_obj = Round(
                session_id=session.id,
                round_number=i+1,
                pos_image_id=pos_pool[i].id,
                neg_image_id=neg_pool[i].id,
                user_choice_side="LEFT" if random.choice([True, False]) else "RIGHT",
                user_action="BUY" if random.choice([True, False]) else "SELL",
                left_action="BUY",
                right_action="SELL",
                start_price=random.uniform(10000, 20000),
                end_price=random.uniform(10000, 20000),
                created_at=datetime.now() - timedelta(minutes=50 - i*10),
                completed_at=datetime.now() - timedelta(minutes=49 - i*10),
                result=result,
                profit_fraction=1.05 if result == RoundResultEnum.SUCCESS.value else 0.95
            )
            db.add(round_obj)
        
        db.commit()
        return session.id


def main():
    """Główna funkcja inicjalizująca bazę danych dla testów."""
    print("Inicjalizacja testowej bazy danych...")
    
    # Utwórz użytkownika testowego
    user = create_test_user()
    print(f"Utworzono użytkownika testowego: {user.username}")
    
    # Utwórz obrazy testowe
    create_test_images(user.id)
    print(f"Utworzono {TEST_IMAGE_COUNT} obrazów testowych")
    
    # Utwórz sesję testową
    session_id = create_test_session(user.id)
    print(f"Utworzono testową sesję ID: {session_id}")
    
    print("Inicjalizacja testowej bazy danych zakończona.")


if __name__ == "__main__":
    main() 