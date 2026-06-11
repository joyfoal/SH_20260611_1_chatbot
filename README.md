# 💬 Chatbot

OpenAI 모델을 활용한 Streamlit 챗봇 앱입니다.

[![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://chatbot-template.streamlit.app/)

## 주요 기능

| 기능 | 설명 |
|------|------|
| **모델 선택** | 사이드바 드롭다운에서 `gpt-4o-mini` / `gpt-4o` / `gpt-3.5-turbo` 선택 |
| **Temperature 슬라이더** | 창의성(0.0 ~ 2.0) 실시간 조절 — 낮을수록 일관된 답변, 높을수록 창의적 |
| **채팅 내보내기** | 대화 기록을 `.txt` 또는 `.json` 파일로 다운로드 |
| **대화 초기화** | 현재 세션의 대화를 한 번에 삭제 |

> 기본 모델은 성능과 가격의 균형이 좋은 **gpt-4o-mini**로 설정되어 있습니다.

## 실행 방법

1. 의존성 설치

   ```
   pip install -r requirements.txt
   ```

2. 앱 실행

   ```
   streamlit run streamlit_app.py
   ```

3. 사이드바에 [OpenAI API 키](https://platform.openai.com/account/api-keys)를 입력하면 대화를 시작할 수 있습니다.
