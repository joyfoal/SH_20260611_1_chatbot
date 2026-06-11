import hashlib
import json
import io
import datetime
import time
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
}
div[data-testid="stVerticalBlockBorderWrapper"] button[kind="primary"]:hover {
    background: #333 !important;
}

/* 카드 안 audio_input 라벨/배경 제거 */
div[data-testid="stVerticalBlockBorderWrapper"] [data-testid="stAudioInput"] {
    background: transparent !important;
    border: none !important;
    padding: 2px 0 !important;
}
</style>
""", unsafe_allow_html=True)

# Enter → 전송 버튼 클릭 JS
components.html("""
<script>
(function() {
    var doc = window.parent.document;
    doc.addEventListener('keydown', function(e) {
        if (e.key !== 'Enter' || e.shiftKey || e.ctrlKey || e.metaKey) return;
        var active = doc.activeElement;
        if (!active || active.tagName !== 'INPUT') return;
        if (active.type === 'submit' || active.type === 'button') return;
        var btns = Array.from(doc.querySelectorAll('button[kind="primary"]'));
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
    "고민 해결": "당신은 따뜻하고 지혜로운 상담사입니다. 사용자의 고민을 경청하고 공감한 뒤 실질적인 해결책을 제시해주세요. 한국어로 대화해주세요.",
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
    "소설": "epic cinematic orchestral ballad with piano, Korean lyrics",
    "수필": "calm acoustic ballad with guitar and piano, Korean lyrics",
    "시":   "lyrical dreamy pop ballad with emotional melody, Korean lyrics",
}

# 오디오 레벨에 반응하는 웨이브폼 (Web Audio API)
REACTIVE_WAVEFORM_HTML = """<!DOCTYPE html>
<html>
<head>
<style>
*{margin:0;padding:0;box-sizing:border-box;}
body{background:transparent;display:flex;align-items:center;height:48px;overflow:hidden;padding:0 6px;}
.bars{display:flex;align-items:center;gap:4px;}
.bar{width:4px;background:#6366f1;border-radius:3px;height:4px;transition:height 0.06s ease;}
.hint{color:#6366f1;font-family:sans-serif;font-size:13px;margin-left:10px;white-space:nowrap;}
</style>
</head>
<body>
<div class="bars" id="bars">
  <div class="bar"></div><div class="bar"></div><div class="bar"></div>
  <div class="bar"></div><div class="bar"></div><div class="bar"></div>
  <div class="bar"></div><div class="bar"></div>
</div>
<span class="hint">🎤 듣는 중...</span>
<script>
(async()=>{
  const bars=document.querySelectorAll('.bar');
  function cssAnim(){
    const s=document.createElement('style');
    s.textContent='@keyframes wv{0%{height:3px}50%{height:28px}100%{height:3px}}';
    document.head.appendChild(s);
    bars.forEach((b,i)=>{b.style.animation=`wv 0.9s ease-in-out ${i*0.11}s infinite`;});
  }
  try{
    const stream=await navigator.mediaDevices.getUserMedia({audio:true,video:false});
    const ctx=new(window.AudioContext||window.webkitAudioContext)();
    const src=ctx.createMediaStreamSource(stream);
    const an=ctx.createAnalyser();
    an.fftSize=64;
    src.connect(an);
    const arr=new Uint8Array(an.frequencyBinCount);
    (function draw(){
      an.getByteFrequencyData(arr);
      bars.forEach((b,i)=>{
        const v=arr[Math.floor(i*arr.length/bars.length)]||0;
        b.style.height=Math.max(3,(v/255)*34)+'px';
      });
      requestAnimationFrame(draw);
    })();
  }catch(e){cssAnim();}
})();
</script>
</body>
</html>"""


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
    style = IMAGE_STYLE.get(genre, "beautiful artistic illustration, vivid colors")
    with st.spinner("🎨 그림 그리는 중..."):
        pr = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": f"다음 한국어 글의 핵심 장면을 DALL-E 프롬프트로 영어 60단어 이내로 써주세요. 스타일: {style}"},
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
장르/분위기/템포/악기를 영어로 한 줄로 설명 (Replicate MusicGen 프롬프트용)"""

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
    """Replicate MusicGen으로 음악 생성 (최신 모델 엔드포인트 사용)."""
    headers = {
        "Authorization": f"Bearer {replicate_key}",
        "Content-Type": "application/json",
        "Prefer": "wait",
    }
    payload = json.dumps({
        "input": {
            "prompt": prompt[:200],
            "model_version": "stereo-large",
            "duration": 15,
            "output_format": "mp3",
            "normalization_strategy": "peak",
        }
    }).encode()

    req = urllib.request.Request(
        "https://api.replicate.com/v1/models/meta/musicgen/predictions",
        data=payload, headers=headers, method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            result = json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        raise Exception(f"Replicate API 오류 {e.code}: {body}")

    if result.get("status") == "succeeded":
        audio_url = result["output"]
        if isinstance(audio_url, list):
            audio_url = audio_url[0]
        with urllib.request.urlopen(audio_url) as r:
            return r.read()

    get_url = result.get("urls", {}).get("get")
    if not get_url:
        raise Exception(f"Replicate 응답 오류: {result}")

    for _ in range(90):
        time.sleep(2)
        req2 = urllib.request.Request(
            get_url, headers={"Authorization": f"Bearer {replicate_key}"}
        )
        with urllib.request.urlopen(req2, timeout=15) as r:
            result = json.loads(r.read())
        status = result.get("status")
        if status == "succeeded":
            audio_url = result["output"]
            if isinstance(audio_url, list):
                audio_url = audio_url[0]
            with urllib.request.urlopen(audio_url) as r:
                return r.read()
        if status in ("failed", "canceled"):
            raise Exception(result.get("error", "음악 생성 실패"))
    raise Exception("음악 생성 시간 초과 (3분)")


def get_content_for_creation() -> str:
    if st.session_state.written_content:
        return st.session_state.written_content
    return "\n".join(
        f"{'나' if m['role'] == 'user' else 'AI'}: {m['content']}"
        for m in st.session_state.messages[-10:]
    )


def get_genre_for_creation() -> str:
    return st.session_state.writing_genre or "소설"


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
            return json.dumps({
                "exported_at": datetime.datetime.now().isoformat(),
                "model": selected_model,
                "messages": st.session_state.messages,
                "written_content": st.session_state.written_content,
            }, ensure_ascii=False, indent=2)
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

# ── 입력 카드 ─────────────────────────────────────────────
user_input = None
send_clicked = False
audio = None

with st.container(border=True):
    if not st.session_state.voice_mode:
        # 일반 모드: [텍스트] [🎤] [전송▶]
        col_t, col_m, col_s = st.columns([7, 1, 1.8])
        with col_t:
            user_input = st.text_input(
                "",
                placeholder="메시지를 입력하세요...",
                key=f"inp_{st.session_state.text_key}",
                label_visibility="collapsed",
            )
        with col_m:
            if st.button("🎤", key="start_voice", help="음성 대화 시작"):
                st.session_state.voice_mode = True
                st.session_state.last_audio_hash = None
                st.rerun()
        with col_s:
            send_clicked = st.button("전송 ▶", type="primary",
                                     key="send_btn", use_container_width=True)
    else:
        # 음성 모드: [반응형 웨이브폼] [음성종료]
        col_w, col_s = st.columns([8.8, 1.8])
        with col_w:
            components.html(REACTIVE_WAVEFORM_HTML, height=50)
        with col_s:
            if st.button("⏹ 음성종료", type="primary",
                         key="stop_voice", use_container_width=True):
                st.session_state.voice_mode = False
                st.rerun()
        # 오디오 입력 (카드 안에 통합, 라벨 숨김)
        audio = st.audio_input(
            "",
            key=f"voice_{st.session_state.voice_counter}",
            label_visibility="collapsed",
        )

# ── 텍스트 전송 처리 ──────────────────────────────────────
if send_clicked and user_input and user_input.strip():
    text = user_input.strip()
    st.session_state.messages.append({"role": "user", "content": text})
    with st.chat_message("user"):
        st.markdown(text)
    response = stream_ai(get_system(st.session_state.chat_mode))
    st.session_state.messages.append({"role": "assistant", "content": response})
    st.session_state.text_key += 1
    st.rerun()

# ── 음성 처리 ─────────────────────────────────────────────
if st.session_state.voice_mode and audio is not None:
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

    # 장르 버튼
    gc = st.columns(3)
    for col, (label, genre) in zip(
        gc, [("📚 소설", "소설"), ("✍️ 수필", "수필"), ("🎵 시", "시")]
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

    # 글 내용 표시 (장르를 선택했을 때)
    if st.session_state.written_content and st.session_state.writing_genre:
        g = st.session_state.writing_genre
        with st.expander(f"📄 {g}", expanded=True):
            st.markdown(st.session_state.written_content)
        d1, d2 = st.columns(2)
        with d1:
            st.download_button(f"📥 {g} 다운로드", st.session_state.written_content,
                               f"나의_{g}.txt", use_container_width=True, key="dl_written")
        with d2:
            if st.button("✏️ 글 쓰기 계속", use_container_width=True,
                         type="primary", key="continue_writing"):
                st.session_state.chat_mode = "글 쓰기 계속"
                st.rerun()

    st.divider()

    # 공통 액션 버튼 (소설/수필/시 선택 여부와 무관하게 항상 표시)
    ab1, ab2, ab3 = st.columns(3)
    with ab1:
        if st.button("🖼️ 그림 생성", use_container_width=True, key="gen_image"):
            content = get_content_for_creation()
            genre = get_genre_for_creation()
            try:
                st.session_state.image_data = generate_image(genre, content)
            except Exception as e:
                st.error(f"그림 생성 실패: {e}")
            st.rerun()
    with ab2:
        if st.button("🎵 음악 만들기", use_container_width=True, key="gen_music"):
            content = get_content_for_creation()
            genre = get_genre_for_creation()
            try:
                lyrics, style = generate_lyrics(genre, content)
                st.session_state.lyrics_content = lyrics
                st.session_state.lyrics_style = style
            except Exception as e:
                st.error(f"가사 생성 실패: {e}")
                lyrics = None
                style = ""
            if lyrics and replicate_key:
                with st.spinner("🎶 음악 생성 중... (1~2분 소요)"):
                    try:
                        st.session_state.music_data = generate_music_replicate(style, replicate_key)
                    except Exception as e:
                        st.error(f"음악 생성 실패: {e}")
            st.rerun()
    with ab3:
        if st.button("🗑️ 대화 초기화", use_container_width=True, key="reset_chat"):
            st.session_state.messages = []
            st.session_state.text_key += 1
            st.rerun()

    # 그림 표시
    if st.session_state.image_data:
        g_label = st.session_state.writing_genre or "대화"
        st.image(io.BytesIO(st.session_state.image_data),
                 caption=f"{g_label} 삽화", use_container_width=True)
        st.download_button(
            "📥 이미지 다운로드",
            st.session_state.image_data,
            f"나의_{g_label}_그림.png",
            "image/png",
            use_container_width=True,
            key="dl_img",
        )

    # 가사·음악 표시
    if st.session_state.lyrics_content:
        g_label = st.session_state.writing_genre or "대화"
        with st.expander("🎵 가사", expanded=True):
            st.markdown(st.session_state.lyrics_content)
            if st.session_state.lyrics_style:
                st.caption(f"음악 스타일: {st.session_state.lyrics_style}")
        st.download_button(
            "📥 가사 다운로드",
            st.session_state.lyrics_content,
            f"나의_{g_label}_가사.txt",
            use_container_width=True,
            key="dl_lyrics",
        )
        if st.session_state.music_data:
            st.audio(st.session_state.music_data, format="audio/mp3")
            st.download_button(
                "📥 음악 다운로드",
                st.session_state.music_data,
                f"나의_{g_label}_음악.mp3",
                "audio/mp3",
                use_container_width=True,
                key="dl_music",
            )
