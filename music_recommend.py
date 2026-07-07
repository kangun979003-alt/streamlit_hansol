import streamlit as st
import urllib.parse
import json
from openai import OpenAI

st.set_page_config(
    page_title="🎵 AI 노래 추천",
    page_icon="🎵",
    layout="centered",
)

# ── 스타일 ──────────────────────────────────────────────────────
st.markdown("""
<style>
    .stApp { background: linear-gradient(135deg, #0f0c29, #302b63, #24243e); }

    /* 모든 텍스트 기본 흰색 */
    .stApp, .stApp p, .stApp span, .stApp div,
    .stApp li, .stApp label, .stApp caption { color: #f0f0f0 !important; }

    /* Streamlit 기본 컴포넌트 텍스트 강제 흰색 */
    [data-testid="stMarkdownContainer"] p,
    [data-testid="stMarkdownContainer"] span,
    [data-testid="stMarkdownContainer"] li { color: #f0f0f0 !important; }

    /* subheader / caption */
    h1, h2, h3 { color: #ffffff !important; }
    [data-testid="stCaptionContainer"] p { color: #c0c0c0 !important; }

    /* 라디오 · 멀티셀렉트 레이블 */
    label, .stRadio label, .stCheckbox label { color: #f0f0f0 !important; }
    .stRadio > div > label p { color: #f0f0f0 !important; font-size: 0.97rem !important; }
    .stRadio > div { gap: 6px; }

    /* 멀티셀렉트 선택 태그 */
    [data-testid="stMultiSelect"] span { color: #ffffff !important; }
    [data-testid="stMultiSelect"] [data-baseweb="tag"] span { color: #1a1a2e !important; }

    /* 슬라이더 레이블 */
    [data-testid="stSlider"] label { color: #f0f0f0 !important; }

    /* expander 제목 */
    [data-testid="stExpander"] summary p,
    [data-testid="stExpander"] summary span,
    details summary p { color: #f0f0f0 !important; font-weight: 600; }

    /* expander 배경 살짝 밝게 */
    [data-testid="stExpander"] {
        background: rgba(255,255,255,0.06) !important;
        border: 1px solid rgba(255,255,255,0.15) !important;
        border-radius: 10px !important;
    }

    /* info / success / warning 배너 */
    [data-testid="stAlert"] p { color: #1a1a2e !important; }

    .hero-title {
        text-align: center;
        font-size: 2.8rem;
        font-weight: 800;
        background: linear-gradient(90deg, #a78bfa, #60a5fa, #f472b6);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 6px;
    }
    .hero-sub {
        text-align: center;
        color: #d1d5db !important;
        font-size: 1rem;
        margin-bottom: 32px;
    }

    /* 설문 카드 */
    .survey-card {
        background: rgba(255,255,255,0.09);
        border: 1px solid rgba(255,255,255,0.2);
        border-radius: 16px;
        padding: 20px 24px 8px 24px;
        margin-bottom: 18px;
    }
    .question-label {
        font-size: 1.05rem;
        font-weight: 700;
        color: #ffffff !important;
        margin-bottom: 10px;
    }

    /* 노래 카드 */
    .song-card {
        background: linear-gradient(135deg, rgba(111,66,193,0.3), rgba(59,130,246,0.3));
        border: 1px solid rgba(139,92,246,0.5);
        border-radius: 14px;
        padding: 16px 20px;
        margin-bottom: 10px;
        transition: border-color 0.2s;
    }
    .song-card:hover { border-color: rgba(139,92,246,0.9); }

    .song-number {
        font-size: 0.75rem;
        color: #c4b5fd !important;
        font-weight: 700;
        letter-spacing: 0.08em;
        margin-bottom: 4px;
    }
    .song-title-link {
        font-size: 1.12rem;
        font-weight: 700;
        color: #ffffff !important;
        text-decoration: none;
    }
    .song-title-link:hover { color: #93c5fd !important; text-decoration: underline; }
    .song-meta {
        font-size: 0.82rem;
        color: #d1d5db !important;
        margin-top: 6px;
    }
    .song-reason {
        font-size: 0.88rem;
        color: #e9d5ff !important;
        margin-top: 10px;
        line-height: 1.6;
        border-left: 3px solid rgba(167,139,250,0.7);
        padding-left: 10px;
    }

    /* 아티스트 더보기 버튼 */
    .artist-more-btn > button {
        background: rgba(99,102,241,0.3) !important;
        border: 1px solid rgba(99,102,241,0.6) !important;
        color: #e0e7ff !important;
        border-radius: 8px !important;
        font-size: 0.82rem !important;
        padding: 4px 12px !important;
        height: auto !important;
        min-height: 0 !important;
        font-weight: 600 !important;
    }
    .artist-more-btn > button:hover {
        background: rgba(99,102,241,0.55) !important;
        color: #ffffff !important;
    }

    /* 기본 버튼 */
    div[data-testid="stButton"] > button {
        background: linear-gradient(135deg, #7c3aed, #2563eb);
        color: #ffffff !important;
        border: none;
        border-radius: 12px;
        padding: 12px;
        font-size: 1rem;
        font-weight: 700;
    }
    div[data-testid="stButton"] > button:hover { opacity: 0.85; }

    /* 아티스트 더보기 패널 */
    .artist-panel {
        background: rgba(16,185,129,0.1);
        border: 1px solid rgba(16,185,129,0.4);
        border-radius: 14px;
        padding: 16px 20px;
        margin: 8px 0 14px 0;
    }
    .artist-panel-title {
        font-size: 0.98rem;
        font-weight: 700;
        color: #6ee7b7 !important;
        margin-bottom: 12px;
    }
    .mini-song-link {
        display: block;
        color: #e5e7eb !important;
        text-decoration: none;
        font-size: 0.9rem;
        padding: 6px 0;
        border-bottom: 1px solid rgba(255,255,255,0.08);
    }
    .mini-song-link:hover { color: #93c5fd !important; }

    /* 무드 배지 */
    .mood-badge {
        display: inline-block;
        background: rgba(139,92,246,0.3);
        border: 1px solid rgba(139,92,246,0.5);
        border-radius: 20px;
        padding: 3px 12px;
        font-size: 0.8rem;
        color: #e9d5ff !important;
        margin-right: 6px;
        margin-bottom: 6px;
    }

    /* 구분선 */
    hr { border-color: rgba(255,255,255,0.15) !important; }
</style>
""", unsafe_allow_html=True)

