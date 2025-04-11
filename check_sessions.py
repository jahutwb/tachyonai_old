from sqlalchemy import create_engine, text

def check_sessions():
    engine = create_engine('sqlite:///tachyonai.db')
    with engine.connect() as conn:
        result = conn.execute(text('SELECT id, user_id, status, started_at, ended_at FROM sessions ORDER BY id DESC LIMIT 10'))
        print('ID | USER_ID | STATUS | STARTED_AT | ENDED_AT')
        print('-' * 100)
        for row in result:
            print(f'{row[0]} | {row[1]} | {row[2]} | {row[3]} | {row[4]}')

if __name__ == "__main__":
    check_sessions()
