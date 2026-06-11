import hashlib
import json
import datetime
import urllib.request
import streamlit as st
from openai import OpenAI

st.set_page_config(page_title="AI 챗봇", page_icon="💬", layout="centered")

# ── Session state ─────────────────────────────────────────
DEFAULTS = {
    "chat_mode": "고민 해결",
    "messages": [],
    "writing_genre": None,
    "written_content": None,
    "image_data": None,
    "last_audio_hash": None,
}
for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ── 프롬프트 ──────────────────────────────────────────────
CHAT_PROMPTS = {
    "고민 해결": (
        "당신은 따뜻하고 지혜로운 상담사입니다. "
        "사용자의 고민을 경청하고 충분히 공감한 뒤 실질적인 해결책을 제시해주세요. "
        "대화 끝에는 '할 수 있다'는 자신감을 심어주고 진심으로 응원해주세요. "
        "한국어로 따뜻하게 대화해주세요."
    ),
    "칭찬 하기": (
        "당신은 사용자의 가장 열렬한 응원자입니다. "
        "사용자가 말하는 것에서 긍정적인 면을 찾아 구체적으로 칭찬하고 격려해주세요. "
        "한국어로 밝고 따뜻하게 대화해주세요."
    ),
    "긍정 반응": (
        "당신은 긍정의 에너지로 가득 찬 친구입니다. "
        "어떤 상황에서도 밝고 희망적인 면을 찾아 사용자를 격려해주세요. "
        "한국어로 활기차게 대화해주세요."
    ),
    "글 쓰기 계속": (
        "당신은 창의적인 글쓰기 파트너입니다. "
        "이전 대화와 앞서 쓴 글의 맥락을 이어받아 사용자의 아이디어를 함께 발전시켜주세요. "
        "한국어로 대화해주세요."
    ),
}

WRITING_PROMPTS = {
    "소설": (
        "아래 대화 내용을 바탕으로 흥미롭고 감동적인 소설을 써주세요. "
        "생생한 묘사, 입체적인 인물, 긴장감 있는 전개로 이야기를 만들어주세요. "
        "한국어로 500자 이상 작성해주세요."
    ),
    "수필": (
        "아래 대화 내용을 바탕으로 아름답고 진솔한 수필을 써주세요. "
        "일상에서 발견하는 소중한 의미와 감동을 섬세한 문체로 담아주세요. "
        "한국어로 400자 이상 작성해주세요."
    ),
    "시": (
        "아래 대화 내용을 바탕으로 감동적인 시를 써주세요. "
        "리듬감 있고 아름다운 언어로 마음속 이야기를 시의 형식으로 전달해주세요. "
        "한국어로 작성해주세요."
    ),
}

IMAGE_STYLE = {
    "소설": "dramatic narrative book illustration, cinematic lighting, detailed scene",
    "수필": "soft watercolor painting, peaceful atmosphere, warm tones",
    "시": "abstract poetic art, dreamy surrealism, emotional and artistic",
}


def get_system(mode: str) -> str:
    s = CHAT_PROMPTS[mode]
    if mode == "글 쓰기 계속" and st.session_state.written_content:
        s += f"\n\n앞서 쓴 글:\n{st.session_state.written_content}"
    return s


def call_ai(system: str, messages: list) -> str:
    """AI 응답을 반환한다 (스트리밍 없이)."""
    resp = client.chat.completions.create(
        model=selected_model,
        messages=[{"role": "system", "content": system}]
        + [{"role": m["role"], "content": m["content"]} for m in messages],
        temperature=temperature,
    )
    return resp.choices[0].message.content


def send_message(user_text: str):
    """사용자 메시지를 추가하고 AI 응답을 받는다."""
    st.session_state.messages.append({"role": "user", "content": user_text})
    with st.spinner("AI 응답 중..."):
        ai_text = call_ai(get_system(st.session_state.chat_mode), st.session_state.messages)
    st.session_state.messages.append({"role": "assistant", "content": ai_text})
    st.rerun()