# ── 헬퍼 함수 ────────────────────────────────────────────────────
def youtube_search_url(title: str, artist: str) -> str:
    query = urllib.parse.quote_plus(f"{title} {artist}")
    return f"https://www.youtube.com/results?search_query={query}"

def youtube_watch_url(title: str, artist: str) -> str:
    """search 대신 바로 재생될 가능성이 높은 첫 결과 URL (search redirect)"""
    query = urllib.parse.quote_plus(f"{title} {artist} official")
    return f"https://www.youtube.com/results?search_query={query}"

def call_gpt(system_msg: str, user_msg: str, temperature: float = 0.85) -> str:
    client = OpenAI(api_key=st.session_state.openai_api_key)
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_msg},
            {"role": "user",   "content": user_msg},
        ],
        temperature=temperature,
        max_tokens=2000,
        response_format={"type": "json_object"},
    )
    return response.choices[0].message.content

def parse_songs(raw_json: str) -> dict:
    try:
        return json.loads(raw_json)
    except Exception:
        return {}

def render_song_cards(songs: list, prefix: str = "main"):
    """songs: list of dict with keys title, artist, genre, tempo, language, reason"""
    for i, song in enumerate(songs):
        title   = song.get("title", "")
        artist  = song.get("artist", "")
        genre   = song.get("genre", "")
        tempo   = song.get("tempo", "")
        lang    = song.get("language", "")
        reason  = song.get("reason", "")
        yt_url  = youtube_watch_url(title, artist)

        # 노래 카드
        st.markdown(f"""
        <div class="song-card">
          <div class="song-number">#{i+1}</div>
          <a class="song-title-link" href="{yt_url}" target="_blank">
            ▶ {title}
            <span style="font-size:0.75rem; color:#f87171; margin-left:6px;">YouTube ↗</span>
          </a>
          <div class="song-meta">🎤 {artist} &nbsp;·&nbsp; {genre} &nbsp;·&nbsp; {tempo} &nbsp;·&nbsp; {lang}</div>
          <div class="song-reason">💡 {reason}</div>
        </div>
        """, unsafe_allow_html=True)

        # 아티스트 더보기 버튼
        btn_key = f"artist_more_{prefix}_{i}_{artist}"
        expand_key = f"expand_artist_{prefix}_{i}"

        with st.container():
            col_artist, col_spacer = st.columns([2, 5])
            with col_artist:
                st.markdown('<div class="artist-more-btn">', unsafe_allow_html=True)
                if st.button(f"🎤 {artist} 더 보기", key=btn_key):
                    # 토글
                    if st.session_state.get(expand_key) == artist:
                        st.session_state.pop(expand_key, None)
                        st.session_state.pop(f"artist_songs_{expand_key}", None)
                    else:
                        st.session_state[expand_key] = artist
                        st.session_state.pop(f"artist_songs_{expand_key}", None)
                st.markdown('</div>', unsafe_allow_html=True)

        # 아티스트 더보기 패널
        if st.session_state.get(expand_key) == artist:
            cache_key = f"artist_songs_{expand_key}"
            if cache_key not in st.session_state:
                with st.spinner(f"🎵 {artist}의 추천곡 검색 중..."):
                    try:
                        raw = call_gpt(
                            system_msg=(
                                "당신은 음악 큐레이터입니다. "
                                "요청한 아티스트의 대표 추천곡 목록을 JSON으로 반환합니다. "
                                "반드시 실제 존재하는 곡만 포함하세요."
                            ),
                            user_msg=(
                                f"아티스트 '{artist}'의 추천 노래 6곡을 알려주세요. "
                                f"방금 추천된 '{title}'은 제외하고 다른 곡으로 추천해주세요.\n\n"
                                "다음 JSON 형식으로만 응답하세요:\n"
                                '{"songs": [{"title": "곡제목", "reason": "한줄 소개"}]}'
                            ),
                            temperature=0.8,
                        )
                        data = parse_songs(raw)
                        st.session_state[cache_key] = data.get("songs", [])
                    except Exception as e:
                        st.session_state[cache_key] = []
                        st.error(f"오류: {e}")

            artist_songs = st.session_state.get(cache_key, [])
            if artist_songs:
                st.markdown(f"""
                <div class="artist-panel">
                  <div class="artist-panel-title">🎤 {artist} 추천 노래 더 보기</div>
                """, unsafe_allow_html=True)
                for asong in artist_songs:
                    at = asong.get("title", "")
                    ar = asong.get("reason", "")
                    ayt = youtube_watch_url(at, artist)
                    st.markdown(
                        f'<a class="mini-song-link" href="{ayt}" target="_blank">'
                        f'▶ {at}'
                        f'<span style="color:#9ca3af; font-size:0.78rem; margin-left:6px;">'
                        f'— {ar}</span>'
                        f'<span style="color:#f87171; font-size:0.72rem; margin-left:6px;">YouTube ↗</span>'
                        f'</a>',
                        unsafe_allow_html=True,
                    )
                st.markdown("</div>", unsafe_allow_html=True)
            else:
                st.warning("추천곡을 불러오지 못했습니다.")

