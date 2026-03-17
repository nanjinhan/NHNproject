# app/main.py

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager

# 페이지(메인, SNS, 게시판, 갤러리, 인증)별 라우터 import
from app.api.routes_main import router as main_router
from app.api.routes_sns import router as sns_router
from app.api.routes_board import router as board_router
from app.api.routes_gallery import router as gallery_router
from app.api.routes_auth import router as auth_router
from app.api.routes_profileGen import router as profileGen_router


# SNS용 LLM 프롬프트 체인 초기화
from app.services.llm_sns import init_llm_chains

# SQLAlchemy 기본 설정 (SQLite) 
from app.db import Base, engine
import app.models  # 모델 정의를 import 해야 create_all 에서 인식됨

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    서버가 부팅될 때 한 번만 실행되는 초기화 로직.
    - SNS 이미지 생성용 LLM 체인을 미리 올려두어 첫 호출 시 지연을 줄임
    """
    init_llm_chains()  
    yield

# FastAPI 앱 인스턴스 생성
app = FastAPI(
    title="Project Day Baseline", 
    lifespan=lifespan
)

# --- DB 초기화 ---
# 앱이 시작될 때 테이블이 없으면 자동으로 생성
Base.metadata.create_all(bind=engine)

# --- 정적 파일 마운트 ---
# SD3.5에서 생성된 이미지를 저장하는 outputs 폴더를 /outputs 경로에 연결
app.mount("/outputs", StaticFiles(directory="outputs"), name="outputs")

# --- 라우터 등록 ---
# 메인 페이지, SNS 스튜디오, 게시판, 갤러리, 로그인/로그아웃 엔드포인트 묶음
app.include_router(main_router)    # "/"
app.include_router(sns_router)     # "/sns"
app.include_router(board_router)   # "/board"
app.include_router(gallery_router) # "/gallery"
app.include_router(auth_router)    # "/login", "/logout", "/signup" 등
app.include_router(profileGen_router)
