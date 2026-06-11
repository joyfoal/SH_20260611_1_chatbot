import hashlib
import json
import datetime
import urllib.request
import streamlit as st
from openai import OpenAI

st.set_page_config(page_title="AI 챗봇", page_icon="💬", layout="centered")

# ── Session state 초기화 ──────────────────────────────────
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

# ── 프롬프트 정의 ─────────────────────────────────────────
CHAT_PROMPTS = {
    "고민 해결": (
        "당신은 따뜻하고 지혜로운 상담사입니다. "
        "사용자의 고민을 경청하고 충분히 공감한 뒤 실질적인 해결책을 제시해주세요. "
        "대화 끝에는 '할 수 있다'는 자신감을 심어주고 진심으로 응원해주세요. "
        "한국어로 따뜻하게 대화해주세요."
    ),
    "칭찬 하기": (
        "당신은 사용자의 가장 열렬한 응원자입니다. "
        "사용자가 말하는 것에서 긍정적인 면과 칭찬할 점을 찾아 구체적으로 칭찬하고 격려해주세요. "
        "진심이 담긴 칭찬으로 자존감을 높여주세요. "
        "한국어로 밝고 따뜻하게 대화해주세요."
    ),
    "긍정 반응": (
        "당신은 긍정의 에너지로 가득 찬 친구입니다. "
        "어떤 상황에서도 밝고 희망적인 면을 찾아 사용자를 격려해주세요. "
        "한국어로 활기차고 따뜻하게 대화해주세요."
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
        "생생한 묘사, 입체적인 인물, 긴장감 있는 전개로 독자를 끌어당기는 이야기를 만들어주세요. "
        "한국어로 작성하고 500자 이상으로 써주세요."
    ),
    "수필": (
        "아래 대화 내용을 바탕으로 아름답고 진솔한 수필을 써주세요. "
        "일상에서 발견하는 소중한 의미와 감동을 섬세한 문체로 담아주세요. "
        "한국어로 작성하고 400자 이상으로 써주세요."
    ),
    "시": (
        "아래 대화 내용을 바탕으로 감동적인 시를 써주세요. "
        "리듬감 있고 아름다운 언어로 마음속 이야기를 시의 형식으로 전달해주세요. "
        "한국어로 작성해주세요."
    ),
}

IMAGE_STYLE = {
    "소설": "dramatic narrative book illustration, cinematic lighting, detailed scene, storytelling art",
    "수필": "soft watercolor painting, peaceful and reflective atmosphere, warm gentle tones",
    "시": "abstract poetic art, dreamy surrealism, emotional colors, artistic and lyrical",
}


def get_chat_system(mode: str) -> str:
    system = CHAT_PROMPTS[mode]
    if mode == "글 쓰기 계속" and st.session_state.written_content:
        system += f"\n\n앞서 쓴 글:\n{st.session_state.written_content}"
    return system


def stream_response(system: str):
    """AI 응답을 스트리밍하고 세션에 저장한다."""
    stream = client.chat.completions.create(
        model=selected_model,
        messages=[{"role": "system", "content": system}]
        + [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages],
        temperature=temperature,
        stream=True,
    )
    with st.chat_message("assistant"):
        response = st.write_stream(stream)
    st.session_state.messages.append({"role": "assistant", "content": response})


def generate_writing(genre: str):
    """대화 내용을 바탕으로 글을 생성한다."""
    system = WRITING_PROMPTS[genre]
    if st.session_state.chat_mode == "글 쓰기 계속" and st.session_state.written_content:
        system += (
            f"\n\n앞서 쓴 {genre} 내용:\n{st.session_state.written_content}\n\n"
            "위의 내용에 자연스럽게 이어서 계속 써주세요."
        )
    messages = [{"role": "system", "content": system}]
    messages += [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages]
    messages.append({"role": "user", "content": f"대화 내용을 바탕으로 {genre}를 써주세요."})
    with st.spinner(f"📝 {genre} 작성 중..."):
        resp = client.chat.completions.create(
            model=selected_model, messages=messages, temperature=temperature
        )
    return resp.choices[0].message.content


def generate_image(genre: str, written_text: str) -> bytes:
    """글의 분위기에 맞는 이미지를 DALL-E 3로 생성한다."""
    # 글 내용 → 영어 이미지 프롬프트 생성
    prompt_resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "다음 한국어 글의 핵심 장면과 분위기를 DALL-E 이미지 프롬프트로 영어 60단어 이내로 작성해주세요. "
                    f"스타일: {IMAGE_STYLE[genre]}"
                ),
            },
            {"role": "user", "content": written_text[:1200]},
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
    image_url = img_resp.data[0].url
    with urllib.request.urlopen(image_url) as r:
        return r.read()


