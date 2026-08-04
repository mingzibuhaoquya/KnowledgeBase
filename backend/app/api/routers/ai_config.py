from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import AIConfig
from app.schemas import AIConfigIn, AIConfigOut
from app.services.security import encrypt_secret, mask_secret

router = APIRouter(prefix="/ai-config", tags=["ai-config"])


def _to_out(config: AIConfig) -> AIConfigOut:
    return AIConfigOut(
        id=config.id,
        provider=config.provider,
        base_url=config.base_url,
        api_key_masked=mask_secret(config.api_key_encrypted),
        model=config.model,
        enabled=bool(config.enabled),
        updated_at=config.updated_at,
    )


@router.get("", response_model=AIConfigOut | None)
def get_ai_config(db: Session = Depends(get_db)) -> AIConfigOut | None:
    config = db.scalar(select(AIConfig).order_by(AIConfig.id.desc()))
    return _to_out(config) if config else None


@router.put("", response_model=AIConfigOut)
def save_ai_config(payload: AIConfigIn, db: Session = Depends(get_db)) -> AIConfigOut:
    config = db.scalar(select(AIConfig).order_by(AIConfig.id.desc()))
    if not config:
        config = AIConfig()
        db.add(config)

    config.provider = payload.provider
    config.base_url = payload.base_url
    config.model = payload.model
    config.enabled = 1 if payload.enabled else 0
    if payload.api_key:
        config.api_key_encrypted = encrypt_secret(payload.api_key)

    db.commit()
    db.refresh(config)
    return _to_out(config)

