# create_tables.py

from app.db import Base, engine
import app.models   # 반드시 필요함: 모델을 import해야 테이블이 생성됨

print("Creating all tables...")
Base.metadata.create_all(bind=engine)
print("Done.")
