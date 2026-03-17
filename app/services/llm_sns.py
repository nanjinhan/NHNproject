# app/services/llm_sns.py
import json
import re
from typing import Tuple

from langchain_core.prompts import ChatPromptTemplate
from langchain_naver import ChatClovaX

from app.core.config import settings

# 한글 포함 여부 체크용 정규식
HANGUL_RE = re.compile(r"[\uac00-\ud7a3]")


def has_hangul(s: str) -> bool:
    """문자열에 한글이 하나라도 들어있는지 확인"""
    return bool(HANGUL_RE.search(s or ""))


def one_line(s: str) -> str:
    """여러 줄/공백을 하나의 라인으로 정리"""
    return " ".join((s or "").split())


def extract_json_block(text: str) -> dict:
    """
    모델이 앞뒤에 설명을 붙여도
    중괄호 기준으로 JSON 부분만 잘라서 파싱
    """
    if not text:
        return {}
    s = text.find("{")
    e = text.rfind("}")
    if s == -1 or e == -1 or e <= s:
        return {}
    try:
        return json.loads(text[s : e + 1])
    except Exception:
        return {}


# 이미지 프롬프트용 시스템 프롬프트
SYSTEM_PROMPT_PROMPTS = """
You are a prompt engineer for Stable Diffusion 3.5.

Given a Korean topic, output ONLY JSON with two English strings like:
{{
  "image_prompt": "<ENGLISH prompt: composition, lens, lighting, style, quality terms>",
  "negative_prompt": "<ENGLISH negative prompt: quality filters, common artifacts>"
}}

Rules:
- English only.
- JSON only (no explanations, no code fences).
- Single-line strings (no newline).
""".strip()

# SNS 캡션용 시스템 프롬프트
SYSTEM_PROMPT_CAPTION = """
당신은 한국어 SNS 카피라이터입니다.
입력 '주제'를 바탕으로 JSON만 출력하세요 (예시):
{{
  "caption": "한글 캡션(1~2문장, 120~180자, 문장 끝에 2~4개의 해시태그 포함)"
}}
규칙:
- 본문은 한글 위주로 자연스럽게.
- 문장 끝에 해시태그 2~4개.
- JSON만 출력(설명/코드펜스 금지).
""".strip()

# LangChain 템플릿 (이미지 프롬프트)
PROMPT_TEMPLATE_PROMPTS = ChatPromptTemplate.from_messages(
    [
        ("system", SYSTEM_PROMPT_PROMPTS),
        ("human", "Topic (Korean): {topic}"),
    ]
)

# LangChain 템플릿 (캡션)
PROMPT_TEMPLATE_CAPTION = ChatPromptTemplate.from_messages(
    [
        ("system", SYSTEM_PROMPT_CAPTION),
        ("human", "주제: {topic}"),
    ]
)

# 전역 체인 객체 (앱 시작 시 한 번만 초기화)
_chain_prompts = None
_chain_caption = None


def init_llm_chains() -> None:
    """
    앱 시작 시 한 번만 호출해서
    ClovaX 기반 체인 두 개 준비
    """
    global _chain_prompts, _chain_caption

    _chain_prompts = PROMPT_TEMPLATE_PROMPTS | ChatClovaX(
        model="HCX-007",
        api_key=settings.CLOVA_KEY,
        temperature=0.2,
    )
    _chain_caption = PROMPT_TEMPLATE_CAPTION | ChatClovaX(
        model="HCX-007",
        api_key=settings.CLOVA_KEY,
        temperature=0.5,
    )


def call_llm_prompts(topic: str) -> Tuple[str, str]:
    """
    SD3.5용 영어 image_prompt / negative_prompt 생성
    - 한글이 섞이면 최대 3번까지 재시도
    - 그래도 안 되면 기본 영어 프롬프트로 폴백
    """
    if _chain_prompts is None:
        raise RuntimeError("LLM 체인이 초기화되지 않았습니다. init_llm_chains()를 먼저 호출하세요.")

    for attempt in range(1, 4):
        raw = _chain_prompts.invoke({"topic": topic}).content.strip()
        data = extract_json_block(raw)
        image_prompt = one_line(data.get("image_prompt", ""))
        negative_prompt = one_line(data.get("negative_prompt", ""))

        print(f"[prompts attempt {attempt}]")
        print(f"  image_prompt: {image_prompt}")
        print(f"  negative_prompt: {negative_prompt}")

        # 둘 다 비어있지 않고, 한글이 없으면 그대로 사용
        if (
            image_prompt
            and negative_prompt
            and not has_hangul(image_prompt)
            and not has_hangul(negative_prompt)
        ):
            print(f"[prompts attempt {attempt}] OK (no Hangul detected)")
            return image_prompt, negative_prompt

        print(f"[prompts attempt {attempt}] RETRY (Hangul detected or empty)")

    # 3회 실패 → 안전한 기본 프롬프트 사용
    image_prompt = one_line(
        "A realistic lifestyle photo in natural light, 50mm lens, "
        "soft shadows, shallow depth of field, highly detailed, high resolution"
    )
    negative_prompt = one_line(
        "low quality, blurry, noisy, artifacts, distortion, extra fingers, watermark, text, logo"
    )
    print("[prompts fallback] Used default English prompts (after 3 failed attempts).")
    return image_prompt, negative_prompt


def call_llm_caption(topic: str) -> str:
    """
    SNS용 한글 캡션 생성
    - JSON 파싱에 실패하거나 caption이 비어 있으면 간단한 기본 문구로 대체
    """
    if _chain_caption is None:
        raise RuntimeError("LLM 체인이 초기화되지 않았습니다. init_llm_chains()를 먼저 호출하세요.")

    raw = _chain_caption.invoke({"topic": topic}).content.strip()
    data = extract_json_block(raw)
    caption = (data.get("caption") or "").strip()

    if not caption:
        caption = (
            f"{topic}의 순간을 담았습니다. "
            "일상 속 작은 영감이 되는 장면을 함께 기록해요. "
            "#daily #moment #사진"
        )

    return caption
