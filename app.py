import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
from openai import OpenAI
import pdfplumber
import io
import feedparser
import urllib.parse
import re
import requests
import zipfile
import xml.etree.ElementTree as ET
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

st.set_page_config(
    page_title="국내 주식 대시보드",
    page_icon="📈",
    layout="wide",
)

# 국내 주요 주식 10개 (Yahoo Finance 티커: 종목코드.KS 또는 .KQ)
STOCKS = {
    "삼성전자": "005930.KS",
    "SK하이닉스": "000660.KS",
    "LG에너지솔루션": "373220.KS",
    "삼성바이오로직스": "207940.KS",
    "현대차": "005380.KS",
    "POSCO홀딩스": "005490.KS",
    "카카오": "035720.KS",
    "네이버(NAVER)": "035420.KS",
    "셀트리온": "068270.KS",
    "KB금융": "105560.KS",
}

st.title("📈 국내 주식 대시보드")
st.caption("yfinance 기반 실시간 국내 주요 종목 10개 분석")

# ── 사이드바 ─────────────────────────────────────────────────
st.sidebar.title("📈 대시보드 설정")

# 1) API 키 (최상단 — 항상 보임)
st.sidebar.subheader("🔑 API 키 설정")
dart_api_key = st.sidebar.text_input(
    "🏛️ OpenDART API Key",
    type="password",
    placeholder="발급받은 DART API 키 입력",
    help="https://opendart.fss.or.kr 에서 무료 발급",
)
if dart_api_key:
    st.sidebar.success("DART 키 입력 완료", icon="✅")
else:
    st.sidebar.caption("공시 조회에 필요합니다.")

openai_api_key = st.sidebar.text_input(
    "🤖 OpenAI API Key",
    type="password",
    placeholder="sk-...",
    help="GPT-4o-mini 챗봇에 사용됩니다.",
)
if openai_api_key:
    st.sidebar.success("OpenAI 키 입력 완료", icon="✅")
else:
    st.sidebar.caption("AI 챗봇에 필요합니다.")

st.sidebar.divider()

# 2) 차트 설정
st.sidebar.subheader("⚙️ 차트 설정")
period_map = {
    "1개월": "1mo",
    "3개월": "3mo",
    "6개월": "6mo",
    "1년": "1y",
    "2년": "2y",
}
selected_period_label = st.sidebar.selectbox("조회 기간", list(period_map.keys()), index=2)
selected_period = period_map[selected_period_label]

interval_map = {
    "일봉": "1d",
    "주봉": "1wk",
    "월봉": "1mo",
}
selected_interval_label = st.sidebar.selectbox("차트 간격", list(interval_map.keys()), index=0)
selected_interval = interval_map[selected_interval_label]

# 3) 종목 선택
st.sidebar.subheader("📊 종목 선택")
selected_stocks = st.sidebar.multiselect(
    "종목",
    options=list(STOCKS.keys()),
    default=list(STOCKS.keys()),
    label_visibility="collapsed",
)

st.sidebar.divider()

# 4) 이메일 설정
st.sidebar.subheader("📧 이메일 발송 설정")
smtp_email = st.sidebar.text_input(
    "발신 이메일 계정",
    placeholder="example@gmail.com",
    help="Gmail 사용 시 Google 계정 이메일을 입력하세요.",
    key="smtp_email",
)
smtp_app_password = st.sidebar.text_input(
    "앱 비밀번호",
    type="password",
    placeholder="Gmail 앱 비밀번호 16자리",
    help="Gmail → 구글 계정 → 보안 → 앱 비밀번호에서 발급",
    key="smtp_app_password",
)
smtp_recipient = st.sidebar.text_input(
    "수신 이메일",
    placeholder="recipient@example.com",
    help="보고서를 받을 이메일 주소",
    key="smtp_recipient",
)
if smtp_email and smtp_app_password and smtp_recipient:
    st.sidebar.success("이메일 설정 완료", icon="✅")
else:
    st.sidebar.caption("보고서 이메일 발송에 필요합니다.")

st.sidebar.divider()
st.sidebar.caption("데이터: Yahoo Finance · Google News · OpenDART")


@st.cache_data(ttl=300)
def fetch_all_quotes(tickers: dict) -> pd.DataFrame:
    rows = []
    for name, ticker in tickers.items():
        try:
            info = yf.Ticker(ticker).fast_info
            rows.append({
                "종목명": name,
                "티커": ticker,
                "현재가": getattr(info, "last_price", None),
                "전일종가": getattr(info, "previous_close", None),
                "52주 최고": getattr(info, "year_high", None),
                "52주 최저": getattr(info, "year_low", None),
                "시가총액(억)": round(getattr(info, "market_cap", 0) / 1e8, 0) if getattr(info, "market_cap", None) else None,
            })
        except Exception:
            rows.append({"종목명": name, "티커": ticker})
    df = pd.DataFrame(rows)
    df["등락률(%)"] = ((df["현재가"] - df["전일종가"]) / df["전일종가"] * 100).round(2)
    df["등락금액"] = (df["현재가"] - df["전일종가"]).round(0)
    return df


@st.cache_data(ttl=300)
def fetch_history(ticker: str, period: str, interval: str) -> pd.DataFrame:
    return yf.download(ticker, period=period, interval=interval, progress=False, auto_adjust=True)


if not selected_stocks:
    st.warning("사이드바에서 종목을 1개 이상 선택해 주세요.")
    st.stop()

# ── 섹션 1: 시세 요약 ─────────────────────────────────────────
st.subheader("📊 종목 현황 요약")

with st.spinner("시세 데이터 수집 중..."):
    selected_tickers = {k: STOCKS[k] for k in selected_stocks}
    quote_df = fetch_all_quotes(selected_tickers)

# 등락률 색상 카드
cols = st.columns(min(len(selected_stocks), 5))
for i, (_, row) in enumerate(quote_df.iterrows()):
    col = cols[i % 5]
    change = row.get("등락률(%)", 0) or 0
    color = "🔴" if change < 0 else ("🔵" if change == 0 else "🟢")
    price = f"{row['현재가']:,.0f}" if pd.notna(row.get("현재가")) else "N/A"
    col.metric(
        label=f"{color} {row['종목명']}",
        value=f"₩{price}",
        delta=f"{change:+.2f}%" if pd.notna(change) else "N/A",
    )

st.divider()

# ── 섹션 2: 데이터 테이블 ──────────────────────────────────────
st.subheader("📋 상세 데이터 테이블")

display_df = quote_df[[
    "종목명", "현재가", "등락금액", "등락률(%)",
    "전일종가", "52주 최고", "52주 최저", "시가총액(억)"
]].copy()

def color_change(val):
    if pd.isna(val):
        return ""
    color = "red" if val < 0 else ("blue" if val == 0 else "green")
    return f"color: {color}; font-weight: bold"

