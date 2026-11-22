"""Bounded, deterministic extraction. Every proposed fact requires user approval."""

import io
import re
import zipfile
from pathlib import Path
from uuid import uuid4

from docx import Document
from pypdf import PdfReader

from ..schemas import FactKind, Suggestion

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_TEXT_CHARS = 100_000
MAX_PDF_PAGES = 20
MAX_DOCX_UNCOMPRESSED = 20 * 1024 * 1024


class ResumeParseError(ValueError):
    pass


def detect_file_type(filename: str, data: bytes) -> tuple[str, str]:
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf" and data.startswith(b"%PDF-"):
        return "application/pdf", "pdf"
    if suffix == ".docx" and data.startswith(b"PK"):
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                if len(archive.infolist()) > 500 or sum(item.file_size for item in archive.infolist()) > MAX_DOCX_UNCOMPRESSED:
                    raise ResumeParseError("DOCX archive is too large")
                if "[Content_Types].xml" not in archive.namelist() or "word/document.xml" not in archive.namelist():
                    raise ResumeParseError("Invalid DOCX document")
        except (zipfile.BadZipFile, OSError) as exc:
            raise ResumeParseError("Invalid DOCX document") from exc
        return "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "docx"
    raise ResumeParseError("Upload a valid PDF or DOCX resume")


def extract_text(data: bytes, extension: str) -> str:
    try:
        if extension == "pdf":
            reader = PdfReader(io.BytesIO(data), strict=True)
            if reader.is_encrypted:
                raise ResumeParseError("Password-protected PDFs are not supported")
            if len(reader.pages) > MAX_PDF_PAGES:
                raise ResumeParseError("PDF has too many pages")
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
        elif extension == "docx":
            document = Document(io.BytesIO(data))
            parts = [paragraph.text for paragraph in document.paragraphs]
            parts.extend(cell.text for table in document.tables for row in table.rows for cell in row.cells)
            text = "\n".join(parts)
        else:
            raise ResumeParseError("Unsupported file type")
    except ResumeParseError:
        raise
    except Exception as exc:
        raise ResumeParseError("Could not read the resume") from exc
    text = text[:MAX_TEXT_CHARS].strip()
    if not text:
        raise ResumeParseError("No readable text was found in the resume")
    return text


EMAIL = re.compile(r"(?<![\w.+-])[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}(?![\w.-])")
PHONE = re.compile(r"(?:\+?\d[\d ()-]{7,}\d)")
URL = re.compile(r"https?://[^\s)>,]+", re.I)
HEADINGS: dict[str, FactKind] = {
    "education": "education", "work experience": "experience", "experience": "experience",
    "professional experience": "experience", "projects": "project", "skills": "skill",
    "technical skills": "skill",
}


def extract_suggestions(text: str) -> list[Suggestion]:
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    lines = [line[:1000] for line in lines if line.strip()]
    suggestions: list[Suggestion] = []
    seen: set[tuple[str, str]] = set()

    def add(kind: FactKind, value: str, source: str) -> None:
        key = (kind, value.casefold())
        if not value or key in seen or len(suggestions) >= 50:
            return
        seen.add(key)
        suggestions.append(Suggestion(id=str(uuid4()), kind=kind, proposed=value[:1000], sourceExcerpt=source[:1000]))

    if lines and 1 <= len(lines[0].split()) <= 6 and len(lines[0]) <= 80 and not EMAIL.search(lines[0]) and lines[0].lower() not in (*HEADINGS, "resume", "curriculum vitae", "cv"):
        add("fullName", lines[0], lines[0])
    section: FactKind | None = None
    for line in lines:
        lower = line.strip(": ").casefold()
        if lower in HEADINGS:
            section = HEADINGS[lower]
            continue
        for match in EMAIL.finditer(line):
            add("email", match.group(), line)
        for match in PHONE.finditer(line):
            add("phone", match.group(), line)
        for match in URL.finditer(line):
            value = match.group().rstrip(".;")
            if "linkedin.com/" in value.lower():
                add("linkedin", value, line)
            elif "github.com/" in value.lower():
                add("github", value, line)
        if section and len(line) >= 3 and lower not in HEADINGS:
            add(section, line, line)
    return suggestions