# ── 헤더 ────────────────────────────────────────────────────────
st.markdown('<div class="hero-title">🎵 AI 노래 추천</div>', unsafe_allow_html=True)
st.markdown('<div class="hero-sub">몇 가지 질문에 답하면 지금 이 순간 딱 맞는 노래를 추천해드려요</div>', unsafe_allow_html=True)

# ── API 키 입력 ──────────────────────────────────────────────────
with st.expander("🔑 OpenAI API 키 설정", expanded=not st.session_state.get("api_key_saved")):
    api_key_input = st.text_input(
        "OpenAI API Key",
        type="password",
        placeholder="sk-...",
        value=st.session_state.get("openai_api_key", ""),
        help="https://platform.openai.com/api-keys 에서 발급",
    )
    col_save, col_clear = st.columns([3, 1])
    with col_save:
        if st.button("저장", key="save_api_key"):
            if api_key_input.strip().startswith("sk-"):
                st.session_state.openai_api_key = api_key_input.strip()
                st.session_state.api_key_saved = True
                st.success("API 키가 저장되었습니다!", icon="✅")
                st.rerun()
            else:
                st.error("올바른 OpenAI API 키 형식이 아닙니다. (sk- 로 시작해야 합니다)", icon="🚫")
    with col_clear:
        if st.button("초기화", key="clear_api_key"):
            st.session_state.openai_api_key = ""
            st.session_state.api_key_saved = False
            st.rerun()

