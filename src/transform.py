import os
import sqlite3
import time
import json
from google import genai
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(dotenv_path=Path(__file__).parent.parent / '.env')

client = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'library.db')


def classify_book(title, author, description):
    """Gemini로 난이도 + 주제 분류"""
    prompt = (
        "당신은 경제/금융 도서 분류 전문가입니다.\n"
        "아래 도서 정보를 보고 난이도와 주제를 분류하세요.\n\n"
        f"[도서명] {title}\n"
        f"[저자] {author}\n"
        f"[소개] {description[:500] if description else '정보 없음'}\n\n"
        "분류 기준:\n"
        "difficulty (1~3):\n"
        "  1 = 입문 (경제 지식 없어도 읽을 수 있음, 어린이/청소년 포함)\n"
        "  2 = 실용 (기본 개념을 알면 실천할 수 있는 수준)\n"
        "  3 = 심화 (전문 용어, 분석 기법, 이론적 깊이 있음)\n\n"
        "main_topic (아래 중 하나만 선택):\n"
        "  돈관리, 투자입문, 주식투자, ETF/펀드, 부동산,\n"
        "  경제교양, 거시경제, 자기계발, 기업분석, 노후준비\n\n"
        "반드시 아래 JSON 형식으로만 답하세요. 다른 텍스트 없이.\n"
        '{"difficulty":2,"main_topic":"투자입문","reason":"2문장 이내 이유"}'
    )

    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt
        )
        result = response.text.strip()
        clean = result.replace('```json', '').replace('```', '').strip()
        data = json.loads(clean)
        return data
    except Exception as e:
        print(f"  API 오류, 건너뜀: {e}")
        return None


def transform():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # raw_books에서 읽기
    cursor.execute('SELECT isbn, title, author, description FROM raw_books')
    books = cursor.fetchall()

    # 이미 분류된 건 건너뛰기
    cursor.execute('SELECT isbn FROM mart_books')
    done = {row[0] for row in cursor.fetchall()}
    conn.close()

    todo = [(isbn, title, author, desc)
            for isbn, title, author, desc in books
            if isbn not in done]

    print(f"총 {len(books)}권 중 {len(todo)}권 분류 시작...\n")

    saved = 0
    for i, (isbn, title, author, desc) in enumerate(todo, 1):
        result = classify_book(title, author, desc)
        time.sleep(1)

        if result and result.get('difficulty'):
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO mart_books
                (isbn, title, author, difficulty, main_topic, reason)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                isbn, title, author,
                result['difficulty'],
                result.get('main_topic', ''),
                result.get('reason', '')
            ))
            conn.commit()
            conn.close()
            saved += 1
            print(f"[{i}/{len(todo)}] D{result['difficulty']} {result.get('main_topic','')} | {title[:25]}")
        else:
            print(f"[{i}/{len(todo)}] 실패 | {title[:25]}")

    print(f"\n완료! {saved}권 분류 저장")


if __name__ == '__main__':
    transform()