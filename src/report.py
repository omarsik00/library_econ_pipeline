from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'library.db')
REPORT_DIR = os.path.join(os.path.dirname(__file__), '..', 'reports')


def _load_data():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM raw_books'); total_books = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM mart_books WHERE age_group='adult'"); adult_cnt = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM mart_books WHERE age_group='child'"); child_cnt = c.fetchone()[0]
    c.execute('SELECT COUNT(*) FROM monthly_keywords'); keywords_count = c.fetchone()[0]
    c.execute("SELECT difficulty, COUNT(*) FROM mart_books WHERE age_group='adult' GROUP BY difficulty ORDER BY difficulty")
    diff_dist = c.fetchall()
    c.execute("SELECT main_topic, COUNT(*) FROM mart_books WHERE age_group='adult' GROUP BY main_topic ORDER BY COUNT(*) DESC")
    topic_dist = c.fetchall()
    c.execute("""SELECT m.difficulty, COUNT(*), ROUND(AVG(r.loan_count))
                 FROM mart_books m JOIN raw_books r ON m.isbn = r.isbn
                 WHERE m.age_group='adult' GROUP BY m.difficulty ORDER BY m.difficulty""")
    validation = c.fetchall()
    c.execute('SELECT rank, keyword, weight FROM monthly_keywords ORDER BY rank')
    keywords = c.fetchall()
    conn.close()
    return {
        'total_books': total_books, 'adult_cnt': adult_cnt, 'child_cnt': child_cnt,
        'keywords_count': keywords_count, 'diff_dist': diff_dist, 'topic_dist': topic_dist,
        'validation': validation, 'keywords': keywords,
        'thin_topics': [(t, cnt) for t, cnt in topic_dist if cnt < 5]
    }


def _make_table(data, font_name):
    t = Table(data, hAlign='LEFT')
    t.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), font_name),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#16213e')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#f8f8f8'), colors.white]),
        ('GRID', (0, 0), (-1, -1), 0.3, colors.HexColor('#dddddd')),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
    ]))
    return t


