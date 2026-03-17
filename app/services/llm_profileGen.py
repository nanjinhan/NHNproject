# app/services/llm_profileGen.py
import json
import re
from typing import Tuple
from typing import Optional, Dict, Any
from langchain_core.prompts import ChatPromptTemplate
from langchain_naver import ChatClovaX
import re
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

# 사용자 자연어 입력 특징 추출 프롬프트
SYSTEM_PROMPT_EXTRACT = """ 당신은 텍스트 분석 전문가입니다. 사용자가 자유롭게 작성한 자기소개 텍스트를 분석하여 핵심 정보를 구조화된 JSON 데이터로 추출해야 합니다.
수행할 작업:
1. 한 줄 요약 (short_bio): 전체 내용을 아우르는 매력적인 1~2문장 요약.
2. 핵심 가치관 (key_values): 텍스트에서 드러나는 중요하게 생각하는 가치나 신념 (키워드 리스트).
3. 관심사 및 스킬 (interests_skills): 언급된 기술 스택, 취미, 학문적 관심사 등 (키워드 리스트).
4. 상세 소개 정리 (structured_intro): 원문을 바탕으로 하되, 웹페이지에 보여주기 좋게 다듬어진 줄글 형태의 소개글 (개조식 아님, 자연스러운 문단).
규칙:
반드시 JSON 형식만 출력하세요. 부연 설명 금지.
입력 텍스트가 부족하면 유추할 수 있는 범위 내에서 작성하되, 과장하지 마십시오.
출력 형식 예시:
JSON
{{
  "short_bio": "세상을 코드로 연결하고 싶은 백엔드 개발자 지망생입니다.",
  "key_values": ["성장", "효율", "협업"],
  "interests_skills": ["Python", "Django", "대용량 트래픽", "클린 아키텍처"],
  "structured_intro": "안녕하세요! 효율적인 서버 구조에 관심이 많은... (중략) ...끊임없이 배우고 성장하는 것을 목표로 합니다."
}}
""".strip()

# 사용자 웹사이트 프로필 이미지용 시스템 프롬프트
SYSTEM_PROMPT_PROFILE = """You are an expert prompt engineer for Stable Diffusion 3.5, specializing in creating photorealistic, high-quality images for personal branding.
Your task is to generate 'profile_prompt': A close-up portrait or object shot representing the user, suitable for a circular profile icon.
**IMPORTANT RULES:**
-   **OUTPUT MUST BE JSON ONLY.** Do not add any explanations before or after the JSON block.
-   Translate Korean inputs into detailed, descriptive English prompts.
-   Add stylistic keywords for high quality: e.g., "photorealistic, 8k resolution, cinematic lighting, highly detailed, natural light, film grain".
-   If the user provided a specific request, prioritize it. If not, infer a suitable scene from their basic info.
**Output Format Example:**
json
{{
  "profile_prompt": "A close-up portrait photograph of a confident young developer smiling, soft natural light, shallow depth of field, film grain, 85mm lens"
}}""".strip()


# 사용자 웹사이트 배너용 시스템 프롬프트
SYSTEM_PROMPT_BANNER = """You are an expert prompt engineer for Stable Diffusion 3.5, specializing in creating photorealistic, high-quality images for personal branding.
Your task is to generate 'banner_prompt': A wide, atmospheric background image that represents the user's vibe, major, or interests. (Aspect ratio implied wide)
**IMPORTANT RULES:**
-   **OUTPUT MUST BE JSON ONLY.** Do not add any explanations before or after the JSON block.
-   Translate Korean inputs into detailed, descriptive English prompts.
-   Add stylistic keywords for high quality: e.g., "photorealistic, 8k resolution, cinematic lighting, highly detailed, natural light, film grain".
-   If the user provided a specific request, prioritize it. If not, infer a suitable scene from their basic info.
**Output Format Example:**
json
{{
  "banner_prompt": "A wide angle landscape photograph of a modern desk setup with code on multiple monitors, large window overlooking a city skyline at sunset, cinematic lighting, 8k resolution",
}}""".strip()