if st.session_state.get("api_key_saved"):
    st.success("API 키 연결됨 ✅", icon="🔑")

st.divider()

# ── 설문 정의 ────────────────────────────────────────────────────
QUESTIONS = [
    {
        "key": "mood",
        "icon": "😊",
        "label": "지금 기분이 어때요?",
        "type": "radio",
        "options": [
            "😄 신나고 활기차요",
            "😌 차분하고 여유로워요",
            "😢 조금 슬프거나 감성적이에요",
            "😤 스트레스를 풀고 싶어요",
            "🥱 피곤하고 졸려요",
            "🤩 설레고 두근거려요",
        ],
    },
    {
        "key": "situation",
        "icon": "🎯",
        "label": "지금 어떤 상황인가요?",
        "type": "radio",
        "options": [
            "🏃 운동 중 / 러닝",
            "📚 공부 / 집중 작업",
            "🚗 드라이브",
            "🛋️ 혼자 쉬는 시간",
            "🥂 파티 / 모임",
            "💤 잠들기 전",
            "☕ 카페 / 브런치",
        ],
    },
    {
        "key": "genre",
        "icon": "🎸",
        "label": "선호하는 음악 장르를 골라주세요 (복수 선택 가능)",
        "type": "multiselect",
        "options": [
            "🎤 K-POP",
            "🎵 팝 (Pop)",
            "🎸 록 / 인디",
            "🎹 발라드 / R&B",
            "🎧 힙합 / 랩",
            "🎻 클래식 / 재즈",
            "🌴 EDM / 댄스",
            "🌿 어쿠스틱 / 포크",
            "🌊 Lo-fi / 칠아웃",
        ],
    },
    {
        "key": "tempo",
        "icon": "⚡",
        "label": "어떤 템포의 음악이 좋으세요?",
        "type": "radio",
        "options": [
            "🔥 빠르고 강렬하게",
            "✨ 적당히 경쾌하게",
            "🌙 느리고 잔잔하게",
            "상관없어요",
        ],
    },
    {
        "key": "language",
        "icon": "🌍",
        "label": "언어 선호도가 있나요?",
        "type": "radio",
        "options": [
            "🇰🇷 한국어 노래가 좋아요",
            "🌐 영어 노래가 좋아요",
            "🌏 둘 다 괜찮아요",
            "그 외 언어도 OK",
        ],
    },
    {
        "key": "era",
        "icon": "🕰️",
        "label": "어떤 시대의 음악을 원하세요?",
        "type": "radio",
        "options": [
            "🆕 최신 (2020년대)",
            "📻 2010년대",
            "💿 2000년대 / 복고",
            "🎙️ 시대 상관없이 명곡",
        ],
    },
]

