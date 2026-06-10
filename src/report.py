import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'library.db')
REPORT_DIR = os.path.join(os.path.dirname(__file__), '..', 'reports')


def generate_report() -> str:
    os.makedirs(REPORT_DIR, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # 기본 통계
    c.execute('SELECT COUNT(*) FROM raw_books')
    total = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM mart_books WHERE age_group='adult'")
    adult_cnt = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM mart_books WHERE age_group='child'")
    child_cnt = c.fetchone()[0]

    # 난이도 분포 (성인)
    c.execute("""
        SELECT difficulty, COUNT(*) FROM mart_books
        WHERE age_group='adult' GROUP BY difficulty ORDER BY difficulty
    """)
    diff_dist = c.fetchall()

    # 주제 분포 (성인)
    c.execute("""
        SELECT main_topic, COUNT(*) FROM mart_books
        WHERE age_group='adult' GROUP BY main_topic ORDER BY COUNT(*) DESC
    """)
    topic_dist = c.fetchall()

    # AI 신뢰도 검증
    c.execute("""
        SELECT m.difficulty, COUNT(*), ROUND(AVG(r.loan_count)) as avg_loan
        FROM mart_books m JOIN raw_books r ON m.isbn = r.isbn
        WHERE m.age_group='adult'
        GROUP BY m.difficulty ORDER BY m.difficulty
    """)
    validation = c.fetchall()

    # 주제 공백
    thin = [(t, cnt) for t, cnt in topic_dist if cnt < 5]

    # 이달의 키워드
    c.execute('SELECT rank, keyword, weight FROM monthly_keywords ORDER BY rank')
    keywords = c.fetchall()

    conn.close()

    diff_labels = {1: '입문(D1)', 2: '실용(D2)', 3: '심화(D3)'}
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    filename = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    filepath = os.path.join(REPORT_DIR, filename)

    lines = []
    lines.append(f"# 공공도서관 경제 도서 데이터 분석 리포트")
    lines.append(f"\n생성일시: {now}")
    lines.append(f"\n---\n")

    lines.append(f"## 1. 기본 통계\n")
    lines.append(f"| 항목 | 수치 |")
    lines.append(f"|------|------|")
    lines.append(f"| 수집 도서 | {total}권 |")
    lines.append(f"| 성인 도서 | {adult_cnt}권 |")
    lines.append(f"| 어린이 도서 | {child_cnt}권 |")
    lines.append(f"| 이달의 키워드 | {len(keywords)}개 |\n")

    lines.append(f"## 2. 성인 도서 난이도 분포\n")
    lines.append(f"| 난이도 | 도서수 | 비율 |")
    lines.append(f"|--------|--------|------|")
    for diff, cnt in diff_dist:
        pct = cnt / adult_cnt * 100
        lines.append(f"| {diff_labels.get(diff,'?')} | {cnt}권 | {pct:.1f}% |")
    lines.append("")

    lines.append(f"## 3. 주제 분포 (성인 도서)\n")
    lines.append(f"| 주제 | 도서수 |")
    lines.append(f"|------|--------|")
    for topic, cnt in topic_dist:
        lines.append(f"| {topic} | {cnt}권 |")
    lines.append("")

    lines.append(f"## 4. AI 분류 신뢰도 검증\n")
    lines.append(f"> 가설: 쉬운 책(D1)일수록 대출수가 높아야 한다\n")
    lines.append(f"| 난이도 | 도서수 | 평균 대출수 |")
    lines.append(f"|--------|--------|------------|")
    for diff, cnt, avg_loan in validation:
        lines.append(f"| {diff_labels.get(diff,'?')} | {cnt}권 | {avg_loan:,} |")

    d1_loan = next((v[2] for v in validation if v[0] == 1), 0)
    d2_loan = next((v[2] for v in validation if v[0] == 2), 0)
    if d1_loan and d2_loan:
        if d1_loan > d2_loan:
            lines.append(f"\n✅ **가설 지지**: D1({d1_loan:,}) > D2({d2_loan:,})")
            lines.append(f"\n어린이 도서 분리 후 성인 도서만 분석하니 쉬운 책일수록 대출이 많다는 가설이 성립했습니다.")
        else:
            lines.append(f"\n⚠️ **가설 기각**: D1({d1_loan:,}) < D2({d2_loan:,})")
    lines.append("")

    lines.append(f"## 5. 주제 공백 분석\n")
    if thin:
        lines.append(f"> 5권 미만 주제 = 독서 경로 구성 어려움\n")
        for topic, cnt in thin:
            lines.append(f"- **{topic}**: {cnt}권")
    else:
        lines.append(f"모든 주제 5권 이상 확보됨")
    lines.append("")

    lines.append(f"## 6. 이달의 키워드 (도서관 전체 대출 트렌드)\n")
    lines.append(f"| 순위 | 키워드 | 가중치 |")
    lines.append(f"|------|--------|--------|")
    for rank, keyword, weight in keywords:
        lines.append(f"| {rank}위 | {keyword} | {weight} |")
    lines.append("")

    lines.append(f"## 7. 핵심 인사이트\n")
    lines.append(f"- **도서관 전체 트렌드**: 사회이슈(차별·평등·혐오) 중심")
    lines.append(f"- **경제 도서 트렌드**: 투자·재테크 편중")
    lines.append(f"- **정보 격차**: 거시경제·경제교양·돈관리 분야 독서 경로 부재")
    lines.append(f"- **서비스 필요성**: 시민의 경제적 고민을 독서 경로로 연결하는 공공 서비스 필요")

    content = '\n'.join(lines)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"리포트 저장 완료: {filepath}")
    return filepath


if __name__ == '__main__':
    generate_report()