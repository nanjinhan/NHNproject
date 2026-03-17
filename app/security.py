# app/security.py

from passlib.context import CryptContext

# bcrypt 기반 비밀번호 해시/검증용 컨텍스트
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """사용자 비밀번호를 해시로 변환"""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """입력 비밀번호와 저장된 해시값이 일치하는지 확인"""
    return pwd_context.verify(plain_password, hashed_password)