styled = display_df.style.map(color_change, subset=["등락률(%)", "등락금액"]) \
    .format({
        "현재가": "{:,.0f}",
        "등락금액": "{:+,.0f}",
        "등락률(%)": "{:+.2f}%",
        "전일종가": "{:,.0f}",
        "52주 최고": "{:,.0f}",
        "52주 최저": "{:,.0f}",
        "시가총액(억)": "{:,.0f}",
    }, na_rep="N/A")

st.dataframe(styled, use_container_width=True, height=400)

st.divider()

# ── 섹션 3: 등락률 막대 차트 ──────────────────────────────────
st.subheader("📉 등락률 비교")

bar_df = quote_df.dropna(subset=["등락률(%)"])
fig_bar = px.bar(
    bar_df,
    x="종목명",
    y="등락률(%)",
    color="등락률(%)",
    color_continuous_scale=["red", "lightgray", "green"],
    color_continuous_midpoint=0,
    text="등락률(%)",
    title=f"등락률 비교 ({selected_period_label})",
)
fig_bar.update_traces(texttemplate="%{text:+.2f}%", textposition="outside")
fig_bar.update_layout(showlegend=False, height=420, xaxis_title="", yaxis_title="등락률 (%)")
st.plotly_chart(fig_bar, use_container_width=True)

st.divider()

# ── 섹션 4: 주가 추이 (멀티라인) ──────────────────────────────
st.subheader(f"📈 주가 추이 ({selected_period_label} / {selected_interval_label})")

chart_stock = st.selectbox("차트로 볼 종목", selected_stocks, key="chart_select")

with st.spinner(f"{chart_stock} 차트 데이터 로딩 중..."):
    hist = fetch_history(STOCKS[chart_stock], selected_period, selected_interval)

if hist.empty:
    st.warning(f"{chart_stock} 데이터를 불러올 수 없습니다.")
else:
    # Close 컬럼 처리 (MultiIndex 대응)
    close = hist["Close"]
    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, 0]

    tab1, tab2 = st.tabs(["캔들차트", "라인차트"])

    with tab1:
        fig_candle = go.Figure(data=[go.Candlestick(
            x=hist.index,
            open=hist["Open"].squeeze(),
            high=hist["High"].squeeze(),
            low=hist["Low"].squeeze(),
            close=close,
            name=chart_stock,
            increasing_line_color="red",
            decreasing_line_color="blue",
        )])
        fig_candle.update_layout(
            title=f"{chart_stock} 캔들차트",
            xaxis_title="날짜",
            yaxis_title="가격 (원)",
            height=500,
            xaxis_rangeslider_visible=False,
        )
        st.plotly_chart(fig_candle, use_container_width=True)

    with tab2:
        fig_line = go.Figure()
        fig_line.add_trace(go.Scatter(
            x=hist.index,
            y=close,
            mode="lines",
            name=chart_stock,
            line=dict(width=2, color="#1f77b4"),
        ))
        # 이동평균선 추가
        ma20 = close.rolling(20).mean()
        ma60 = close.rolling(60).mean()
        fig_line.add_trace(go.Scatter(x=hist.index, y=ma20, mode="lines",
                                      name="MA20", line=dict(width=1, color="orange", dash="dash")))
        fig_line.add_trace(go.Scatter(x=hist.index, y=ma60, mode="lines",
                                      name="MA60", line=dict(width=1, color="purple", dash="dot")))
        fig_line.update_layout(
            title=f"{chart_stock} 라인차트 + 이동평균",
            xaxis_title="날짜",
            yaxis_title="가격 (원)",
            height=500,
            hovermode="x unified",
        )
        st.plotly_chart(fig_line, use_container_width=True)

    # 거래량
    vol = hist["Volume"]
    if isinstance(vol, pd.DataFrame):
        vol = vol.iloc[:, 0]
    fig_vol = px.bar(x=hist.index, y=vol, title="거래량", labels={"x": "날짜", "y": "거래량"})
    fig_vol.update_layout(height=250)
    st.plotly_chart(fig_vol, use_container_width=True)

st.divider()

# ── 섹션 5: 정규화 비교 ────────────────────────────────────────
st.subheader("📊 정규화 주가 비교 (기준=100)")

# 최대 5개로 제한하여 과부하 방지
norm_stocks = selected_stocks[:5]
if len(selected_stocks) > 5:
    st.caption(f"⚡ 성능을 위해 상위 5개 종목만 표시합니다. (선택: {len(selected_stocks)}개)")

if st.button("📊 정규화 차트 불러오기", key="load_norm"):
    st.session_state.load_norm_chart = True

if st.session_state.get("load_norm_chart"):
    with st.spinner("비교 데이터 로딩 중..."):
        norm_data = {}
        for name in norm_stocks:
            h = fetch_history(STOCKS[name], selected_period, "1d")
            if not h.empty:
                c = h["Close"].squeeze()
                if isinstance(c, pd.Series) and not c.empty:
                    norm_data[name] = (c / c.iloc[0] * 100).rename(name)

    if norm_data:
        norm_df = pd.concat(norm_data.values(), axis=1)
        fig_norm = px.line(norm_df, title=f"정규화 주가 비교 ({selected_period_label})", height=450)
        fig_norm.update_layout(xaxis_title="날짜", yaxis_title="상대 수익률 (기준=100)", hovermode="x unified")
        fig_norm.add_hline(y=100, line_dash="dash", line_color="gray", annotation_text="기준선")
        st.plotly_chart(fig_norm, use_container_width=True)
else:
    st.info("버튼을 클릭하면 정규화 비교 차트를 불러옵니다.", icon="📊")

st.divider()

# ── 섹션 6: 기업 뉴스 ────────────────────────────────────────
st.subheader("📰 기업 관련 뉴스")
st.caption("Google News RSS 기반 실시간 뉴스 수집")

@st.cache_data(ttl=600)
def fetch_news(company_name: str, max_items: int = 5) -> list:
    query = urllib.parse.quote(f"{company_name} 주식")
    url = f"https://news.google.com/rss/search?q={query}&hl=ko&gl=KR&ceid=KR:ko"
    try:
        feed = feedparser.parse(url)
        results = []
        for entry in feed.entries[:max_items]:
            # 발행 시각 파싱
            published = ""
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                from time import mktime
                dt = datetime.fromtimestamp(mktime(entry.published_parsed))
                diff = datetime.now() - dt
                if diff.days > 0:
                    published = f"{diff.days}일 전"
                elif diff.seconds >= 3600:
                    published = f"{diff.seconds//3600}시간 전"
                else:
                    published = f"{diff.seconds//60}분 전"
            # 출처 추출
            source = ""
            if hasattr(entry, "source") and hasattr(entry.source, "title"):
                source = entry.source.title
            # 요약 태그 제거
            summary = re.sub(r"<[^>]+>", "", getattr(entry, "summary", ""))[:120]
            results.append({
                "title": entry.title,
                "link": entry.link,
                "published": published,
                "source": source,
                "summary": summary,
            })
        return results
    except Exception:
        return []

