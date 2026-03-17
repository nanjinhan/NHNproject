from sqlalchemy.orm import Session
from typing import Optional, List
from app import models
from app.schemas import BasicInfoCreate

def upsert_user_basic_info(db: Session, basic: BasicInfoCreate, user: models.User):
    # 1) 프로필 조회
    profile = user.profile

    # 2) 프로필 없으면 생성
    if not profile:
        profile = models.UserProfile(user_id=user.id)
        db.add(profile)

    # 3) 프로필 값 업데이트
    profile.display_name = basic.name
    profile.major = basic.major
    profile.email = basic.email
    profile.tags = ",".join(basic.tags) if basic.tags else None
    profile.values = ",".join(basic.values) if basic.values else None
    profile.interests = ",".join(basic.interests) if basic.interests else None
    profile.intro_raw_text = basic.intro_text

    db.commit()
    db.refresh(profile)

    return user, profile