def generate_writing(genre: str) -> str:
    system = WRITING_PROMPTS[genre]
    if st.session_state.chat_mode == "글 쓰기 계속" and st.session_state.written_content:
        system += (
            f"\n\n앞서 쓴 {genre}:\n{st.session_state.written_content}\n\n"
            "위 내용에 자연스럽게 이어서 계속 써주세요."
        )
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
        prompt_resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "다음 한국어 글의 핵심 장면과 분위기를 DALL-E 이미지 프롬프트로 "
                        f"영어 60단어 이내로 작성해주세요. 스타일: {IMAGE_STYLE[genre]}"
                    ),
                },
                {"role": "user", "content": text[:1200]},
            ],
            max_tokens=120,
        )
        image_prompt = prompt_resp.choices[0].message.content
        img_resp = client.images.generate(
            model="dall-e-3",
            prompt=image_prompt,
            size="1024x1024",
            quality="standard",
            n=1,
        )
        with urllib.request.urlopen(img_resp.data[0].url) as r:
            return r.read()


# ── 사이드바 ──────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ 설정")
    openai_api_key = st.text_input("OpenAI API Key", type="password")
    st.divider()

    selected_model = st.selectbox(
        "모델 선택",
        ["gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo"],
        help="gpt-4o-mini: 빠르고 저렴 / gpt-4o: 최고 성능",
    )
    temperature = st.slider("창의성 (Temperature)", 0.0, 2.0, 0.7, 0.05)
    st.divider()

    if st.session_state.messages:
        st.subheader("📥 내보내기")

        def build_txt():
            lines = []
            for m in st.session_state.messages:
                role = "나" if m["role"] == "user" else "AI"
                lines.append(f"[{role}]\n{m['content']}")
            if st.session_state.written_content:
                g = st.session_state.writing_genre or "글"
                lines.append(f"\n[{g}]\n{st.session_state.written_content}")
            return "\n\n".join(lines)

        def build_json():
            return json.dumps(
                {
                    "exported_at": datetime.datetime.now().isoformat(),
                    "model": selected_model,
                    "chat_mode": st.session_state.chat_mode,
                    "messages": st.session_state.messages,
                    "written_content": st.session_state.written_content,
                },
                ensure_ascii=False,
                indent=2,
            )

        c1, c2 = st.columns(2)
        with c1:
            st.download_button(".txt", build_txt(), "chat.txt", "text/plain", use_container_width=True)
        with c2:
            st.download_button(".json", build_json(), "chat.json", "application/json", use_container_width=True)

    if st.button("🗑️ 전체 초기화", use_container_width=True):
        for k, v in DEFAULTS.items():
            st.session_state[k] = v
        st.rerun()

# ── API 키 확인 ───────────────────────────────────────────
if not openai_api_key:
    st.title("💬 AI 챗봇")
    st.info("사이드바에 OpenAI API 키를 입력하면 시작할 수 있습니다.", icon="🗝️")
    st.stop()

client = OpenAI(api_key=openai_api_key)

# ── 헤더 ─────────────────────────────────────────────────
st.title("💬 AI 챗봇")

# 모드 버튼
MODES = [
    ("🤔 고민 해결", "고민 해결"),
    ("🌟 칭찬 하기", "칭찬 하기"),
    ("☀️ 긍정 반응", "긍정 반응"),
    ("✏️ 글 쓰기 계속", "글 쓰기 계속"),
]
mode_cols = st.columns(len(MODES))
for col, (label, mode) in zip(mode_cols, MODES):
    with col:
        is_active = st.session_state.chat_mode == mode
        if st.button(label, use_container_width=True,
                     type="primary" if is_active else "secondary",
                     key=f"mode_{mode}"):
            if not is_active:
                st.session_state.chat_mode = mode
                if mode != "글 쓰기 계속":
                    st.session_state.messages = []
                    st.session_state.written_content = None
                    st.session_state.image_data = None
                    st.session_state.writing_genre = None
                st.rerun()

st.caption(f"현재 모드: **{st.session_state.chat_mode}**")