# 뉴스 UI
news_col1, news_col2 = st.columns([1, 3])
with news_col1:
    news_stock = st.selectbox(
        "종목 선택",
        options=selected_stocks,
        key="news_stock_select",
    )
    max_news = st.slider("최대 뉴스 수", 3, 10, 5)
    refresh_news = st.button("🔄 뉴스 새로고침", use_container_width=True)
    if refresh_news:
        st.cache_data.clear()

with news_col2:
    with st.spinner(f"'{news_stock}' 뉴스 수집 중..."):
        news_items = fetch_news(news_stock, max_news)

    if not news_items:
        st.warning("뉴스를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.", icon="⚠️")
    else:
        for i, item in enumerate(news_items):
            with st.container():
                col_title, col_meta = st.columns([5, 1])
                with col_title:
                    st.markdown(f"**[{item['title']}]({item['link']})**")
                    if item["summary"]:
                        st.caption(item["summary"] + "…")
                with col_meta:
                    if item["source"]:
                        st.caption(f"📌 {item['source']}")
                    if item["published"]:
                        st.caption(f"🕐 {item['published']}")
                if i < len(news_items) - 1:
                    st.markdown("<hr style='margin:6px 0;border-color:#2A4A68'>", unsafe_allow_html=True)

st.divider()

# ── 섹션 7: OpenDART 공시 정보 ───────────────────────────────
st.subheader("🏛️ 기업 공시 정보 (OpenDART)")
st.caption("금융감독원 DART 공시 시스템 기반 실시간 공시 조회")

# 외부 원본 파일 우선 사용, 없으면 프로젝트 내 파일 폴백
_EXT_CORPCODE = r"C:\Users\admin\AppData\Local\Temp\corpcode.csv"
_LOCAL_CORPCODE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "corpcode.csv")
CORPCODE_PATH = _EXT_CORPCODE if os.path.exists(_EXT_CORPCODE) else _LOCAL_CORPCODE

@st.cache_data(ttl=86400)
def load_corpcode() -> pd.DataFrame:
    """상장사(stock_code 있는 기업)만 필터링하여 로드."""
    df = pd.read_csv(CORPCODE_PATH, dtype=str, encoding="utf-8-sig",
                     usecols=["corp_code", "corp_name", "stock_code"])
    df = df.dropna(subset=["stock_code"])
    df = df[df["stock_code"].str.strip() != ""].reset_index(drop=True)
    return df

@st.cache_data(ttl=86400)
def search_corpcode(keyword: str) -> pd.DataFrame:
    """기업명 키워드 검색 (캐시된 상장사 목록 사용)."""
    df = load_corpcode()
    return df[df["corp_name"].str.contains(keyword, na=False, case=False)]

@st.cache_data(ttl=600)
def fetch_dart_disclosures(api_key: str, corp_code: str, bgn_de: str, end_de: str, pblntf_ty: str = "A") -> list:
    url = "https://opendart.fss.or.kr/api/list.json"
    params = {
        "crtfc_key": api_key,
        "corp_code": corp_code,
        "bgn_de": bgn_de,
        "end_de": end_de,
        "pblntf_ty": pblntf_ty,
        "page_count": 20,
    }
    try:
        res = requests.get(url, params=params, timeout=10)
        data = res.json()
        if data.get("status") == "000":
            return data.get("list", [])
        return []
    except Exception:
        return []

@st.cache_data(ttl=600)
def fetch_dart_company_info(api_key: str, corp_code: str) -> dict:
    url = "https://opendart.fss.or.kr/api/company.json"
    try:
        res = requests.get(url, params={"crtfc_key": api_key, "corp_code": corp_code}, timeout=10)
        data = res.json()
        if data.get("status") == "000":
            return data
        return {}
    except Exception:
        return {}

PBLNTF_TYPE_MAP = {
    "전체": "",
    "정기공시": "A",
    "주요사항보고": "B",
    "발행공시": "C",
    "지분공시": "D",
    "기타공시": "E",
    "외부감사": "F",
    "펀드공시": "G",
    "자산유동화": "H",
    "거래소공시": "I",
    "공정위공시": "J",
}


# 10개 주요 종목 매핑 (로컬 CSV 기준, 캐시 사용)
@st.cache_data(ttl=86400)
def load_local_corpcode() -> dict:
    df = pd.read_csv(_LOCAL_CORPCODE, dtype=str)
    return dict(zip(df["corp_name"], df["corp_code"]))

stock_name_to_corp = load_local_corpcode()

dart_col1, dart_col2 = st.columns([1, 3])
with dart_col1:
    # 검색 모드 선택
    dart_search_mode = st.radio("검색 방식", ["주요 종목 선택", "기업명 직접 검색"], horizontal=True, key="dart_mode")

    if dart_search_mode == "주요 종목 선택":
        dart_stock = st.selectbox("조회 종목", options=list(stock_name_to_corp.keys()), key="dart_stock")
        selected_corp_code = stock_name_to_corp.get(dart_stock, "")
        selected_corp_name = dart_stock
    else:
        dart_keyword = st.text_input("기업명 검색", placeholder="예: 삼성, 현대, LG", key="dart_keyword")
        if dart_keyword:
            search_result = search_corpcode(dart_keyword)
            if not search_result.empty:
                options = search_result["corp_name"].tolist()
                chosen = st.selectbox("검색 결과", options, key="dart_search_result")
                row = search_result[search_result["corp_name"] == chosen].iloc[0]
                selected_corp_code = row["corp_code"]
                selected_corp_name = chosen
            else:
                st.warning("검색 결과 없음")
                selected_corp_code = ""
                selected_corp_name = ""
        else:
            selected_corp_code = ""
            selected_corp_name = ""
            st.info("기업명을 입력하세요")

    dart_period = st.selectbox("조회 기간", ["1개월", "3개월", "6개월", "1년"], index=1, key="dart_period")
    dart_type_label = st.selectbox("공시 유형", list(PBLNTF_TYPE_MAP.keys()), key="dart_type")
    search_dart = st.button("📋 공시 조회", use_container_width=True, type="primary",
                            disabled=not selected_corp_code)

