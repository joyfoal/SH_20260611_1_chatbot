import hashlib
import json
import io
import datetime
import urllib.request
import streamlit as st
import streamlit.components.v1 as components
from openai import OpenAI

st.set_page_config(page_title="나의 이야기로 글 쓰기", page_icon="📖", layout="centered")

# ── CSS ───────────────────────────────────────────────────
st.markdown("""
<style>
[data-testid="stAppViewContainer"] { background: #f0f0f0; }
[data-testid="stHeader"] { background: transparent; }
[data-testid="stSidebar"] { background: white; }

/* 채팅 메시지 */
[data-testid="stChatMessage"] {
    background: white;
    border-radius: 14px;
    padding: 4px 8px;
    margin: 2px 0;
}

/* 입력 카드 */
div[data-testid="stVerticalBlockBorderWrapper"] {
    border-radius: 20px !important;
    border: 1.5px solid #ddd !important;
    box-shadow: 0 4px 24px rgba(0,0,0,0.10) !important;
    background: white !important;
    padding: 4px 12px 6px !important;
}

/* 입력창 안 text_input 테두리 제거 */
div[data-testid="stVerticalBlockBorderWrapper"] [data-baseweb="base-input"],
div[data-testid="stVerticalBlockBorderWrapper"] [data-baseweb="input"] {
    border: none !important;
    box-shadow: none !important;
    background: transparent !important;
}
div[data-testid="stVerticalBlockBorderWrapper"] input[type="text"] {
    border: none !important;
    box-shadow: none !important;
    background: transparent !important;
    font-size: 15px !important;
    padding: 6px 4px !important;
}
div[data-testid="stVerticalBlockBorderWrapper"] input[type="text"]:focus {
    border: none !important;
    box-shadow: none !important;
    outline: none !important;
}

/* 마이크·전송 버튼 */
div[data-testid="stVerticalBlockBorderWrapper"] .stButton > button {
    border-radius: 50% !important;
    background: transparent !important;
    border: none !important;
    color: #555 !important;
    font-size: 20px !important;
    width: 40px !important;
    height: 40px !important;
    padding: 2px !important;
    line-height: 1 !important;
}
div[data-testid="stVerticalBlockBorderWrapper"] .stButton > button:hover {
    background: #f0f0f0 !important;
}
div[data-testid="stVerticalBlockBorderWrapper"] button[kind="primary"] {
    border-radius: 10px !important;
    background: #1a1a1a !important;
    color: white !important;
    font-size: 14px !important;
    width: auto !important;
    padding: 6px 14px !important;
    border: none !important;
    height: 38px !important;
    border-radius: 10px !important;
}
div[data-testid="stVerticalBlockBorderWrapper"] button[kind="primary"]:hover {
    background: #333 !important;
}

/* 웨이브폼 애니메이션 */
@keyframes wv {
    0%, 100% { transform: scaleY(0.25); opacity: 0.6; }
    50%       { transform: scaleY(1);    opacity: 1; }
}
.wv-bar {
    width: 4px;
    background: #6366f1;
    border-radius: 3px;
    animation: wv 0.85s ease-in-out infinite;
}
.wv-wrap {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 4px;
    height: 38px;
    cursor: pointer;
}
</style>
""", unsafe_allow_html=True)

# Enter → 전송 버튼 클릭 JS 인젝션
components.html("""
<script>
(function() {
    var doc = window.parent.document;
    doc.addEventListener('keydown', function(e) {
        if (e.key !== 'Enter' || e.shiftKey || e.ctrlKey || e.metaKey) return;
        var active = doc.activeElement;
        if (!active || active.tagName !== 'INPUT') return;
        // 마이크/음성 위젯 제외
        if (active.type === 'submit' || active.type === 'button') return;
        // primary 버튼 클릭 (전송 버튼)
        var btns = Array.from(
            doc.querySelectorAll('button[kind="primary"]')
        );
        if (btns.length > 0) {
            e.preventDefault();
            e.stopPropagation();
            btns[btns.length - 1].click();
        }
    }, true);
})();
</script>
""", height=0, scrolling=False)

