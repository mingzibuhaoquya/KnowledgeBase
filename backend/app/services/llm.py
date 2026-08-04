import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AIConfig
from app.services.security import decrypt_secret


class LLMService:
    def answer(self, db: Session, question: str, context_blocks: list[str]) -> tuple[str, str]:
        config = db.scalar(select(AIConfig).order_by(AIConfig.id.desc()))
        if config and config.enabled and config.provider != "mock" and config.base_url and config.model:
            try:
                return self._remote_answer(config, question, context_blocks), "ai"
            except Exception as exc:
                fallback = self._mock_answer(question, context_blocks)
                return f"{fallback}\n\n[AI remote call failed: {exc}]", "mock_fallback"
        return self._mock_answer(question, context_blocks), "mock"

    def _remote_answer(self, config: AIConfig, question: str, context_blocks: list[str]) -> str:
        api_key = decrypt_secret(config.api_key_encrypted)
        url = config.base_url.rstrip("/")
        if not url.endswith("/chat/completions"):
            url = f"{url}/chat/completions"
        messages = [
            {
                "role": "system",
                "content": (
                    "你是测试团队使用的知识库助手。请使用中文回答。"
                    "只基于提供的知识库上下文回答；如果上下文不足，请明确说明。"
                    "尽量按要点组织，并指出可能的测试关注点。"
                ),
            },
            {
                "role": "user",
                "content": "知识库上下文：\n"
                + "\n\n".join(context_blocks)
                + f"\n\n用户问题：\n{question}",
            },
        ]
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        with httpx.Client(timeout=45) as client:
            response = client.post(url, headers=headers, json={"model": config.model, "messages": messages, "temperature": 0.2})
            response.raise_for_status()
            data = response.json()
        return data["choices"][0]["message"]["content"].strip()

    def _mock_answer(self, question: str, context_blocks: list[str]) -> str:
        if not context_blocks:
            return "没有检索到足够的知识库内容。请先上传需求文档，或换一个更具体的问题。"

        joined = "\n".join(context_blocks)
        lines = [line.strip() for line in joined.splitlines() if len(line.strip()) >= 8]
        selected = lines[:6]
        answer = [
            "当前使用的是本地 mock 问答，还没有调用真实大模型。",
            f"你的问题：{question}",
            "根据已检索到的知识库内容，可以先关注这些信息：",
        ]
        answer.extend(f"- {line[:180]}" for line in selected)
        answer.append("接入真实 AI 配置后，这里会生成更完整的总结、推理、测试点和追问建议。")
        return "\n".join(answer)


llm_service = LLMService()
