#!/usr/bin/env python
"""
Script to load test data for the RoundResult schema changes testing.
"""

import os
import sys
import random
from datetime import datetime, timedelta

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import SessionLocal, engine
from backend.models import Base, User, Session as SessionModel, Round, Image, ImageTypeEnum
from backend.auth import get_password_hash
from backend.schemas import RoundResultEnum, SessionStatusEnum

# Create tables if they don't exist
Base.metadata.create_all(bind=engine)

# Create a database session
db = SessionLocal()

def create_test_users():
    """Create test users if they don't exist."""
    print("Creating test users...")
    
    # Check if test users already exist
    test_user = db.query(User).filter(User.username == "test_user").first()
    admin_user = db.query(User).filter(User.username == "admin_user").first()
    
    if not test_user:
        test_user = User(
            username="test_user",
            email="test@example.com",
            hashed_password=get_password_hash("test_password"),
            created_at=datetime.now()
        )
        db.add(test_user)
        print("Created test_user")
    
    if not admin_user:
        admin_user = User(
            username="admin_user",
            email="admin@example.com",
            hashed_password=get_password_hash("admin_password"),
            is_admin=True,
            created_at=datetime.now()
        )
        db.add(admin_user)
        print("Created admin_user")
    
    db.commit()
    return test_user, admin_user

def create_test_images():
    """Create test images if they don't exist."""
    print("Creating test images...")
    
    # Check if we already have enough images
    image_count = db.query(Image).count()
    if image_count >= 20:
        print(f"Already have {image_count} images, skipping creation")
        return
    
    # Create positive images
    for i in range(1, 11):
        image = Image(
            filename=f"positive_{i}.jpg",
            type=ImageTypeEnum.POSITIVE,
            total_successes=random.randint(0, 10),
            total_failures=random.randint(0, 5)
        )
        db.add(image)
    
    # Create negative images
    for i in range(1, 11):
        image = Image(
            filename=f"negative_{i}.jpg",
            type=ImageTypeEnum.NEGATIVE,
            total_successes=random.randint(0, 10),
            total_failures=random.randint(0, 5)
        )
        db.add(image)
    
    db.commit()
    print(f"Created {20 - image_count} new images")

def create_test_sessions(user):
    """Create test sessions for the user."""
    print("Creating test sessions...")
    
    # Check if the user already has sessions
    session_count = db.query(SessionModel).filter(SessionModel.user_id == user.id).count()
    if session_count >= 3:
        print(f"User already has {session_count} sessions, skipping creation")
        return
    
    # Get all images
    pos_images = db.query(Image).filter(Image.type == ImageTypeEnum.POSITIVE).all()
    neg_images = db.query(Image).filter(Image.type == ImageTypeEnum.NEGATIVE).all()
    
    # Create an active session
    active_session = SessionModel(
        user_id=user.id,
        status=SessionStatusEnum.ACTIVE,
        remaining_pairs=10,
        session_profit_factor=1.0,
        started_at=datetime.now() - timedelta(hours=1),
        pos_pool_json=[{"id": img.id, "successes": img.total_successes, "failures": img.total_failures} for img in pos_images],
        neg_pool_json=[{"id": img.id, "successes": img.total_successes, "failures": img.total_failures} for img in neg_images]
    )
    db.add(active_session)
    
    # Create a completed session
    completed_session = SessionModel(
        user_id=user.id,
        status=SessionStatusEnum.COMPLETED,
        remaining_pairs=0,
        session_profit_factor=1.15,
        started_at=datetime.now() - timedelta(days=1),
        ended_at=datetime.now() - timedelta(days=1) + timedelta(hours=2),
        pos_pool_json=[{"id": img.id, "successes": img.total_successes, "failures": img.total_failures} for img in pos_images],
        neg_pool_json=[{"id": img.id, "successes": img.total_successes, "failures": img.total_failures} for img in neg_images]
    )
    db.add(completed_session)
    
    # Create an abandoned session
    abandoned_session = SessionModel(
        user_id=user.id,
        status=SessionStatusEnum.ABANDONED,
        remaining_pairs=5,
        session_profit_factor=0.95,
        started_at=datetime.now() - timedelta(days=2),
        ended_at=datetime.now() - timedelta(days=2) + timedelta(hours=1),
        pos_pool_json=[{"id": img.id, "successes": img.total_successes, "failures": img.total_failures} for img in pos_images],
        neg_pool_json=[{"id": img.id, "successes": img.total_successes, "failures": img.total_failures} for img in neg_images]
    )
    db.add(abandoned_session)
    
    db.commit()
    print(f"Created {3 - session_count} new sessions")
    
    return active_session, completed_session, abandoned_session