# ── Session state ─────────────────────────────────────────
DEFAULTS = {
    "chat_mode": "고민 해결",
    "messages": [],
    "writing_genre": None,
    "written_content": None,
    "image_data": None,
    "lyrics_content": None,
    "lyrics_style": "",
    "music_data": None,
    "voice_mode": False,
    "voice_counter": 0,
    "last_audio_hash": None,
    "text_key": 0,
}
for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ── 프롬프트 ──────────────────────────────────────────────
CHAT_PROMPTS = {
    "고민 해결": "당신은 따뜻하고 지혜로운 상담사입니다. 사용자의 고민을 경청하고 공감한 뒤 실질적인 해결책을 제시해주세요. '할 수 있다'는 자신감을 심어주고 진심으로 응원해주세요. 한국어로 대화해주세요.",
    "칭찬 하기": "당신은 사용자의 가장 열렬한 응원자입니다. 사용자가 말하는 것에서 긍정적인 면을 찾아 구체적으로 칭찬하고 격려해주세요. 한국어로 밝고 따뜻하게 대화해주세요.",
    "긍정 반응": "당신은 긍정의 에너지로 가득 찬 친구입니다. 어떤 상황에서도 밝고 희망적인 면을 찾아 격려해주세요. 한국어로 활기차게 대화해주세요.",
    "글 쓰기 계속": "당신은 창의적인 글쓰기 파트너입니다. 이전 대화와 앞서 쓴 글의 맥락을 이어받아 사용자의 아이디어를 발전시켜주세요. 한국어로 대화해주세요.",
}
WRITING_PROMPTS = {
    "소설": "아래 대화를 바탕으로 흥미롭고 감동적인 소설을 한국어로 500자 이상 써주세요.",
    "수필": "아래 대화를 바탕으로 아름답고 진솔한 수필을 한국어로 400자 이상 써주세요.",
    "시":   "아래 대화를 바탕으로 감동적인 시를 한국어로 써주세요.",
}
IMAGE_STYLE = {
    "소설": "dramatic narrative book illustration, cinematic lighting",
    "수필": "soft watercolor painting, peaceful warm tones",
    "시":   "abstract poetic art, dreamy surrealism, emotional colors",
}

MUSIC_GENRE_STYLE = {
    "소설": "웅장하고 서사적인 영화음악 스타일 발라드, 오케스트라와 피아노",
    "수필": "잔잔하고 감성적인 어쿠스틱 발라드, 기타와 피아노",
    "시":   "서정적이고 몽환적인 팝 발라드, 감성적인 멜로디",
}

WAVEFORM_HTML = """
<div class="wv-wrap" title="녹음 중... 클릭하면 종료">
  <div class="wv-bar" style="height:12px;animation-delay:0s"></div>
  <div class="wv-bar" style="height:22px;animation-delay:.12s"></div>
  <div class="wv-bar" style="height:32px;animation-delay:.24s"></div>
  <div class="wv-bar" style="height:22px;animation-delay:.36s"></div>
  <div class="wv-bar" style="height:12px;animation-delay:.48s"></div>
</div>
"""


def get_system(mode: str) -> str:
    s = CHAT_PROMPTS[mode]
    if mode == "글 쓰기 계속" and st.session_state.written_content:
        s += f"\n\n앞서 쓴 글:\n{st.session_state.written_content}"
    return s


def stream_ai(system: str):
    stream = client.chat.completions.create(
        model=selected_model,
        messages=[{"role": "system", "content": system}]
        + [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages],
        temperature=temperature,
        stream=True,
    )
    with st.chat_message("assistant"):
        response = st.write_stream(stream)
    return response


def call_ai(system: str) -> str:
    resp = client.chat.completions.create(
        model=selected_model,
        messages=[{"role": "system", "content": system}]
        + [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages],
        temperature=temperature,
    )
    return resp.choices[0].message.content


def generate_writing(genre: str) -> str:
    system = WRITING_PROMPTS[genre]
    if st.session_state.chat_mode == "글 쓰기 계속" and st.session_state.written_content:
        system += f"\n\n앞서 쓴 {genre}:\n{st.session_state.written_content}\n\n위 내용에 이어서 계속 써주세요."
    msgs = [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages]
    msgs.append({"role": "user", "content": f"대화 내용을 바탕으로 {genre}를 써주세요."})
    with st.spinner(f"📝 {genre} 작성 중..."):
        resp = client.chat.completions.create(
            model=selected_model,
            messages=[{"role": "system", "content": system}] + msgs,
            temperature=temperature,
        )
    return resp.choices[0].message.content


def generate_image(genre: str, text: str) -> bytes:
    with st.spinner("🎨 그림 그리는 중..."):
        pr = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": f"다음 한국어 글의 핵심 장면을 DALL-E 프롬프트로 영어 60단어 이내로 써주세요. 스타일: {IMAGE_STYLE[genre]}"},
                {"role": "user", "content": text[:1200]},
            ],
            max_tokens=120,
        )
        img = client.images.generate(
            model="dall-e-3",
            prompt=pr.choices[0].message.content,
            size="1024x1024", n=1,
        )
        with urllib.request.urlopen(img.data[0].url) as r:
            return r.read()


