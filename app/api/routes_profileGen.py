import logging
import json
import re
import asyncio
from typing import Optional

from fastapi import APIRouter, Form, HTTPException, Request, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db import get_db
from app import crud, schemas, models
from app.deps import get_current_user

# AI 서비스 모듈들
from app.services.llm_sns import call_llm_prompts, call_llm_caption
from app.services.image_sd3_api_genProfileBanner import generate_image_from_sd3
import app.services.llm_profileGen as llm_profileGen

router = APIRouter(prefix="/profileGen")
templates = Jinja2Templates(directory="app/templates")
logger = logging.getLogger(__name__)

# --- [초기화] ---
try:
    llm_profileGen.init_llm_chains()
    logger.info("LLM ProfileGen chains initialized successfully.")
except Exception as e:
    logger.error(f"Failed to initialize LLM chains: {e}")


# --- [GET] 폼 페이지 렌더링 ---
@router.get("/", response_class=HTMLResponse)
async def get_profile_form(request: Request):
    return templates.TemplateResponse("profileGen.html", {"request": request})


# --- [POST] 프로필 저장 및 생성 (핵심 로직 통합) ---
@router.post("/generate", response_class=HTMLResponse)
async def generate_profile(
    request: Request,
    # 1. 의존성 주입
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user), # User 모델 반환
    
    # 2. Form 데이터 수신
    base_name: str = Form(...),
    base_major: str = Form(...),
    base_email: str = Form(...),
    base_tags: str = Form(...),
    answer_intro: str = Form(...),
    answer_value: str = Form(...),
    github_id: str = Form(...),
    
    # 3. (선택) 이미지 요청 사항
    profile_img_request: Optional[str] = Form(None),
    banner_img_request: Optional[str] = Form(None),
):
    """
    1) 사용자 입력을 DB에 저장/업데이트하고
    2) AI를 통해 포트폴리오를 생성하여
    3) 최종 HTML을 반환합니다.
    """
    # 로그인 체크
    if not current_user:
        return templates.TemplateResponse("login.html", {"request": request, "error": "로그인이 필요합니다."})

    try:
        # --- [STEP 1] 데이터 전처리 및 DB 저장 ---
        logger.info(f"Processing profile for user: {current_user.username}")
        
        # 태그 문자열 -> 리스트 변환
        tags_list = [tag.strip() for tag in base_tags.split(",") if tag.strip()]
        
        # 자기소개 합치기 (필요하다면)
        full_intro = answer_intro + "\n\n" + answer_value

        # 스키마 생성
        basic_info_schema = schemas.BasicInfoCreate(
            name=base_name,
            major=base_major,
            email=base_email,
            tags=tags_list,
            values=[answer_value],
            interests=[],
            intro_text=full_intro
        )

        # ★ 핵심: CRUD 함수를 사용하여 DB 업데이트 (User와 UserProfile 관계 활용)
        # 반환된 updated_profile을 사용하면 최신 데이터를 보장받습니다.
        current_user, updated_profile = crud.upsert_user_basic_info(db, basic_info_schema, current_user)
        
        logger.info(f"DB Updated for user: {updated_profile.display_name}")


        # --- [STEP 2] LLM: 특징 추출 ---
        # DB가 아니라 방금 입력받은 텍스트(full_intro)를 바로 써도 됩니다.
        logger.info("STEP 2: Extracting features...")
        # run potentially blocking LLM call in a thread to avoid blocking the event loop
        extracted_features = await asyncio.to_thread(llm_profileGen.extract_user_features, full_intro)
        

        # --- [STEP 3] LLM: 이미지 프롬프트 생성 ---
        # LLM에게 넘겨줄 정보 딕셔너리 구성
        basic_info_dict = {
            "name": updated_profile.display_name,
            "major": updated_profile.major,
            "email": updated_profile.email,
            "tags": tags_list,
            "github_id": github_id
        }

        logger.info("STEP 3: Generating prompts...")
        # run prompt generation in a thread to avoid blocking; use a lambda to pass kwargs
        profile_prompt, banner_prompt = await asyncio.to_thread(
            lambda: llm_profileGen.generate_image_prompts(
                basic_info_dict,
                extracted_features,
                profile_request=profile_img_request,
                banner_request=banner_img_request,
            )
        )


        # --- [STEP 4] SD3.5 API: 이미지 생성 ---
        logger.info("STEP 4: Generating images (SD3)...")
        
        # 4-1. 프로필 이미지
        # generate_image_from_sd3 performs blocking network + PIL work — run in thread
        p_data = await asyncio.to_thread(generate_image_from_sd3, profile_prompt, None, None, "png", "profile")
        profile_url = p_data["path"]
        
        # 4-2. 배너 이미지
        b_data = await asyncio.to_thread(generate_image_from_sd3, banner_prompt, None, None, "png", "banner")
        banner_url = b_data["path"]
        
        image_urls = {
            "profile_url": profile_url,
            "banner_url": banner_url
        }


        # --- [STEP 5] LLM: 최종 HTML 생성 ---
        logger.info("STEP 5: Generating HTML...")
        # run HTML generation in thread to avoid blocking
        final_html_content = await asyncio.to_thread(
            llm_profileGen.generate_portfolio_html,
            basic_info_dict,
            extracted_features,
            image_urls,
        )


        # --- [STEP 6] 결과 DB 저장 ---
        # 생성된 결과를 UserProfile 테이블에 업데이트
        updated_profile.intro_features_json = json.dumps(extracted_features, ensure_ascii=False)
        updated_profile.intro_html = final_html_content
        updated_profile.github_url = f"https://github.com/{github_id}" # 깃허브 주소 저장
        
        db.add(updated_profile)
        db.commit()


        # --- [STEP 7] 응답 반환 ---
        # 마크다운 코드 블록 제거 (```html ... ```)
        final_pure_html = re.sub(r"^```html\s*|^```\s*|\s*```$", "", final_html_content, flags=re.MULTILINE).strip()
        
        return HTMLResponse(content=final_pure_html, status_code=200)


    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        # 에러 발생 시 JSON으로 원인 반환 (디버깅용) 또는 에러 페이지 렌더링
        return JSONResponse(status_code=500, content={"detail": f"Internal server error: {str(e)}"})