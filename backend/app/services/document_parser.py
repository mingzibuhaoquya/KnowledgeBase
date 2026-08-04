import shutil
import csv
import uuid
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from fastapi import HTTPException, UploadFile

from app.core.config import settings
from app.services.ocr import ocr_service


@dataclass
class ParsedImage:
    filename: str
    file_path: str
    ocr_text: str = ""


@dataclass
class ParsedDocument:
    stored_filename: str
    file_path: str
    file_type: str
    file_hash: str
    file_size: int
    content_text: str
    images: list[ParsedImage] = field(default_factory=list)


class DocumentParser:
    allowed_suffixes = {".txt", ".md", ".docx", ".pdf", ".xlsx", ".csv"}

    async def save_and_parse(self, upload: UploadFile) -> ParsedDocument:
        suffix = Path(upload.filename or "document").suffix.lower()
        if suffix not in self.allowed_suffixes:
            raise HTTPException(status_code=400, detail="Unsupported file type. Please upload txt, md, docx, pdf, xlsx, or csv.")

        doc_dir = settings.upload_root / uuid.uuid4().hex
        image_dir = doc_dir / "images"
        image_dir.mkdir(parents=True, exist_ok=True)

        stored_filename = f"source{suffix or '.bin'}"
        target_path = doc_dir / stored_filename
        with target_path.open("wb") as buffer:
            shutil.copyfileobj(upload.file, buffer)
        file_size = target_path.stat().st_size
        if file_size == 0:
            shutil.rmtree(doc_dir, ignore_errors=True)
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")
        file_hash = self._sha256(target_path)

        try:
            text = self._extract_text(target_path, suffix)
            images = self._extract_images(target_path, suffix, image_dir)
        except Exception as exc:
            text = f"Parse failed: {exc}"
            images = []
        ocr_lines: list[str] = []
        for image in images:
            image.ocr_text = ocr_service.extract_text(Path(image.file_path))
            if image.ocr_text:
                ocr_lines.append(image.ocr_text)

        if ocr_lines:
            text = f"{text}\n\nImage OCR:\n" + "\n".join(ocr_lines)

        return ParsedDocument(
            stored_filename=stored_filename,
            file_path=str(target_path),
            file_type=suffix.removeprefix(".") or "unknown",
            file_hash=file_hash,
            file_size=file_size,
            content_text=text.strip(),
            images=images,
        )

    def _sha256(self, file_path: Path) -> str:
        import hashlib

        digest = hashlib.sha256()
        with file_path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _extract_text(self, file_path: Path, suffix: str) -> str:
        if suffix in {".txt", ".md"}:
            return file_path.read_text(encoding="utf-8", errors="ignore")
        if suffix == ".docx":
            return self._extract_docx_text(file_path)
        if suffix == ".pdf":
            return self._extract_pdf_text(file_path)
        if suffix == ".xlsx":
            return self._extract_xlsx_text(file_path)
        if suffix == ".csv":
            return self._extract_csv_text(file_path)
        return ""

    def _extract_docx_text(self, file_path: Path) -> str:
        try:
            from docx import Document
        except ImportError:
            return "[python-docx is not installed. Cannot parse docx text.]"

        doc = Document(str(file_path))
        paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
        table_lines: list[str] = []
        for table in doc.tables:
            for row in table.rows:
                cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                if cells:
                    table_lines.append(" | ".join(cells))
        return "\n".join(paragraphs + table_lines)

    def _extract_pdf_text(self, file_path: Path) -> str:
        try:
            from pypdf import PdfReader
        except ImportError:
            return "[pypdf is not installed. Cannot parse pdf text.]"

        reader = PdfReader(str(file_path))
        return "\n".join(page.extract_text() or "" for page in reader.pages)

    def _extract_xlsx_text(self, file_path: Path) -> str:
        try:
            from openpyxl import load_workbook
        except ImportError:
            return "[openpyxl is not installed. Cannot parse xlsx text.]"

        workbook = load_workbook(str(file_path), data_only=True, read_only=True)
        sections: list[str] = []
        for sheet in workbook.worksheets:
            rows = list(sheet.iter_rows(values_only=True))
            if not rows:
                continue
            sections.append(f"Sheet: {sheet.title}")
            header = self._clean_row(rows[0])
            if header:
                sections.append("Columns: " + " | ".join(header))
            for row_index, row in enumerate(rows[1:] if header else rows, start=2 if header else 1):
                cells = self._clean_row(row)
                if not cells:
                    continue
                if header and len(header) == len(cells):
                    pairs = [f"{name}: {value}" for name, value in zip(header, cells)]
                    sections.append(f"Row {row_index}: " + " | ".join(pairs))
                else:
                    sections.append(f"Row {row_index}: " + " | ".join(cells))
        workbook.close()
        return "\n".join(sections)

    def _extract_csv_text(self, file_path: Path) -> str:
        text = file_path.read_text(encoding="utf-8-sig", errors="ignore")
        rows = list(csv.reader(text.splitlines()))
        if not rows:
            return ""
        sections = ["CSV Table"]
        header = self._clean_row(rows[0])
        if header:
            sections.append("Columns: " + " | ".join(header))
        for row_index, row in enumerate(rows[1:] if header else rows, start=2 if header else 1):
            cells = self._clean_row(row)
            if not cells:
                continue
            if header and len(header) == len(cells):
                sections.append(f"Row {row_index}: " + " | ".join(f"{name}: {value}" for name, value in zip(header, cells)))
            else:
                sections.append(f"Row {row_index}: " + " | ".join(cells))
        return "\n".join(sections)

    def _clean_row(self, row) -> list[str]:
        cells: list[str] = []
        for value in row:
            if value is None:
                continue
            text = str(value).strip()
            if text:
                cells.append(text)
        return cells

    def _extract_images(self, file_path: Path, suffix: str, image_dir: Path) -> list[ParsedImage]:
        if suffix != ".docx":
            return []

        images: list[ParsedImage] = []
        with zipfile.ZipFile(file_path) as archive:
            for item in archive.namelist():
                if not item.startswith("word/media/"):
                    continue
                source_name = Path(item).name
                target_name = f"{len(images) + 1:03d}_{source_name}"
                target_path = image_dir / target_name
                with archive.open(item) as source, target_path.open("wb") as target:
                    shutil.copyfileobj(source, target)
                images.append(ParsedImage(filename=target_name, file_path=str(target_path)))
        return images


document_parser = DocumentParser()