def generate_lyrics(genre: str, written_text: str) -> tuple:
    """GPT로 가사와 음악 스타일 설명을 생성한다."""
    style_hint = MUSIC_GENRE_STYLE.get(genre, "감성적인 한국 발라드")
    system = f"""당신은 한국의 전문 가사 작가입니다.
아래 {genre} 내용을 바탕으로 한국어 노래 가사를 써주세요.
음악 스타일: {style_hint}

다음 형식을 반드시 지켜주세요:

[인트로]
(짧은 도입 가사)

[버스 1]
(이야기의 시작과 감정)

[코러스]
(핵심 메시지 - 반복될 부분, 강렬하게)

[버스 2]
(이야기의 전개와 심화)

[코러스]
(핵심 메시지 반복)

[브릿지]
(감정의 절정, 전환)

[코러스]
(마지막 코러스)

[아웃트로]
(여운이 남는 마무리)

---
[음악 스타일]
장르/분위기/템포/악기를 한 줄로 설명"""

    with st.spinner("🎵 가사 작성 중..."):
        resp = client.chat.completions.create(
            model=selected_model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": f"이 {genre} 내용으로 가사를 써주세요:\n\n{written_text[:2000]}"},
            ],
            temperature=0.95,
        )
    full = resp.choices[0].message.content

    if "---" in full and "[음악 스타일]" in full:
        parts = full.split("---")
        lyrics = parts[0].strip()
        style = parts[1].replace("[음악 스타일]", "").strip()
    else:
        lyrics = full
        style = style_hint
    return lyrics, style