with dart_col2:
    if not dart_api_key:
        st.info("사이드바에서 OpenDART API 키를 입력하면 공시 정보를 조회할 수 있습니다.", icon="🔑")
    else:
        # 버튼 클릭 시에만 API 호출 → 결과를 세션에 저장
        if search_dart:
            end_de = datetime.now().strftime("%Y%m%d")
            period_days = {"1개월": 30, "3개월": 90, "6개월": 180, "1년": 365}
            bgn_de = (datetime.now() - timedelta(days=period_days[dart_period])).strftime("%Y%m%d")
            pblntf_ty = PBLNTF_TYPE_MAP[dart_type_label]

            with st.spinner(f"{selected_corp_name} 공시 정보 조회 중..."):
                disclosures = fetch_dart_disclosures(dart_api_key, selected_corp_code, bgn_de, end_de, pblntf_ty)

            st.session_state.dart_result = {
                "disclosures": disclosures,
                "corp_name": selected_corp_name,
                "bgn_de": bgn_de,
                "end_de": end_de,
            }

        # 저장된 결과 표시
        result = st.session_state.get("dart_result")
        if result:
            disclosures = result["disclosures"]
            corp_name_r = result["corp_name"]
            bgn_de_r = result["bgn_de"]
            end_de_r = result["end_de"]

            if not disclosures:
                st.warning("조회된 공시가 없거나 API 키를 확인해 주세요.", icon="⚠️")
            else:
                st.caption(
                    f"**{corp_name_r}** — 총 **{len(disclosures)}건** 조회됨 "
                    f"({bgn_de_r[:4]}.{bgn_de_r[4:6]}.{bgn_de_r[6:]} ~ "
                    f"{end_de_r[:4]}.{end_de_r[4:6]}.{end_de_r[6:]})"
                )
                for item in disclosures:
                    rcept_dt = item.get("rcept_dt", "")
                    dt_fmt = f"{rcept_dt[:4]}.{rcept_dt[4:6]}.{rcept_dt[6:]}" if len(rcept_dt) == 8 else rcept_dt
                    rcept_no = item.get("rcept_no", "")
                    dart_url = f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcept_no}"
                    with st.container():
                        c1, c2 = st.columns([5, 1])
                        with c1:
                            st.markdown(f"**[{item.get('report_nm', '')}]({dart_url})**")
                            st.caption(f"제출인: {item.get('flr_nm', '')}  |  유형: {item.get('pblntf_ty', '')}")
                        with c2:
                            st.caption(dt_fmt)
                        st.markdown("<hr style='margin:4px 0;border-color:#1E3A55'>", unsafe_allow_html=True)
        else:
            st.info("종목과 기간을 선택한 뒤 **공시 조회** 버튼을 클릭하세요.", icon="🏛️")

st.divider()

# ── 섹션 8: AI 챗봇 ──────────────────────────────────────────
st.subheader("🤖 AI 분석 챗봇")

if not openai_api_key:
    st.info("사이드바에 OpenAI API 키를 입력하면 챗봇을 사용할 수 있습니다.", icon="🔑")
