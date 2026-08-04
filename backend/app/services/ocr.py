from pathlib import Path


class OCRService:
    def extract_text(self, image_path: Path) -> str:
        return f"[OCR pending] {image_path.name}"


ocr_service = OCRService()
