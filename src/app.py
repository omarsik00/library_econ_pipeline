import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
import sys

sys.path.append(os.path.dirname(__file__))

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'library.db')

# ── 페이지 설정 ──────────────────────────────────────
st.set_page_config(
    page_title="경제 도서 분석 대시보드",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
    .metric-card {
        background: #f8f9fa;
        border-radius: 12px;
        padding: 20px 24px;
        border-left: 4px solid #4f8ef7;
    }
    .metric-value { font-size: 2rem; font-weight: 700; color: #1a1a2e; margin: 4px 0; }
    .metric-label { font-size: 0.85rem; color: #666; text-transform: uppercase; letter-spacing: 0.5px; }
    .insight-box {
        background: linear-gradient(135deg, #667eea15, #764ba215);
        border-radius: 10px;
        padding: 16px 20px;
        border-left: 3px solid #667eea;
        margin: 8px 0;
    }
    .gap-badge {
        display: inline-block;
        background: #fff3cd;
        color: #856404;
        border: 1px solid #ffc107;
        border-radius: 20px;
        padding: 3px 12px;
        font-size: 0.82rem;
        margin: 3px;
    }
    .section-title {
        font-size: 1.1rem;
        font-weight: 600;
        color: #1a1a2e;
        margin-bottom: 12px;
        padding-bottom: 6px;
        border-bottom: 2px solid #f0f0f0;
    }
    div[data-testid="stTabs"] button { font-size: 0.9rem; }
</style>
""", unsafe_allow_html=True)


# ── 데이터 로드 ──────────────────────────────────────
@st.cache_data(ttl=60)
def load_data():
    conn = sqlite3.connect(DB_PATH)
    df_raw  = pd.read_sql('SELECT * FROM raw_books', conn)
    df_mart = pd.read_sql('SELECT * FROM mart_books', conn)
    df_kw   = pd.read_sql('SELECT * FROM monthly_keywords ORDER BY rank', conn)
    conn.close()
    df = pd.merge(df_mart, df_raw[['isbn','loan_count','sales_point','description']], on='isbn', how='left')
    return df, df_raw, df_kw

df, df_raw, df_kw = load_data()
df_adult = df[df['age_group'] == 'adult'].copy()
df_child = df[df['age_group'] == 'child'].copy()

# ── 헤더 ─────────────────────────────────────────────
st.title("📚 공공도서관 경제 도서 데이터 분석")
st.caption("정보나루 인기대출 기반 | ETL 파이프라인 미니 프로젝트")

# ── 사이드바 ──────────────────────────────────────────
with st.sidebar:
    st.markdown("### 📚 library_econ_pipeline")
    st.markdown("---")

    # 마지막 수집/분류 시간
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT MAX(created_at) FROM raw_books")
    last_extract = c.fetchone()[0]
    c.execute("SELECT MAX(created_at) FROM mart_books")
    last_transform = c.fetchone()[0]
    conn.close()

    st.markdown("**🕐 데이터 현황**")
    st.caption(f"마지막 수집: {last_extract or '없음'}")
    st.caption(f"마지막 분류: {last_transform or '없음'}")
    st.markdown("---")

    # 파이프라인
    st.markdown("**⚙️ 파이프라인 실행**")
    if st.button("🔄 수집 실행 (Extract)", use_container_width=True):
        with st.spinner("수집 중..."):
            from extract import extract
            extract()
        st.success("수집 완료!")
        st.cache_data.clear()
        st.rerun()

    if st.button("🤖 분류 실행 (Transform)", use_container_width=True):
        with st.spinner("AI 분류 중..."):
            from transform import transform
            transform()
        st.success("분류 완료!")
        st.cache_data.clear()
        st.rerun()

    st.markdown("---")

    # 리포트
    st.markdown("**📋 리포트 생성**")
    if st.button("📄 마크다운 리포트", use_container_width=True):
        from report import generate_report
        fp = generate_report()
        with open(fp, 'r', encoding='utf-8') as f:
            st.download_button("⬇️ 다운로드 (.md)", f.read(),
                               os.path.basename(fp), 'text/markdown',
                               use_container_width=True)
        st.success("생성 완료!")

    if st.button("📑 PDF 리포트", use_container_width=True):
        with st.spinner("PDF 생성 중..."):
            from report import generate_pdf_report
            fp = generate_pdf_report()
        with open(fp, 'rb') as f:
            st.download_button("⬇️ 다운로드 (.pdf)", f.read(),
                               os.path.basename(fp), 'application/pdf',
                               use_container_width=True)
        st.success("생성 완료!")

    st.markdown("---")
    st.caption("정보나루 인기대출 기반\nETL 파이프라인 미니 프로젝트")

# ── 탭 ───────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs([
    "📊 현황 분석", "🔍 AI 분류 검증", "📖 도서 탐색", "🔑 이달의 키워드"
])


# ────────────────────────────────────────────────────
# 탭 1: 현황 분석
# ────────────────────────────────────────────────────
with tab1:
    # 메트릭 카드
    c1, c2, c3, c4, c5 = st.columns(5)
    metrics = [
        (c1, "수집 도서", f"{len(df_raw):,}권", "#4f8ef7"),
        (c2, "성인 도서", f"{len(df_adult):,}권", "#22c55e"),
        (c3, "어린이 도서", f"{len(df_child):,}권", "#f59e0b"),
        (c4, "이달의 키워드", f"{len(df_kw)}개", "#8b5cf6"),
        (c5, "주제 공백", f"{len(df_adult['main_topic'].value_counts()[df_adult['main_topic'].value_counts() < 5])}개", "#ef4444"),
    ]
    for col, label, val, color in metrics:
        col.markdown(f"""
        <div class="metric-card" style="border-left-color:{color}">
            <div class="metric-label">{label}</div>
            <div class="metric-value" style="color:{color}">{val}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown('<div class="section-title">성인 도서 난이도 분포</div>', unsafe_allow_html=True)
        diff_map = {1: 'D1 입문', 2: 'D2 실용', 3: 'D3 심화'}
        diff_df = df_adult['difficulty'].map(diff_map).value_counts().reset_index()
        diff_df.columns = ['난이도', '도서수']
        diff_df = diff_df.sort_values('난이도')
        fig1 = px.bar(diff_df, x='난이도', y='도서수',
                      color='난이도',
                      color_discrete_map={'D1 입문': '#4f8ef7', 'D2 실용': '#22c55e', 'D3 심화': '#f59e0b'},
                      text='도서수')
        fig1.update_traces(textposition='outside')
        fig1.update_layout(showlegend=False, height=320,
                           plot_bgcolor='white', paper_bgcolor='white',
                           margin=dict(t=20, b=20))
        st.plotly_chart(fig1, use_container_width=True)
        d1_pct = len(df_adult[df_adult['difficulty'] == 1]) / len(df_adult) * 100
        st.info(f"입문(D1) {d1_pct:.1f}% — 대출 상위권은 교양·입문서 위주")

    with col_b:
        st.markdown('<div class="section-title">주제 분포 (성인 도서)</div>', unsafe_allow_html=True)
        topic_df = df_adult['main_topic'].value_counts().reset_index()
        topic_df.columns = ['주제', '도서수']
        colors_list = ['#ef4444' if c < 5 else '#4f8ef7' for c in topic_df['도서수']]
        fig2 = px.bar(topic_df, x='주제', y='도서수',
                      color='도서수',
                      color_continuous_scale=[[0, '#fca5a5'], [0.1, '#f87171'], [0.3, '#4f8ef7'], [1, '#1d4ed8']],
                      text='도서수')
        fig2.update_traces(textposition='outside')
        fig2.update_layout(showlegend=False, height=320,
                           plot_bgcolor='white', paper_bgcolor='white',
                           coloraxis_showscale=False,
                           margin=dict(t=20, b=20))
        st.plotly_chart(fig2, use_container_width=True)
        thin = topic_df[topic_df['도서수'] < 5]['주제'].tolist()
        if thin:
            badges = ''.join([f'<span class="gap-badge">⚠️ {t}</span>' for t in thin])
            st.markdown(f'주제 공백 (5권 미만): {badges}', unsafe_allow_html=True)

    # 핵심 인사이트
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown('<div class="section-title">핵심 인사이트</div>', unsafe_allow_html=True)
    insights = [
        ("📌", "주제 공백", "노후준비·거시경제·부동산·돈관리·기업분석이 5권 미만 — 이 고민을 가진 시민은 독서 경로를 찾기 어려움"),
        ("📊", "정보 격차", "도서관 전체 키워드(차별·평등·혐오)와 경제 도서(투자·재테크) 간 간극 존재"),
        ("✅", "AI 분류 검증", "어린이 도서 분리 후 D1 평균대출(8,447) > D2(7,226) — 가설 지지"),
    ]
    for icon, title, desc in insights:
        st.markdown(f"""
        <div class="insight-box">
            <strong>{icon} {title}</strong><br>
            <span style="color:#555;font-size:0.9rem">{desc}</span>
        </div>
        """, unsafe_allow_html=True)

# ────────────────────────────────────────────────────
# 탭 2: AI 분류 검증
# ────────────────────────────────────────────────────
with tab2:
    st.markdown('<div class="section-title">AI 분류 신뢰도 검증 (성인 도서 기준)</div>', unsafe_allow_html=True)
    st.caption("가설: 쉬운 책(D1)일수록 대출수가 높아야 한다")

    val_df = df_adult.groupby('difficulty').agg(
        도서수=('isbn', 'count'),
        평균대출수=('loan_count', 'mean'),
        평균판매지수=('sales_point', 'mean')
    ).round(0).reset_index()
    val_df['난이도'] = val_df['difficulty'].map({1: 'D1 입문', 2: 'D2 실용', 3: 'D3 심화'})

    st.dataframe(val_df[['난이도', '도서수', '평균대출수', '평균판매지수']],
                 use_container_width=True, hide_index=True)

    col1, col2 = st.columns(2)
    with col1:
        fig3 = px.bar(val_df, x='난이도', y='평균대출수',
                      color='난이도',
                      color_discrete_map={'D1 입문': '#4f8ef7', 'D2 실용': '#22c55e', 'D3 심화': '#f59e0b'},
                      title='난이도별 평균 대출수', text='평균대출수')
        fig3.update_traces(texttemplate='%{text:,.0f}', textposition='outside')
        fig3.update_layout(showlegend=False, height=320,
                           plot_bgcolor='white', paper_bgcolor='white',
                           margin=dict(t=40, b=20))
        st.plotly_chart(fig3, use_container_width=True)

    with col2:
        fig4 = px.bar(val_df, x='난이도', y='평균판매지수',
                      color='난이도',
                      color_discrete_map={'D1 입문': '#4f8ef7', 'D2 실용': '#22c55e', 'D3 심화': '#f59e0b'},
                      title='난이도별 평균 판매지수', text='평균판매지수')
        fig4.update_traces(texttemplate='%{text:,.0f}', textposition='outside')
        fig4.update_layout(showlegend=False, height=320,
                           plot_bgcolor='white', paper_bgcolor='white',
                           margin=dict(t=40, b=20))
        st.plotly_chart(fig4, use_container_width=True)

    d1_loan = df_adult[df_adult['difficulty'] == 1]['loan_count'].mean()
    d2_loan = df_adult[df_adult['difficulty'] == 2]['loan_count'].mean()
    if d1_loan > d2_loan:
        st.success(f"✅ 가설 지지: D1 평균 대출수({d1_loan:,.0f}) > D2({d2_loan:,.0f})\n\n"
                   "어린이 도서를 분리한 후 성인 도서만 분석하니 쉬운 책일수록 대출이 많다는 가설이 성립했습니다.")
    else:
        st.warning(f"⚠️ 가설 기각: D1({d1_loan:,.0f}) < D2({d2_loan:,.0f})")

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown('<div class="section-title">주제별 평균 대출수 (성인)</div>', unsafe_allow_html=True)
    topic_loan = df_adult.groupby('main_topic')['loan_count'].mean().sort_values(ascending=False).reset_index()
    topic_loan.columns = ['주제', '평균대출수']
    topic_loan['평균대출수'] = topic_loan['평균대출수'].round(0)
    fig5 = px.bar(topic_loan, x='주제', y='평균대출수',
                  color='평균대출수',
                  color_continuous_scale='Blues',
                  text='평균대출수')
    fig5.update_traces(texttemplate='%{text:,.0f}', textposition='outside')
    fig5.update_layout(height=380, plot_bgcolor='white', paper_bgcolor='white',
                       coloraxis_showscale=False, margin=dict(t=20, b=20))
    st.plotly_chart(fig5, use_container_width=True)


# ────────────────────────────────────────────────────
# 탭 3: 도서 탐색
# ────────────────────────────────────────────────────
with tab3:
    st.markdown('<div class="section-title">도서 탐색</div>', unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)
    with col1:
        sel_age = st.selectbox("대상", ['성인', '어린이', '전체'])
    with col2:
        sel_diff = st.selectbox("난이도", ['전체', 'D1 입문', 'D2 실용', 'D3 심화'],
                                disabled=(sel_age == '어린이'))
    with col3:
        topics = ['전체'] + sorted(df_adult['main_topic'].unique().tolist())
        sel_topic = st.selectbox("주제", topics)

    col4, col5 = st.columns([3, 1])
    with col4:
        search_query = st.text_input("🔍 제목 검색", placeholder="검색어 입력...")
    with col5:
        sort_by = st.selectbox("정렬", ['대출수 높은 순', '제목순'])

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
    if search_query:
        filtered = filtered[filtered['title'].str.contains(search_query, na=False)]
    if sort_by == '대출수 높은 순':
        filtered = filtered.sort_values('loan_count', ascending=False)
    else:
        filtered = filtered.sort_values('title')

    st.caption(f"검색 결과: {len(filtered)}권")
    st.markdown("<br>", unsafe_allow_html=True)

    # 카드 3열 그리드
    items = filtered.head(21).to_dict('records')
    for i in range(0, len(items), 3):
        cols = st.columns(3)
        for j, row in enumerate(items[i:i+3]):
            with cols[j]:
                diff_label = {1: '🟢 입문', 2: '🟡 실용', 3: '🔴 심화'}.get(row.get('difficulty'), '⚪')
                age_label = '👶' if row.get('age_group') == 'child' else '🧑'
                loan = int(row['loan_count']) if pd.notna(row.get('loan_count')) else 0
                sales = int(row['sales_point']) if pd.notna(row.get('sales_point')) else 0
                desc = str(row.get('description', ''))[:100] + '...' if row.get('description') else ''
                reason = str(row.get('reason', ''))

                st.markdown(f"""
                <div style="background:#f8f9fa;border-radius:10px;padding:16px;margin-bottom:12px;
                            border-top:3px solid {'#4f8ef7' if row.get('age_group')=='adult' else '#f59e0b'}">
                    <div style="font-size:0.75rem;color:#888;margin-bottom:4px">{age_label} {diff_label} · {row.get('main_topic','')}</div>
                    <div style="font-weight:600;font-size:0.9rem;color:#1a1a2e;margin-bottom:8px;line-height:1.4">{str(row['title'])[:45]}</div>
                    <div style="font-size:0.8rem;color:#555;margin-bottom:8px">{str(row.get('author',''))[:20]}</div>
                    <div style="display:flex;gap:12px;font-size:0.8rem">
                        <span style="color:#4f8ef7">📖 대출 {loan:,}</span>
                        <span style="color:#22c55e">💰 판매 {sales:,}</span>
                    </div>
                    {f'<div style="font-size:0.75rem;color:#888;margin-top:8px;line-height:1.4">{desc}</div>' if desc else ''}
                    {f'<div style="font-size:0.75rem;color:#999;margin-top:6px;font-style:italic">AI: {reason[:60]}</div>' if reason else ''}
                </div>
                """, unsafe_allow_html=True)


# ────────────────────────────────────────────────────
# 탭 4: 이달의 키워드
# ────────────────────────────────────────────────────
with tab4:
    st.markdown('<div class="section-title">🔑 이달의 키워드 (전체 도서관 대출 트렌드)</div>', unsafe_allow_html=True)
    st.caption("정보나루 이달의키워드 페이지 크롤링")

    if len(df_kw) > 0:
        # 키워드 가로 바 차트
        fig6 = px.bar(df_kw.sort_values('weight'), x='weight', y='keyword',
                      orientation='h',
                      color='weight',
                      color_continuous_scale='Purples',
                      text='weight',
                      labels={'weight': '가중치', 'keyword': '키워드'})
        fig6.update_traces(texttemplate='%{text:.3f}', textposition='outside')
        fig6.update_layout(height=380, plot_bgcolor='white', paper_bgcolor='white',
                           coloraxis_showscale=False, margin=dict(t=20, b=20))
        st.plotly_chart(fig6, use_container_width=True)

        # 테이블
        st.dataframe(
            df_kw[['rank', 'keyword', 'weight']].rename(
                columns={'rank': '순위', 'keyword': '키워드', 'weight': '가중치'}),
            use_container_width=True, hide_index=True
        )

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('<div class="section-title">트렌드 비교: 도서관 전체 vs 경제 도서</div>', unsafe_allow_html=True)

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**📚 도서관 전체 — 이달의 키워드**")
            for _, row in df_kw.iterrows():
                pct = row['weight'] / df_kw['weight'].sum() * 100
                st.markdown(f"""
                <div style="display:flex;align-items:center;gap:10px;margin:6px 0">
                    <span style="width:24px;color:#888;font-size:0.8rem">{int(row['rank'])}위</span>
                    <span style="font-weight:500">{row['keyword']}</span>
                    <div style="flex:1;background:#f0f0f0;border-radius:4px;height:6px">
                        <div style="width:{pct*2.5:.0f}%;background:#8b5cf6;border-radius:4px;height:6px"></div>
                    </div>
                    <span style="font-size:0.8rem;color:#888">{row['weight']}</span>
                </div>
                """, unsafe_allow_html=True)

        with col2:
            st.markdown("**💰 경제 도서 — 주제 분포 (성인)**")
            topic_counts = df_adult['main_topic'].value_counts()
            total = topic_counts.sum()
            for topic, cnt in topic_counts.head(7).items():
                pct = cnt / total * 100
                color = '#ef4444' if cnt < 5 else '#4f8ef7'
                st.markdown(f"""
                <div style="display:flex;align-items:center;gap:10px;margin:6px 0">
                    <span style="width:60px;font-size:0.8rem;color:#888">{cnt}권</span>
                    <span style="font-weight:500">{topic}</span>
                    <div style="flex:1;background:#f0f0f0;border-radius:4px;height:6px">
                        <div style="width:{pct:.0f}%;background:{color};border-radius:4px;height:6px"></div>
                    </div>
                    <span style="font-size:0.8rem;color:#888">{pct:.1f}%</span>
                </div>
                """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        st.info("📌 **핵심 발견:** 도서관 전체 트렌드는 사회이슈(차별·평등·혐오) 중심인 반면, "
                "경제 도서 대출은 투자·재테크에 집중되어 있습니다. "
                "거시경제·경제교양·돈관리 분야의 독서 경로가 부재하여 **경제 정보 격차**가 존재합니다.")
    else:
        st.warning("키워드 데이터가 없습니다.")