# 사용자 전용 웹사이트를 생성하는 시스템 프롬프트 (HTML)
# SYSTEM_PROMPT_HTML = """
# 당신은 모던하고 미려한 디자인의 웹사이트를 제작하는 숙련된 프론트엔드 웹 개발자입니다.
# 당신의 임무는 제공된 사용자의 구조화된 데이터(JSON)를 바탕으로, 즉시 사용 가능한 **단일 HTML5 개인 포트폴리오 웹페이지 코드**를 생성하는 것입니다.

# **입력 데이터 명세 (JSON 형식으로 제공될 예정):**
# 웹페이지 생성 시 다음과 같은 필드를 포함한 통합 JSON 데이터가 입력으로 주어집니다:
# - 'basic_info': {{ 'name' (이름), 'major' (전공/직무), 'email' (이메일) }}
# - 'extracted_features': {{ 'short_bio' (한 줄 요약), 'structured_intro' (상세 소개글), 'key_values' (가치관 리스트), 'interests_skills' (관심사실/스킬 리스트) }}
# - 'images': {{ 'banner_url' (배너 이미지 주소), 'profile_url' (프로필 이미지 주소) }}

# **구현 핵심 요구사항:**

# 1.  **기술 스택 및 스타일링:**
#     -   별도의 CSS 파일 없이 작동하는 단일 HTML 파일을 작성하세요.
#     -   스타일링을 위해 '<head>' 태그 내에 **Tailwind CSS CDN** 스크립트를 반드시 포함하세요.
#     -   **디자인 컨셉:** 깨끗하고, 현대적이며, 전문적인 느낌을 주어야 합니다. 모바일 및 데스크탑 환경 모두에 최적화된 **반응형 디자인(Responsive Design)**을 적용하세요.

# 2.  **필수 레이아웃 구조 및 데이터 매핑:**
#     -   **헤더/배너 영역 (Hero Section):**
#         -   'banner_url'을 사용하여 화면 상단에 넓고 인상적인 배경 이미지 영역을 만드세요.
#     -   **프로필 요약 영역:**
#         -   배너 영역과 겹치거나 그 바로 아래에 'profile_url'을 사용한 원형(circular) 프로필 이미지를 배치하세요.
#         -   그 옆이나 아래에 두드러지게 'name'과 'major'를 표시하세요.
#         -   'short_bio'를 매력적인 태그라인(Tagline)처럼 디자인하여 배치하세요.
#     -   **메인 콘텐츠 영역 (About Me):**
#         -   'structured_intro'의 내용을 자연스러운 줄글 문단('<p>')으로 구성하여 가독성 좋게 배치하세요.
#     -   **스킬 및 가치관 영역:**
#         -   'key_values'와 'interests_skills' 배열의 각 항목을 반복하여 세련된 디자인의 **뱃지(Badge) 또는 태그** 형태로 시각화하세요. (예: 둥근 모서리의 색상 배경 칩)
#     -   **연락처 및 푸터:**
#         -   페이지 하단에 'email' 정보를 포함하여 연락을 유도하는 섹션을 만드세요.

# **출력 규칙:**

# -   **반드시 완성된 HTML 코드('<!DOCTYPE html>'로 시작하여 '</html>'로 끝나는)만 출력하세요.**
# -   마크다운 코드 블록('''html ... ''')이나 서론, 결론 등 불필요한 설명 텍스트를 절대 포함하지 마십시오.
# -   코드는 적절히 들여쓰기하여 가독성을 높이세요.
# -   제공된 'banner_url'과 'profile_url'은 반드시 각각 <img> 태그의 src 속성에 정확히 포함되어야 합니다. 절대 누락하지 마십시오.
# """.strip()

