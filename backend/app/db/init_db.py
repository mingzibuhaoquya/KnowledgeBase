from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ModelConfig, User
from app.services.auth import hash_password


def ensure_seed_data(db: Session) -> None:
    admin = db.scalar(select(User).where(User.username == "admin"))
    if admin:
        return
    db.add(
        User(
            username="admin",
            email="admin@example.local",
            password_hash=hash_password("admin123"),
            role="admin",
        )
    )
    db.commit()


def ensure_default_model_configs(db: Session) -> None:
    defaults = {
        "chat": {
            "provider": "openai_compatible",
            "base_url": "https://api.deepseek.com/v1",
            "model": "deepseek-chat",
            "dimension": None,
        },
        "embedding": {
            "provider": "openai_compatible",
            "base_url": "",
            "model": "",
            "dimension": 1024,
        },
        "rerank": {
            "provider": "openai_compatible",
            "base_url": "",
            "model": "",
            "dimension": None,
        },
    }
    changed = False
    for kind, values in defaults.items():
        config = db.scalar(select(ModelConfig).where(ModelConfig.kind == kind))
        if config:
            continue
        db.add(ModelConfig(kind=kind, enabled=0, **values))
        changed = True
    if changed:
        db.commit()
