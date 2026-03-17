# app/deps.py

from fastapi import Depends, Request, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional

# 프로젝트 구조에 맞게 임포트 경로를 확인해주세요.
from app.db import get_db
from app import models

def get_current_user(
    request: Request,
    db: Session = Depends(get_db)
) -> Optional[models.User]:  # [수정] 반환 타입을 User로 변경
    """
    쿠키의 username을 통해 User 모델을 반환합니다.
    """
    # 1. 쿠키에서 username 가져오기
    username = request.cookies.get("user")
    if not username:
        return None

    # 2. [수정] UserProfile이 아니라 User 테이블에서 검색해야 함
    #    User.username (String) vs cookie value (String) -> 매칭 성공
    user = db.query(models.User).filter(models.User.username == username).first()

    return user