else:
    # ── 공통 유틸 ──────────────────────────────────────────────
    def build_stock_context(df: pd.DataFrame) -> str:
        lines = ["[현재 수집된 국내 주식 데이터]", f"조회 기준: {datetime.now().strftime('%Y-%m-%d %H:%M')}"]
        for _, row in df.iterrows():
            price = f"{row['현재가']:,.0f}원" if pd.notna(row.get("현재가")) else "N/A"
            chg   = f"{row['등락률(%)']:+.2f}%" if pd.notna(row.get("등락률(%)")) else "N/A"
            hi52  = f"{row['52주 최고']:,.0f}원" if pd.notna(row.get("52주 최고")) else "N/A"
            lo52  = f"{row['52주 최저']:,.0f}원" if pd.notna(row.get("52주 최저")) else "N/A"
            cap   = f"{row['시가총액(억)']:,.0f}억원" if pd.notna(row.get("시가총액(억)")) else "N/A"
            lines.append(
                f"- {row['종목명']} ({row['티커']}): 현재가 {price}, 등락률 {chg}, "
                f"52주 고가 {hi52}, 52주 저가 {lo52}, 시가총액 {cap}"
            )
        return "\n".join(lines)

    def extract_pdf_text(file_bytes: bytes) -> str:
        text_parts = []
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            total = len(pdf.pages)
            for i, page in enumerate(pdf.pages):
                txt = page.extract_text()
                if txt:
                    text_parts.append(f"[{i+1}/{total} 페이지]\n{txt}")
        return "\n\n".join(text_parts) if text_parts else ""

    def ask_gpt(user_message: str, system_prompt: str, history: list) -> str:
        client = OpenAI(api_key=openai_api_key)
        messages = [{"role": "system", "content": system_prompt}]
        for h in history[-6:]:
            messages.append({"role": h["role"], "content": h["content"]})
        messages.append({"role": "user", "content": user_message})
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.7,
            max_tokens=1500,
        )
        return response.choices[0].message.content

    # ── 탭: 주식 / 뉴스 / 공시 / PDF ──────────────────────────
    chat_tab1, chat_tab_news, chat_tab_dart, chat_tab2 = st.tabs([
        "📈 주식 데이터 기반 질문",
        "📰 뉴스 기반 질문",
        "🏛️ 공시 기반 질문",
        "📄 PDF 문서 기반 질문",
    ])

    # ════════════════════════════════════════════════════════════
    # 탭 1 – 주식 챗봇
    # ════════════════════════════════════════════════════════════
    with chat_tab1:
        st.caption("수집된 실시간 주식 데이터를 기반으로 GPT-4o-mini가 답변합니다.")

        if "chat_history" not in st.session_state:
            st.session_state.chat_history = []

        STOCK_SYSTEM = (
            "당신은 국내 주식 전문 AI 애널리스트입니다.\n"
            "사용자가 제공하는 실시간 주식 데이터를 바탕으로 분석, 비교, 투자 인사이트를 제공합니다.\n"
            "- 데이터에 없는 정보는 추측하지 말고 '데이터에 없는 정보입니다'라고 명시하세요.\n"
            "- 투자 권유가 아닌 참고용 분석임을 항상 인지하세요.\n"
            "- 한국어로 명확하고 간결하게 답변하세요.\n"
            "- 수치를 언급할 때는 원, %, 억원 단위를 정확히 표기하세요.\n\n"
        ) + build_stock_context(quote_df)

        # 빠른 질문 버튼
        quick_cols = st.columns(4)
        quick_questions = [
            "오늘 가장 많이 오른 종목은?",
            "시가총액 Top 3를 알려줘",
            "52주 신고가에 가장 근접한 종목은?",
            "전체 종목 현황을 요약해줘",
        ]
        for i, q in enumerate(quick_questions):
            if quick_cols[i].button(q, key=f"sq_{i}", use_container_width=True):
                st.session_state.stock_pending = q

        # 채팅 출력
        chat_box = st.container(height=400)
        with chat_box:
            if not st.session_state.chat_history:
                st.markdown(
                    "<div style='text-align:center;color:gray;padding:60px 0'>"
                    "💬 주식 데이터에 대해 무엇이든 질문하세요!</div>",
                    unsafe_allow_html=True,
                )
            for msg in st.session_state.chat_history:
                with st.chat_message(msg["role"], avatar="🧑" if msg["role"] == "user" else "🤖"):
                    st.markdown(msg["content"])

        user_input = st.chat_input("질문을 입력하세요 (예: 삼성전자 현재 상태는?)", key="stock_input")
        if "stock_pending" in st.session_state:
            user_input = st.session_state.pop("stock_pending")

        if user_input:
            st.session_state.chat_history.append({"role": "user", "content": user_input})
            with st.spinner("GPT-4o-mini가 분석 중..."):
                try:
                    answer = ask_gpt(user_input, STOCK_SYSTEM, st.session_state.chat_history[:-1])
                except Exception as e:
                    answer = f"오류가 발생했습니다: {e}"
            st.session_state.chat_history.append({"role": "assistant", "content": answer})
            st.rerun()

        if st.session_state.get("chat_history"):
            if st.button("🗑️ 대화 초기화", key="stock_clear"):
                st.session_state.chat_history = []
                st.rerun()

    # ════════════════════════════════════════════════════════════
    # 탭 2 – 뉴스 기반 챗봇
    # ════════════════════════════════════════════════════════════
    with chat_tab_news:
        st.caption("수집된 기업 뉴스를 기반으로 GPT-4o-mini가 답변합니다.")

        if "news_chat_history" not in st.session_state:
            st.session_state.news_chat_history = []

        # 뉴스 수집 & 컨텍스트 구성
        news_chat_stock = st.selectbox("뉴스 조회 종목", selected_stocks, key="news_chat_stock_sel")

        @st.cache_data(ttl=600)
        def fetch_news_for_chat(company: str, n: int = 8) -> list:
            query = urllib.parse.quote(f"{company} 주식")
            url = f"https://news.google.com/rss/search?q={query}&hl=ko&gl=KR&ceid=KR:ko"
            try:
                feed = feedparser.parse(url)
                items = []
                for e in feed.entries[:n]:
                    summary = re.sub(r"<[^>]+>", "", getattr(e, "summary", ""))[:200]
                    items.append({
                        "title": e.title,
                        "summary": summary,
                        "published": getattr(e, "published", ""),
                        "link": e.link,
                    })
                return items
            except Exception:
                return []

        with st.spinner(f"{news_chat_stock} 뉴스 수집 중..."):
            news_items_for_chat = fetch_news_for_chat(news_chat_stock)

        if news_items_for_chat:
            st.success(f"{len(news_items_for_chat)}개 뉴스 수집 완료", icon="📰")
            with st.expander("수집된 뉴스 목록 보기"):
                for i, n in enumerate(news_items_for_chat, 1):
                    st.markdown(f"**{i}. [{n['title']}]({n['link']})**")
                    if n["summary"]:
                        st.caption(n["summary"])
        else:
            st.warning("뉴스를 수집하지 못했습니다.", icon="⚠️")

        def build_news_context(stock: str, items: list) -> str:
            lines = [f"[{stock} 관련 최신 뉴스 {len(items)}건]"]
            for i, item in enumerate(items, 1):
                lines.append(f"{i}. 제목: {item['title']}")
                if item["summary"]:
                    lines.append(f"   요약: {item['summary']}")
                if item["published"]:
                    lines.append(f"   발행: {item['published']}")
            return "\n".join(lines)

        NEWS_SYSTEM = (
            "당신은 뉴스 분석 전문 AI입니다.\n"
            "아래 제공된 최신 뉴스 기사들을 바탕으로 사용자의 질문에 답변하세요.\n"
            "- 뉴스에 없는 내용은 추측하지 말고 명시하세요.\n"
            "- 뉴스 출처(제목)를 인용하며 답변하세요.\n"
            "- 투자 권유가 아닌 참고용 분석임을 인지하세요.\n"
            "- 한국어로 명확하게 답변하세요.\n\n"
        ) + build_news_context(news_chat_stock, news_items_for_chat)

        news_quick_cols = st.columns(4)
        news_quick_qs = [
            f"{news_chat_stock} 최신 이슈는?",
            "긍정적인 뉴스 요약해줘",
            "부정적인 뉴스 있어?",
            "뉴스 전체 요약해줘",
        ]
        for i, q in enumerate(news_quick_qs):
            if news_quick_cols[i].button(q, key=f"nq_{i}", use_container_width=True):
                st.session_state.news_chat_pending = q

        news_chat_box = st.container(height=380)
        with news_chat_box:
            if not st.session_state.news_chat_history:
                st.markdown(
                    "<div style='text-align:center;color:gray;padding:50px 0'>"
                    "📰 수집된 뉴스에 대해 질문하세요!</div>",
                    unsafe_allow_html=True,
                )
            for msg in st.session_state.news_chat_history:
                with st.chat_message(msg["role"], avatar="🧑" if msg["role"] == "user" else "🤖"):
                    st.markdown(msg["content"])

        news_chat_input = st.chat_input("뉴스 관련 질문을 입력하세요", key="news_chat_input")
        if "news_chat_pending" in st.session_state:
            news_chat_input = st.session_state.pop("news_chat_pending")

        if news_chat_input:
            st.session_state.news_chat_history.append({"role": "user", "content": news_chat_input})
            with st.spinner("GPT-4o-mini가 뉴스를 분석 중..."):
                try:
                    answer = ask_gpt(news_chat_input, NEWS_SYSTEM, st.session_state.news_chat_history[:-1])
                except Exception as e:
                    answer = f"오류가 발생했습니다: {e}"
            st.session_state.news_chat_history.append({"role": "assistant", "content": answer})
            st.rerun()

        if st.session_state.get("news_chat_history"):
            if st.button("🗑️ 대화 초기화", key="news_chat_clear"):
                st.session_state.news_chat_history = []
                st.rerun()

    # ════════════════════════════════════════════════════════════
    # 탭 3 – 공시 기반 챗봇
    # ════════════════════════════════════════════════════════════
    with chat_tab_dart:
        st.caption("수집된 DART 공시 정보를 기반으로 GPT-4o-mini가 답변합니다.")

        if not dart_api_key:
            st.info("사이드바에서 OpenDART API 키를 입력하면 공시 기반 챗봇을 사용할 수 있습니다.", icon="🔑")
        else:
            if "dart_chat_history" not in st.session_state:
                st.session_state.dart_chat_history = []

            dart_chat_stock = st.selectbox("공시 조회 종목", list(stock_name_to_corp.keys()), key="dart_chat_stock")
            # 기업명 직접 검색도 지원
            dart_chat_kw = st.text_input("또는 기업명 직접 검색", placeholder="예: 카카오뱅크, LG전자", key="dart_chat_kw")
            if dart_chat_kw:
                found = search_corpcode(dart_chat_kw)
                if not found.empty:
                    opts = found["corp_name"].tolist()
                    dart_chat_stock = st.selectbox("검색된 기업", opts, key="dart_chat_search")
                    corp_code2 = found[found["corp_name"] == dart_chat_stock].iloc[0]["corp_code"]
                else:
                    corp_code2 = stock_name_to_corp.get(dart_chat_stock, "")
            else:
                corp_code2 = stock_name_to_corp.get(dart_chat_stock, "")
            dart_chat_period = st.selectbox("공시 조회 기간", ["1개월", "3개월", "6개월"], index=1, key="dart_chat_period")

            end_de2 = datetime.now().strftime("%Y%m%d")
            p_days2 = {"1개월": 30, "3개월": 90, "6개월": 180}
            bgn_de2 = (datetime.now() - timedelta(days=p_days2[dart_chat_period])).strftime("%Y%m%d")

            load_dart_chat = st.button("🏛️ 공시 불러오기", key="load_dart_chat_btn")
            if load_dart_chat:
                with st.spinner(f"{dart_chat_stock} 공시 수집 중..."):
                    dart_items = fetch_dart_disclosures(dart_api_key, corp_code2, bgn_de2, end_de2, "")
                st.session_state.dart_chat_items = dart_items
                st.session_state.dart_chat_stock_name = dart_chat_stock

            dart_items = st.session_state.get("dart_chat_items", [])

            if dart_items:
                st.success(f"{len(dart_items)}건 공시 수집 완료 ({st.session_state.get('dart_chat_stock_name','')})", icon="🏛️")
                with st.expander("수집된 공시 목록 보기"):
                    for d in dart_items[:10]:
                        rcept_dt = d.get("rcept_dt","")
                        dt_fmt = f"{rcept_dt[:4]}.{rcept_dt[4:6]}.{rcept_dt[6:]}" if len(rcept_dt)==8 else rcept_dt
                        st.markdown(f"- **{d.get('report_nm','')}** ({dt_fmt}) — {d.get('flr_nm','')}")
            else:
                st.warning("공시 정보를 불러오지 못했습니다.", icon="⚠️")

            def build_dart_context(stock: str, items: list) -> str:
                lines = [f"[{stock} DART 공시 정보 {len(items)}건]"]
                for i, d in enumerate(items[:15], 1):
                    rcept_dt = d.get("rcept_dt","")
                    dt_fmt = f"{rcept_dt[:4]}.{rcept_dt[4:6]}.{rcept_dt[6:]}" if len(rcept_dt)==8 else rcept_dt
                    lines.append(
                        f"{i}. [{dt_fmt}] {d.get('report_nm','')} "
                        f"(제출: {d.get('flr_nm','')}, 유형: {d.get('pblntf_ty','')})"
                    )
                return "\n".join(lines)

            DART_SYSTEM = (
                "당신은 기업 공시 분석 전문 AI입니다.\n"
                "아래 제공된 DART 공시 목록을 바탕으로 사용자의 질문에 답변하세요.\n"
                "- 공시에 없는 내용은 추측하지 마세요.\n"
                "- 공시 보고서명과 날짜를 인용하며 답변하세요.\n"
                "- 투자 판단에 직접적인 권유는 하지 마세요.\n"
                "- 한국어로 명확하게 답변하세요.\n\n"
            ) + build_dart_context(dart_chat_stock, dart_items)

            dart_quick_cols = st.columns(4)
            dart_quick_qs = [
                "최근 주요 공시 요약해줘",
                "정기공시 현황은?",
                "최근 주요사항보고 있어?",
                "공시 전체 목록 알려줘",
            ]
            for i, q in enumerate(dart_quick_qs):
                if dart_quick_cols[i].button(q, key=f"dq_{i}", use_container_width=True):
                    st.session_state.dart_chat_pending = q

            dart_chat_box = st.container(height=380)
            with dart_chat_box:
                if not st.session_state.dart_chat_history:
                    st.markdown(
                        "<div style='text-align:center;color:gray;padding:50px 0'>"
                        "🏛️ 공시 정보에 대해 질문하세요!</div>",
                        unsafe_allow_html=True,
                    )
                for msg in st.session_state.dart_chat_history:
                    with st.chat_message(msg["role"], avatar="🧑" if msg["role"] == "user" else "🤖"):
                        st.markdown(msg["content"])

            dart_chat_input = st.chat_input("공시 관련 질문을 입력하세요", key="dart_chat_input")
            if "dart_chat_pending" in st.session_state:
                dart_chat_input = st.session_state.pop("dart_chat_pending")

            if dart_chat_input:
                st.session_state.dart_chat_history.append({"role": "user", "content": dart_chat_input})
                with st.spinner("GPT-4o-mini가 공시를 분석 중..."):
                    try:
                        answer = ask_gpt(dart_chat_input, DART_SYSTEM, st.session_state.dart_chat_history[:-1])
                    except Exception as e:
                        answer = f"오류가 발생했습니다: {e}"
                st.session_state.dart_chat_history.append({"role": "assistant", "content": answer})
                st.rerun()

            if st.session_state.get("dart_chat_history"):
                if st.button("🗑️ 대화 초기화", key="dart_chat_clear"):
                    st.session_state.dart_chat_history = []
                    st.rerun()

    # ════════════════════════════════════════════════════════════
    # 탭 4 – PDF 챗봇
    # ════════════════════════════════════════════════════════════
    with chat_tab2:
        st.caption("PDF 파일을 업로드하면 해당 내용을 기반으로 GPT-4o-mini가 답변합니다.")

        uploaded_file = st.file_uploader(
            "PDF 파일 업로드",
            type=["pdf"],
            help="최대 50MB 이내의 텍스트 기반 PDF를 권장합니다.",
            key="pdf_uploader",
        )

        # PDF 텍스트 추출 및 세션 저장
        if uploaded_file is not None:
            file_key = f"{uploaded_file.name}_{uploaded_file.size}"
            if st.session_state.get("pdf_file_key") != file_key:
                with st.spinner(f"'{uploaded_file.name}' 텍스트 추출 중..."):
                    raw_bytes = uploaded_file.read()
                    extracted = extract_pdf_text(raw_bytes)
                if extracted:
                    # 토큰 초과 방지: 최대 12000자
                    MAX_CHARS = 12000
                    truncated = len(extracted) > MAX_CHARS
                    st.session_state.pdf_text = extracted[:MAX_CHARS]
                    st.session_state.pdf_file_key = file_key
                    st.session_state.pdf_name = uploaded_file.name
                    st.session_state.pdf_chat_history = []
                    if truncated:
                        st.warning(
                            f"문서가 길어 앞부분 {MAX_CHARS:,}자만 사용합니다. "
                            "중요 내용이 뒤에 있다면 해당 페이지만 추출한 PDF를 올려주세요.",
                            icon="⚠️",
                        )
                else:
                    st.error("텍스트를 추출할 수 없습니다. 스캔 이미지 PDF는 지원되지 않습니다.", icon="🚫")
                    st.session_state.pdf_text = None

        # PDF 로드 상태 표시
        if st.session_state.get("pdf_text"):
            pdf_name = st.session_state.get("pdf_name", "문서")
            char_count = len(st.session_state.pdf_text)
            st.success(f"📄 **{pdf_name}** 로드 완료 — {char_count:,}자 추출됨", icon="✅")

            with st.expander("추출된 텍스트 미리보기 (앞 500자)"):
                st.text(st.session_state.pdf_text[:500] + "…")

            st.divider()

            PDF_SYSTEM = (
                "당신은 문서 분석 전문 AI 어시스턴트입니다.\n"
                "아래에 제공된 PDF 문서 내용만을 근거로 사용자의 질문에 답변하세요.\n"
                "- 문서에 없는 내용은 '문서에서 확인되지 않는 내용입니다'라고 명시하세요.\n"
                "- 출처 페이지가 있다면 '[X페이지]' 형태로 인용하세요.\n"
                "- 한국어로 명확하고 간결하게 답변하세요.\n\n"
                f"[PDF 문서 내용: {pdf_name}]\n"
                f"{st.session_state.pdf_text}"
            )

            if "pdf_chat_history" not in st.session_state:
                st.session_state.pdf_chat_history = []

            # PDF 빠른 질문
            pdf_quick_cols = st.columns(4)
            pdf_quick_questions = [
                "이 문서를 요약해줘",
                "핵심 내용이 뭐야?",
                "주요 수치나 통계를 알려줘",
                "결론은 무엇인가?",
            ]
            for i, q in enumerate(pdf_quick_questions):
                if pdf_quick_cols[i].button(q, key=f"pq_{i}", use_container_width=True):
                    st.session_state.pdf_pending = q

            # 채팅 출력
            pdf_chat_box = st.container(height=400)
            with pdf_chat_box:
                if not st.session_state.pdf_chat_history:
                    st.markdown(
                        "<div style='text-align:center;color:gray;padding:60px 0'>"
                        "📄 PDF 내용에 대해 무엇이든 질문하세요!</div>",
                        unsafe_allow_html=True,
                    )
                for msg in st.session_state.pdf_chat_history:
                    with st.chat_message(msg["role"], avatar="🧑" if msg["role"] == "user" else "🤖"):
                        st.markdown(msg["content"])

            pdf_input = st.chat_input("PDF 내용에 대해 질문하세요", key="pdf_input")
            if "pdf_pending" in st.session_state:
                pdf_input = st.session_state.pop("pdf_pending")

            if pdf_input:
                st.session_state.pdf_chat_history.append({"role": "user", "content": pdf_input})
                with st.spinner("GPT-4o-mini가 문서를 분석 중..."):
                    try:
                        answer = ask_gpt(pdf_input, PDF_SYSTEM, st.session_state.pdf_chat_history[:-1])
                    except Exception as e:
                        answer = f"오류가 발생했습니다: {e}"
                st.session_state.pdf_chat_history.append({"role": "assistant", "content": answer})
                st.rerun()

            if st.session_state.get("pdf_chat_history"):
                col_clear, col_new = st.columns([1, 5])
                if col_clear.button("🗑️ 대화 초기화", key="pdf_clear"):
                    st.session_state.pdf_chat_history = []
                    st.rerun()
        else:
            st.info("위에서 PDF 파일을 업로드하면 챗봇이 활성화됩니다.", icon="📎")

