# app/api/routes_auth.py

from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app import models
from app.db import get_db
from app.models import User
from app.security import hash_password, verify_password

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/login")
def login_form(request: Request):
    """로그인 화면"""
    user = request.cookies.get("user")
    return templates.TemplateResponse(
        "login.html",
        {
            "request": request,
            "user": user,
            "error": None,
        },
    )


@router.post("/login")
def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    """
    로그인 처리
    - 가입된 사용자인지 확인
    - bcrypt 해시로 비밀번호 검증
    - 성공 시 'user' 쿠키에 username 저장
    """
    user_obj = db.query(User).filter(User.username == username).first()

    # 가입되지 않은 아이디
    if user_obj is None:
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "user": None,
                "error": "가입되지 않은 아이디입니다. 회원가입 후 이용해주세요.",
            },
            status_code=400,
        )

    # 비밀번호 불일치
    if not verify_password(password, user_obj.password):
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "user": None,
                "error": "아이디 또는 비밀번호가 올바르지 않습니다.",
            },
            status_code=400,
        )

    # 로그인 성공
    resp = RedirectResponse("/", status_code=303)
    # username만 쿠키에 저장, 만료 7일
    resp.set_cookie(key="user", value=user_obj.username, max_age=7 * 24 * 3600)
    return resp


@router.get("/signup")
def signup_form(request: Request):
    """회원가입 화면"""
    user = request.cookies.get("user")
    return templates.TemplateResponse(
        "signup.html",
        {
            "request": request,
            "user": user,
            "error": None,
        },
    )


@router.post("/signup")
def signup(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    password_confirm: str = Form(...),
    db: Session = Depends(get_db),
):
    """
    회원가입 처리
    - 비밀번호/비밀번호 확인 일치 여부 체크
    - username 중복 체크
    - 통과 시 bcrypt로 해시한 비밀번호 저장
    """
    # 비밀번호 확인
    if password != password_confirm:
        return templates.TemplateResponse(
            "signup.html",
            {
                "request": request,
                "user": None,
                "error": "비밀번호와 비밀번호 확인이 일치하지 않습니다.",
            },
            status_code=400,
        )

    # 중복 아이디 체크
    exists = db.query(User).filter(User.username == username).first()
    if exists:
        return templates.TemplateResponse(
            "signup.html",
            {
                "request": request,
                "user": None,
                "error": "이미 사용 중인 아이디입니다.",
            },
            status_code=400,
        )

    # 새 유저 생성 (비밀번호는 해시로 저장)
    hashed_pw = hash_password(password)
    user_obj = User(username=username, password=hashed_pw)
    db.add(user_obj)
    db.commit()
    db.refresh(user_obj)

    new_profile = models.UserProfile(
        user_id=user_obj.id,
        display_name=username, # 초기값은 아이디와 동일하게 설정
        major="",
        email=""
    )
    db.add(new_profile)
    db.commit()

    # 회원가입 후 자동 로그인
    resp = RedirectResponse("/", status_code=303)
    resp.set_cookie(key="user", value=user_obj.username, max_age=7 * 24 * 3600)
    return resp


@router.get("/logout")
def logout():
    """로그아웃: 'user' 쿠키 삭제 후 메인으로 이동"""
    resp = RedirectResponse("/", status_code=303)
    resp.delete_cookie("user")
    return resp
