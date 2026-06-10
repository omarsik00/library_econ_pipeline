import requests
import sqlite3
import os
import time
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from pathlib import Path
from bs4 import BeautifulSoup, NavigableString

load_dotenv(dotenv_path=Path(__file__).parent.parent / '.env')

API_KEY       = os.getenv('DATA4LIBRARY_API_KEY')
ALADIN_KEY    = os.getenv('ALADIN_API_KEY')
NAVER_ID      = os.getenv('NAVER_CLIENT_ID')
NAVER_SECRET  = os.getenv('NAVER_CLIENT_SECRET')

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'library.db')

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                  'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}


# ─────────────────────────────────────────
# 1. 정보나루 API — 경제 인기 대출 도서
# ─────────────────────────────────────────
def fetch_books_from_library(page_size=200):
    """정보나루 loanItemSrch: dtl_kdc로 경제 인기대출 도서"""
    url = 'http://data4library.kr/api/loanItemSrch'
    params = {
        'authKey': API_KEY,
        'startDt': '2025-01-01',
        'endDt': '2026-06-06',
        'dtl_kdc': '32',
        'pageSize': page_size,
        'format': 'json'
    }
    resp = requests.get(url, params=params, timeout=10)
    data = resp.json()
    docs = data.get('response', {}).get('docs', [])
    print(f"  정보나루 수집: {len(docs)}권")
    return docs


# ─────────────────────────────────────────
# 2. 네이버 도서 API — 책 소개
# ─────────────────────────────────────────
def fetch_naver_description(isbn: str) -> str:
    url = 'https://openapi.naver.com/v1/search/book_adv.json'
    headers = {
        'X-Naver-Client-Id': NAVER_ID,
        'X-Naver-Client-Secret': NAVER_SECRET,
    }
    try:
        resp = requests.get(url, headers=headers,
                            params={'d_isbn': isbn}, timeout=5)
        items = resp.json().get('items', [])
        if items:
            return items[0].get('description', '')
    except Exception as e:
        print(f"    네이버 API 오류 ({isbn}): {e}")
    return ''


# ─────────────────────────────────────────
# 3. 알라딘 API — 판매지수
# ─────────────────────────────────────────
def fetch_sales_point(isbn: str) -> int:
    url = 'http://www.aladin.co.kr/ttb/api/ItemLookUp.aspx'
    params = {
        'ttbkey': ALADIN_KEY,
        'itemIdType': 'ISBN13',
        'ItemId': isbn,
        'output': 'js',
        'Version': '20131101',
    }
    try:
        resp = requests.get(url, params=params, timeout=5)
        items = resp.json().get('item', [])
        if items:
            return items[0].get('salesPoint', 0)
    except Exception as e:
        print(f"    알라딘 API 오류 ({isbn}): {e}")
    return 0

# ─────────────────────────────────────────
# YES24 크롤링 — 목차 수집
# ─────────────────────────────────────────
def crawl_yes24_toc(isbn: str) -> str:
    """YES24 상품페이지에서 전체 목차 크롤링"""
    try:
        # 1. ISBN 검색
        search_url = f'https://www.yes24.com/Product/Search?domain=BOOK&query={isbn}'
        resp = requests.get(search_url, headers=HEADERS, timeout=8)
        soup = BeautifulSoup(resp.text, 'lxml')

        link = soup.select_one('a.gd_name')
        if not link:
            return ''

        # 2. 상품 페이지
        product_url = 'https://www.yes24.com' + link['href']
        time.sleep(1)
        resp2 = requests.get(product_url, headers=HEADERS, timeout=8)
        soup2 = BeautifulSoup(resp2.text, 'lxml')

        # 3. 목차 추출 (전체, 자르지 않음)
        toc_div = soup2.select_one('#infoset_toc')
        if toc_div:
            for br in toc_div.find_all('br'):
                br.replace_with('\n')
            text = toc_div.get_text(strip=False)
            text = text.replace('목차', '', 1).strip()
            # 맨 끝 "펼쳐보기접어보기" 제거
            text = text.replace('펼쳐보기접어보기', '').strip()
            return text
    except Exception as e:
        print(f"    YES24 오류 ({isbn}): {e}")
    return ''

