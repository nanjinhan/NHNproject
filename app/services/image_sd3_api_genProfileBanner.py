# app/services/image_sd3_api_genProfileBanner.py

import os
import time
import secrets
from io import BytesIO
from typing import Optional, Dict, Any

import requests
from PIL import Image

from app.core.config import settings

# Stability AI SD3/SD3.5 이미지 생성 엔드포인트
SD35_API_URL = "https://api.stability.ai/v2beta/stable-image/generate/sd3"
SD35_API_KEY = settings.SD35_API_KEY

# 생성된 이미지를 저장할 로컬 폴더
os.makedirs("outputs", exist_ok=True)


def generate_image_from_sd3(
    prompt: str,
    negative_prompt: Optional[str] = None,
    seed: Optional[int] = None,
    output_format: str = "png",
    imgClass: Optional[str] = "profile" or "banner",
    aspect_ratio: str = None,          # 기본은 1:1
) -> Dict[str, Any]:
    """
    Stability AI SD3 / SD3.5 Medium API를 호출해 이미지를 한 장 생성하는 함수.

    - prompt: 영어 프롬프트
    - negative_prompt: 영어 네거티브 프롬프트
    - aspect_ratio: "1:1", "3:4", "4:5", "9:16" 등 비율 문자열 지정 가능 / 없으면 imgClass에 따라 자동 결정
    - seed: 없으면 내부에서 랜덤 생성
    - output_format: "png" 또는 "jpeg"
    - imgClass: "profile" 또는 "banner" 중 하나로, 기본 aspect_ratio 결정에 사용

    반환 예시:
    {
      "path": "/outputs/....png",
      "width": 1024,
      "height": 1536,
      "seed": 123456789
    }
    
    - imgClass에 따라 기본 aspect_ratio가 자동으로 결정됩니다.
      - profile: "1:1" (정사각형)
      - banner: "16:9" (가로로 넓은 형태)
    - 만약 aspect_ratio 인자를 명시적으로 전달하면, 그 값이 최우선으로 적용됩니다.
    """

    # --- 유효성 검사 로직 추가 ---
    valid_classes = ["profile", "banner"]
    if imgClass not in valid_classes:
        # 허용되지 않은 값이 들어오면 에러 발생
        raise ValueError(f"imgClass는 다음 중 하나여야 합니다: {valid_classes}, 입력된 값: {imgClass}")
    # -------------------------

    final_aspect_ratio = aspect_ratio
    if final_aspect_ratio is None:
        if imgClass == "banner":
            final_aspect_ratio = "16:9"  # 배너는 가로로 길게
        elif imgClass == "profile":
            final_aspect_ratio = "1:1"   # 프로필은 정사각형
        else:
            # 혹시 모를 예외 상황에 대한 기본값
            final_aspect_ratio = "1:1"

    if not SD35_API_KEY:
        # 환경변수에 키가 없으면 바로 예외
        raise RuntimeError("SD35_API_KEY 환경변수가 설정되어 있지 않습니다.")

    if seed is None:
        # 시드가 없으면 랜덤 시드 하나 생성
        seed = secrets.randbelow(2**31)

    headers = {
        "authorization": f"Bearer {SD35_API_KEY}",
        # 바이너리 이미지 응답을 받기 위해 accept 를 image/* 로 설정
        "accept": "image/*",
    }

    # v2beta stable-image/generate/sd3 스펙에 맞춰 폼 데이터 구성
    data: Dict[str, Any] = {
        "prompt": prompt,
        "output_format": output_format,
        "aspect_ratio": final_aspect_ratio,
        "seed": seed,
        "model": "sd3.5-medium",     # 사용할 SD3.5 모델
        "mode": "text-to-image",     # 텍스트 → 이미지 모드
    }
    if negative_prompt:
        data["negative_prompt"] = negative_prompt

    print(f"[SD3.5 API] request: aspect_ratio={final_aspect_ratio}, seed={seed}")

    # multipart/form-data 전송을 위해 dummy 파일 필드를 같이 보냄
    resp = requests.post(
        SD35_API_URL,
        headers=headers,
        data=data,
        files={"none": ""},   # 실제 파일은 없지만, form-data 형식 유지용
        timeout=120,
    )

    if resp.status_code != 200:
        # 에러 메시지를 그대로 올려서 디버깅에 쓰기 좋게 함
        raise RuntimeError(f"SD3.5 API error: {resp.status_code} {resp.text}")

    # 응답 헤더에 seed 값이 있으면 그것으로 갱신
    header_seed = resp.headers.get("seed")
    if header_seed is not None:
        try:
            seed = int(header_seed)
        except ValueError:
            # 형식이 이상하면 그냥 기존 seed 그대로 사용
            pass

    # 바이너리 이미지를 PIL 이미지로 변환해서 사이즈 확인 후 로컬에 저장
    image_bytes = resp.content
    img = Image.open(BytesIO(image_bytes)).convert("RGB")
    width, height = img.size

    ts = time.strftime("%Y%m%d-%H%M%S")
    filename = f"outputs/sd35_{ts}_seed{seed}_{imgClass}.{output_format}"
    img.save(filename)

    return {
        "path": "/" + filename.replace("\\", "/"),
        "width": width,
        "height": height,
        "seed": seed,
    }
