import streamlit as st
import sqlite3
import pandas as pd
import os

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'library.db')


def get_conn():
    return sqlite3.connect(DB_PATH)


st.set_page_config(page_title="경제 도서 분석 대시보드", layout="wide")
st.title("📚 공공도서관 경제 도서 데이터 분석")
st.caption("정보나루 인기대출 도서 기반 | ETL 파이프라인 미니 프로젝트")

# ── 데이터 로드 ──────────────────────────────────────
conn = get_conn()
df_raw = pd.read_sql('SELECT * FROM raw_books', conn)
df_mart = pd.read_sql('SELECT * FROM mart_books', conn)
df_kw = pd.read_sql('SELECT * FROM monthly_keywords ORDER BY rank', conn)
conn.close()

df = pd.merge(df_mart, df_raw[['isbn', 'loan_count', 'sales_point', 'description']],
              on='isbn', how='left')
df_adult = df[df['age_group'] == 'adult'].copy()
df_child = df[df['age_group'] == 'child'].copy()

# ── 탭 ───────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs([
    "📊 현황 분석", "🔍 AI 분류 검증", "📖 도서 탐색", "🔑 이달의 키워드"
])

# ────────────────────────────────────────────────────
# 탭 1: 현황 분석
# ────────────────────────────────────────────────────
with tab1:
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("수집 도서", f"{len(df_raw)}권")
    col2.metric("성인 도서", f"{len(df_adult)}권")
    col3.metric("어린이 도서", f"{len(df_child)}권")
    col4.metric("이달의 키워드", f"{len(df_kw)}개")

    st.divider()

    col_a, col_b = st.columns(2)

    with col_a:
        st.subheader("성인 도서 난이도 분포")
        diff_map = {1: 'D1 입문', 2: 'D2 실용', 3: 'D3 심화'}
        diff_counts = df_adult['difficulty'].map(diff_map).value_counts().sort_index()
        st.bar_chart(diff_counts)
        d1_pct = len(df_adult[df_adult['difficulty'] == 1]) / len(df_adult) * 100
        st.info(f"입문(D1) {d1_pct:.1f}% — 경제 지식 없어도 읽을 수 있는 교양서 위주")

    with col_b:
        st.subheader("주제 분포 (성인 도서)")
        topic_counts = df_adult['main_topic'].value_counts()
        st.bar_chart(topic_counts)
        thin = topic_counts[topic_counts < 5]
        if len(thin) > 0:
            st.warning(f"주제 공백 ({len(thin)}개): {', '.join(thin.index)}")

    st.divider()
    st.subheader("연령대 분포")
    age_counts = pd.Series({
        '성인 도서': len(df_adult),
        '어린이 도서': len(df_child)
    })
    st.bar_chart(age_counts)
    st.caption("어린이 도서는 도서 탐색 탭에서 따로 조회할 수 있어요.")

    st.divider()
    if st.button("📄 리포트 생성 (마크다운)"):
        import sys
        sys.path.append(os.path.dirname(__file__))
        from report import generate_report
        filepath = generate_report()
        st.success(f"리포트 저장 완료: `{filepath}`")
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        st.download_button(
            label="⬇️ 리포트 다운로드",
            data=content,
            file_name=os.path.basename(filepath),
            mime='text/markdown'
        )

# ────────────────────────────────────────────────────
# 탭 2: AI 분류 검증
# ────────────────────────────────────────────────────
with tab2:
    st.subheader("AI 분류 신뢰도 검증 (성인 도서 기준)")
    st.caption("가설: 쉬운 책(D1)일수록 대출수·판매지수가 높아야 한다")

    validation = df_adult.groupby('difficulty').agg(
        도서수=('isbn', 'count'),
        평균대출수=('loan_count', 'mean'),
        평균판매지수=('sales_point', 'mean')
    ).round(0)
    validation.index = validation.index.map({1: 'D1 입문', 2: 'D2 실용', 3: 'D3 심화'})
    st.dataframe(validation, use_container_width=True)

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("난이도별 평균 대출수")
        st.bar_chart(validation['평균대출수'])
    with col2:
        st.subheader("난이도별 평균 판매지수")
        st.bar_chart(validation['평균판매지수'])

    d1_loan = df_adult[df_adult['difficulty'] == 1]['loan_count'].mean()
    d2_loan = df_adult[df_adult['difficulty'] == 2]['loan_count'].mean()
    if d1_loan > d2_loan:
        st.success(
            f"✅ 가설 지지: D1 평균 대출수({d1_loan:.0f}) > D2({d2_loan:.0f})\n\n"
            "어린이 도서를 분리한 후 성인 도서만 분석하니 "
            "쉬운 책일수록 대출이 많다는 가설이 성립했습니다. "
            "AI 분류가 합리적임을 간접 확인했습니다."
        )
    else:
        st.warning(f"⚠️ 가설 기각: D1({d1_loan:.0f}) < D2({d2_loan:.0f})")

    st.divider()
    st.subheader("주제별 평균 대출수 (성인)")
    topic_loan = df_adult.groupby('main_topic')['loan_count'].mean().sort_values(ascending=False).round(0)
    st.bar_chart(topic_loan)

