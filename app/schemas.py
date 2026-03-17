#입력 JSON 스키마
from typing import List, Optional
from pydantic import BaseModel


class BasicInfoCreate(BaseModel):
    name: str
    major: str
    email: str
    tags: List[str] = []
    values: List[str] = []
    interests: List[str] = []
    intro_text: Optional[str] = None