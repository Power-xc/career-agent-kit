"""PDF(또는 서류) 감사: 추출 텍스트 저장, 섹션·날짜·연락처·링크·숨김·읽기 순서·규칙 결과."""
from __future__ import annotations

import json
from pathlib import Path

from .document import Document, load_document
from .pdfchecks import hangul_integrity
from .rules import RuleContext, evaluate_rules, has_high_failure
from .textio import EMAIL_RE, PHONE_RE, redact, redact_obj

PAGE_BREAK = "\n\n===== page {n} =====\n\n"


def audit_document(root: Path, doc: Document, kind: str, platform: str | None = None, max_mb: float | None = None) -> dict:
    ctx = RuleContext(root, doc, kind, platform, max_mb)
    rules = evaluate_rules(ctx)
    hidden = ctx.cache.get("hidden", {"status": "skipped", "count": 0, "items": []})
    reading = ctx.cache.get("reading", {"status": "skipped", "count": 0, "items": []})
    return {
        "file": doc.path.name, "kind": kind, "format": doc.kind,
        "size_mb": round(doc.path.stat().st_size / (1024 * 1024), 2),
        "pages": len(doc.pages), "page_characters": [len(p.strip()) for p in doc.pages],
        "sections": doc.section_names(),
        "dates": doc.date_summary,
        "contact": {"email": bool(EMAIL_RE.search(doc.text)), "phone": bool(PHONE_RE.search(doc.text))},
        "links": doc.links,
        "hidden_text": hidden, "reading_order": reading,
        "hangul_integrity": hangul_integrity(doc.text),
        "rules": rules, "high_failure": has_high_failure(rules),
    }


def write_text_outputs(out: Path, named_pages: tuple[tuple[str, list[str]], ...]) -> list[str]:
    """쪽별 텍스트를 이메일·전화번호를 가려 저장한다."""
    out.mkdir(parents=True, exist_ok=True)
    for name, pages in named_pages:
        body = "".join(PAGE_BREAK.format(n=i + 1) + redact(p) for i, p in enumerate(pages))
        (out / name).write_text(body.lstrip("\n"), encoding="utf-8")
    return [name for name, _ in named_pages]


def mupdf_text_pages(doc: Document) -> list[str]:
    """MuPDF 추출 (PDF가 아니거나 PyMuPDF가 없으면 기본 추출과 같다)."""
    return doc.mupdf_pages or doc.pages


def write_audit_outputs(out: Path, doc: Document, result: dict) -> list[str]:
    """가림 처리한 추출 텍스트(default·layout)와 audit.json 저장."""
    written = write_text_outputs(out, (("text_default.txt", doc.pages), ("text_layout.txt", doc.layout_pages)))
    (out / "audit.json").write_text(json.dumps(redact_obj(result), ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return written + ["audit.json"]


def run_audit(root: Path, path: Path, kind: str, platform: str | None, out: Path | None, max_mb: float | None = None) -> dict:
    doc = load_document(root, path)
    result = audit_document(root, doc, kind, platform, max_mb)
    if out:
        result["written"] = write_audit_outputs(out, doc, result)
    return result