# ────────────────────────────────────────────────────
# 탭 3: 도서 탐색
# ────────────────────────────────────────────────────
with tab3:
    st.subheader("도서 탐색")

    col1, col2, col3 = st.columns(3)
    with col1:
        sel_age = st.selectbox("대상", ['성인', '어린이', '전체'])
    with col2:
        diff_options = ['전체', 'D1 입문', 'D2 실용', 'D3 심화']
        sel_diff = st.selectbox("난이도", diff_options,
                                disabled=(sel_age == '어린이'))
    with col3:
        topics = ['전체'] + sorted(df_adult['main_topic'].unique().tolist())
        sel_topic = st.selectbox("주제", topics)

    # 필터 적용
    if sel_age == '성인':
        filtered = df_adult.copy()
    elif sel_age == '어린이':
        filtered = df_child.copy()
    else:
        filtered = df.copy()

    if sel_diff != '전체' and sel_age != '어린이':
        diff_num = {'D1 입문': 1, 'D2 실용': 2, 'D3 심화': 3}[sel_diff]
        filtered = filtered[filtered['difficulty'] == diff_num]
    if sel_topic != '전체':
        filtered = filtered[filtered['main_topic'] == sel_topic]

    sort_by = st.radio("정렬", ['대출수 높은 순', '제목순'], horizontal=True)
    if sort_by == '대출수 높은 순':
        filtered = filtered.sort_values('loan_count', ascending=False)
    else:
        filtered = filtered.sort_values('title')

    st.caption(f"검색 결과: {len(filtered)}권")

    for _, row in filtered.head(20).iterrows():
        age_label = '👶 어린이' if row.get('age_group') == 'child' else '🧑 성인'
        diff_label = {1: '🟢 입문', 2: '🟡 실용', 3: '🔴 심화'}.get(row['difficulty'], '⚪')
        loan = int(row['loan_count']) if pd.notna(row['loan_count']) else 0

        with st.expander(f"{age_label} {diff_label} | {row['title'][:40]} (대출 {loan:,})"):
            st.write(f"**저자:** {row['author']}")
            if row.get('age_group') == 'adult':
                st.write(f"**난이도:** D{row['difficulty']} | **주제:** {row['main_topic']}")
            st.write(f"**대출수:** {loan:,} | **판매지수:** {int(row.get('sales_point', 0) or 0):,}")
            if row.get('reason'):
                st.write(f"**AI 분류 사유:** {row['reason']}")
            if row.get('description'):
                st.write(f"**소개:** {str(row['description'])[:200]}...")

# ────────────────────────────────────────────────────
# 탭 4: 이달의 키워드
# ────────────────────────────────────────────────────
with tab4:
    st.subheader("🔑 이달의 키워드 (전체 도서관 대출 트렌드)")
    st.caption("정보나루 이달의키워드 페이지 크롤링")

    if len(df_kw) > 0:
        kw_chart = df_kw.set_index('keyword')['weight']
        st.bar_chart(kw_chart)

        st.dataframe(
            df_kw[['rank', 'keyword', 'weight']].rename(
                columns={'rank': '순위', 'keyword': '키워드', 'weight': '가중치'}
            ),
            use_container_width=True,
            hide_index=True
        )

        st.divider()
        st.subheader("트렌드 비교: 도서관 전체 vs 경제 도서")

        col1, col2 = st.columns(2)
        with col1:
            st.write("**📚 도서관 전체 — 이달의 키워드**")
            for _, row in df_kw.iterrows():
                st.write(f"  {int(row['rank'])}위 **{row['keyword']}** ({row['weight']})")
        with col2:
            st.write("**💰 경제 도서 — 상위 주제 (성인)**")
            for topic, cnt in df_adult['main_topic'].value_counts().head(5).items():
                st.write(f"  **{topic}**: {cnt}권")

        st.info(
            "📌 **핵심 발견:** 도서관 전체 트렌드는 사회이슈(차별·평등·혐오) 중심인 반면, "
            "경제 도서 대출은 투자·재테크에 집중되어 있습니다.\n\n"
            "거시경제·경제교양·돈관리 분야의 독서 경로가 부재하여 "
            "**경제 정보 격차**가 존재합니다. "
            "이는 시민의 경제적 고민을 독서 경로로 연결하는 서비스의 필요성을 보여줍니다."
        )
    else:
        st.warning("키워드 데이터가 없습니다.")