st.divider()

# ── 섹션 9: 보고서 생성 및 이메일 발송 ────────────────────────
st.subheader("📧 주식 보고서 생성 및 이메일 발송")
st.caption("수집된 주식 데이터와 뉴스를 기반으로 보고서를 생성하고 이메일로 발송합니다.")

report_col1, report_col2 = st.columns([1, 2])

with report_col1:
    st.markdown("**보고서 설정**")

    report_stocks = st.multiselect(
        "보고서 포함 종목",
        options=selected_stocks,
        default=selected_stocks[:5],
        key="report_stocks_sel",
    )

    report_news_count = st.slider("종목별 뉴스 수", 2, 5, 3, key="report_news_cnt")

    report_type = st.selectbox(
        "보고서 유형",
        ["일일 시황 요약", "종목별 상세 분석", "투자 인사이트 리포트"],
        key="report_type_sel",
    )

    generate_report_btn = st.button(
        "📝 보고서 생성",
        use_container_width=True,
        type="primary",
        disabled=not openai_api_key,
        key="gen_report_btn",
    )

    if not openai_api_key:
        st.caption("⚠️ OpenAI API 키가 필요합니다.")

    st.divider()
    st.markdown("**이메일 발송**")

    send_email_btn = st.button(
        "📨 이메일로 발송",
        use_container_width=True,
        disabled=not (smtp_email and smtp_app_password and smtp_recipient),
        key="send_email_btn",
    )

    if not (smtp_email and smtp_app_password and smtp_recipient):
        st.caption("⚠️ 사이드바에서 이메일 설정을 완료하세요.")

