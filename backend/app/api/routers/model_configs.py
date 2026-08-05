from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import ModelConfig
from app.schemas import ModelConfigIn, ModelConfigOut, ModelTestRequest, ModelTestResponse
from app.services.model_clients import chat_model_client, embedding_client, rerank_client
from app.services.model_config import MODEL_KINDS, model_config_service

router = APIRouter(prefix="/model-configs", tags=["model-configs"])


def _to_out(config: ModelConfig) -> ModelConfigOut:
    return ModelConfigOut(
        id=config.id,
        kind=config.kind,
        provider=config.provider,
        base_url=config.base_url,
        api_key_masked=model_config_service.masked_key(config),
        model=config.model,
        dimension=config.dimension,
        enabled=bool(config.enabled),
        updated_at=config.updated_at,
    )


@router.get("", response_model=list[ModelConfigOut])
def list_model_configs(db: Session = Depends(get_db)) -> list[ModelConfigOut]:
    model_config_service.bootstrap_from_legacy_ai_config(db)
    return [_to_out(config) for config in model_config_service.list(db)]


@router.get("/{kind}", response_model=ModelConfigOut | None)
def get_model_config(kind: str, db: Session = Depends(get_db)) -> ModelConfigOut | None:
    if kind not in MODEL_KINDS:
        raise HTTPException(status_code=404, detail="Unsupported model kind.")
    model_config_service.bootstrap_from_legacy_ai_config(db)
    config = model_config_service.get(db, kind)
    return _to_out(config) if config else None


@router.put("/{kind}", response_model=ModelConfigOut)
def save_model_config(kind: str, payload: ModelConfigIn, db: Session = Depends(get_db)) -> ModelConfigOut:
    if kind not in MODEL_KINDS:
        raise HTTPException(status_code=404, detail="Unsupported model kind.")
    try:
        config = model_config_service.save(
            db,
            kind=kind,
            provider=payload.provider,
            base_url=payload.base_url,
            api_key=payload.api_key,
            model=payload.model,
            dimension=payload.dimension,
            enabled=payload.enabled,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _to_out(config)


@router.post("/{kind}/test", response_model=ModelTestResponse)
def test_model_config(kind: str, payload: ModelTestRequest, db: Session = Depends(get_db)) -> ModelTestResponse:
    config = model_config_service.get(db, kind)
    if not config or not config.enabled:
        raise HTTPException(status_code=400, detail="Model config is not enabled.")
    if not config.base_url or not config.model:
        raise HTTPException(status_code=400, detail="Base URL and model are required.")
    try:
        if kind == "chat":
            result = chat_model_client.test(config, payload.text)
            return ModelTestResponse(ok=True, kind=kind, message="Chat model call succeeded.", detail=result[:500])
        if kind == "embedding":
            vector = embedding_client.embed_strict(config, payload.text)
            return ModelTestResponse(ok=True, kind=kind, message=f"Embedding model returned {len(vector)} dimensions.")
        if kind == "rerank":
            results = rerank_client.test(config, payload.text)
            return ModelTestResponse(ok=True, kind=kind, message=f"Rerank model returned {len(results)} results.")
    except Exception as exc:
        return ModelTestResponse(ok=False, kind=kind, message="Model test failed.", detail=str(exc))
    raise HTTPException(status_code=404, detail="Unsupported model kind.")
