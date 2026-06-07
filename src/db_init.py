import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'library.db')


def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 수집 레이어: 크롤링 + API 원본
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS raw_books (
            isbn         TEXT PRIMARY KEY,
            title        TEXT NOT NULL,
            author       TEXT,
            publisher    TEXT,
            pub_year     TEXT,
            description  TEXT,
            toc          TEXT,
            loan_count   INTEGER,
            class_no     TEXT,
            sales_point  INTEGER,
            review_rank  REAL,
            created_at   TEXT DEFAULT (datetime('now', 'localtime'))
        )
    ''')

    # 활용 레이어: AI 분류 결과
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS mart_books (
            isbn         TEXT PRIMARY KEY,
            title        TEXT NOT NULL,
            author       TEXT,
            difficulty   INTEGER,
            main_topic   TEXT,
            reason       TEXT,
            created_at   TEXT DEFAULT (datetime('now', 'localtime'))
        )
    ''')

    conn.commit()
    conn.close()
    print("DB 초기화 완료!")
    print(f"  위치: {os.path.abspath(DB_PATH)}")


if __name__ == '__main__':
    init_db()