# 사용자 전용 웹사이트를 생성하는 시스템 프롬프트 (HTML) - SSR 렌더링 강제 버전
SYSTEM_PROMPT_HTML = """
당신은 Python의 Jinja2와 같은 **Server-Side Rendering (SSR) 엔진**입니다.
당신의 임무는 입력받은 [데이터(JSON)]를 [HTML 템플릿]의 지정된 위치에 정확히 치환(Replacement)하여, **최종 완성된 정적 HTML 코드**만 출력하는 것입니다.

**절대 금지 사항 (Strict Constraints):**
1. `[[name]]`, `{{major}}`와 같은 **변수 표기(Placeholder)를 절대 남기지 마십시오.** 무조건 실제 데이터 값으로 바꿔야 합니다.
2. "데이터 반영 설명", "실제 동작을 위해서는..." 같은 **설명(Comments)이나 주석을 절대 추가하지 마십시오.**
3. 자바스크립트나 별도의 로직 없이, 오직 HTML/CSS로만 내용이 보여야 합니다.

**작업 수행 방법:**
아래 제공된 [HTML 템플릿]의 대문자 마킹된 부분(예: `__NAME__`)을 사용자의 JSON 데이터로 갈아끼우십시오.

**[HTML 템플릿]:**
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>__NAME__님의 포트폴리오</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" as="style" crossorigin href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css" />
    <style>
        body {{ font-family: "Pretendard Variable", Pretendard, -apple-system, BlinkMacSystemFont, system-ui, Roboto, "Helvetica Neue", "Segoe UI", "Apple SD Gothic Neo", "Noto Sans KR", "Malgun Gothic", "Apple Color Emoji", "Segoe UI Emoji", "Segoe UI Symbol", sans-serif; }}
        .glass-card {{ background: rgba(255, 255, 255, 0.95); backdrop-filter: blur(10px); }}
    </style>
</head>
<body class="bg-gray-50 text-gray-800 antialiased selection:bg-blue-100 selection:text-blue-600">
    
    <div class="relative w-full h-80 md:h-96 overflow-hidden group">
        <div class="absolute inset-0 bg-gray-900/30 transition-colors group-hover:bg-gray-900/20 z-10"></div>
        <img src="__BANNER_URL__" alt="Background" class="w-full h-full object-cover transform transition-transform duration-700 group-hover:scale-105">
    </div>

    <div class="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 -mt-32 relative z-20 pb-20">
        
        <div class="glass-card rounded-3xl shadow-2xl overflow-hidden border border-white/50 animate-fade-in-up">
            <div class="p-8 md:p-10 flex flex-col md:flex-row gap-8 items-center md:items-start text-center md:text-left">
                
                <div class="relative shrink-0 group">
                    <div class="absolute -inset-0.5 bg-gradient-to-r from-blue-500 to-indigo-600 rounded-full opacity-75 blur transition duration-500 group-hover:opacity-100"></div>
                    <img src="__PROFILE_URL__" alt="Profile" class="relative w-40 h-40 md:w-48 md:h-48 rounded-full border-4 border-white shadow-xl object-cover bg-gray-100">
                </div>

                <div class="flex-1 space-y-4 pt-2">
                    <div>
                        <span class="inline-flex items-center px-3 py-1 rounded-full text-sm font-semibold bg-blue-50 text-blue-700 ring-1 ring-inset ring-blue-700/10 mb-2">
                            __MAJOR__
                        </span>
                        <h1 class="text-4xl md:text-5xl font-extrabold text-gray-900 tracking-tight">
                            __NAME__
                        </h1>
                    </div>
                    
                    <p class="text-xl text-gray-600 font-medium leading-relaxed">
                        "__SHORT_BIO__"
                    </p>

                    <div class="flex items-center justify-center md:justify-start gap-2 text-gray-500 text-sm font-medium pt-2">
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"></path></svg>
                        __EMAIL__
                        <span class="mx-2 text-gray-300">|</span>
                        <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 24 24"><path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/></svg>
                        <a href="https://github.com/__GITHUB_ID__" target="_blank" class="hover:text-gray-900 transition-colors">GitHub</a>
                    </div>
                </div>
            </div>

            <div class="h-px bg-gray-100"></div>

            <div class="p-8 md:p-12 space-y-12">
                
                <section>
                    <h3 class="text-xl font-bold text-gray-900 mb-6 flex items-center gap-2">
                        <span class="w-8 h-1 bg-blue-600 rounded-full"></span>
                        About Me
                    </h3>
                    <div class="prose prose-lg text-gray-600 max-w-none leading-loose">
                        __STRUCTURED_INTRO__
                    </div>
                </section>

                <div class="grid grid-cols-1 md:grid-cols-2 gap-12">
                    <section>
                         <h3 class="text-lg font-bold text-gray-900 mb-4">Core Values</h3>
                         <div class="flex flex-wrap gap-2">
                            __KEY_VALUES_LOOP__
                         </div>
                    </section>

                    <section>
                         <h3 class="text-lg font-bold text-gray-900 mb-4">Tech Stack & Interests</h3>
                         <div class="flex flex-wrap gap-2">
                             __SKILLS_LOOP__
                         </div>
                    </section>
                </div>

            </div>
        </div>
        
        <footer class="text-center mt-12 text-gray-400 text-sm font-medium">
            &copy; 2025 __NAME__. Generated by DevFolio AI.
        </footer>
    </div>
</body>
</html>

**입력 데이터(JSON):**
{{input_json_data}}

**[마지막 지시사항]:**
위 템플릿의 `__KEY_VALUES_LOOP__`와 `__SKILLS_LOOP__` 위치에는, JSON 리스트 데이터를 사용하여 `<span class="px-3 py-1 bg-gray-100 text-gray-600 rounded-lg text-sm font-medium border border-gray-200">데이터</span>` 형태의 태그들을 나열해서 출력하십시오.
""" .strip()

