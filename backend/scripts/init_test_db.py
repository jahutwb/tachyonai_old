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
from sqlalchemy.orm import Session

# Dodaj katalog główny projektu do ścieżki Pythona
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.models import Base, engine, User, Image, Sessions, Rounds
from backend.schemas import ImageType, RoundStatus, SessionStatus

# Usuń istniejącą bazę danych testową, jeśli istnieje
if os.path.exists('test.db'):
    os.remove('test.db')

# Utwórz nową bazę danych
Base.metadata.create_all(engine)

# Stałe dla testów
TEST_USERNAME = "testuser"
TEST_PASSWORD = "password123"
TEST_IMAGE_COUNT = 30  # po 15 pozytywnych i negatywnych obrazów


def create_test_user():
    """Tworzy testowego użytkownika w bazie danych."""
    with Session(engine) as db:
        # Sprawdź, czy użytkownik już istnieje
        user = db.query(User).filter(User.username == TEST_USERNAME).first()
        if user:
            return user
        
        # Hashuj hasło
        hashed_password = bcrypt.hashpw(TEST_PASSWORD.encode('utf-8'), bcrypt.gensalt())
        
        # Utwórz nowego użytkownika
        new_user = User(
            username=TEST_USERNAME,
            hashed_password=hashed_password.decode('utf-8'),
            created_at=datetime.now()
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        return new_user


def create_test_images(user_id):
    """Tworzy testowe obrazy w bazie danych."""
    with Session(engine) as db:
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
                filepath=f"test_positive_{i}.jpg",
                type=ImageType.POSITIVE.value,
                embedding=json.dumps(embedding),
                img_metadata=json.dumps(metadata),
                success_count=random.randint(0, 10),
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
                filepath=f"test_negative_{i}.jpg",
                type=ImageType.NEGATIVE.value,
                embedding=json.dumps(embedding),
                img_metadata=json.dumps(metadata),
                success_count=random.randint(0, 10),
                created_at=datetime.now()
            )
            db.add(new_image)
        
        db.commit()


def create_test_session(user_id):
    """Tworzy testową sesję z rundami dla użytkownika."""
    with Session(engine) as db:
        # Pobierz obrazy
        pos_images = db.query(Image).filter(Image.type == ImageType.POSITIVE.value).all()
        neg_images = db.query(Image).filter(Image.type == ImageType.NEGATIVE.value).all()
        
        # Wybierz 3 pary obrazów dla sesji
        pos_pool = random.sample(pos_images, min(6, len(pos_images)))
        neg_pool = random.sample(neg_images, min(6, len(neg_images)))
        
        # Utwórz pulę JSON
        pos_pool_json = json.dumps([{
            "id": img.id,
            "filepath": img.filepath,
            "origin": "random"
        } for img in pos_pool])
        
        neg_pool_json = json.dumps([{
            "id": img.id,
            "filepath": img.filepath,
            "origin": "random"
        } for img in neg_pool])
        
        # Utwórz sesję
        session = Sessions(
            user_id=user_id,
            status=SessionStatus.COMPLETED.value,
            start_time=datetime.now() - timedelta(hours=1),
            end_time=datetime.now(),
            pos_pool_json=pos_pool_json,
            neg_pool_json=neg_pool_json,
            start_funds=1000.0,
            current_funds=1150.0,
            session_profit_factor=1.15,
            created_at=datetime.now()
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        
        # Utwórz rundy dla sesji
        for i in range(min(6, len(pos_pool))):
            if i >= len(pos_pool) or i >= len(neg_pool):
                break
                
            status = RoundStatus.COMPLETED.value
            success = random.choice([True, False])
            
            # Utwórz rundę
            round = Rounds(
                session_id=session.id,
                pos_image_id=pos_pool[i].id,
                neg_image_id=neg_pool[i].id,
                status=status,
                start_price=random.uniform(10000, 20000),
                end_price=random.uniform(10000, 20000),
                start_time=datetime.now() - timedelta(minutes=50 - i*10),
                end_time=datetime.now() - timedelta(minutes=49 - i*10),
                selected_pos=random.choice([True, False]),
                success=success,
                profit_factor=1.05 if success else 0.95,
                created_at=datetime.now() - timedelta(minutes=50 - i*10)
            )
            db.add(round)
        
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