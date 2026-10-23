"""PDF 텍스트·링크 추출. pdftotext가 기본이고 없으면 PyMuPDF로 대체한다."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from .textio import normalize_text

PDFTOTEXT_PATHS = ("/opt/homebrew/bin/pdftotext", "/usr/local/bin/pdftotext")
PDFTOTEXT_TIMEOUT_SEC = 120


class InputError(ValueError):
    """사용자에게 그대로 보여 줄 수 있는 입력 오류 (종료 코드 2)."""


def load_pymupdf():
    """PyMuPDF 모듈 또는 None. 1.24 이하는 fitz, 2.x는 pymupdf."""
    try:
        import pymupdf
        return pymupdf
    except ImportError:
        pass
    try:
        import fitz
        return fitz
    except ImportError:
        return None


def _find_pdftotext() -> str | None:
    found = shutil.which("pdftotext")
    if found:
        return found
    return next((p for p in PDFTOTEXT_PATHS if Path(p).exists()), None)


def _split_pages(raw: str) -> list[str]:
    pages = raw.split("\f")
    if pages and not pages[-1].strip():
        pages = pages[:-1]
    return [normalize_text(page) for page in pages]


def pymupdf_pages(path: Path) -> list[str]:
    fitz = load_pymupdf()
    if fitz is None:
        raise InputError("PDF 텍스트를 추출할 도구가 없습니다. poppler(pdftotext) 또는 pymupdf를 설치하세요.")
    with fitz.open(path) as doc:
        return [normalize_text(page.get_text()) for page in doc]


def pdf_pages(path: Path, layout: bool = False) -> list[str]:
    """페이지별 텍스트. layout=True면 pdftotext -layout."""
    tool = _find_pdftotext()
    if tool is None:
        return pymupdf_pages(path)
    cmd = [tool, "-enc", "UTF-8"] + (["-layout"] if layout else []) + [str(path), "-"]
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=PDFTOTEXT_TIMEOUT_SEC, check=False)
    except subprocess.TimeoutExpired as exc:
        raise InputError(f"PDF 텍스트 추출 시간이 초과됐습니다: {path.name}") from exc
    if proc.returncode != 0:
        raise InputError(f"PDF를 읽을 수 없습니다: {path.name} ({proc.stderr.decode('utf-8', 'replace').strip()})")
    return _split_pages(proc.stdout.decode("utf-8", "replace"))


def pdf_links(path: Path) -> list[dict]:
    """페이지별 링크 URI. PyMuPDF가 없으면 빈 목록."""
    fitz = load_pymupdf()
    if fitz is None:
        return []
    links = []
    with fitz.open(path) as doc:
        for page in doc:
            for link in page.get_links():
                if link.get("uri"):
                    links.append({"page": page.number + 1, "uri": link["uri"]})
    return links


def require_file(path: Path) -> Path:
    if not path.is_file():
        raise InputError(f"입력 파일이 없습니다: {path}")
    return path
