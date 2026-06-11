import json
import datetime
import streamlit as st
from openai import OpenAI

st.title("💬 Chatbot")
st.write(
    "OpenAI 모델을 활용한 챗봇입니다. "
    "사용하려면 OpenAI API 키가 필요합니다. "
    "[여기서 발급받으세요](https://platform.openai.com/account/api-keys)."
)

# --- Sidebar controls ---
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
        min_value=0.0,
        max_value=2.0,
        value=0.7,
        step=0.05,
        help="낮을수록 일관된 답변, 높을수록 창의적·다양한 답변",
    )

    st.divider()

    st.subheader("📥 채팅 내보내기")

    def build_txt():
        lines = []
        for m in st.session_state.get("messages", []):
            role = "나" if m["role"] == "user" else "AI"
            lines.append(f"[{role}] {m['content']}")
        return "\n\n".join(lines)

    def build_json():
        export = {
            "exported_at": datetime.datetime.now().isoformat(),
            "model": selected_model,
            "temperature": temperature,
            "messages": st.session_state.get("messages", []),
        }
        return json.dumps(export, ensure_ascii=False, indent=2)

    col1, col2 = st.columns(2)
    with col1:
        st.download_button(
            label=".txt",
            data=build_txt(),
            file_name="chat_history.txt",
            mime="text/plain",
            use_container_width=True,
        )
    with col2:
        st.download_button(
            label=".json",
            data=build_json(),
            file_name="chat_history.json",
            mime="application/json",
            use_container_width=True,
        )

    if st.button("🗑️ 대화 초기화", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

# --- Main chat area ---
if not openai_api_key:
    st.info("사이드바에 OpenAI API 키를 입력하면 대화를 시작할 수 있습니다.", icon="🗝️")
    st.stop()

client = OpenAI(api_key=openai_api_key)

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("메시지를 입력하세요..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    stream = client.chat.completions.create(
        model=selected_model,
        messages=[
            {"role": m["role"], "content": m["content"]}
            for m in st.session_state.messages
        ],
        temperature=temperature,
        stream=True,
    )

    with st.chat_message("assistant"):
        response = st.write_stream(stream)
    st.session_state.messages.append({"role": "assistant", "content": response})