# ── 사이드바 ──────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ 설정")
    openai_api_key = st.text_input("OpenAI API Key", type="password")
    st.divider()

    selected_model = st.selectbox(
        "모델 선택",
        options=["gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo"],
        index=0,
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

# ── 메인 UI ───────────────────────────────────────────────
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
        btn_type = "primary" if st.session_state.chat_mode == mode else "secondary"
        if st.button(label, use_container_width=True, type=btn_type, key=f"mode_{mode}"):
            if st.session_state.chat_mode != mode:
                prev = st.session_state.chat_mode
                st.session_state.chat_mode = mode
                # 글 쓰기 계속으로 진입: 대화·글 유지
                # 다른 모드로 전환: 초기화
                if mode != "글 쓰기 계속":
                    st.session_state.messages = []
                    st.session_state.written_content = None
                    st.session_state.image_data = None
                    st.session_state.writing_genre = None
                st.rerun()

st.caption(f"현재 모드: **{st.session_state.chat_mode}**")

# 글 쓰기 계속 모드: 이전 글 열람 & 다운로드
if st.session_state.chat_mode == "글 쓰기 계속" and st.session_state.written_content:
    genre_label = st.session_state.writing_genre or "글"
    with st.expander(f"📄 이전에 쓴 {genre_label} 보기 / 다운로드", expanded=False):
        st.markdown(st.session_state.written_content)
        st.download_button(
            f"📥 {genre_label} 다운로드",
            data=st.session_state.written_content,
            file_name=f"나의_{genre_label}.txt",
            mime="text/plain",
            key="prev_dl",
        )

st.divider()

# 대화 표시
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# ── 음성 입력 ─────────────────────────────────────────────
audio = st.audio_input("🎤 마이크로 말하기 (누르고 말한 뒤 다시 누르면 전송)")
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
            st.session_state.messages.append({"role": "user", "content": f"🎤 {voice_text}"})
            with st.chat_message("user"):
                st.markdown(f"🎤 {voice_text}")
            stream_response(get_chat_system(st.session_state.chat_mode))

# ── 글로 만들기 섹션 ──────────────────────────────────────
if st.session_state.messages:
    st.subheader("✍️ 글로 만들기")
    st.caption("대화 내용을 바탕으로 원하는 형식의 글을 써드립니다.")

    g_cols = st.columns(3)
    for col, (label, genre) in zip(g_cols, [("📚 소설", "소설"), ("✍️ 수필", "수필"), ("🎵 시", "시")]):
        with col:
            is_active = st.session_state.writing_genre == genre
            if st.button(label, use_container_width=True,
                         type="primary" if is_active else "secondary",
                         key=f"genre_{genre}"):
                st.session_state.writing_genre = genre
                st.session_state.image_data = None
                st.session_state.written_content = generate_writing(genre)
                st.rerun()

    # 생성된 글 표시
    if st.session_state.written_content and st.session_state.writing_genre:
        g = st.session_state.writing_genre
        with st.expander(f"📄 {g}", expanded=True):
            st.markdown(st.session_state.written_content)

        act_cols = st.columns(3)

        with act_cols[0]:
            st.download_button(
                f"📥 {g} 다운로드",
                data=st.session_state.written_content,
                file_name=f"나의_{g}.txt",
                mime="text/plain",
                use_container_width=True,
            )

        with act_cols[1]:
            if st.button("🖼️ 그림 생성", use_container_width=True, key="gen_image"):
                with st.spinner("🎨 그림을 그리는 중..."):
                    try:
                        st.session_state.image_data = generate_image(g, st.session_state.written_content)
                    except Exception as e:
                        st.error(f"그림 생성 실패: {e}")
                st.rerun()

        with act_cols[2]:
            if st.button("✏️ 글 쓰기 계속", use_container_width=True, type="primary", key="continue_write"):
                st.session_state.chat_mode = "글 쓰기 계속"
                st.rerun()

        # 생성된 이미지 표시
        if st.session_state.image_data:
            st.image(st.session_state.image_data, caption=f"{g} 삽화", use_container_width=True)
            st.download_button(
                "📥 이미지 다운로드",
                data=st.session_state.image_data,
                file_name=f"나의_{g}_그림.png",
                mime="image/png",
                use_container_width=True,
                key="dl_image",
            )

# ── 텍스트 입력 ───────────────────────────────────────────
if prompt := st.chat_input("무엇이든 말해보세요..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    stream_response(get_chat_system(st.session_state.chat_mode))