# ─────────────────────────────────────────
# 4. 정보나루 이달의키워드 크롤링 ← 크롤링 요건
# ─────────────────────────────────────────
def crawl_monthly_keywords() -> list:
    """정보나루 이달의키워드 페이지 크롤링 → [{rank, keyword, weight}]"""
    url = 'https://data4library.kr/thema/monthlyKeywords'
    results = []
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(resp.text, 'lxml')

        for li in soup.find_all('li'):
            em = li.find('em')
            span = li.find('span')
            if em and span:
                keyword = ''.join(
                    str(node).strip()
                    for node in li.children
                    if isinstance(node, NavigableString)
                ).strip()
                weight = em.get_text(strip=True)
                rank = span.get_text(strip=True)
                if keyword:
                    results.append({
                        'rank': int(rank),
                        'keyword': keyword,
                        'weight': float(weight)
                    })

        print(f"  이달의키워드 크롤링: {len(results)}개")
        if results:
            print(f"  샘플: {[r['keyword'] for r in results[:3]]}")

    except Exception as e:
        print(f"  크롤링 오류: {e}")
    return results


# ─────────────────────────────────────────
# 5. DB 저장
# ─────────────────────────────────────────

def save_keywords(keywords: list):
    """크롤링한 키워드를 DB에 저장"""
    if not keywords:
        return
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    for kw in keywords:
        cursor.execute('''
            INSERT INTO monthly_keywords (rank, keyword, weight)
            VALUES (?, ?, ?)
        ''', (kw['rank'], kw['keyword'], kw['weight']))
    conn.commit()
    conn.close()
    print(f"  키워드 {len(keywords)}개 DB 저장 완료")

def save_books(docs: list):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('SELECT isbn FROM raw_books')
    existing = {row[0] for row in cursor.fetchall()}

    saved = 0
    for item in docs:
        doc = item.get('doc', {})
        isbn      = doc.get('isbn13', '').strip()
        title     = doc.get('bookname', '').strip()
        author    = doc.get('authors', '').strip()
        class_no  = doc.get('class_no', '').strip()
        loan_count = int(doc.get('loan_count', 0) or 0)

        if not isbn or not title:
            continue
        if isbn in existing:
            continue

        print(f"  [{saved+1}] {title[:30]}")

        # 네이버 API로 소개 수집
        description = fetch_naver_description(isbn)
        time.sleep(0.3)

        # 알라딘 API로 판매지수
        sales_point = fetch_sales_point(isbn)
        time.sleep(0.3)

        cursor.execute('''
            INSERT OR IGNORE INTO raw_books
            (isbn, title, author, description,
             loan_count, class_no, sales_point)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (isbn, title, author, description,
              loan_count, class_no, sales_point))

        existing.add(isbn)
        saved += 1

    conn.commit()
    conn.close()
    print(f"\n도서 저장 완료: {saved}권")


# ─────────────────────────────────────────
# 6. 메인
# ─────────────────────────────────────────
def extract():
    print("=== 수집 시작 ===")

    # 이달의 키워드 크롤링 (크롤링 요건 충족)
    print("\n[1] 이달의키워드 크롤링")
    keywords = crawl_monthly_keywords()
    if keywords:
        print(f"  키워드 샘플: {keywords[:5]}")
        save_keywords(keywords)

    # 경제 도서 수집
    print("\n[2] 경제 도서 수집 (정보나루 + 네이버 + 알라딘)")
    docs = fetch_books_from_library(page_size=200)
    save_books(docs)

    print("\n=== 수집 완료 ===")


if __name__ == '__main__':
    extract()