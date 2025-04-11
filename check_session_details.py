from sqlalchemy import create_engine, text
import json

def check_session_details():
    engine = create_engine('sqlite:///tachyonai.db')
    with engine.connect() as conn:
        # Pobierz podstawowe informacje o sesji
        result = conn.execute(text('SELECT id, user_id, status, session_profit_factor, remaining_pairs FROM sessions WHERE id = 6'))
        print('ID | USER_ID | STATUS | PROFIT_FACTOR | REMAINING_PAIRS')
        print('-' * 100)
        for row in result:
            print(f'{row[0]} | {row[1]} | {row[2]} | {row[3]} | {row[4]}')
        
        # Pobierz rundy dla sesji
        result = conn.execute(text('SELECT COUNT(*) FROM rounds WHERE session_id = 6 AND result = "SUCCESS"'))
        success_count = result.fetchone()[0]
        
        result = conn.execute(text('SELECT COUNT(*) FROM rounds WHERE session_id = 6 AND result = "FAILURE"'))
        failure_count = result.fetchone()[0]
        
        print(f"\nLiczba sukcesów: {success_count}")
        print(f"Liczba porażek: {failure_count}")
        
        # Pobierz pule obrazów
        result = conn.execute(text('SELECT pos_pool_json, neg_pool_json FROM sessions WHERE id = 6'))
        row = result.fetchone()
        if row:
            pos_pool = json.loads(row[0]) if row[0] else []
            neg_pool = json.loads(row[1]) if row[1] else []
            
            print(f"\nPula pozytywna: {len(pos_pool)} obrazów")
            print(f"Pula negatywna: {len(neg_pool)} obrazów")
            
            # Pokaż sukcesy dla każdego obrazu
            print("\nSukcesy w puli pozytywnej:")
            for i, item in enumerate(pos_pool):
                print(f"  Obraz {i+1}: id={item.get('id')}, successes={item.get('successes', 0)}")
            
            print("\nSukcesy w puli negatywnej:")
            for i, item in enumerate(neg_pool):
                print(f"  Obraz {i+1}: id={item.get('id')}, successes={item.get('successes', 0)}")

if __name__ == "__main__":
    check_session_details()
