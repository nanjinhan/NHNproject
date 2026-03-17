# app/api/routes_sns.py

import time

from fastapi import APIRouter, Form, Request
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates

from app.services.llm_sns import call_llm_prompts, call_llm_caption
from app.services.image_sd3_api import generate_image_from_sd3

router = APIRouter(prefix="/sns")
templates = Jinja2Templates(directory="app/templates")


@router.get("")
def sns_page(request: Request):
    """
    SNS 이미지 생성 화면
    """
    # 로그인 사용자 표시용 (없으면 None)
    user = request.cookies.get("user")

    # 기본 예시 문구 하나 넘겨줌
    return templates.TemplateResponse(
        "sns.html",
        {
            "request": request,
            "user": user,
            "defaults": {
                "topic": "지구를 배경으로 달 위에 커피를 들고 서있는 우주비행사",
            },
        },
    )


@router.post("/api/generate")
def api_generate(topic: str = Form(...)):
    """
    SNS 이미지 생성 API
    - LLM으로 프롬프트/캡션 생성
    - SD3.5 API 호출해 이미지 생성
    """
    t0 = time.time()

    # 이미지용 프롬프트/네거티브 프롬프트 생성
    img_prompt, neg_prompt = call_llm_prompts(topic)
    # SNS용 캡션 생성
    caption = call_llm_caption(topic)
    # SD3.5 호출해서 실제 이미지 생성
    img_info = generate_image_from_sd3(img_prompt, neg_prompt)

    elapsed_total = round(time.time() - t0, 2)

    # 프론트에서 그대로 쓰기 편하게 JSON 구조 정리
    return JSONResponse(
        {
            "ok": True,
            "elapsed_sec": elapsed_total,
            "image": {
                "path": img_info["path"],
                "width": img_info["width"],
                "height": img_info["height"],
                "seed": img_info["seed"],
            },
            "llm": {
                "image_prompt": img_prompt,
                "negative_prompt": neg_prompt,
                "caption": caption,
            },
        }
    )
