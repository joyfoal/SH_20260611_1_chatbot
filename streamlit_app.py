import hashlib
import json
import datetime
import streamlit as st
from openai import OpenAI

st.set_page_config(page_title="AI 챗봇", page_icon="💬")

# Session state 초기화
for key, default in [
    ("chatbot_type", None),
    ("messages", []),
    ("encourage_mode", "고민 해결"),
    ("story_genre", "소설"),
    ("last_audio_hash", None),
]:
    if key not in st.session_state:
        st.session_state[key] = default

SYSTEM_PROMPTS = {
    "encourage": {
        "고민 해결": (
            "당신은 따뜻하고 지혜로운 상담사입니다. "
            "사용자의 고민을 경청하고 충분히 공감한 뒤, 실질적인 해결책을 제시해주세요. "
            "대화 끝에는 항상 '할 수 있다'는 자신감을 심어주고 진심으로 응원해주세요. "
            "한국어로 따뜻하게 대화해주세요."
        ),
        "칭찬": (
            "당신은 사용자의 가장 열렬한 응원자입니다. "
            "사용자가 말하는 것에서 긍정적인 면과 칭찬할 점을 찾아 구체적으로 칭찬하고 격려해주세요. "
            "진심이 담긴 칭찬으로 사용자의 자존감을 높여주세요. "
            "한국어로 밝고 따뜻하게 대화해주세요."
        ),
        "긍정 반응": (
            "당신은 긍정의 에너지로 가득 찬 친구입니다. "
            "어떤 상황에서도 밝고 희망적인 면을 찾아 사용자를 격려해주세요. "
            "'할 수 있다', '잘 될 거야'라는 메시지를 자연스럽게 전달해주세요. "
            "한국어로 활기차고 따뜻하게 대화해주세요."
        ),
    },
    "story": {
        "소설": (
            "당신은 전문 소설가입니다. "
            "사용자와 나누는 대화를 바탕으로 흥미롭고 감동적인 소설을 써주세요. "
            "생생한 묘사, 입체적인 인물, 긴장감 있는 전개로 독자를 끌어당기는 이야기를 만들어가세요. "
            "한국어로 작성해주세요."
        ),
        "수필": (
            "당신은 감성적인 수필 작가입니다. "
            "사용자의 경험과 생각을 바탕으로 아름답고 진솔한 수필을 써주세요. "
            "일상에서 발견하는 소중한 의미와 감동을 섬세한 문체로 담아주세요. "
            "한국어로 작성해주세요."
        ),
        "시": (
            "당신은 재능 있는 시인입니다. "
            "사용자의 감정과 이야기를 아름다운 시로 표현해주세요. "
            "리듬감 있고 감동적인 언어로 마음속 이야기를 시의 형식으로 전달해주세요. "
            "한국어로 작성해주세요."
        ),
    },
}

# ── 사이드바 ──────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ 설정")
    openai_api_key = st.text_input("OpenAI API Key", type="password")
    st.divider()

    selected_model = st.selectbox(
        "모델 선택",
        options=["gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo"],
        index=0,
        help="gpt-4o-mini: 빠르고 저렴 / gpt-4o: 최고 성능 / gpt-3.5-turbo: 구형 모델",
    )
    temperature = st.slider(
        "창의성 (Temperature)",
        min_value=0.0, max_value=2.0, value=0.7, step=0.05,
        help="낮을수록 일관된 답변, 높을수록 창의적 답변",
    )
    st.divider()

    if st.session_state.chatbot_type:
        if st.button("🏠 처음으로", use_container_width=True):
            st.session_state.chatbot_type = None
            st.session_state.messages = []
            st.session_state.last_audio_hash = None
            st.rerun()

    if st.session_state.messages:
        st.subheader("📥 내보내기")

        def build_txt():
            lines = []
            for m in st.session_state.messages:
                role = "나" if m["role"] == "user" else "AI"
                lines.append(f"[{role}]\n{m['content']}")
            return "\n\n".join(lines)

        def build_json():
            return json.dumps(
                {
                    "exported_at": datetime.datetime.now().isoformat(),
                    "model": selected_model,
                    "chatbot_type": st.session_state.chatbot_type,
                    "messages": st.session_state.messages,
                },
                ensure_ascii=False, indent=2,
            )

        col1, col2 = st.columns(2)
        with col1:
            st.download_button(".txt", build_txt(), "chat.txt", "text/plain", use_container_width=True)
        with col2:
            st.download_button(".json", build_json(), "chat.json", "application/json", use_container_width=True)

        if st.button("🗑️ 대화 초기화", use_container_width=True):
            st.session_state.messages = []
            st.session_state.last_audio_hash = None
            st.rerun()

# ── API 키 확인 ───────────────────────────────────────────
if not openai_api_key:
    st.title("💬 AI 챗봇")
    st.info("사이드바에 OpenAI API 키를 입력하면 시작할 수 있습니다.", icon="🗝️")
    st.stop()

client = OpenAI(api_key=openai_api_key)