def generate_report() -> str:
    os.makedirs(REPORT_DIR, exist_ok=True)
    d = _load_data()
    diff_labels = {1: '입문(D1)', 2: '실용(D2)', 3: '심화(D3)'}
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    filepath = os.path.join(REPORT_DIR, f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md")

    lines = []
    lines.append("# 공공도서관 경제 도서 데이터 분석 리포트")
    lines.append(f"\n생성일시: {now}\n\n---\n")
    lines.append("## 1. 기본 통계\n")
    lines.append("| 항목 | 수치 |")
    lines.append("|------|------|")
    lines.append(f"| 수집 도서 | {d['total_books']}권 |")
    lines.append(f"| 성인 도서 | {d['adult_cnt']}권 |")
    lines.append(f"| 어린이 도서 | {d['child_cnt']}권 |")
    lines.append(f"| 이달의 키워드 | {d['keywords_count']}개 |\n")
    lines.append("## 2. 성인 도서 난이도 분포\n")
    lines.append("| 난이도 | 도서수 | 비율 |")
    lines.append("|--------|--------|------|")
    for diff, cnt in d['diff_dist']:
        lines.append(f"| {diff_labels.get(diff,'?')} | {cnt}권 | {cnt/d['adult_cnt']*100:.1f}% |")
    lines.append("\n## 3. 주제 분포 (성인 도서)\n")
    lines.append("| 주제 | 도서수 |")
    lines.append("|------|--------|")
    for topic, cnt in d['topic_dist']:
        lines.append(f"| {topic} | {cnt}권 |")
    lines.append("\n## 4. AI 분류 신뢰도 검증\n")
    lines.append("> 가설: 쉬운 책(D1)일수록 대출수가 높아야 한다\n")
    lines.append("| 난이도 | 도서수 | 평균 대출수 |")
    lines.append("|--------|--------|------------|")
    for diff, cnt, avg_loan in d['validation']:
        lines.append(f"| {diff_labels.get(diff,'?')} | {cnt}권 | {avg_loan:,} |")
    d1 = next((v[2] for v in d['validation'] if v[0] == 1), 0)
    d2 = next((v[2] for v in d['validation'] if v[0] == 2), 0)
    if d1 and d2:
        lines.append(f"\n✅ **가설 지지**: D1({d1:,}) > D2({d2:,})" if d1 > d2 else f"\n⚠️ **가설 기각**: D1({d1:,}) < D2({d2:,})")
    lines.append("\n## 5. 주제 공백 분석\n")
    if d['thin_topics']:
        lines.append("> 5권 미만 주제 = 독서 경로 구성 어려움\n")
        for topic, cnt in d['thin_topics']:
            lines.append(f"- **{topic}**: {cnt}권")
    lines.append("\n## 6. 이달의 키워드\n")
    lines.append("| 순위 | 키워드 | 가중치 |")
    lines.append("|------|--------|--------|")
    for rank, keyword, weight in d['keywords']:
        lines.append(f"| {rank}위 | {keyword} | {weight} |")
    lines.append("\n## 7. 핵심 인사이트\n")
    lines += [
        "- **도서관 전체 트렌드**: 사회이슈(차별·평등·혐오) 중심",
        "- **경제 도서 트렌드**: 투자·재테크 편중",
        "- **정보 격차**: 거시경제·경제교양·돈관리 분야 독서 경로 부재",
        "- **서비스 필요성**: 시민의 경제적 고민을 독서 경로로 연결하는 공공 서비스 필요",
    ]
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(f"마크다운 리포트 저장: {filepath}")
    return filepath


def generate_pdf_report() -> str:
    os.makedirs(REPORT_DIR, exist_ok=True)
    filepath = os.path.join(REPORT_DIR, f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf")

    font_paths = [
        '/System/Library/Fonts/AppleSDGothicNeo.ttc',
        '/System/Library/Fonts/Supplemental/AppleGothic.ttf',
    ]
    font_registered = False
    for fp in font_paths:
        if os.path.exists(fp):
            try:
                pdfmetrics.registerFont(TTFont('Korean', fp))
                font_registered = True
                break
            except Exception:
                continue
    font_name = 'Korean' if font_registered else 'Helvetica'

    title_style = ParagraphStyle('title', fontName=font_name, fontSize=20, spaceAfter=6, textColor=colors.HexColor('#1a1a2e'))
    h2_style = ParagraphStyle('h2', fontName=font_name, fontSize=14, spaceBefore=16, spaceAfter=6, textColor=colors.HexColor('#16213e'))
    body_style = ParagraphStyle('body', fontName=font_name, fontSize=10, spaceAfter=4, leading=16, textColor=colors.HexColor('#333333'))
    caption_style = ParagraphStyle('caption', fontName=font_name, fontSize=9, textColor=colors.HexColor('#666666'), spaceAfter=8)

    d = _load_data()
    diff_labels = {1: 'D1 입문', 2: 'D2 실용', 3: 'D3 심화'}
    now = datetime.now().strftime('%Y-%m-%d %H:%M')

    doc = SimpleDocTemplate(filepath, pagesize=A4,
                            leftMargin=20*mm, rightMargin=20*mm,
                            topMargin=20*mm, bottomMargin=20*mm)
    story = []

    story.append(Paragraph("공공도서관 경제 도서 데이터 분석 리포트", title_style))
    story.append(Paragraph(f"생성일시: {now}", caption_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#cccccc')))
    story.append(Spacer(1, 8))

    story.append(Paragraph("1. 기본 통계", h2_style))
    story.append(_make_table([
        ['항목', '수치'],
        ['수집 도서', f"{d['total_books']}권"],
        ['성인 도서', f"{d['adult_cnt']}권"],
        ['어린이 도서', f"{d['child_cnt']}권"],
        ['이달의 키워드', f"{d['keywords_count']}개"],
    ], font_name))
    story.append(Spacer(1, 8))

    story.append(Paragraph("2. 성인 도서 난이도 분포", h2_style))
    diff_data = [['난이도', '도서수', '비율']]
    for diff, cnt in d['diff_dist']:
        diff_data.append([diff_labels.get(diff,'?'), f"{cnt}권", f"{cnt/d['adult_cnt']*100:.1f}%"])
    story.append(_make_table(diff_data, font_name))
    story.append(Spacer(1, 8))

    story.append(Paragraph("3. 주제 분포 (성인 도서)", h2_style))
    story.append(_make_table([['주제', '도서수']] + [[t, f"{c}권"] for t, c in d['topic_dist']], font_name))
    story.append(Spacer(1, 8))

    story.append(Paragraph("4. AI 분류 신뢰도 검증", h2_style))
    story.append(Paragraph("가설: 쉬운 책(D1)일수록 대출수가 높아야 한다", caption_style))
    val_data = [['난이도', '도서수', '평균 대출수']]
    for diff, cnt, avg_loan in d['validation']:
        val_data.append([diff_labels.get(diff,'?'), f"{cnt}권", f"{avg_loan:,}"])
    story.append(_make_table(val_data, font_name))
    d1 = next((v[2] for v in d['validation'] if v[0] == 1), 0)
    d2 = next((v[2] for v in d['validation'] if v[0] == 2), 0)
    if d1 and d2:
        txt = f"✅ 가설 지지: D1({d1:,.0f}) > D2({d2:,.0f})" if d1 > d2 else f"⚠️ 가설 기각: D1({d1:,.0f}) < D2({d2:,.0f})"
        story.append(Paragraph(txt, body_style))
    story.append(Spacer(1, 8))

    story.append(Paragraph("5. 주제 공백 분석", h2_style))
    story.append(Paragraph("5권 미만 주제 = 독서 경로 구성 어려움", caption_style))
    for topic, cnt in d['thin_topics']:
        story.append(Paragraph(f"• {topic}: {cnt}권", body_style))
    story.append(Spacer(1, 8))

    story.append(Paragraph("6. 이달의 키워드", h2_style))
    story.append(_make_table(
        [['순위', '키워드', '가중치']] + [[f"{r}위", kw, str(w)] for r, kw, w in d['keywords']],
        font_name
    ))
    story.append(Spacer(1, 8))

    story.append(Paragraph("7. 핵심 인사이트", h2_style))
    for insight in [
        "도서관 전체 트렌드는 사회이슈(차별·평등·혐오) 중심",
        "경제 도서 대출은 투자·재테크에 편중",
        "거시경제·경제교양·돈관리 분야 독서 경로 부재 = 경제 정보 격차 존재",
        "시민의 경제적 고민을 독서 경로로 연결하는 공공 서비스 필요",
    ]:
        story.append(Paragraph(f"• {insight}", body_style))

    doc.build(story)
    print(f"PDF 리포트 저장: {filepath}")
    return filepath


if __name__ == '__main__':
    generate_report()
    generate_pdf_report()