# ── 설문 UI ──────────────────────────────────────────────────────
st.subheader("📋 설문에 답해주세요")
st.caption("아래 질문들에 답하면 AI가 맞춤 노래를 추천해드립니다.")

answers = {}
all_answered = True

for q in QUESTIONS:
    st.markdown(
        f'<div class="survey-card">'
        f'<div class="question-label">{q["icon"]} {q["label"]}</div>',
        unsafe_allow_html=True,
    )
    if q["type"] == "radio":
        val = st.radio(
            label=q["label"],
            options=q["options"],
            index=None,
            key=f"q_{q['key']}",
            label_visibility="collapsed",
        )
        answers[q["key"]] = val
        if val is None:
            all_answered = False
    elif q["type"] == "multiselect":
        val = st.multiselect(
            label=q["label"],
            options=q["options"],
            key=f"q_{q['key']}",
            label_visibility="collapsed",
            placeholder="장르를 선택하세요 (복수 선택 가능)",
        )
        answers[q["key"]] = val
        if not val:
            all_answered = False
    st.markdown("</div>", unsafe_allow_html=True)

st.divider()

rec_count = st.select_slider(
    "🎶 추천받을 노래 수",
    options=[3, 5, 7, 10],
    value=5,
    key="rec_count",
)

st.markdown("<br>", unsafe_allow_html=True)

recommend_btn = st.button(
    "✨ 나만의 플레이리스트 추천받기",
    disabled=not (all_answered and st.session_state.get("openai_api_key")),
    key="recommend_btn",
)

if not st.session_state.get("openai_api_key"):
    st.warning("먼저 상단에서 OpenAI API 키를 입력하고 저장해주세요.", icon="🔑")
elif not all_answered:
    st.info("모든 질문에 답하면 추천 버튼이 활성화됩니다.", icon="📝")

# ── GPT 호출 ────────────────────────────────────────────────────
def build_prompt(answers: dict, count: int) -> str:
    genres_clean = [g.split(" ", 1)[1] if " " in g else g for g in (answers.get("genre") or [])]
    return f"""사용자 설문 결과를 바탕으로 노래 {count}곡을 추천해주세요.

[사용자 정보]
- 현재 기분: {answers.get('mood', '알 수 없음')}
- 현재 상황: {answers.get('situation', '알 수 없음')}
- 선호 장르: {', '.join(genres_clean) if genres_clean else '무관'}
- 선호 템포: {answers.get('tempo', '무관')}
- 언어 선호: {answers.get('language', '무관')}
- 시대 선호: {answers.get('era', '무관')}

반드시 실제 존재하는 노래만 추천하고, 다양한 아티스트를 포함하세요.

다음 JSON 형식으로만 응답하세요:
{{
  "playlist_mood": "이 플레이리스트의 전체 분위기 한 줄 요약",
  "songs": [
    {{
      "title": "곡 제목",
      "artist": "아티스트명",
      "genre": "장르",
      "tempo": "빠름/보통/느림",
      "language": "한국어/영어/기타",
      "reason": "이 사람의 현재 기분과 상황에 어울리는 이유 1~2문장"
    }}
  ]
}}"""

if recommend_btn:
    # 이전 아티스트 패널 세션 초기화
    keys_to_del = [k for k in st.session_state if k.startswith("expand_artist_") or k.startswith("artist_songs_")]
    for k in keys_to_del:
        del st.session_state[k]

    with st.spinner("🎵 AI가 플레이리스트를 만들고 있어요..."):
        try:
            raw = call_gpt(
                system_msg=(
                    "당신은 음악 큐레이터 전문가입니다. "
                    "사용자의 현재 감정과 상황에 딱 맞는 노래를 추천합니다. "
                    "반드시 JSON 형식으로만 응답하세요."
                ),
                user_msg=build_prompt(answers, rec_count),
                temperature=0.85,
            )
            data = parse_songs(raw)
            if data.get("songs"):
                st.session_state.recommendation = data
                st.session_state.rec_answers = dict(answers)
            else:
                st.error("추천 결과를 파싱하지 못했습니다. 다시 시도해주세요.", icon="🚫")
        except Exception as e:
            st.error(f"추천 생성 실패: {e}", icon="🚫")

