from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AIConfig, ModelConfig
from app.services.security import decrypt_secret, encrypt_secret, mask_secret


MODEL_KINDS = ("chat", "embedding", "rerank")


class ModelConfigService:
    def get(self, db: Session, kind: str) -> ModelConfig | None:
        return db.scalar(select(ModelConfig).where(ModelConfig.kind == kind))

    def list(self, db: Session) -> list[ModelConfig]:
        existing = {item.kind: item for item in db.scalars(select(ModelConfig)).all()}
        ordered: list[ModelConfig] = []
        for kind in MODEL_KINDS:
            if kind in existing:
                ordered.append(existing[kind])
        return ordered

    def save(
        self,
        db: Session,
        *,
        kind: str,
        provider: str,
        base_url: str,
        api_key: str,
        model: str,
        dimension: int | None,
        enabled: bool,
    ) -> ModelConfig:
        if kind not in MODEL_KINDS:
            raise ValueError(f"Unsupported model kind: {kind}")
        config = self.get(db, kind)
        if not config:
            config = ModelConfig(kind=kind)
            db.add(config)
        config.provider = provider
        config.base_url = base_url.strip()
        config.model = model.strip()
        config.dimension = dimension
        config.enabled = 1 if enabled else 0
        if api_key:
            config.api_key_encrypted = encrypt_secret(api_key)
        db.commit()
        db.refresh(config)
        return config

    def bootstrap_from_legacy_ai_config(self, db: Session) -> None:
        if self.get(db, "chat"):
            return
        legacy = db.scalar(select(AIConfig).order_by(AIConfig.id.desc()))
        if not legacy:
            return
        db.add(
            ModelConfig(
                kind="chat",
                provider=legacy.provider,
                base_url=legacy.base_url,
                api_key_encrypted=legacy.api_key_encrypted,
                model=legacy.model,
                enabled=legacy.enabled,
            )
        )
        db.commit()

    def api_key(self, config: ModelConfig) -> str:
        return decrypt_secret(config.api_key_encrypted)

    def masked_key(self, config: ModelConfig) -> str:
        return mask_secret(config.api_key_encrypted)


model_config_service = ModelConfigService()
