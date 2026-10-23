"""report.md (한국어) 렌더링. 입력은 runner.run_all의 결과(가림 처리 후)."""
from __future__ import annotations

PRIORITY_COUNT = 5
STATUS_LABEL = {"pass": "통과", "fail": "실패", "warn": "주의", "skipped": "건너뜀"}
DISCLAIMER = "이 점수는 휴리스틱입니다. 합격 확률이 아닙니다. 서류를 기계가 얼마나 근거 있게 읽는지의 근사치입니다."


def _rule_lines(rules: list[dict]) -> list[str]:
    return [f"- [{STATUS_LABEL.get(r['status'], r['status'])}] {r['id']} ({r['severity']}) {r['title']}: {r['message']}"
            for r in rules if r["status"] != "pass"] or ["- 모든 규칙 통과"]


def _summary(b: dict) -> list[str]:
    s, a = b["score"], b["audit"]
    high = [r["id"] for r in a["rules"] if r["severity"] == "high" and r["status"] == "fail"]
    return [
        "## 요약", "",
        f"- 공고: {b['jd']['company']} / {b['jd']['title']} (직군 {b['jd']['family']}, 최소 연차 {b['jd']['years_min']})",
        f"- 이력서: {b['resume']}" + (f", 포트폴리오: {b['portfolio']}" if b["portfolio"] else ""),
        f"- 매칭 점수 {s['total']}점, 구간 '{s['band']}' (감점 {s['penalty_points']}점)",
        f"- high 규칙 실패: {', '.join(high) or '없음'}",
        f"- 진실성 검사: {'통과' if b['claims']['ok'] else '근거 없는 항목 ' + str(b['claims']['high']) + '건'}",
        f"- {DISCLAIMER}", "",
    ]


def _parse_section(b: dict) -> list[str]:
    a, d = b["audit"], b["audit"]["dates"]
    lines = ["## 파싱 감사", "",
             f"- 형식 {a['format']}, {a['pages']}쪽, 인식한 섹션: {', '.join(a['sections']) or '없음'}",
             f"- 총 경력 {d.get('total_months', 0)}개월 (휴직 제외), 공백 {len(d.get('gaps', []))}건, 겹침 {len(d.get('overlaps', []))}건",
             f"- 연락처: 이메일 {'있음' if a['contact']['email'] else '없음'}, 전화번호 {'있음' if a['contact']['phone'] else '없음'}",
             f"- 한글 무결성: {'이상 없음' if a['hangul_integrity']['ok'] else a['hangul_integrity']}", "", "### 규칙 결과 (통과 제외)", ""]
    lines += _rule_lines(a["rules"])
    if b.get("portfolio_audit"):
        lines += ["", "### 포트폴리오", ""] + _rule_lines(b["portfolio_audit"]["rules"])
    return lines + [""]


def _family_section(b: dict) -> list[str]:
    f = b["family"]
    top = ", ".join(f"{r['id']} {r['share']:.0%}" for r in f["ranking"][:3] if r["score"])
    lines = ["## 직군 분류", "",
             f"- 헤드라인: {f['headline']} → {f['headline_family']}", f"- 최근 직함: {f['recent_title']} → {f['recent_family']}",
             f"- 신호 분포 상위: {top}", f"- 예측 1순위: {f['predicted']}"]
    return lines + [f"- 주의: {w}" for w in f["warnings"]] + [""]


def _match_section(b: dict) -> list[str]:
    c = b["score"]["components"]
    lines = ["## 공고 매칭", ""]
    for name, label in (("parse", "파싱"), ("title", "직함"), ("required", "필수"), ("preferred", "우대"), ("seniority", "연차"), ("impact", "성과")):
        lines.append(f"- {label}: {c[name]['score']} / {c[name]['max']}")
    lines += ["", "### 근거 없는 갭 (쓰지 않는다)"]
    nogap = [g for g in b["score"]["gaps"] if not g["evidence_facts"]]
    lines += [f"- {g['concept']} ({g['importance']}): {g['suggestion']}" for g in nogap] or ["- 없음"]
    lines += ["", "### 근거가 있어 보완할 수 있는 갭"]
    withev = b["score"]["suggestions"]
    lines += [f"- {s['concept']}: {', '.join(s['fact_ids'])} — {s['hint']}" for s in withev] or ["- 없음"]
    return lines + [""]


def _claims_section(b: dict) -> list[str]:
    cl = b["claims"]
    lines = ["## 진실성 검사", "", f"- 모드 {cl['mode']}, high {cl['high']}건, 주의 {cl['warnings']}건"]
    for i in cl["issues"]:
        detail = i.get("number") or i.get("fact") or i.get("skill") or i.get("link") or i.get("pattern") or i.get("ref") or i.get("title", "")
        where = f" ({i['path']})" if i.get("path") else ""
        note = f" — {i['note']}" if i.get("note") else ""
        lines.append(f"- [{i['severity']}] {i['type']}: {detail}{where}{note}")
    return lines + [""]


def _consistency_section(b: dict) -> list[str]:
    c = b["consistency"]
    lines = ["## 일관성", ""]
    lines += [f"- {i['file']}: {i['field']} '{i['found']}' → 정본 '{i['canonical']}'" for i in c["issues"]] or ["- 정본과 다른 표기 없음"]
    return lines + [""]


def priority_fixes(b: dict) -> list[str]:
    fixes = [f"{r['id']}: {r['message']}" for r in b["audit"]["rules"] if r["severity"] == "high" and r["status"] == "fail"]
    fixes += [f"근거 없는 항목 정리: {i['type']} {i.get('number') or i.get('fact') or i.get('skill') or ''}" for i in b["claims"]["issues"] if i["severity"] == "high"]
    gaps = b["score"]["gaps"]
    fixes += [f"필수 '{g['concept']}'를 사실 {', '.join(g['evidence_facts'][:2])} 근거로 경력 문장에 반영" for g in gaps if g["importance"] == "required" and g["evidence_facts"]]
    fixes += [f"일관성: {i['field']} '{i['found']}' → '{i['canonical']}'" for i in b["consistency"]["issues"]]
    fixes += [f"{r['id']}: {r['message']}" for r in b["audit"]["rules"] if r["status"] in ("fail", "warn") and r["severity"] != "high"]
    fixes += [f"우대 '{g['concept']}'를 사실 {', '.join(g['evidence_facts'][:2])} 근거로 반영" for g in gaps if g["importance"] == "preferred" and g["evidence_facts"]]
    fixes += [f"필수 '{g['concept']}': 사실 은행에 근거 없음, 쓰지 말고 지원 전 사실 확인" for g in gaps if g["importance"] == "required" and not g["evidence_facts"]]
    return fixes[:PRIORITY_COUNT]


def render_report(bundle: dict) -> str:
    lines = [f"# 서류 심사 시뮬레이션 보고서: {bundle['jd']['company']}", ""]
    for part in (_summary, _parse_section, _family_section, _match_section, _claims_section, _consistency_section):
        lines += part(bundle)
    lines += ["## 우선 수정 5개", ""]
    lines += [f"{n}. {text}" for n, text in enumerate(priority_fixes(bundle), 1)] or ["수정할 항목이 없습니다."]
    return "\n".join(lines) + "\n"