def create_test_rounds(sessions):
    """Create test rounds for the sessions."""
    print("Creating test rounds...")
    
    active_session, completed_session, abandoned_session = sessions
    
    # Get all images
    pos_images = db.query(Image).filter(Image.type == ImageTypeEnum.POSITIVE).all()
    neg_images = db.query(Image).filter(Image.type == ImageTypeEnum.NEGATIVE).all()
    
    # Create rounds for the active session
    for i in range(1, 4):
        round_obj = Round(
            session_id=active_session.id,
            round_number=i,
            pos_image_id=random.choice(pos_images).id,
            neg_image_id=random.choice(neg_images).id,
            start_price=50000.0,
            left_action="BUY" if random.random() > 0.5 else "SELL",
            right_action="SELL" if random.random() > 0.5 else "BUY",
            created_at=datetime.now() - timedelta(hours=1) + timedelta(minutes=i*10)
        )
        db.add(round_obj)
    
    # Create rounds for the completed session
    for i in range(1, 11):
        round_obj = Round(
            session_id=completed_session.id,
            round_number=i,
            pos_image_id=random.choice(pos_images).id,
            neg_image_id=random.choice(neg_images).id,
            start_price=50000.0,
            end_price=50000.0 * (1 + random.uniform(-0.01, 0.01)),
            left_action="BUY" if random.random() > 0.5 else "SELL",
            right_action="SELL" if random.random() > 0.5 else "BUY",
            user_choice_side="LEFT" if random.random() > 0.5 else "RIGHT",
            user_action="BUY" if random.random() > 0.5 else "SELL",
            profit_fraction=random.uniform(-0.01, 0.01),
            result=RoundResultEnum.SUCCESS if random.random() > 0.5 else RoundResultEnum.FAILURE,
            created_at=datetime.now() - timedelta(days=1) + timedelta(minutes=i*10),
            completed_at=datetime.now() - timedelta(days=1) + timedelta(minutes=i*10 + 5)
        )
        db.add(round_obj)
    
    # Create rounds for the abandoned session
    for i in range(1, 6):
        round_obj = Round(
            session_id=abandoned_session.id,
            round_number=i,
            pos_image_id=random.choice(pos_images).id,
            neg_image_id=random.choice(neg_images).id,
            start_price=50000.0,
            end_price=50000.0 * (1 + random.uniform(-0.01, 0.01)),
            left_action="BUY" if random.random() > 0.5 else "SELL",
            right_action="SELL" if random.random() > 0.5 else "BUY",
            user_choice_side="LEFT" if random.random() > 0.5 else "RIGHT",
            user_action="BUY" if random.random() > 0.5 else "SELL",
            profit_fraction=random.uniform(-0.01, 0.01),
            result=RoundResultEnum.SUCCESS if random.random() > 0.5 else RoundResultEnum.FAILURE,
            created_at=datetime.now() - timedelta(days=2) + timedelta(minutes=i*10),
            completed_at=datetime.now() - timedelta(days=2) + timedelta(minutes=i*10 + 5)
        )
        db.add(round_obj)
    
    db.commit()
    print("Created test rounds")

def main():
    """Main function to load test data."""
    try:
        # Create test users
        test_user, admin_user = create_test_users()
        
        # Create test images
        create_test_images()
        
        # Create test sessions for the test user
        sessions = create_test_sessions(test_user)
        
        # Create test rounds for the sessions
        if sessions:
            create_test_rounds(sessions)
        
        print("Test data loaded successfully!")
    except Exception as e:
        print(f"Error loading test data: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    main()
