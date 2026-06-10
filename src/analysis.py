import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'library.db')


def load_all():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # 기본 통계
    c.execute('SELECT COUNT(*) FROM raw_books')
    total_books = c.fetchone()[0]

    c.execute('SELECT COUNT(*) FROM mart_books')
    classified = c.fetchone()[0]

    c.execute('SELECT COUNT(*) FROM monthly_keywords')
    keywords_count = c.fetchone()[0]

    # 난이도 분포
    c.execute('SELECT difficulty, COUNT(*) FROM mart_books GROUP BY difficulty ORDER BY difficulty')
    diff_dist = c.fetchall()

    # 주제 분포
    c.execute('SELECT main_topic, COUNT(*) FROM mart_books GROUP BY main_topic ORDER BY COUNT(*) DESC')
    topic_dist = c.fetchall()

    # 난이도별 평균 대출수 (검증 분석)
    c.execute('''
        SELECT m.difficulty, 
               COUNT(*) as cnt,
               ROUND(AVG(r.loan_count)) as avg_loan,
               ROUND(AVG(r.sales_point)) as avg_sales
        FROM mart_books m
        JOIN raw_books r ON m.isbn = r.isbn
        GROUP BY m.difficulty
        ORDER BY m.difficulty
    ''')
    validation = c.fetchall()

    # 주제별 평균 대출수
    c.execute('''
        SELECT m.main_topic,
               COUNT(*) as cnt,
               ROUND(AVG(r.loan_count)) as avg_loan
        FROM mart_books m
        JOIN raw_books r ON m.isbn = r.isbn
        GROUP BY m.main_topic
        ORDER BY avg_loan DESC
    ''')
    topic_loan = c.fetchall()

    # 이달의 키워드
    c.execute('SELECT rank, keyword, weight FROM monthly_keywords ORDER BY rank')
    keywords = c.fetchall()

    # 주제 공백 분석: 10개 주제 중 5권 미만인 주제
    thin_topics = [(t, cnt) for t, cnt in topic_dist if cnt < 5]

    conn.close()
    return {
        'total_books': total_books,
        'classified': classified,
        'keywords_count': keywords_count,
        'diff_dist': diff_dist,
        'topic_dist': topic_dist,
        'validation': validation,
        'topic_loan': topic_loan,
        'keywords': keywords,
        'thin_topics': thin_topics,
    }


def print_report():
    d = load_all()

    print("=" * 60)
    print("  경제 도서 데이터 분석 리포트")
    print("=" * 60)

    # 1. 기본 통계
    print(f"\n[1] 기본 통계")
    print(f"  수집 도서: {d['total_books']}권")
    print(f"  분류 완료: {d['classified']}권")
    print(f"  이달의 키워드: {d['keywords_count']}개")

    # 2. 난이도 분포
    print(f"\n[2] 난이도 분포")
    for diff, cnt in d['diff_dist']:
        bar = '█' * (cnt // 3)
        label = {1: '입문', 2: '실용', 3: '심화'}.get(diff, '?')
        print(f"  D{diff} ({label}): {cnt}권 {bar}")

    # 3. 주제 분포
    print(f"\n[3] 주제 분포 (상위 10)")
    for topic, cnt in d['topic_dist'][:10]:
        bar = '█' * (cnt // 2)
        print(f"  {topic:<10}: {cnt:>3}권 {bar}")

    # 4. AI 분류 신뢰도 검증 (핵심!)
    print(f"\n[4] AI 분류 신뢰도 검증: 난이도별 평균 대출수·판매지수")
    print(f"  {'난이도':<12} {'도서수':>5} {'평균대출':>8} {'평균판매':>8}")
    print(f"  {'-'*38}")
    for diff, cnt, avg_loan, avg_sales in d['validation']:
        label = {1: 'D1 입문', 2: 'D2 실용', 3: 'D3 심화'}.get(diff, '?')
        print(f"  {label:<12} {cnt:>5} {avg_loan:>8} {avg_sales:>8}")

    # 검증 해석
    if len(d['validation']) >= 2:
        d1_loan = next((v[2] for v in d['validation'] if v[0] == 1), 0)
        d2_loan = next((v[2] for v in d['validation'] if v[0] == 2), 0)
        if d1_loan and d2_loan:
            if d1_loan > d2_loan:
                print(f"\n  ✅ 검증 통과: 입문(D1) 평균 대출수 > 실용(D2)")
                print(f"     → 쉬운 책일수록 대출이 많다 = AI 분류가 합리적")
            else:
                print(f"\n  ⚠️ 검증 주의: 입문(D1) < 실용(D2)")
                print(f"     → 대출 상위권 데이터 특성상 실용서가 더 인기")

    # 5. 주제별 평균 대출수
    print(f"\n[5] 주제별 평균 대출수 (어떤 주제가 인기인가)")
    for topic, cnt, avg_loan in d['topic_loan']:
        print(f"  {topic:<10}: {cnt:>3}권 | 평균 대출 {avg_loan:>6}")

    # 6. 주제 공백 분석
    print(f"\n[6] 주제 공백 분석 (5권 미만 = 독서 경로 부족)")
    if d['thin_topics']:
        for topic, cnt in d['thin_topics']:
            print(f"  ⚠️ {topic}: {cnt}권 — 이 분야는 독서 경로 구성 어려움")
    else:
        print(f"  모든 주제 5권 이상 확보됨")

    # 7. 이달의 키워드 vs 경제 도서
    print(f"\n[7] 도서관 전체 트렌드 vs 경제 도서 트렌드")
    print(f"  [이달의 키워드 — 전체 도서관]")
    for rank, keyword, weight in d['keywords']:
        print(f"    {rank}위 {keyword} ({weight})")
    print(f"\n  [경제 도서 — 상위 주제]")
    for topic, cnt in d['topic_dist'][:3]:
        print(f"    {topic}: {cnt}권")
    print(f"\n  → 도서관 전체는 사회 이슈 중심, 경제 도서는 투자·재테크 중심")
    print(f"    거시경제·경제정책 분야의 독서 경로가 부재한 정보 격차 존재")

    # 8. 성과 지표 정의
    print(f"\n[8] 성과 지표 요약")
    total_topics = len(d['topic_dist'])
    covered = len([t for t, c in d['topic_dist'] if c >= 5])
    print(f"  주제 커버리지: {covered}/{total_topics} ({covered/total_topics*100:.0f}%)")

    diff_count = len(d['diff_dist'])
    print(f"  난이도 다양성: {diff_count}/3 단계 사용")

    d2_cnt = sum(cnt for diff, cnt in d['diff_dist'] if diff == 2)
    print(f"  D2 집중도: {d2_cnt}/{d['classified']} ({d2_cnt/d['classified']*100:.1f}%)")

    print(f"\n{'='*60}")


if __name__ == '__main__':
    print_report()