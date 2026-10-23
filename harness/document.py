"""입력 서류(PDF, TXT/MD, 이력서 변형 YAML)를 하나의 Document로 통일한다."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from . import dates
from .extract import InputError, load_pymupdf, pdf_links, pdf_pages, pymupdf_pages, require_file
from .facts import YAML_SUFFIXES, Variant, load_facts, load_variant, variant_job_spans
from .sections import section_resolver, split_sections
from .textio import normalize_text

MIN_BULLET_CHARS = 15
BULLET_MARKER = "•"
LEAVE_RE = re.compile(r"휴직")  # 군 복무 휴직 항목은 총 경력에서 빠지므로 성과 bullet로 세지 않는다 (변형 YAML의 kind: leave와 같다)
NON_BULLET_RE = re.compile(r"\(주\)|\d{4}\s*[.\-]\s*\d{1,2}\s*[~–-]|→\s*(?:책임|선임)|^\W*(?:책임|선임|매니저)")
BULLET_SECTIONS = ("experience", "projects")
HANGUL_RE = re.compile(r"[가-힣]")
WRAPPED_LINE_CHARS = 60  # 이보다 긴 줄 다음 줄은 같은 bullet이 줄바꿈된 것으로 본다
LABEL_MAX_CHARS = 50  # 한글도 화살표도 없는 짧은 줄은 bullet이 아니라 직함·라벨이다 (예: "Senior Product Designer", "AI Product · AX")


@dataclass
class Document:
    path: Path
    kind: str  # pdf | yaml | text
    text: str
    layout_text: str
    pages: list[str] = field(default_factory=list)
    layout_pages: list[str] = field(default_factory=list)
    sections: dict[str, str] = field(default_factory=dict)
    bullets: list[str] = field(default_factory=list)
    variant: Variant | None = None
    date_summary: dict = field(default_factory=dict)
    links: list[dict] = field(default_factory=list)
    mupdf_pages: list[str] = field(default_factory=list)  # PDF만. 숫자 주장 검사와 text_mupdf.txt용

    @property
    def is_pdf(self) -> bool:
        return self.kind == "pdf"

    @property
    def claim_text(self) -> str:
        """숫자 주장 검사용 텍스트. PDF는 MuPDF 추출을 쓴다 (Poppler 조각 '202', '3.02'가 주장으로 잡히지 않게)."""
        return "\n".join(self.mupdf_pages) if self.mupdf_pages else self.text

    @property
    def total_months(self) -> int:
        return int(self.date_summary.get("total_months", 0))

    def section_names(self) -> list[str]:
        return [name for name, body in self.sections.items() if body.strip()]


def _is_label(line: str) -> bool:
    return len(line) <= LABEL_MAX_CHARS and "→" not in line and not HANGUL_RE.search(line)


def _marked_bullets(lines: list[str]) -> list[str]:
    """"•"로 시작하는 줄이 새 bullet이고, 마커 없는 줄은 앞 bullet의 줄바꿈 이어짐이다. 마커 앞의 줄(직함 등)은 버린다."""
    bullets: list[str] = []
    for line in lines:
        if line.startswith(BULLET_MARKER):
            bullets.append(line[len(BULLET_MARKER):].strip())
        elif bullets and line:
            bullets[-1] = f"{bullets[-1]} {line}"
    return [b for b in bullets if len(b) >= MIN_BULLET_CHARS]


def _paragraph_bullets(paragraph: str) -> list[str]:
    """한 문단을 bullet로 나눈다. 직함·날짜 줄은 버리고, 앞줄이 줄 끝까지 찼으면(줄바꿈된 bullet) 이어 붙인다."""
    lines = [" ".join(raw.split()) for raw in paragraph.splitlines()]
    if any(line.startswith(BULLET_MARKER) for line in lines):
        return _marked_bullets(lines)
    bullets: list[str] = []
    prev_len = 0
    for raw in paragraph.splitlines():
        line = " ".join(raw.split())
        if not line or NON_BULLET_RE.search(line) or _is_label(line):
            prev_len = 0
            continue
        if bullets and prev_len >= WRAPPED_LINE_CHARS:
            bullets[-1] = f"{bullets[-1]} {line}"
        else:
            bullets.append(line)
        prev_len = len(line)
    return [b for b in bullets if len(b) >= MIN_BULLET_CHARS]


def _bullets_from_sections(sections: dict[str, str]) -> list[str]:
    bullets = []
    for name in BULLET_SECTIONS:
        body = sections.get(name, "").split("\n", 1)[-1]
        for paragraph in re.split(r"\n\s*\n", body):
            bullets.extend(b for b in _paragraph_bullets(paragraph) if not LEAVE_RE.search(b))
    return bullets


def _load_pdf(path: Path) -> Document:
    pages = pdf_pages(path)
    layout_pages = pdf_pages(path, layout=True)
    text, layout = "\n".join(pages), "\n".join(layout_pages)
    ranges = dates.find_ranges(layout, section_resolver(layout))
    return Document(
        path, "pdf", text, layout, pages, layout_pages,
        sections=split_sections(text),
        bullets=_bullets_from_sections(split_sections(text)),
        date_summary=dates.summarize(ranges),
        links=pdf_links(path),
        mupdf_pages=pymupdf_pages(path) if load_pymupdf() else [],
    )


def _load_text(path: Path) -> Document:
    try:
        text = normalize_text(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as exc:
        raise InputError(f"텍스트 파일을 읽을 수 없습니다: {path} ({exc})") from exc
    ranges = dates.find_ranges(text, section_resolver(text))
    sections = split_sections(text)
    return Document(path, "text", text, text, [text], [text], sections=sections,
                    bullets=_bullets_from_sections(sections), date_summary=dates.summarize(ranges))


def _load_yaml(root: Path, path: Path) -> Document:
    bank = load_facts(root)
    variant = load_variant(path, bank)
    text = "\n".join(body for body in variant.sections.values() if body.strip())
    spans = variant_job_spans(variant.data, bank)
    summary = {"total_months": dates.total_months(spans), "ranges": [], "gaps": [], "overlaps": [], "leave_months": 0}
    return Document(path, "yaml", text, text, [text], [text], sections=dict(variant.sections),
                    bullets=list(variant.bullets), variant=variant, date_summary=summary)


def load_document(root: Path, path: Path) -> Document:
    require_file(path)
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return _load_pdf(path)
    if suffix in YAML_SUFFIXES:
        return _load_yaml(root, path)
    return _load_text(path)