# 글 쓰기 계속: 이전 글 표시
if st.session_state.chat_mode == "글 쓰기 계속" and st.session_state.written_content:
    g = st.session_state.writing_genre or "글"
    with st.expander(f"📄 이전에 쓴 {g} 보기 / 다운로드", expanded=False):
        st.markdown(st.session_state.written_content)
        st.download_button(
            f"📥 {g} 다운로드",
            data=st.session_state.written_content,
            file_name=f"나의_{g}.txt",
            mime="text/plain",
            key="prev_dl",
        )

st.divider()

# ── 대화 메시지 표시 ──────────────────────────────────────
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# ── 입력 영역: 텍스트 + 음성 나란히 ──────────────────────
st.write("")  # 메시지와 입력창 사이 여백

text_col, voice_col = st.columns([3, 1])

with text_col:
    with st.form("chat_form", clear_on_submit=True, border=False):
        user_input = st.text_input(
            "메시지 입력",
            placeholder="메시지를 입력하세요... (Enter 또는 전송 버튼)",
            label_visibility="collapsed",
        )
        submitted = st.form_submit_button(
            "전송 ▶",
            use_container_width=True,
            type="primary",
        )

with voice_col:
    st.markdown("**🎤 음성 입력**")
    audio = st.audio_input("", label_visibility="collapsed")

# 텍스트 전송 처리
if submitted and user_input.strip():
    send_message(user_input.strip())

# 음성 전송 처리
if audio is not None:
    audio_bytes = audio.read()
    audio_hash = hashlib.md5(audio_bytes).hexdigest()
    if audio_hash != st.session_state.last_audio_hash:
        st.session_state.last_audio_hash = audio_hash
        with st.spinner("🎤 음성 변환 중..."):
            try:
                transcript = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=("audio.wav", audio_bytes, "audio/wav"),
                    language="ko",
                )
                voice_text = transcript.text.strip()
            except Exception as e:
                st.error(f"음성 변환 실패: {e}")
                voice_text = ""
        if voice_text:
            st.info(f"🎤 인식된 텍스트: **{voice_text}**")
            send_message(f"🎤 {voice_text}")

st.divider()

# ── 글로 만들기 섹션 ──────────────────────────────────────
if st.session_state.messages:
    st.subheader("✍️ 글로 만들기")
    st.caption("대화 내용을 바탕으로 원하는 형식의 글을 써드립니다.")

    g_cols = st.columns(3)
    for col, (label, genre) in zip(
        g_cols, [("📚 소설", "소설"), ("✍️ 수필", "수필"), ("🎵 시", "시")]
    ):
        with col:
            is_active = st.session_state.writing_genre == genre
            if st.button(
                label,
                use_container_width=True,
                type="primary" if is_active else "secondary",
                key=f"genre_{genre}",
            ):
                st.session_state.writing_genre = genre
                st.session_state.image_data = None
                st.session_state.written_content = generate_writing(genre)
                st.rerun()

    # 생성된 글 표시
    if st.session_state.written_content and st.session_state.writing_genre:
        g = st.session_state.writing_genre
        with st.expander(f"📄 {g}", expanded=True):
            st.markdown(st.session_state.written_content)

        act1, act2, act3 = st.columns(3)

        with act1:
            st.download_button(
                f"📥 {g} 다운로드",
                data=st.session_state.written_content,
                file_name=f"나의_{g}.txt",
                mime="text/plain",
                use_container_width=True,
            )

        with act2:
            if st.button("🖼️ 그림 생성", use_container_width=True):
                try:
                    st.session_state.image_data = generate_image(
                        g, st.session_state.written_content
                    )
                except Exception as e:
                    st.error(f"그림 생성 실패: {e}")
                st.rerun()

        with act3:
            if st.button("✏️ 글 쓰기 계속", use_container_width=True, type="primary"):
                st.session_state.chat_mode = "글 쓰기 계속"
                st.rerun()

        # 생성된 이미지
        if st.session_state.image_data:
            st.image(
                st.session_state.image_data,
                caption=f"{g} 삽화",
                use_container_width=True,
            )
            st.download_button(
                "📥 이미지 다운로드",
                data=st.session_state.image_data,
                file_name=f"나의_{g}_그림.png",
                mime="image/png",
                use_container_width=True,
                key="dl_image",
            )