with report_col2:
    # 보고서 생성
    if generate_report_btn and openai_api_key and report_stocks:
        with st.spinner("보고서 생성 중... (뉴스 수집 + AI 분석)"):
            # 주식 데이터 컨텍스트
            report_quote_df = quote_df[quote_df["종목명"].isin(report_stocks)]

            def build_report_stock_ctx(df):
                lines = [f"[주식 현황 — {datetime.now().strftime('%Y-%m-%d %H:%M')}]"]
                for _, row in df.iterrows():
                    price = f"{row['현재가']:,.0f}원" if pd.notna(row.get("현재가")) else "N/A"
                    chg = f"{row['등락률(%)']:+.2f}%" if pd.notna(row.get("등락률(%)")) else "N/A"
                    cap = f"{row['시가총액(억)']:,.0f}억원" if pd.notna(row.get("시가총액(억)")) else "N/A"
                    hi52 = f"{row['52주 최고']:,.0f}원" if pd.notna(row.get("52주 최고")) else "N/A"
                    lo52 = f"{row['52주 최저']:,.0f}원" if pd.notna(row.get("52주 최저")) else "N/A"
                    lines.append(
                        f"- {row['종목명']}: 현재가 {price}, 등락률 {chg}, "
                        f"52주 고가 {hi52}, 52주 저가 {lo52}, 시가총액 {cap}"
                    )
                return "\n".join(lines)

            # 뉴스 수집
            all_news_ctx = []
            for sname in report_stocks:
                items = fetch_news(sname, report_news_count)
                if items:
                    all_news_ctx.append(f"\n[{sname} 뉴스]")
                    for item in items:
                        all_news_ctx.append(f"- {item['title']}")
                        if item["summary"]:
                            all_news_ctx.append(f"  {item['summary'][:100]}")

            stock_ctx = build_report_stock_ctx(report_quote_df)
            news_ctx = "\n".join(all_news_ctx) if all_news_ctx else "뉴스 없음"

            report_type_prompts = {
                "일일 시황 요약": (
                    "오늘의 국내 주식 시황을 요약하는 일일 리포트를 작성하세요. "
                    "전체 시장 분위기, 상승/하락 종목 동향, 주요 뉴스 이슈를 포함하세요."
                ),
                "종목별 상세 분석": (
                    "각 종목별로 현재 주가 상황, 52주 고저 대비 위치, 뉴스 동향을 분석하는 "
                    "종목별 상세 분석 리포트를 작성하세요."
                ),
                "투자 인사이트 리포트": (
                    "주가 데이터와 뉴스를 종합하여 투자 관점의 인사이트 리포트를 작성하세요. "
                    "주목할 종목, 리스크 요인, 단기 모멘텀을 분석하세요. "
                    "투자 권유가 아닌 참고용 분석임을 명시하세요."
                ),
            }

            prompt_suffix = report_type_prompts.get(report_type, "")

            REPORT_SYSTEM = (
                "당신은 전문 주식 리서치 애널리스트입니다.\n"
                "제공된 주식 데이터와 뉴스를 바탕으로 전문적인 리포트를 작성합니다.\n"
                "- 마크다운 형식으로 작성하세요 (##, ###, **볼드**, - 리스트 사용).\n"
                "- 수치를 정확히 인용하세요.\n"
                "- 한국어로 작성하세요.\n"
                "- 보고서 상단에 날짜와 보고서 유형을 표기하세요.\n\n"
                f"{stock_ctx}\n\n{news_ctx}"
            )

            user_prompt = (
                f"다음 조건으로 보고서를 작성해주세요: {prompt_suffix}\n"
                f"포함 종목: {', '.join(report_stocks)}"
            )

            try:
                client = OpenAI(api_key=openai_api_key)
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": REPORT_SYSTEM},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.6,
                    max_tokens=2000,
                )
                generated_report = response.choices[0].message.content
                st.session_state.generated_report = generated_report
                st.session_state.report_generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
                st.success("보고서 생성 완료!", icon="✅")
            except Exception as e:
                st.error(f"보고서 생성 실패: {e}", icon="🚫")

    # 보고서 표시
    if st.session_state.get("generated_report"):
        st.markdown(f"*생성 시각: {st.session_state.get('report_generated_at', '')}*")
        st.markdown("---")
        st.markdown(st.session_state.generated_report)

        # 텍스트 다운로드
        st.download_button(
            "⬇️ 보고서 다운로드 (.md)",
            data=st.session_state.generated_report.encode("utf-8"),
            file_name=f"stock_report_{datetime.now().strftime('%Y%m%d_%H%M')}.md",
            mime="text/markdown",
            key="download_report_btn",
        )
    else:
        st.info("보고서 설정을 선택하고 '보고서 생성' 버튼을 클릭하세요.", icon="📝")

