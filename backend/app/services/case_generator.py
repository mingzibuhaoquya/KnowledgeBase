import re

from app.models import KnowledgeDocument, TestCaseDraft


class CaseGenerator:
    def generate(self, document: KnowledgeDocument, max_cases: int = 8) -> list[TestCaseDraft]:
        candidates = self._split_requirements(document.content_text)
        if not candidates:
            candidates = [document.title or document.original_filename]

        cases: list[TestCaseDraft] = []
        for index, requirement in enumerate(candidates[:max_cases], start=1):
            title = self._build_title(requirement, index)
            cases.append(
                TestCaseDraft(
                    document_id=document.id,
                    title=title,
                    priority="P2",
                    precondition="系统已部署，测试账号和基础数据已准备。",
                    steps=f"1. 打开相关功能页面或接口。\n2. 按需求执行：{requirement}\n3. 记录实际结果。",
                    expected_result=f"功能表现符合需求描述：{requirement}",
                    project=document.project,
                    module=document.module,
                    api_path=self._find_api_path(requirement),
                    method=self._find_method(requirement),
                    source="ai_mock",
                    status="draft",
                )
            )
        return cases

    def _split_requirements(self, text: str) -> list[str]:
        lines = [line.strip(" -*\t\r") for line in text.splitlines()]
        meaningful = [
            line
            for line in lines
            if len(line) >= 8 and not line.startswith("[OCR pending]") and not line.startswith("Image OCR")
        ]
        if meaningful:
            return meaningful
        sentences = re.split(r"[。；;.!?]\s*", text)
        return [sentence.strip() for sentence in sentences if len(sentence.strip()) >= 8]

    def _build_title(self, requirement: str, index: int) -> str:
        title = requirement[:48].strip()
        return f"TC-{index:03d} {title}"

    def _find_api_path(self, requirement: str) -> str | None:
        match = re.search(r"(/[A-Za-z0-9_./{}:-]+)", requirement)
        return match.group(1) if match else None

    def _find_method(self, requirement: str) -> str | None:
        match = re.search(r"\b(GET|POST|PUT|PATCH|DELETE)\b", requirement, re.IGNORECASE)
        return match.group(1).upper() if match else None


case_generator = CaseGenerator()
