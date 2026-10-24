"""규칙 기반 매칭 점수 (휴리스틱, 합격 확률 아님). 계수는 rules/scoring.yaml."""
from __future__ import annotations

from pathlib import Path

from .document import Document
from .extract import InputError
from .facts import load_facts
from .gaps import concept_gap_rows
from .jd import preferred_concepts, required_concepts
from .rules import ARROW_PAIR_RE, RuleContext, classify_doc, evaluate_rules
from .rules_data import load_rules, load_scoring
from .taxonomy import Haystack, Taxonomy, load_taxonomy
from .textio import STATED_YEARS_RE, number_tokens

SEVERITY_SHARE = {"high": 3, "med": 2, "low": 1}  # parse 점수에서 규칙 비중
PENALTY_EXEMPT_PREFIXES = ("R-PARSE", "R-CLASS-01", "R-IMPACT")  # 다른 구성 점수에 이미 반영된 규칙
SUMMARY_SECTIONS = ("header", "summary", "strengths", "motivation")
EXPERIENCE_SECTIONS = ("experience", "projects")
MONTHS_PER_YEAR = 12


def _section_text(doc: Document, names) -> str:
    return "\n".join(doc.sections.get(n, "") for n in names)


def concept_coverage(doc: Document, taxonomy: Taxonomy, concept_id: str, weights: dict) -> tuple[float, str]:
    """개념이 서류 어디에 나오는지에 따른 커버리지 (값, 위치)."""
    def found(text: str, cid: str) -> bool:
        hay = Haystack(text)
        return any(hay.has(t) for t in taxonomy.concept_terms(cid))
    if found(_section_text(doc, EXPERIENCE_SECTIONS), concept_id):
        return weights["in_experience"], "experience"
    if found(_section_text(doc, SUMMARY_SECTIONS), concept_id):
        return weights["in_summary"], "summary"
    if found(doc.text, concept_id):
        return weights["in_skills_only"], "skills_or_other"
    related = taxonomy.concept_by_id.get(concept_id, {}).get("related", [])
    if any(found(doc.text, r) for r in related):
        return weights["related_only"], "related"
    return 0.0, "missing"


def _coverage_block(doc, taxonomy, concepts: list[str], max_points: float, weights: dict) -> dict:
    rows = {c: concept_coverage(doc, taxonomy, c, weights) for c in concepts}
    mean = sum(v for v, _ in rows.values()) / len(rows) if rows else 1.0
    return {
        "score": round(max_points * mean, 1), "max": max_points,
        "covered": [c for c, (v, _) in rows.items() if v >= weights["in_skills_only"]],
        "missing": [c for c, (v, _) in rows.items() if v < weights["in_skills_only"]],
        "where": {c: where for c, (_, where) in rows.items()},
    }


def _parse_block(results: list[dict], max_points: float) -> dict:
    parse = [r for r in results if r["id"].startswith("R-PARSE") and r["status"] != "skipped"]
    total = sum(SEVERITY_SHARE[r["severity"]] for r in parse) or 1
    lost = sum(SEVERITY_SHARE[r["severity"]] * {"fail": 1, "warn": 0.5}.get(r["status"], 0) for r in parse)
    notes = [f"{r['id']}: {r['message']}" for r in parse if r["status"] in ("fail", "warn")]
    return {"score": round(max_points * (1 - lost / total), 1), "max": max_points, "notes": notes}


def _family_credit(family: str | None, jd_family: str | None, taxonomy: Taxonomy, off_target: list[str], coef: dict) -> float:
    if family is None:
        return coef["off_target"]
    if family == jd_family:
        return coef["exact_family"]
    if jd_family and taxonomy.group_of(family) != taxonomy.group_of(jd_family):
        return coef["cross_group"]  # 개발자 서류로 디자이너 공고에 지원하는 식의 직군 묶음 불일치
    if taxonomy.family_by_id.get(family, {}).get("target"):
        return coef["target_family"]
    return coef["off_target"] if family in off_target else coef["adjacent_family"]


def _family_weights(scoring: dict, taxonomy: Taxonomy, family_id: str | None) -> dict:
    """직군 묶음별 구성 점수 배분 (scoring.yaml family_weights). 정의가 없으면 기본 weights."""
    override = scoring.get("family_weights", {}).get(taxonomy.group_of(family_id) or "")
    weights = {**scoring["weights"], **(override or {})}
    if sum(weights.values()) != sum(scoring["weights"].values()):
        raise InputError(f"rules/scoring.yaml family_weights 합이 weights 합과 다릅니다: {taxonomy.group_of(family_id)}")
    return weights


def _family_evidence(doc: Document, taxonomy: Taxonomy, family_id: str | None) -> list[dict]:
    """직군에서 결정적인 근거(포트폴리오, GitHub, 캠페인 수치 등)가 서류에 있는지. 점수에는 넣지 않고 알린다."""
    hay = Haystack(doc.text)
    spec = taxonomy.family_by_id.get(family_id or "", {}).get("decisive_evidence", [])
    return [{"label": e["label"], "found": [t for t in e["terms"] if hay.has(t)][:3]} for e in spec]


def _title_block(ctx: RuleContext, jd: dict, scoring: dict, max_points: float) -> dict:
    info, taxonomy = classify_doc(ctx), ctx.taxonomy
    off = next((r["params"].get("off_target", []) for r in load_rules() if r["type"] == "family_balance"), [])
    candidates = [f for f in (info["headline_family"], info["recent_family"]) if f] or [info["predicted"]]
    credit = max(_family_credit(f, jd["family"], taxonomy, off, scoring["title"]) for f in candidates)
    notes = [f"공고 직군 {jd['family']}, 서류 헤드라인 {info['headline_family']}, 최근 직함 {info['recent_family']}"]
    return {"score": round(max_points * credit, 1), "max": max_points, "jd_family": jd["family"],
            "doc_families": candidates, "notes": notes}


