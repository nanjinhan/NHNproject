# app/models.py

from sqlalchemy import Column, Integer, String, Text, DateTime, func, ForeignKey
from sqlalchemy.orm import relationship
from app.db import Base

class User(Base):
    """사용자 계정 정보를 저장하는 테이블"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)                 # 내부에서 사용하는 사용자 ID
    username = Column(String(50), unique=True, index=True, nullable=False)   # 로그인 ID
    password = Column(String(255), nullable=False)                     # 비밀번호(해시값 등 저장용)
    # email = Column(String(255), unique=True, nullable=False)           # 이메일 (길이 25 → 255로 확장)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    # 1:1 관계 - UserProfile
    profile = relationship(
        "UserProfile",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )

    # 1:N 관계 - 게시글
    posts = relationship(
        "BoardPost",
        back_populates="author",
        cascade="all, delete-orphan",
    )

    # ⚠ Project 모델을 아직 안 쓴다면, 아래 관계는 잠시 주석/삭제하는 게 안전함
    # projects = relationship(
    #     "Project",
    #     back_populates="owner",
    #     cascade="all, delete-orphan",
    # )


class BoardPost(Base):
    """게시판 글 정보를 저장하는 테이블"""
    __tablename__ = "board_posts"

    id = Column(Integer, primary_key=True, index=True)          # 게시글 번호
    title = Column(String(200), nullable=False)                 # 게시글 제목
    content = Column(Text, nullable=False)                      # 게시글 내용

    # 작성자 : users.id 를 참조
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    author = relationship("User", back_populates="posts")       # User와의 관계 설정

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),                              # 생성 시각 자동 기록
    )


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    user = relationship("User", back_populates="profile")

    # 기본 정보
    display_name = Column(String(50), nullable=True)      # 이름(화면에 보이는 이름)
    major = Column(String(100), nullable=True)            # 전공
    email = Column(String(255), nullable=True)
    role_title = Column(String(100), nullable=True)       # ex) "Backend & DB 지향 개발자"
    headline = Column(String(200), nullable=True)         # 한 줄 소개
    values = Column(String(255), nullable=True)           # 가치관 리스트
    interests = Column(String(255), nullable=True)        # 관심 분야
    about_me = Column(Text, nullable=True)                # 자유 자기소개(요약용)

    # 태그 (간단 버전)
    tags = Column(String(500), nullable=True)

    # 링크
    github_url = Column(String(255), nullable=True)
    blog_url = Column(String(255), nullable=True)

    # Clova X 파이프라인용 필드들
    intro_raw_text = Column(Text, nullable=True)          # 사용자가 직접 입력한 자기소개 텍스트
    intro_features_json = Column(Text, nullable=True)     # Clova X가 추출한 특징 JSON (문자열로 저장)
    intro_html = Column(Text, nullable=True)              # 최종 생성된 소개 페이지 HTML

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
