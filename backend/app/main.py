from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routers import admin, ai_config, auth, chat, dashboard, documents, knowledge, model_configs, test_cases
from app.core.config import settings
from app.db.session import Base, engine
from app.db.init_db import ensure_default_model_configs, ensure_seed_data
from app.db.session import SessionLocal


Base.metadata.create_all(bind=engine)
with SessionLocal() as db:
    ensure_seed_data(db)
    ensure_default_model_configs(db)

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/uploads", StaticFiles(directory=settings.upload_root), name="uploads")

app.include_router(documents.router, prefix=settings.api_v1_prefix)
app.include_router(test_cases.router, prefix=settings.api_v1_prefix)
app.include_router(ai_config.router, prefix=settings.api_v1_prefix)
app.include_router(model_configs.router, prefix=settings.api_v1_prefix)
app.include_router(knowledge.router, prefix=settings.api_v1_prefix)
app.include_router(chat.router, prefix=settings.api_v1_prefix)
app.include_router(auth.router, prefix=settings.api_v1_prefix)
app.include_router(dashboard.router, prefix=settings.api_v1_prefix)
app.include_router(admin.router, prefix=settings.api_v1_prefix)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