# ==========================================
# 전역 체인 객체
# ==========================================
_chain_extract = None
_chain_profile = None
_chain_banner = None
_chain_html = None


def init_llm_chains() -> None:
    """
    앱 시작 시 한 번만 호출해서 ClovaX 기반 체인들을 초기화합니다.
    각 작업의 특성에 맞게 temperature를 다르게 설정합니다.
    """
    global _chain_extract, _chain_profile, _chain_banner, _chain_html

    # 1. 정확한 정보 추출용 (낮은 Temperature)
    clova_precise = ChatClovaX(
        model="HCX-007",
        api_key=settings.CLOVA_KEY,
        temperature=0.1,
        max_tokens=2048
    )

    # 2. 창의적인 이미지 프롬프트 및 HTML 디자인용 (중간/높은 Temperature)
    clova_creative = ChatClovaX(
        model="HCX-007",
        api_key=settings.CLOVA_KEY,
        temperature=0.6, # 창의성 필요
        max_tokens=2048
    )
    
    # HTML은 좀 더 길게 생성될 수 있음
    clova_html_gen = ChatClovaX(
        model="HCX-007",
        api_key=settings.CLOVA_KEY,
        temperature=0.7,
        max_tokens=4096 
    )


    # --- Prompt Templates 정의 ---
    prompt_extract = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT_EXTRACT),
        ("human", "사용자 입력 텍스트:\n{user_text}"),
    ])

    # 이미지 프롬프트는 사용자 컨텍스트와 선택적 요청사항을 받음
    img_prompt_template_str = """User Context: {user_context}
User Specific Request (If any): {user_request}"""
    
    prompt_profile = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT_PROFILE),
        ("human", img_prompt_template_str),
    ])

    prompt_banner = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT_BANNER),
        ("human", img_prompt_template_str),
    ])

    # HTML 생성용 템플릿
    prompt_html = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT_HTML),
        ("human", """--- basic_info (JSON) ---
{basic_info_json}

--- extracted_features (JSON) ---
{extracted_features_json}

--- images (JSON) ---
{images_json}
"""),
    ])

    # --- Chains 연결 ---
    _chain_extract = prompt_extract | clova_precise
    _chain_profile = prompt_profile | clova_creative
    _chain_banner = prompt_banner | clova_creative
    _chain_html = prompt_html | clova_html_gen


