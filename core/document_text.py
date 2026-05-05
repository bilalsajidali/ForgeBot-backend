import re
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_PAGES_PDF = 48
MAX_CHARS_PDF_EXTRACT = 55_000
MAX_CHARS_DOCX_EXTRACT = 55_000
MAX_CHARS_TXT_EXTRACT = 200_000
MAX_FILES_PER_AGENT = 12
MAX_TOTAL_STORED_CHARS = 400_000

ALLOWED_SUFFIXES = (".pdf", ".docx", ".txt")

_DOC_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"


def safe_document_filename(name: str) -> str:
    base = re.sub(r"[^\w.\- ()\[\]]+", "_", (name or "").strip())[:180]
    if not base:
        return "document.txt"
    lower = base.lower()
    if any(lower.endswith(s) for s in ALLOWED_SUFFIXES):
        return base
    return base + ".txt"


def extract_pdf_text(file_bytes: bytes) -> str:
    reader = PdfReader(BytesIO(file_bytes))
    parts: list[str] = []
    for page in reader.pages[:MAX_PAGES_PDF]:
        try:
            t = page.extract_text() or ""
        except Exception:
            t = ""
        if t:
            parts.append(t)
    text = "\n\n".join(parts).strip()
    if len(text) > MAX_CHARS_PDF_EXTRACT:
        text = text[:MAX_CHARS_PDF_EXTRACT] + "\n\n[Content truncated from this PDF.]"
    return text


def extract_docx_text(file_bytes: bytes) -> str:
    from docx import Document

    doc = Document(BytesIO(file_bytes))
    paragraphs = [p.text.strip() for p in doc.paragraphs if p.text and p.text.strip()]
    text = "\n\n".join(paragraphs).strip()
    if len(text) > MAX_CHARS_DOCX_EXTRACT:
        text = text[:MAX_CHARS_DOCX_EXTRACT] + "\n\n[Content truncated from this DOCX.]"
    return text


def extract_txt_text(file_bytes: bytes) -> str:
    text = file_bytes.decode("utf-8", errors="replace").strip()
    if len(text) > MAX_CHARS_TXT_EXTRACT:
        text = text[:MAX_CHARS_TXT_EXTRACT] + "\n\n[Content truncated from this text file.]"
    return text


def extract_document_text(filename: str, data: bytes) -> str:
    lower = Path(filename).name.lower()

    if lower.endswith(".doc") and not lower.endswith(".docx"):
        if len(data) >= 8 and data[:8] == _DOC_MAGIC:
            raise ValueError(
                "Legacy Word .doc is not supported. Save the file as .docx and upload again."
            )
        raise ValueError("Unsupported file type. Use PDF, DOCX, or TXT.")

    if lower.endswith(".pdf"):
        if len(data) < 5 or not data.startswith(b"%PDF"):
            raise ValueError("not a valid PDF")
        text = extract_pdf_text(data)
        if not text.strip():
            raise ValueError("no extractable text (scanned PDFs may be empty)")
        return text

    if lower.endswith(".docx"):
        try:
            text = extract_docx_text(data)
        except Exception as exc:
            raise ValueError(f"could not read DOCX ({exc})") from exc
        if not text.strip():
            raise ValueError("no extractable text in DOCX")
        return text

    if lower.endswith(".txt"):
        text = extract_txt_text(data)
        if not text.strip():
            raise ValueError("text file is empty")
        return text

    raise ValueError("Unsupported type. Use PDF, DOCX, or TXT.")


def unique_filename(existing: set[str], proposal: str) -> str:
    proposal = (proposal or "document.txt").strip()
    if "." in proposal:
        stem, ext = proposal.rsplit(".", 1)
        ext = "." + ext.lower()
    else:
        stem, ext = proposal, ".txt"
    candidate = f"{stem}{ext}"
    n = 1
    while candidate in existing:
        candidate = f"{stem}_{n}{ext}"
        n += 1
    return candidate
