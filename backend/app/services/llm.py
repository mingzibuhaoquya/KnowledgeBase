from sqlalchemy.orm import Session

from app.services.model_clients import chat_model_client
from app.services.model_config import model_config_service


class LLMService:
    def answer(self, db: Session, question: str, context_blocks: list[str]) -> tuple[str, str]:
        config = model_config_service.get(db, "chat")
        if config and config.enabled and config.provider != "mock" and config.base_url and config.model:
            try:
                return chat_model_client.answer(config, question, context_blocks), "ai"
            except Exception as exc:
                fallback = self._mock_answer(question, context_blocks)
                return f"{fallback}\n\n[Remote chat model call failed: {exc}]", "mock_fallback"
        return self._mock_answer(question, context_blocks), "mock"

    def _mock_answer(self, question: str, context_blocks: list[str]) -> str:
        if not context_blocks:
            return (
                "没有检索到足够的知识库内容。请先上传并索引需求文档，"
                "或换一个更具体的问题。"
            )

        joined = "\n".join(context_blocks)
        lines = [line.strip() for line in joined.splitlines() if len(line.strip()) >= 8]
        selected = lines[:6]
        answer = [
            "当前使用的是本地兜底问答，还没有调用真实大模型。",
            f"你的问题：{question}",
            "根据已检索到的知识库内容，可以先关注这些信息：",
        ]
        answer.extend(f"- {line[:180]}" for line in selected)
        answer.append("配置并启用 Chat 模型后，这里会生成更完整的总结、推理、测试关注点和追问建议。")
        return "\n".join(answer)


llm_service = LLMService()