# ── 결과 표시 ───────────────────────────────────────────────────
if st.session_state.get("recommendation"):
    data = st.session_state.recommendation
    songs = data.get("songs", [])
    playlist_mood = data.get("playlist_mood", "")

    st.divider()
    st.subheader("🎧 나만의 추천 플레이리스트")

    # 플레이리스트 무드 배지
    saved_ans = st.session_state.get("rec_answers", {})
    badges = []
    if saved_ans.get("mood"):    badges.append(saved_ans["mood"].split(" ", 1)[0] + " " + saved_ans["mood"].split(" ", 1)[-1][:6])
    if saved_ans.get("situation"): badges.append(saved_ans["situation"].split(" ", 1)[-1][:8])
    if saved_ans.get("tempo"):   badges.append(saved_ans["tempo"].split(" ", 1)[-1][:8])

    badges_html = "".join(f'<span class="mood-badge">{b}</span>' for b in badges)
    if playlist_mood:
        st.markdown(
            f'{badges_html}<br><span style="color:#9ca3af; font-size:0.88rem;">🎼 {playlist_mood}</span>',
            unsafe_allow_html=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)
    st.caption("🔗 곡 제목 클릭 → YouTube 검색 &nbsp;|&nbsp; 🎤 아티스트 버튼 → 해당 가수 노래 더 보기")

    # 노래 카드 렌더링
    render_song_cards(songs, prefix="main")

    st.divider()

    # 하단 버튼들
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("🔄 다시 추천받기", key="retry_btn"):
            keys_to_del = [k for k in st.session_state if k.startswith("expand_artist_") or k.startswith("artist_songs_")]
            for k in keys_to_del:
                del st.session_state[k]
            with st.spinner("🎵 새 플레이리스트 생성 중..."):
                try:
                    raw = call_gpt(
                        system_msg=(
                            "당신은 음악 큐레이터 전문가입니다. "
                            "이전과 다른 노래들로 추천해주세요. "
                            "반드시 JSON 형식으로만 응답하세요."
                        ),
                        user_msg=build_prompt(saved_ans, rec_count),
                        temperature=0.95,
                    )
                    data = parse_songs(raw)
                    if data.get("songs"):
                        st.session_state.recommendation = data
                        st.rerun()
                except Exception as e:
                    st.error(f"오류: {e}")

    with col2:
        if st.button("🗑️ 초기화", key="reset_btn"):
            for q in QUESTIONS:
                st.session_state.pop(f"q_{q['key']}", None)
            keys_to_del = [k for k in st.session_state if
                           k.startswith("expand_artist_") or k.startswith("artist_songs_")]
            for k in keys_to_del:
                del st.session_state[k]
            st.session_state.pop("recommendation", None)
            st.session_state.pop("rec_answers", None)
            st.rerun()

    with col3:
        playlist_text = "\n".join(
            f"{i+1}. {s['title']} - {s['artist']}"
            for i, s in enumerate(songs)
        )
        st.download_button(
            "⬇️ 저장 (.txt)",
            data=playlist_text.encode("utf-8"),
            file_name="my_playlist.txt",
            mime="text/plain",
            key="download_playlist",
        )

st.divider()
st.caption("Powered by OpenAI GPT-4o-mini · 곡 제목 클릭 시 YouTube 검색 페이지로 이동합니다 · 투자/의료 목적이 아닌 참고용입니다")