def document_years(root: Path, doc: Document) -> float:
    """서류의 총 경력 연수: 날짜 범위 합 > 문장에 쓴 경력 N년 > 사실 은행 years_stated."""
    if doc.total_months:
        return doc.total_months / MONTHS_PER_YEAR
    stated = STATED_YEARS_RE.findall(doc.text)
    return float(stated[0]) if stated else float(load_facts(root).years_stated())


def _seniority_block(root: Path, doc: Document, jd: dict, scoring: dict, max_points: float) -> dict:
    years, minimum = document_years(root, doc), jd["years_min"]
    if minimum is None or years >= minimum:
        credit = 1.0
    else:
        credit = max(0.0, 1 - (minimum - years) * scoring["seniority"]["partial_per_missing_year"])
    return {"score": round(max_points * credit, 1), "max": max_points, "years": round(years, 1), "years_min": minimum}


def _impact_block(doc: Document, scoring: dict, max_points: float) -> dict:
    bullets, cfg = doc.bullets, scoring["impact"]
    quantified = sum(bool(number_tokens(b)) for b in bullets)
    ratio = quantified / len(bullets) if bullets else 0.0
    bonus = cfg["before_after_bonus"] if any(ARROW_PAIR_RE.search(b) for b in bullets) else 0.0
    credit = min(1.0, ratio / cfg["min_quantified_ratio_for_full"] + bonus)
    return {"score": round(max_points * credit, 1), "max": max_points, "quantified_ratio": round(ratio, 2),
            "bullets": len(bullets), "before_after": bool(bonus)}


def _penalties(results: list[dict], scoring: dict, prefix: str = "") -> list[dict]:
    points, warn_factor = scoring["penalties"], scoring["warn_penalty_factor"]
    return [
        {"rule_id": prefix + r["id"], "points": round(points[r["severity"]] * (1 if r["status"] == "fail" else warn_factor), 1),
         "reason": r["message"]}
        for r in results
        if r["status"] in ("fail", "warn") and not r["id"].startswith(PENALTY_EXEMPT_PREFIXES)
    ]


def _suggestions(root: Path, gaps: list[dict]) -> list[dict]:
    facts = load_facts(root).facts
    return [
        {"concept": g["concept"], "fact_ids": g["evidence_facts"][:3],
         "hint": "이 사실을 경력 문장 안에서 풀어 쓴다: " + facts[g["evidence_facts"][0]]["ko"]}
        for g in gaps if g["evidence_facts"]
    ]


def band_for(total: float, scoring: dict) -> str:
    return next((b["label"] for b in sorted(scoring["bands"], key=lambda b: -b["min"]) if total >= b["min"]), "")


def score_resume(root: Path, jd: dict, doc: Document, resume_audit: dict | None = None,
                 portfolio_audit: dict | None = None) -> dict:
    scoring, taxonomy = load_scoring(), load_taxonomy()
    ctx = RuleContext(root, doc, "resume")
    family_id = jd["family"] or classify_doc(ctx)["predicted"]  # 공고 직군을 모르면 서류에서 예측한 직군
    w, cov = _family_weights(scoring, taxonomy, family_id), scoring["coverage"]
    results = resume_audit["rules"] if resume_audit else evaluate_rules(ctx)
    required, preferred = required_concepts(jd), preferred_concepts(jd)
    components = {
        "parse": _parse_block(results, w["parse"]),
        "title": _title_block(ctx, jd, scoring, w["title"]),
        "required": _coverage_block(doc, taxonomy, required, w["required"], cov),
        "preferred": _coverage_block(doc, taxonomy, preferred, w["preferred"], cov),
        "seniority": _seniority_block(root, doc, jd, scoring, w["seniority"]),
        "impact": _impact_block(doc, scoring, w["impact"]),
    }
    use_portfolio = portfolio_audit and taxonomy.portfolio_expected(family_id)  # 포트폴리오가 기대되지 않는 직군은 감점하지 않는다
    penalties = _penalties(results, scoring) + (_penalties(portfolio_audit["rules"], scoring, "portfolio:") if use_portfolio else [])
    deduction = min(scoring["penalty_cap"], sum(p["points"] for p in penalties))
    total = max(0, min(100, round(sum(c["score"] for c in components.values()) - deduction)))
    weak = {c for block in ("required", "preferred") for c, where in components[block]["where"].items() if where in ("missing", "related", "skills_or_other")}
    gaps = [g for g in concept_gap_rows(root, taxonomy, jd) if g["concept"] in weak]
    for g in gaps:
        g["where"] = components[g["importance"]]["where"][g["concept"]]
    return {"total": total, "band": band_for(total, scoring), "penalty_points": deduction, "components": components,
            "penalties": penalties, "gaps": gaps,
            "family": {"id": family_id, "group": taxonomy.group_of(family_id), "weights": w,
                       "portfolio_expected": taxonomy.portfolio_expected(family_id),
                       "portfolio_penalties_applied": bool(use_portfolio)},
            "family_evidence": _family_evidence(doc, taxonomy, family_id), "suggestions": _suggestions(root, gaps),
            "note": "휴리스틱 점수입니다. 합격 확률이 아닙니다."}
