"""rules/rules.yaml 평가 (contract 3.7). 모르는 type은 경고만 낸다."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from . import pdfchecks
from .claims import claims, unsupported_numbers_by_page
from .consistency import check_consistency
from .dates import non_standard_dates
from .document import Document
from .family import classify
from .rules_data import load_platforms, load_rules
from .taxonomy import Haystack, Taxonomy, load_taxonomy, load_yaml
from .textio import EMAIL_RE, PHONE_RE, STATED_YEARS_RE, compact, number_tokens
from .sections import split_sections

MB = 1024 * 1024
SHOWN_ITEMS = 10
MIN_CONCEPT_TERM_CHARS = 3  # 키워드 밀도: 2자 이하 약어(AI, UX)는 반복해도 나열이 아니다
YEARS_EN_RE = re.compile(r"\d+\+?\s*years?", re.I)
PERCENT_RE = re.compile(r"\d+(?:\.\d+)?\s*%")
ARROW_PAIR_RE = re.compile(r"\d[\d.,]*\s*\S{0,3}\s*(?:→|➜|->|=>)\s*\d")
LIST_SPLIT_RE = re.compile(r"[,，·/|、;]")
PDF_ONLY = "PDF 전용 검사"


@dataclass
class RuleContext:
    root: Path
    doc: Document
    kind: str
    platform: str | None = None
    max_mb: float | None = None  # --max-mb: 플랫폼 용량 제한 대신 쓸 값
    cache: dict = field(default_factory=dict)

    @property
    def taxonomy(self) -> Taxonomy:
        return load_taxonomy()

    def cached(self, key: str, make):
        if key not in self.cache:
            self.cache[key] = make()
        return self.cache[key]


def _r(status: str, count: int = 0, message: str = "", **details) -> dict:
    return {"status": status, "count": count, "message": message, **({"details": details} if details else {})}


def _pdf_only(ctx: RuleContext) -> dict | None:
    return None if ctx.doc.is_pdf else _r("skipped", message=PDF_ONLY)


def _text_layer(ctx, params):
    if (skip := _pdf_only(ctx)):
        return skip
    minimum = params.get("min_chars_per_page", 0)
    thin = [i + 1 for i, page in enumerate(ctx.doc.pages) if len(page.strip()) < minimum]
    return _r("fail" if thin else "pass", len(thin), f"텍스트 {minimum}자 미만 페이지: {thin[:SHOWN_ITEMS]}" if thin else "모든 페이지에 텍스트 층 있음")


def _max_file_mb(ctx, params):
    platforms = {p["id"]: p for p in load_platforms()}
    platform = platforms.get(ctx.platform or params.get("platform", "default"), {})
    size_mb = ctx.doc.path.stat().st_size / MB
    if ctx.max_mb:
        limit, source = ctx.max_mb, f"--max-mb 지정 (플랫폼 '{platform.get('name', '기본값')}' 제한 {platform.get('max_file_mb') or '미확인'} 대신 사용)"
    else:
        limit, source = params.get("mb") or platform.get("max_file_mb"), platform.get("name", "직접 지정")
    if not limit:
        seen = platform.get("observed_ok_mb")
        note = f" (실제 업로드 성공 {seen}MB)" if seen else ""
        return _r("skipped", message=f"{platform.get('name', '플랫폼')} 용량 제한 미확인, 파일 {size_mb:.1f}MB{note}")
    over = size_mb > limit
    return _r("fail" if over else "pass", int(over), f"{size_mb:.1f}MB / 제한 {limit}MB ({source})", limit_mb=limit, limit_source=source)


def _max_pages(ctx, params):
    if (skip := _pdf_only(ctx)):
        return skip
    pages, limit = len(ctx.doc.pages), params.get("pages", 0)
    return _r("fail" if pages > limit else "pass", int(pages > limit), f"{pages}쪽 / 제한 {limit}쪽")


def _section_present(ctx, params):
    found = set(ctx.doc.section_names())
    missing = [s for s in params.get("sections", []) if s not in found]
    advice = [s for s in params.get("recommended", []) if s not in found]
    msg = (f"인식 실패: {missing}. " if missing else "필수 섹션 모두 인식. ") + (f"권장 누락: {advice}" if advice else "")
    return _r("fail" if missing else "pass", len(missing), msg.strip(), found=sorted(found))


def _contact_policy(ctx, params):
    if ctx.doc.kind == "yaml":
        return _r("skipped", message="연락처는 렌더 때 contact.local.yaml에서 넣는다")
    email, phone = bool(EMAIL_RE.search(ctx.doc.text)), bool(PHONE_RE.search(ctx.doc.text))
    problems = []
    if params.get("email") == "required" and not email:
        problems.append("이메일 없음")
    if params.get("phone") == "forbid" and phone:
        problems.append("전화번호 있음")
    return _r("fail" if problems else "pass", len(problems), ", ".join(problems) or f"이메일 {'있음' if email else '없음'}, 전화번호 {'있음' if phone else '없음'}")


def _injection_patterns(root: Path) -> list[str]:
    return [p for rule in load_rules() if rule["type"] == "forbidden_patterns" for p in (rule.get("params") or {}).get("patterns", [])]


def _hidden(ctx, params):
    if (skip := _pdf_only(ctx)):
        return skip
    result = ctx.cached("hidden", lambda: pdfchecks.find_hidden_text(
        ctx.doc.path, params.get("min_font_pt", 4), params.get("min_contrast", 1.5), _injection_patterns(ctx.root)))
    if result["status"] == "skipped":
        return _r("skipped", message=result["reason"])
    if result["status"] == "ok":
        return _r("pass", 0, "숨김 텍스트 없음", items=[])
    verdict = "fail" if result["status"] == "fail" else "warn"
    where = "; ".join(f"{g['page']}쪽 {g['reason']} {g['count']}개" for g in result["items"][:SHOWN_ITEMS])
    return _r(verdict, result["count"], f"숨김 의심 텍스트 {result['count']}개 ({where}). {result['items'][0]['recommendation']}", items=result["items"])


def _date_format(ctx, params):
    bad = non_standard_dates(ctx.doc.text, params.get("pattern", r"^\d{4}\.\d{2}$"))
    return _r("fail" if bad else "pass", len(bad), f"YYYY.MM이 아닌 표기: {bad[:SHOWN_ITEMS]}" if bad else "날짜 표기 일관")


def classify_doc(ctx: RuleContext) -> dict:
    off = next((r["params"] for r in load_rules() if r["type"] == "family_balance"), {})
    return ctx.cached("classify", lambda: classify(ctx.doc, ctx.taxonomy, off.get("off_target"), off.get("max_share", 0.25)))


def _title_alignment(ctx, params):
    targets, info = set(params.get("target_families", [])), classify_doc(ctx)
    aligned = [info[k] in targets for k in ("headline_family", "recent_family")]
    detail = f"헤드라인 '{info['headline']}'→{info['headline_family']}, 최근 직함 '{info['recent_title']}'→{info['recent_family']}"
    if all(aligned):
        return _r("pass", 0, detail)
    if any(aligned):
        return _r("warn", 1, detail + " (한쪽만 목표 직군)")
    return _r("fail", 2, detail + " (목표 직군으로 정규화되지 않음)")


def _family_balance(ctx, params):
    info = classify_doc(ctx)
    return _r("warn" if info["warnings"] else "pass", len(info["warnings"]), "; ".join(info["warnings"]) or "비목표 직군 신호 비중 낮음")


def _terms_outside_skills(ctx) -> str:
    sections = split_sections(ctx.doc.text) if ctx.doc.is_pdf else ctx.doc.sections
    return "\n".join(body for name, body in sections.items() if name != "skills")


def _keyword_density(ctx, params):
    body = _terms_outside_skills(ctx)
    hay, length = Haystack(body), max(len(body), 1)
    worst, listed = ("", 0.0), 0
    all_terms = {t for c in ctx.taxonomy.concepts for t in ctx.taxonomy.concept_terms(c["id"])}
    for term in all_terms:
        if len(term) >= MIN_CONCEPT_TERM_CHARS and (density := hay.find(term) / length * 1000) > worst[1]:
            worst = (term, density)
    keys = {compact(t) for t in all_terms}
    for line in body.split("\n"):
        listed = max(listed, sum(compact(item) in keys for item in LIST_SPLIT_RE.split(line)))
    limit_d, limit_l = params.get("max_per_1000_chars", 6), params.get("max_list_terms_outside_skills", 8)
    bad = worst[1] > limit_d or listed > limit_l
    return _r("fail" if bad else "pass", int(worst[1] > limit_d) + int(listed > limit_l),
              f"최다 반복 '{worst[0]}' {worst[1]:.1f}/1000자(상한 {limit_d}), 한 줄 최대 용어 나열 {listed}개(상한 {limit_l})")


def _quantified_ratio(ctx, params):
    bullets = ctx.doc.bullets
    if not bullets:
        return _r("skipped", message="경력 bullet을 찾지 못함")
    ratio = sum(bool(number_tokens(b)) for b in bullets) / len(bullets)
    low = ratio < params.get("min_ratio", 0.5)
    return _r("fail" if low else "pass", int(low), f"숫자가 있는 bullet {ratio:.0%} ({len(bullets)}개 중), 기준 {params.get('min_ratio', 0.5):.0%}")


def _forbidden(ctx, params):
    hits = [p for p in params.get("patterns", []) if re.search(p, ctx.doc.text)]
    return _r("fail" if hits else "pass", len(hits), f"금지 패턴 발견: {hits}" if hits else "지시문·인젝션 패턴 없음")


def _consistency(ctx, params):
    result = check_consistency(ctx.root, [ctx.doc], params.get("fields"))
    msg = "; ".join(f"{i['field']}: '{i['found']}' (정본 '{i['canonical']}')" for i in result["issues"])
    return _r("fail" if result["issues"] else "pass", len(result["issues"]), msg or "정본과 같은 표기", issues=result["issues"])


def _edited_portfolio_pages(root: Path, page_count: int) -> set[int]:
    """하네스가 바꿔 끼우는 포트폴리오 쪽 (figma_map.yaml portfolio.replaces). 지도가 없으면 모든 쪽."""
    path = root / "profile" / "figma_map.yaml"
    replaces = (load_yaml(path).get("portfolio") or {}).get("replaces") or {} if path.is_file() else {}
    return {int(page) for page in replaces.values()} or set(range(1, page_count + 1))


def _portfolio_claims(ctx) -> dict:
    """포트폴리오는 하네스가 고치는 쪽만 실패로 본다. 나머지 쪽의 숫자(목업·인용 통계)는 경고로 알린다."""
    found = unsupported_numbers_by_page(ctx.root, ctx.doc.mupdf_pages or ctx.doc.pages)
    edited = _edited_portfolio_pages(ctx.root, len(ctx.doc.pages))
    hard = {page: nums for page, nums in found.items() if page in edited}
    soft = {page: nums for page, nums in found.items() if page not in edited}
    shown = "; ".join(f"{page}쪽 {nums[:SHOWN_ITEMS]}" for page, nums in sorted((hard or soft).items())[:SHOWN_ITEMS])
    if hard:
        return _r("fail", sum(map(len, hard.values())), f"하네스가 고치는 쪽의 사실 은행 밖 숫자: {shown}", pages=hard)
    if soft:
        return _r("warn", sum(map(len, soft.values())), f"기존 슬라이드의 사실 은행 밖 숫자 (목업·인용 통계일 수 있음, 확인 권장): {shown}", pages=soft)
    return _r("pass", message="숫자 모두 근거 있음(loose)")


def _claims_supported(ctx, params):
    strict = params.get("mode") == "strict" or ctx.doc.kind == "yaml"
    if ctx.kind == "portfolio" and ctx.doc.is_pdf and not strict:
        return _portfolio_claims(ctx)
    result = claims(ctx.root, ctx.doc, strict=strict)
    bad = [i for i in result["issues"] if i["type"] == "unsupported_number"]
    return _r("fail" if bad else "pass", len(bad), f"사실 은행 밖 숫자 {[i['number'] for i in bad][:SHOWN_ITEMS]}" if bad else f"숫자 모두 근거 있음({result['mode']})")


def _reading_order(ctx, params):
    if (skip := _pdf_only(ctx)):
        return skip
    result = ctx.cached("reading", lambda: pdfchecks.find_reading_order_issues(ctx.doc.path, ctx.doc.pages))
    if result["status"] == "skipped":
        return _r("skipped", message=result["reason"])
    return _r("fail" if result["count"] else "pass", result["count"], f"추출 순서가 기하 순서와 다른 숫자 줄 {result['count']}개 (숫자가 바뀐 줄 {result['digit_changed']}개)" if result["count"] else "읽기 순서 이상 없음", items=result["items"])


def _extractor_agreement(ctx, params):
    if (skip := _pdf_only(ctx)):
        return skip
    minimum = params.get("min_share", 0.95)
    result = ctx.cached("extractor", lambda: pdfchecks.find_extractor_disagreement(ctx.doc.path, ctx.doc.pages, minimum))
    if result["status"] == "skipped":
        return _r("skipped", message=result["reason"])
    if not result["count"]:
        return _r("pass", 0, f"모든 쪽에서 MuPDF 단어의 {minimum:.0%} 이상이 Poppler에도 온전히 나옴 (최저 {result['worst_share']:.0%})")
    worst = "; ".join(f"{p['page']}쪽 {p['share']:.0%} {p['examples']}" for p in result["pages"])
    return _r("warn", result["count"], f"추출기마다 단어가 다르게 나오는 쪽 {result['count']}개: {worst}", pages=result["pages"])


def _first_page_signals(ctx, params):
    pages = params.get("portfolio_pages", 2) if ctx.kind == "portfolio" else 1
    first = "\n".join(ctx.doc.pages[:pages]) if ctx.doc.is_pdf else ctx.doc.text
    hay, tax = Haystack(first), ctx.taxonomy
    has = {
        "title": any(hay.has(t) for f in tax.families if f.get("target") for t in f.get("titles", [])),
        "years": bool(STATED_YEARS_RE.search(first) or YEARS_EN_RE.search(first)),
        "metric": bool(PERCENT_RE.search(first) or ARROW_PAIR_RE.search(first)),
    }
    missing = [k for k in params.get("must_include", []) if not has.get(k)]
    return _r("fail" if missing else "pass", len(missing), f"첫 {pages}쪽에 없음: {missing}" if missing else f"첫 {pages}쪽에 직함·연차·성과 숫자 있음", present=has)


HANDLERS = {
    "text_layer": _text_layer, "max_file_mb": _max_file_mb, "max_pages": _max_pages,
    "section_present": _section_present, "contact_policy": _contact_policy, "hidden_text_none": _hidden,
    "date_format": _date_format, "title_alignment": _title_alignment, "family_balance": _family_balance,
    "keyword_density": _keyword_density, "quantified_ratio": _quantified_ratio, "forbidden_patterns": _forbidden,
    "consistency": _consistency, "claims_supported": _claims_supported, "reading_order": _reading_order,
    "first_page_signals": _first_page_signals, "extractor_agreement": _extractor_agreement,
}


def evaluate_rules(ctx: RuleContext) -> list[dict]:
    results = []
    for rule in load_rules():
        if ctx.kind not in rule.get("applies_to", []):
            continue
        base = {"id": rule["id"], "title": rule.get("title", ""), "severity": rule.get("severity", "low"), "type": rule["type"]}
        handler = HANDLERS.get(rule["type"])
        if handler is None:
            results.append({**base, "status": "warn", "count": 0, "message": f"unsupported rule type: {rule['type']}"})
            continue
        results.append({**base, **handler(ctx, rule.get("params") or {})})
    return results


def has_high_failure(results: list[dict]) -> bool:
    return any(r["severity"] == "high" and r["status"] == "fail" for r in results)
