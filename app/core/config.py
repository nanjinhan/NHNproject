# app/core/config.py
import os
from dotenv import load_dotenv, find_dotenv


class Settings:
    def __init__(self) -> None:
        # .env 파일 로드 (.env가 없으면 무시)
        load_dotenv(find_dotenv())

        # ===== ClovaX / LLM =====
        # 네이버 클로바 스튜디오 API 키
        self.CLOVA_KEY = os.getenv("CLOVASTUDIO_API_KEY", "")

        # ===== SD3.5 API 설정 =====
        # SD3.5 호출에 사용할 API 키
        self.SD35_API_KEY = os.getenv("SD35_API_KEY", "")

        # 생성된 이미지를 저장할 로컬 폴더
        self.OUTPUT_DIR = os.getenv("OUTPUT_DIR", "outputs")
        os.makedirs(self.OUTPUT_DIR, exist_ok=True)


# 전역 설정 인스턴스
settings = Settings()