# 이메일 발송 처리 (컬럼 밖에서 실행)
if send_email_btn:
    report_content = st.session_state.get("generated_report", "")
    if not report_content:
        st.warning("먼저 보고서를 생성해주세요.", icon="⚠️")
    else:
        with st.spinner("이메일 발송 중..."):
            try:
                # Markdown → HTML 간단 변환
                def md_to_html(md_text: str) -> str:
                    lines = md_text.split("\n")
                    html_lines = []
                    for line in lines:
                        if line.startswith("### "):
                            html_lines.append(f"<h3>{line[4:]}</h3>")
                        elif line.startswith("## "):
                            html_lines.append(f"<h2>{line[3:]}</h2>")
                        elif line.startswith("# "):
                            html_lines.append(f"<h1>{line[2:]}</h1>")
                        elif line.startswith("- "):
                            html_lines.append(f"<li>{line[2:]}</li>")
                        elif line.strip() == "---" or line.strip() == "***":
                            html_lines.append("<hr>")
                        elif line.strip() == "":
                            html_lines.append("<br>")
                        else:
                            # **볼드** 처리
                            processed = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", line)
                            html_lines.append(f"<p>{processed}</p>")
                    return "\n".join(html_lines)

                report_html = f"""
<html>
<body style="font-family: 'Malgun Gothic', Arial, sans-serif; max-width: 800px; margin: auto; padding: 20px; color: #333;">
  <div style="background: linear-gradient(135deg, #1a3c5e, #2d6a9f); padding: 20px; border-radius: 8px; margin-bottom: 20px;">
    <h1 style="color: white; margin: 0;">📈 국내 주식 보고서</h1>
    <p style="color: #cce4ff; margin: 5px 0 0 0;">생성 시각: {st.session_state.get('report_generated_at', datetime.now().strftime('%Y-%m-%d %H:%M'))}</p>
  </div>
  <div style="background: #f8f9fa; padding: 20px; border-radius: 8px; border-left: 4px solid #2d6a9f;">
    {md_to_html(report_content)}
  </div>
  <div style="margin-top: 20px; padding: 10px; background: #e8f4f8; border-radius: 8px; font-size: 12px; color: #666;">
    본 보고서는 참고용이며 투자 권유가 아닙니다. 데이터: Yahoo Finance · Google News RSS
  </div>
</body>
</html>
"""
                msg = MIMEMultipart("alternative")
                msg["Subject"] = f"[주식 보고서] {report_type} — {datetime.now().strftime('%Y-%m-%d')}"
                msg["From"] = smtp_email
                msg["To"] = smtp_recipient

                msg.attach(MIMEText(report_content, "plain", "utf-8"))
                msg.attach(MIMEText(report_html, "html", "utf-8"))

                # Gmail SMTP (587 TLS)
                with smtplib.SMTP("smtp.gmail.com", 587) as server:
                    server.ehlo()
                    server.starttls()
                    server.login(smtp_email, smtp_app_password)
                    server.sendmail(smtp_email, smtp_recipient, msg.as_string())

                st.success(f"이메일 발송 완료! → {smtp_recipient}", icon="📨")
            except smtplib.SMTPAuthenticationError:
                st.error(
                    "인증 실패: 이메일 주소 또는 앱 비밀번호를 확인하세요.\n\n"
                    "Gmail 앱 비밀번호 발급: Google 계정 → 보안 → 2단계 인증 활성화 후 앱 비밀번호 생성",
                    icon="🔐",
                )
            except smtplib.SMTPException as e:
                st.error(f"SMTP 오류: {e}", icon="🚫")
            except Exception as e:
                st.error(f"이메일 발송 실패: {e}", icon="🚫")

st.divider()
st.caption(
    f"마지막 업데이트: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} "
    "| 데이터: Yahoo Finance · Google News RSS · OpenDART | AI: GPT-4o-mini"
)