def send_message(system_prompt: str, user_text: str):
    """메시지를 세션에 저장하고 AI 응답을 스트리밍한다."""
    st.session_state.messages.append({"role": "user", "content": user_text})
    with st.chat_message("user"):
        st.markdown(user_text)

    stream = client.chat.completions.create(
        model=selected_model,
        messages=[{"role": "system", "content": system_prompt}]
        + [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages],
        temperature=temperature,
        stream=True,
    )
    with st.chat_message("assistant"):
        response = st.write_stream(stream)
    st.session_state.messages.append({"role": "assistant", "content": response})


def run_chat(system_prompt: str, placeholder: str):
    # 기존 대화 표시
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # ── 음성 입력 ──────────────────────────────────────────
    audio = st.audio_input("🎤 마이크로 말하기 (누르고 말한 뒤 다시 누르면 전송)")

    if audio is not None:
        audio_bytes = audio.read()
        audio_hash = hashlib.md5(audio_bytes).hexdigest()

        # 같은 녹음을 두 번 처리하지 않는다
        if audio_hash != st.session_state.last_audio_hash:
            st.session_state.last_audio_hash = audio_hash

            with st.spinner("🎤 음성을 텍스트로 변환 중..."):
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
                send_message(system_prompt, f"🎤 {voice_text}")

    # ── 텍스트 입력 ────────────────────────────────────────
    if prompt := st.chat_input(placeholder):
        send_message(system_prompt, prompt)


# ── 메인 화면 ─────────────────────────────────────────────
if st.session_state.chatbot_type is None:
    st.title("💬 AI 챗봇")
    st.write("어떤 챗봇을 시작할까요?")
    st.write("")

    col1, col2 = st.columns(2, gap="large")

    with col1:
        with st.container(border=True):
            st.markdown("### 💪 할 수 있다")
            st.write("고민을 들어주고 칭찬과 응원으로 자신감을 키워드립니다.")
            st.markdown("- 🤔 고민 해결\n- 🌟 칭찬\n- ☀️ 긍정 반응")
            st.write("")
            if st.button("💪 할 수 있다 시작", use_container_width=True, type="primary"):
                st.session_state.chatbot_type = "encourage"
                st.session_state.messages = []
                st.session_state.last_audio_hash = None
                st.rerun()

    with col2:
        with st.container(border=True):
            st.markdown("### 📖 이야기")
            st.write("대화를 나누면서 소설, 수필, 시를 함께 만들어갑니다.")
            st.markdown("- 📚 소설\n- ✍️ 수필\n- 🎵 시")
            st.write("")
            if st.button("📖 이야기 시작", use_container_width=True, type="primary"):
                st.session_state.chatbot_type = "story"
                st.session_state.messages = []
                st.session_state.last_audio_hash = None
                st.rerun()

# ── 할 수 있다 챗봇 ───────────────────────────────────────
elif st.session_state.chatbot_type == "encourage":
    st.title("💪 할 수 있다")

    modes = [("🤔 고민 해결", "고민 해결"), ("🌟 칭찬", "칭찬"), ("☀️ 긍정 반응", "긍정 반응")]
    cols = st.columns(len(modes))
    for col, (label, mode) in zip(cols, modes):
        with col:
            btn_type = "primary" if st.session_state.encourage_mode == mode else "secondary"
            if st.button(label, use_container_width=True, type=btn_type):
                if st.session_state.encourage_mode != mode:
                    st.session_state.encourage_mode = mode
                    st.session_state.messages = []
                    st.session_state.last_audio_hash = None
                    st.rerun()

    st.caption(f"현재 모드: **{st.session_state.encourage_mode}**")
    st.divider()

    run_chat(
        SYSTEM_PROMPTS["encourage"][st.session_state.encourage_mode],
        "무엇이든 말해보세요...",
    )

# ── 이야기 챗봇 ───────────────────────────────────────────
elif st.session_state.chatbot_type == "story":
    st.title("📖 이야기")

    genres = [("📚 소설", "소설"), ("✍️ 수필", "수필"), ("🎵 시", "시")]
    cols = st.columns(len(genres))
    for col, (label, genre) in zip(cols, genres):
        with col:
            btn_type = "primary" if st.session_state.story_genre == genre else "secondary"
            if st.button(label, use_container_width=True, type=btn_type):
                if st.session_state.story_genre != genre:
                    st.session_state.story_genre = genre
                    st.session_state.messages = []
                    st.session_state.last_audio_hash = None
                    st.rerun()

    st.caption(f"현재 장르: **{st.session_state.story_genre}**")

    ai_texts = [m["content"] for m in st.session_state.messages if m["role"] == "assistant"]
    if ai_texts:
        now = datetime.datetime.now().strftime("%Y년 %m월 %d일")
        book = f"# {st.session_state.story_genre}\n\n작성일: {now}\n\n---\n\n" + "\n\n".join(ai_texts)
        st.download_button(
            "📕 책으로 만들기",
            data=book,
            file_name=f"나의_{st.session_state.story_genre}.txt",
            mime="text/plain",
        )

    st.divider()

    run_chat(
        SYSTEM_PROMPTS["story"][st.session_state.story_genre],
        "이야기를 시작해보세요...",
    )
