# app/api/routes_main.py

from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/")
def landing(request: Request):
    """
    서비스 메인 화면
    """
    # 로그인 쿠키가 있으면 사용자 이름으로 표시
    user = request.cookies.get("user")

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "user": user,
        },
    )
