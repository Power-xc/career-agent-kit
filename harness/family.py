"""직군 신호 분포, 예측 순위, 헤드라인·최근 직함 정규화."""
from __future__ import annotations

import re
from dataclasses import dataclass

from .document import Document
from .rules_data import load_scoring
from .taxonomy import Haystack, Taxonomy

HEADLINE_SCAN_LINES = 12
TITLE_MAX_CHARS = 60
TOP_SIGNALS_SHOWN = 8


@dataclass
class TitleScan:
    headline: str | None
    headline_family: str | None
    recent: str | None
    recent_family: str | None


def _title_candidates(lines: list[str], taxonomy: Taxonomy) -> list[tuple[str, str]]:
    found = []
    for line in lines:
        text = line.strip(" -·|•")
        if 2 <= len(text) <= TITLE_MAX_CHARS and not re.search(r"\d{4}", text):
            family = taxonomy.normalize_title(text)
            if family:
                found.append((text, family))
    return found


def scan_titles(doc: Document, taxonomy: Taxonomy) -> TitleScan:
    """헤드라인(문서 맨 위 직함 줄)과 최근 경력 직함을 직군으로 정규화."""
    if doc.variant:
        header = doc.variant.data.get("header") or {}
        blocks = doc.variant.data.get("experience") or []
        recent = next((b.get("title_display") for b in blocks if b.get("title_display")), None)
        headline = header.get("title")
        return TitleScan(headline, taxonomy.normalize_title(headline or ""), recent, taxonomy.normalize_title(recent or ""))
    head = _title_candidates(doc.text.split("\n")[:HEADLINE_SCAN_LINES], taxonomy)
    experience = doc.sections.get("experience") or doc.text
    recent = _title_candidates(experience.split("\n")[1:], taxonomy)
    return TitleScan(*(head[0] if head else (None, None)), *(recent[0] if recent else (None, None)))


def family_distribution(doc_text: str, taxonomy: Taxonomy) -> list[dict]:
    """직군별 신호 점수와 비중(0~1). 점수 = 신호 용어 등장 횟수 합 + 직군 core_skills 개념 수 x 가중."""
    haystack = Haystack(doc_text)
    skill_weight = load_scoring()["classification"]["core_skill_weight"]
    needed = {c for f in taxonomy.families for c in f.get("core_skills", [])}
    found = {c for c in needed if any(haystack.has(t) for t in taxonomy.concept_terms(c))}
    rows = []
    for family in taxonomy.families:
        hits = {s: haystack.find(s) for s in family.get("signals", [])}
        hits = {s: n for s, n in hits.items() if n}
        skills = [c for c in family.get("core_skills", []) if c in found]
        rows.append({"id": family["id"], "target": bool(family.get("target")),
                     "score": sum(hits.values()) + skill_weight * len(skills),
                     "signals": dict(sorted(hits.items(), key=lambda kv: -kv[1])[:TOP_SIGNALS_SHOWN])})
    total = sum(r["score"] for r in rows) or 1
    for row in rows:
        row["share"] = round(row["score"] / total, 3)
    return rows


def classify(doc: Document, taxonomy: Taxonomy, off_target: list[str] | None = None, max_share: float = 0.25) -> dict:
    titles = scan_titles(doc, taxonomy)
    rows = family_distribution(doc.text, taxonomy)
    for family_id in (titles.headline_family, titles.recent_family):
        row = next((r for r in rows if r["id"] == family_id), None)
        if row:
            row["score"] += load_scoring()["classification"]["title_bonus"]
    total = sum(r["score"] for r in rows) or 1
    for row in rows:
        row["share"] = round(row["score"] / total, 3)
    ranking = sorted(rows, key=lambda r: (-r["score"], not r["target"], r["id"]))
    own = {titles.headline_family, titles.recent_family}  # 본인이 내건 직군은 비목표로 보지 않는다 (예: 그래픽 디자이너 지원자)
    warnings = [
        f"비목표 직군 신호 비중이 높습니다: {r['id']} {r['share']:.0%}"
        for r in ranking if r["id"] in (off_target or []) and r["share"] > max_share
        and not (r["id"] in own and r["target"])
    ]
    return {
        "headline": titles.headline, "headline_family": titles.headline_family,
        "recent_title": titles.recent, "recent_family": titles.recent_family,
        "ranking": ranking, "predicted": ranking[0]["id"] if ranking and ranking[0]["score"] else None,
        "warnings": warnings,
    }


def infer_family(text: str, taxonomy: Taxonomy) -> str | None:
    """제목으로 직군을 못 정할 때 본문(공고 업무·자격 요건) 신호로 가장 가까운 직군 id. 근거가 약하면 None."""
    rows = family_distribution(text, taxonomy)
    best = max(rows, key=lambda r: (r["score"], r["target"]), default=None)
    return best["id"] if best and best["score"] >= load_scoring()["classification"]["jd_fallback_min_score"] else None