def _check_chains_initialized():
    if any(c is None for c in [_chain_extract, _chain_profile, _chain_banner, _chain_html]):
        raise RuntimeError("LLM chains not initialized. Call init_llm_chains() first.")


# ==========================================
# 서비스 함수 구현
# ==========================================

def extract_user_features(user_text: str) -> Dict[str, Any]:
    """
    1. 사용자의 자연어 입력을 받아 구조화된 특징(JSON)을 추출합니다.
    """
    _check_chains_initialized()
    if not user_text.strip():
        # 입력이 없을 경우 기본 빈 값 반환
        return {"short_bio": "", "key_values": [], "interests_skills": [], "structured_intro": ""}

    response = _chain_extract.invoke({"user_text": user_text})
    return extract_json_block(response.content)


def generate_image_prompts(
    basic_info: Dict[str, Any], 
    extracted_features: Dict[str, Any],
    profile_request: Optional[str] = None,
    banner_request: Optional[str] = None
) -> Tuple[str, str]:
    """
    2. 사용자 정보와 요청사항을 바탕으로 프로필 및 배너 이미지용 영문 프롬프트를 생성합니다.
    요청사항이 없으면 기본 정보(이름, 전공, 한줄소개)를 컨텍스트로 제공하여 자동 생성합니다.
    Returns: (profile_prompt_eng, banner_prompt_eng)
    """
    _check_chains_initialized()

    # 프롬프트 생성을 위한 기본 컨텍스트 구성
    user_context = (
        f"Name: {basic_info.get('name', 'Unknown')}, "
        f"Major/Role: {basic_info.get('major', 'Unknown')}, "
        f"Summary: {extracted_features.get('short_bio', '')}"
    )
    
    # 요청사항이 None이면 "None" 문자열로 처리하여 프롬프트에 전달
    p_req_str = profile_request if profile_request and profile_request.strip() else "None. Infer from user context."
    b_req_str = banner_request if banner_request and banner_request.strip() else "None. Infer from user context."

    # 병렬 실행 가능하지만, 간단하게 순차 실행
    profile_resp = _chain_profile.invoke({"user_context": user_context, "user_request": p_req_str})
    banner_resp = _chain_banner.invoke({"user_context": user_context, "user_request": b_req_str})

    profile_data = extract_json_block(profile_resp.content)
    banner_data = extract_json_block(banner_resp.content)

    # JSON 파싱 실패 시 안전장치 (빈 문자열 반환) 또는 재시도 로직 필요
    # 여기서는 간단히 처리
    profile_prompt_eng = one_line(profile_data.get("profile_prompt", ""))
    banner_prompt_eng = one_line(banner_data.get("banner_prompt", ""))
    
    # (옵션) 한글 포함 여부 체크하여 재시도 로직 추가 가능

    return profile_prompt_eng, banner_prompt_eng


def generate_portfolio_html(
    basic_info: Dict[str, Any],
    extracted_features: Dict[str, Any],
    image_urls: Dict[str, str]
) -> str:
    """
    3. 수집된 모든 데이터를 취합하여 최종 HTML 코드를 생성합니다.
    image_urls 예시: {"banner_url": "...", "profile_url": "..."}
    """
    _check_chains_initialized()

    # 프롬프트에 주입하기 위해 JSON 문자열로 변환
    response = _chain_html.invoke({
        "basic_info_json": json.dumps(basic_info, ensure_ascii=False),
        "extracted_features_json": json.dumps(extracted_features, ensure_ascii=False),
        "images_json": json.dumps(image_urls, ensure_ascii=False),
    })

    html_content = response.content.strip()
    
    # 마크다운 코드블록 제거 (혹시 남아있을 경우)
    cleaned_html = html_content.replace("```html", "").replace("```", "").strip()
    
    return cleaned_html