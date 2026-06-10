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
    """Gemini로 연령대 + 난이도 + 주제 분류"""
    prompt = (
        "당신은 경제/금융 도서 분류 전문가입니다.\n"
        "아래 도서 정보를 보고 분류하세요.\n\n"
        f"[도서명] {title}\n"
        f"[저자] {author}\n"
        f"[소개] {description[:500] if description else '정보 없음'}\n\n"
        "**중요: 아래 기준은 반드시 성인 독자 기준입니다.**\n"
        "어린이/청소년 대상 도서는 age_group을 'child'로 표시하고 difficulty는 0으로 하세요.\n\n"
        "age_group:\n"
        "  child = 어린이/청소년 대상 (표지·제목·소개에 어린이 대상임이 명확)\n"
        "  adult = 성인 대상\n\n"
        "difficulty (adult만 해당, 성인 독자 기준 내용의 깊이):\n"
        "  0 = 해당없음 (child인 경우)\n"
        "  1 = 입문 (경제 개념 설명 위주, 사례·스토리 중심, 수식 없음)\n"
        "      예: 돈의 속성, 부자 아빠 가난한 아빠, 경제 교양서\n"
        "  2 = 실용 (구체적 투자법·전략·매매 기법 포함, 실행 가이드)\n"
        "      예: ETF 투자법, 주식 매매 전략, 재무제표 보는 법\n"
        "  3 = 심화 (이론·모델·데이터 분석, 전문 용어 다수, 거시경제 분석)\n"
        "      예: 계량경제, 포트폴리오 이론, 거시경제 정책 분석\n\n"
        "main_topic (아래 중 하나만):\n"
        "  돈관리, 투자입문, 주식투자, ETF/펀드, 부동산,\n"
        "  경제교양, 거시경제, 자기계발, 기업분석, 노후준비\n\n"
        "JSON 형식으로만 답하세요:\n"
        '{"age_group":"adult","difficulty":1,"main_topic":"투자입문","reason":"2문장 이내"}'
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

    cursor.execute('SELECT isbn, title, author, description FROM raw_books')
    books = cursor.fetchall()

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
        time.sleep(4)

        if result and result.get('age_group'):
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO mart_books
                (isbn, title, author, difficulty, main_topic, reason, age_group)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                isbn, title, author,
                result.get('difficulty', 0),
                result.get('main_topic', ''),
                result.get('reason', ''),
                result.get('age_group', 'adult')
            ))
            conn.commit()
            conn.close()
            saved += 1
            print(f"[{i}/{len(todo)}] {result.get('age_group','?')} D{result.get('difficulty',0)} {result.get('main_topic','')} | {title[:25]}")
        else:
            print(f"[{i}/{len(todo)}] 실패 | {title[:25]}")

    print(f"\n완료! {saved}권 분류 저장")


if __name__ == '__main__':
    transform()