"""run / corpus: 여러 검사를 묶어 한 번에 돌린다."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from .audit import audit_document, mupdf_text_pages, write_text_outputs
from .claims import claims
from .consistency import check_consistency
from .document import Document, load_document
from .jd import parse_jd
from .report import render_report
from .rules import classify_doc, RuleContext
from .score import score_resume
from .taxonomy import load_taxonomy
from .textio import redact_obj

JD_GLOB = "**/*.md"
JD_SKIP_NAMES = {"README.md"}
SUMMARY_MESSAGE_CHARS = 160


def run_all(root: Path, jd_path: Path, resume_path: Path, portfolio_path: Path | None = None,
            max_mb: float | None = None, out: Path | None = None) -> dict:
    taxonomy = load_taxonomy()
    jd = parse_jd(taxonomy, jd_path)
    resume = load_document(root, resume_path)
    portfolio = load_document(root, portfolio_path) if portfolio_path else None
    resume_audit = audit_document(root, resume, "resume", max_mb=max_mb)
    portfolio_audit = audit_document(root, portfolio, "portfolio", max_mb=max_mb) if portfolio else None
    score = score_resume(root, jd, resume, resume_audit, portfolio_audit)
    docs = [d for d in (resume, portfolio) if d]
    family = classify_doc(RuleContext(root, resume, "resume"))
    texts = write_text_outputs(out, (("text_default.txt", resume.pages), ("text_mupdf.txt", mupdf_text_pages(resume)))) if out else []
    return {"texts": texts,
        "jd": {k: jd[k] for k in ("file", "company", "title", "family", "years_min", "language", "concepts")},
        "resume": resume_path.name, "portfolio": portfolio_path.name if portfolio_path else None,
        "audit": resume_audit, "portfolio_audit": portfolio_audit, "family": family,
        "claims": claims(root, resume, strict=True), "consistency": check_consistency(root, docs),
        "score": score,
    }


def write_run(out: Path, bundle: dict) -> list[str]:
    out.mkdir(parents=True, exist_ok=True)
    safe = redact_obj(bundle)
    (out / "report.json").write_text(json.dumps(safe, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    (out / "report.md").write_text(render_report(safe), encoding="utf-8")
    return ["report.md", "report.json"]


def run_exit_code(bundle: dict) -> int:
    """이력서 또는 포트폴리오 감사에 high 실패가 있거나 진실성 검사가 실패하면 1."""
    portfolio = bundle.get("portfolio_audit")
    return 1 if bundle["audit"]["high_failure"] or (portfolio and portfolio["high_failure"]) or not bundle["claims"]["ok"] else 0


def _short(message: str) -> str:
    return message if len(message) <= SUMMARY_MESSAGE_CHARS else message[:SUMMARY_MESSAGE_CHARS - 1] + "…"


def _rule_summary(label: str, audit: dict) -> list[str]:
    return [f"  [{r['status']}] {label}{r['id']} ({r['severity']}): {_short(r['message'])}" for r in audit["rules"] if r["status"] in ("fail", "warn")]


def render_summary(bundle: dict) -> str:
    """사람이 읽는 짧은 요약: 점수, 실패·주의 규칙, 출력 경로. 전체 내용은 파일과 --json에만 둔다."""
    score = bundle["score"]
    lines = [f"점수 {score['total']}점 ({score['band']}), 감점 {score['penalty_points']}점. 휴리스틱이며 합격 확률이 아닙니다.",
             f"진실성 검사: {'통과' if bundle['claims']['ok'] else '근거 없는 항목 ' + str(bundle['claims']['high']) + '건'}"]
    flagged = _rule_summary("", bundle["audit"]) + (_rule_summary("포트폴리오 ", bundle["portfolio_audit"]) if bundle.get("portfolio_audit") else [])
    lines += ["실패·주의 규칙:"] + (flagged or ["  없음"])
    lines += ["출력: " + ", ".join(bundle.get("written", []) + bundle.get("texts", []))]
    return "\n".join(lines)


def run_corpus(root: Path, jd_dir: Path, resume_path: Path) -> dict:
    taxonomy = load_taxonomy()
    resume = load_document(root, resume_path)
    resume_audit = audit_document(root, resume, "resume")
    files = sorted(p for p in jd_dir.glob(JD_GLOB) if p.name not in JD_SKIP_NAMES)
    jobs, missing = [], Counter()
    for path in files:
        jd = parse_jd(taxonomy, path)
        result = score_resume(root, jd, resume, resume_audit)
        absent = result["components"]["required"]["missing"]
        missing.update(absent)
        jobs.append({"file": str(path.relative_to(jd_dir)), "company": jd["company"], "title": jd["title"],
                     "total": result["total"], "band": result["band"], "missing_required": absent})
    jobs.sort(key=lambda j: -j["total"])
    return {"jd_dir": str(jd_dir), "resume": resume_path.name, "count": len(jobs), "jobs": jobs,
            "frequent_missing": [{"concept": c, "jobs": n} for c, n in missing.most_common()]}
