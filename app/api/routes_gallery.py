import requests
from glob import glob
from fastapi import APIRouter, Form, HTTPException, Request, Depends
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.deps import get_current_user
from app import crud, schemas, models

# 필요한 의존성 임포트
from app.db import get_db
# from app.deps import get_current_user  # 로그인 기능 연동 시 주석 해제
# from app import crud, schemas, models 

router = APIRouter(prefix="/gallery")
templates = Jinja2Templates(directory="app/templates")

# 1. 갤러리(스튜디오) 페이지 보여주기
@router.get("")
def gallery_list(request: Request):
    """
    AI 인터뷰 스튜디오 페이지 렌더링
    """
    user = request.cookies.get("user")

    # (선택 사항) 저장된 이미지 목록 불러오기
    pngs = glob("outputs/*.png")
    jpgs = glob("outputs/*.jpg")
    files = sorted(pngs + jpgs, reverse=True)
    images = ["/" + f.replace("\\", "/") for f in files]

    return templates.TemplateResponse(
        "gallery_list.html",
        {
            "request": request,
            "images": images,
            "user": user,
        },
    )

# 2. [핵심] GitHub ID 유효성 검사 API
# (프론트엔드에서 채팅 마지막 단계에 호출함)
@router.post("/check_github")
async def check_github_id(github_id: str = Form(...)):
    """
    입력받은 GitHub ID가 실제로 존재하는지 확인
    """
    try:
        url = f"https://api.github.com/users/{github_id}"
        # 타임아웃 5초 설정 (서버 멈춤 방지)
        response = requests.get(url, timeout=5)
        
        if response.status_code == 200:
            return JSONResponse(content={"exists": True})
        else:
            # 404 Not Found 등
            return JSONResponse(content={"exists": False})
            
    except Exception as e:
        print(f"GitHub API Error: {e}")
        # 에러가 나면 안전하게 '없음' 처리하거나 에러 메시지 반환
        return JSONResponse(content={"exists": False})

# 3. 기본 정보 저장 API (DB 연동용)
@router.post("/sendProfile")
async def send_profile(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
    base_name: str = Form(...),
    base_major: str = Form(...),
    base_email: str = Form(...),
    base_tags: str = Form(...),
    answer_intro: str = Form(...),
    answer_value: str = Form(...),
):
    """
    Stage 1에서 입력한 기본 정보를 DB에 저장 (선택 사항)
    """
    if not current_user:
         raise HTTPException(status_code=401, detail="로그인이 필요합니다.")
    
    try:
        print(f"✅ 기본 정보 수신: {base_name} / {base_major} / {base_tags}") # 테이블에 저장하도록 수정해야됨

        profile = db.query(models.UserProfile).filter(models.UserProfile.user_id == current_user.id).first()
        intro = answer_intro + "\n" + answer_value
        if not profile:
            # 4-1. 프로필이 없으면 새로 생성 (Insert)
            profile = models.UserProfile(
                user_id=current_user.id,
                display_name=base_name,
                major=base_major,
                email=base_email,
                tags=base_tags, # PostgreSQL ARRAY 타입이므로 리스트 그대로 저장
                intro_raw_text=intro
            )
            db.add(profile)
            print(f"사용자 {current_user.username}의 프로필을 새로 생성했습니다.")
        else:
            # 4-2. 프로필이 있으면 정보 업데이트 (Update)
            profile.display_name = base_name
            profile.major = base_major
            profile.email = base_email
            profile.tags = base_tags
            profile.intro_raw_text = intro
            print(f"사용자 {current_user.username}의 프로필을 업데이트했습니다.")
        
        # 5. DB에 반영
        db.commit()
        db.refresh(profile) # 업데이트된 정보 다시 불러오기 (선택사항)
        
        return JSONResponse(
            status_code=200,
            content={"message": "기본 정보가 성공적으로 저장되었습니다.", "profile_id": profile.id}
        )
    except Exception as e:
        db.rollback() # 에러 발생 시 롤백
        print(f"❌ Error saving profile: {e}")
        return JSONResponse(status_code=500, content={"detail": str(e)})
      