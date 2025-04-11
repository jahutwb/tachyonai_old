from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import sys
import os

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import the database URL from your application
from backend.database import DATABASE_URL

# Create engine and session
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
db = SessionLocal()

# Query active sessions
result = db.execute(text("SELECT id, user_id, status, started_at, ended_at FROM sessions WHERE status = 'ACTIVE' ORDER BY started_at DESC LIMIT 5"))
active_sessions = result.fetchall()

print("Active Sessions:")
print("ID | User ID | Status | Started At | Ended At")
print("-" * 80)
for row in active_sessions:
    print(f"{row[0]} | {row[1]} | {row[2]} | {row[3]} | {row[4]}")
print(f"Total count: {len(active_sessions)}")

# For each active session, check if it has stimuli pools
print("\nChecking for stimuli pools in active sessions:")
for row in active_sessions:
    session_id = row[0]
    
    # Check for pool data directly in the session
    result = db.execute(text(f"SELECT pos_pool_json, neg_pool_json FROM sessions WHERE id = {session_id}"))
    pools_data = result.fetchone()
    if pools_data:
        has_pos_pool = pools_data[0] is not None
        has_neg_pool = pools_data[1] is not None
        print(f"Session {session_id}: Has positive pool: {has_pos_pool}, Has negative pool: {has_neg_pool}")
    
    # Also check for rounds in this session
    result = db.execute(text(f"SELECT COUNT(*) FROM rounds WHERE session_id = {session_id}"))
    rounds_count = result.scalar()
    print(f"Session {session_id}: {rounds_count} rounds")

db.close()