def generate_music_replicate(prompt: str, replicate_key: str) -> bytes:
    """Replicate MusicGen으로 배경음악을 생성한다 (Prefer: wait 동기 방식)."""
    import time
    headers = {
        "Authorization": f"Bearer {replicate_key}",
        "Content-Type": "application/json",
    }
    payload = json.dumps({
        "version": "671ac645ce5e552cc63a54a2bbff63fcf798043055d2dac5fc9e36a837eedcfb",
        "input": {
            "prompt": prompt,
            "duration": 20,
            "model_version": "stereo-large",
            "output_format": "mp3",
        },
    }).encode()

    req = urllib.request.Request(
        "https://api.replicate.com/v1/predictions",
        data=payload, headers=headers, method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        prediction = json.loads(r.read())

    get_url = prediction["urls"]["get"]
    for _ in range(90):
        time.sleep(2)
        req2 = urllib.request.Request(
            get_url,
            headers={"Authorization": f"Bearer {replicate_key}"},
        )
        with urllib.request.urlopen(req2, timeout=15) as r:
            result = json.loads(r.read())
        if result["status"] == "succeeded":
            audio_url = result["output"]
            if isinstance(audio_url, list):
                audio_url = audio_url[0]
            with urllib.request.urlopen(audio_url) as r:
                return r.read()
        if result["status"] == "failed":
            raise Exception(result.get("error", "음악 생성 실패"))
    raise Exception("음악 생성 시간 초과 (3분)")


# ── 사이드바 ──────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ 설정")
    openai_api_key = st.text_input("OpenAI API Key", type="password")
    st.divider()
    selected_model = st.selectbox("모델", ["gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo"])
    temperature = st.slider("창의성", 0.0, 2.0, 0.7, 0.05)
    st.divider()
    st.markdown("**🎵 음악 생성 (선택)**")
    replicate_key = st.text_input(
        "Replicate API Key",
        type="password",
        help="배경음악 파일 생성용. replicate.com에서 무료 발급. 없으면 가사만 생성됩니다.",
    )
    st.divider()

    if st.session_state.messages:
        st.subheader("📥 내보내기")
        def build_txt():
            lines = [f"[{'나' if m['role']=='user' else 'AI'}]\n{m['content']}"
                     for m in st.session_state.messages]
            if st.session_state.written_content:
                lines.append(f"\n[{st.session_state.writing_genre or '글'}]\n{st.session_state.written_content}")
            return "\n\n".join(lines)
        def build_json():
            return json.dumps({"exported_at": datetime.datetime.now().isoformat(),
                               "model": selected_model,
                               "messages": st.session_state.messages,
                               "written_content": st.session_state.written_content},
                              ensure_ascii=False, indent=2)
        c1, c2 = st.columns(2)
        with c1: st.download_button(".txt", build_txt(), "chat.txt", use_container_width=True)
        with c2: st.download_button(".json", build_json(), "chat.json", use_container_width=True)

    if st.button("🗑️ 전체 초기화", use_container_width=True):
        for k, v in DEFAULTS.items():
            st.session_state[k] = v
        st.rerun()

# ── API 키 확인 ───────────────────────────────────────────
if not openai_api_key:
    st.title("📖 나의 이야기로 글 쓰기")
    st.info("사이드바에 OpenAI API 키를 입력하세요.", icon="🗝️")
    st.stop()

client = OpenAI(api_key=openai_api_key)

# ── 헤더 & 모드 버튼 ──────────────────────────────────────
st.title("📖 나의 이야기로 글 쓰기")

MODES = [("🤔 고민 해결","고민 해결"),("🌟 칭찬 하기","칭찬 하기"),
         ("☀️ 긍정 반응","긍정 반응"),("✏️ 글 쓰기 계속","글 쓰기 계속")]
mc = st.columns(len(MODES))
for col, (label, mode) in zip(mc, MODES):
    with col:
        active = st.session_state.chat_mode == mode
        if st.button(label, use_container_width=True,
                     type="primary" if active else "secondary", key=f"mode_{mode}"):
            if not active:
                st.session_state.chat_mode = mode
                if mode != "글 쓰기 계속":
                    st.session_state.messages = []
                    st.session_state.written_content = None
                    st.session_state.image_data = None
                    st.session_state.writing_genre = None
                st.rerun()

st.caption(f"현재 모드: **{st.session_state.chat_mode}**")

if st.session_state.chat_mode == "글 쓰기 계속" and st.session_state.written_content:
    g = st.session_state.writing_genre or "글"
    with st.expander(f"📄 이전에 쓴 {g}", expanded=False):
        st.markdown(st.session_state.written_content)
        st.download_button(f"📥 {g} 다운로드", st.session_state.written_content,
                           f"나의_{g}.txt", key="prev_dl")

st.divider()

# ── 대화 메시지 ───────────────────────────────────────────
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

st.write("")

# ── 입력 카드: [텍스트] [🎤/웨이브폼] [전송▶] 한 줄 ────────
with st.container(border=True):
    col_text, col_mic, col_send = st.columns([7, 1, 1.8])

    with col_text:
        user_input = st.text_input(
            "",
            placeholder="메시지를 입력하세요...",
            key=f"inp_{st.session_state.text_key}",
            label_visibility="collapsed",
        )

    with col_mic:
        if st.session_state.voice_mode:
            # 애니메이션 웨이브폼
            st.markdown(WAVEFORM_HTML, unsafe_allow_html=True)
            # 웨이브폼 아래 작은 종료 버튼
            if st.button("⏹", key="stop_voice", help="음성 종료"):
                st.session_state.voice_mode = False
                st.rerun()
        else:
            if st.button("🎤", key="start_voice", help="음성 대화 시작"):
                st.session_state.voice_mode = True
                st.rerun()

    with col_send:
        send_clicked = st.button("전송 ▶", type="primary",
                                 key="send_btn", use_container_width=True)

# ── 텍스트 전송 처리 ──────────────────────────────────────
if send_clicked:
    text = user_input.strip() if user_input else ""
    if text:
        st.session_state.messages.append({"role": "user", "content": text})
        with st.chat_message("user"):
            st.markdown(text)
        response = stream_ai(get_system(st.session_state.chat_mode))
        st.session_state.messages.append({"role": "assistant", "content": response})
        st.session_state.text_key += 1
        st.rerun()

# ── 음성 대화 모드 ────────────────────────────────────────
if st.session_state.voice_mode:
    st.markdown("---")
    st.markdown("**🎤 음성 대화 모드** — 녹음 버튼을 눌러 말하면 자동으로 응답합니다.")

    audio = st.audio_input(
        "누르고 말하세요",
        key=f"voice_{st.session_state.voice_counter}",
    )

    if audio is not None:
        audio_bytes = audio.read()
        audio_hash = hashlib.md5(audio_bytes).hexdigest()

        if audio_hash != st.session_state.last_audio_hash:
            st.session_state.last_audio_hash = audio_hash

            with st.spinner("🎤 음성 인식 중..."):
                try:
                    transcript = client.audio.transcriptions.create(
                        model="whisper-1",
                        file=("audio.wav", audio_bytes, "audio/wav"),
                        language="ko",
                    )
                    voice_text = transcript.text.strip()
                except Exception as e:
                    st.error(f"음성 인식 실패: {e}")
                    voice_text = ""

            if voice_text:
                st.session_state.messages.append({"role": "user", "content": f"🎤 {voice_text}"})
                with st.chat_message("user"):
                    st.markdown(f"🎤 {voice_text}")

                with st.spinner("💭 답변 생성 중..."):
                    ai_text = call_ai(get_system(st.session_state.chat_mode))
                st.session_state.messages.append({"role": "assistant", "content": ai_text})
                with st.chat_message("assistant"):
                    st.markdown(ai_text)

                st.session_state.voice_counter += 1
                st.rerun()

st.divider()

# ── 글로 만들기 섹션 ──────────────────────────────────────
if st.session_state.messages:
    st.subheader("✍️ 글로 만들기")
    st.caption("대화 내용을 바탕으로 원하는 형식의 글을 써드립니다.")

    gc = st.columns(3)
    for col, (label, genre) in zip(
        gc, [("📚 소설","소설"),("✍️ 수필","수필"),("🎵 시","시")]
    ):
        with col:
            active = st.session_state.writing_genre == genre
            if st.button(label, use_container_width=True,
                         type="primary" if active else "secondary", key=f"genre_{genre}"):
                st.session_state.writing_genre = genre
                st.session_state.image_data = None
                st.session_state.lyrics_content = None
                st.session_state.lyrics_style = ""
                st.session_state.music_data = None
                st.session_state.written_content = generate_writing(genre)
                st.rerun()

    if st.session_state.written_content and st.session_state.writing_genre:
        g = st.session_state.writing_genre
        with st.expander(f"📄 {g}", expanded=True):
            st.markdown(st.session_state.written_content)

        # 버튼 행: 다운로드 | 그림 생성 | 음악 만들기 | 글 쓰기 계속 | 대화 초기화
        a1, a2, a3, a4, a5 = st.columns(5)
        with a1:
            st.download_button(f"📥 {g} 다운로드", st.session_state.written_content,
                               f"나의_{g}.txt", use_container_width=True)
        with a2:
            if st.button("🖼️ 그림 생성", use_container_width=True):
                try:
                    st.session_state.image_data = generate_image(g, st.session_state.written_content)
                except Exception as e:
                    st.error(f"그림 생성 실패: {e}")
                st.rerun()
        with a3:
            if st.button("🎵 음악 만들기", use_container_width=True):
                with st.spinner("🎵 가사 생성 중..."):
                    try:
                        lyrics, style = generate_lyrics(g, st.session_state.written_content)
                        st.session_state.lyrics_content = lyrics
                        st.session_state.lyrics_style = style
                    except Exception as e:
                        st.error(f"가사 생성 실패: {e}")
                        lyrics = None
                if lyrics and replicate_key:
                    with st.spinner("🎶 음악 생성 중... (1~2분 소요)"):
                        try:
                            st.session_state.music_data = generate_music_replicate(style, replicate_key)
                        except Exception as e:
                            st.error(f"음악 생성 실패: {e}")
                st.rerun()
        with a4:
            if st.button("✏️ 글 쓰기 계속", use_container_width=True, type="primary"):
                st.session_state.chat_mode = "글 쓰기 계속"
                st.rerun()
        with a5:
            if st.button("🗑️ 대화 초기화", use_container_width=True):
                st.session_state.messages = []
                st.session_state.text_key += 1
                st.rerun()

        if st.session_state.image_data:
            st.image(st.session_state.image_data, caption=f"{g} 삽화",
                     use_container_width=True)
            st.download_button("📥 이미지 다운로드", st.session_state.image_data,
                               f"나의_{g}_그림.png", "image/png",
                               use_container_width=True, key="dl_img")

        if st.session_state.lyrics_content:
            with st.expander("🎵 가사", expanded=True):
                st.markdown(st.session_state.lyrics_content)
                if st.session_state.lyrics_style:
                    st.caption(f"음악 스타일: {st.session_state.lyrics_style}")
            st.download_button("📥 가사 다운로드", st.session_state.lyrics_content,
                               f"나의_{g}_가사.txt", use_container_width=True, key="dl_lyrics")
            if st.session_state.music_data:
                st.audio(st.session_state.music_data, format="audio/mp3")
                st.download_button("📥 음악 다운로드", st.session_state.music_data,
                                   f"나의_{g}_음악.mp3", "audio/mp3",
                                   use_container_width=True, key="dl_music")
