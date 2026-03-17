# app/api/routes_board.py

from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import BoardPost, UserProfile, User

router = APIRouter(prefix="/board")
templates = Jinja2Templates(directory="app/templates")


@router.get("")
def board_list(request: Request, db: Session = Depends(get_db)):
    """
    게시판 목록
    """
    posts = db.query(BoardPost).order_by(BoardPost.id.desc()).all()
    user = request.cookies.get("user")
    return templates.TemplateResponse(
        "board_list.html",
        {"request": request, "posts": posts, "user": user},
    )

@router.get("")
def board_list(request: Request, db: Session = Depends(get_db)):
    """
    게시판 목록 - intro_html이 있는 모든 유저 프로필 표시
    """
    
# app/api/routes_board.py
from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import UserProfile, User

router = APIRouter(prefix="/board")
templates = Jinja2Templates(directory="app/templates")


@router.get("")
def board_list(request: Request, db: Session = Depends(get_db)):
    """
    게시판 목록 - intro_html이 있는 모든 유저 프로필 표시
    """
    # 🔍 디버깅: 전체 UserProfile 수 확인
    total_profiles = db.query(UserProfile).count()
    print(f"[DEBUG] 전체 UserProfile 개수: {total_profiles}")
    
    # 🔍 디버깅: intro_html이 있는 프로필 확인
    profiles_with_html = db.query(UserProfile).filter(
        UserProfile.intro_html.isnot(None)
    ).all()
    print(f"[DEBUG] intro_html이 NOT NULL인 프로필 개수: {len(profiles_with_html)}")
    
    for p in profiles_with_html:
        print(f"[DEBUG] Profile ID: {p.id}, User ID: {p.user_id}, intro_html 길이: {len(p.intro_html) if p.intro_html else 0}")
    
    # intro_html이 null이 아닌 유저만 조회
    profiles = (
        db.query(UserProfile)
        .join(User, UserProfile.user_id == User.id)
        .filter(UserProfile.intro_html.isnot(None))
        .filter(UserProfile.intro_html != "")  # 빈 문자열도 제외
        .order_by(UserProfile.created_at.desc())
        .all()
    )
    
    print(f"[DEBUG] 필터링 후 최종 프로필 개수: {len(profiles)}")
    
    # 템플릿에 전달할 데이터 구조화
    profile_list = []
    for profile in profiles:
        profile_list.append({
            "id": profile.id,
            "user_id": profile.user_id,
            "display_name": profile.display_name or profile.user.username,
            "role_title": profile.role_title,
            "headline": profile.headline,
            "tags": profile.tags,
            "created_at": profile.created_at.strftime("%Y-%m-%d") if profile.created_at else "",
            "author": profile.display_name or profile.user.username,
        })
    
    print(f"[DEBUG] 최종 profile_list 개수: {len(profile_list)}")
    
    user = request.cookies.get("user")
    
    print(f"[DEBUG] 현재 로그인 유저: {user}")
    return templates.TemplateResponse(
        "board_list.html",
        {
            "request": request, 
            "posts": profile_list,  # 기존 템플릿 변수명 유지
            "user": user
        },
    )


@router.get("/{profile_id}")
def board_detail(
    profile_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    프로필 상세 보기 - intro_html을 그대로 렌더링
    """
    profile = (
        db.query(UserProfile)
        .filter(UserProfile.id == profile_id)
        .first()
    )
    
    if not profile or not profile.intro_html:
        # 프로필이 없거나 intro_html이 없으면 목록으로
        return RedirectResponse("/board", status_code=303)
    
    # intro_html을 그대로 렌더링
    return HTMLResponse(content=profile.intro_html)