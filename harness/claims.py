"""진실성 검사: 사실 은행 밖 숫자, 없는 fact id, 확인 필요 사실, 비공개 링크, 금지 패턴."""
from __future__ import annotations

import re
from pathlib import Path

from .document import Document
from .facts import FactBank, load_facts
from .rules_data import load_rules
from .textio import NumberToken, number_tokens, tokens_of_all

HIGH, WARN = "high", "warn"
SNIPPET_CHARS = 80


def _snippet(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()[:SNIPPET_CHARS]


def _issue(kind: str, severity: str = HIGH, **detail) -> dict:
    return {"type": kind, "severity": severity, **detail}


def _unit_conflict(token: NumberToken, allowed: list[NumberToken]) -> bool:
    """값은 같지만 단위가 모두 다른 경우 (둘 다 단위가 있을 때만)."""
    same = [a for a in allowed if a.value == token.value]
    return bool(token.unit and same and all(a.unit and a.unit != token.unit for a in same))


def check_numbers(text: str, allowed: list[NumberToken], where: dict) -> list[dict]:
    issues = []
    values = {a.value for a in allowed}
    for token in number_tokens(text):
        if token.value not in values:
            issues.append(_issue("unsupported_number", number=token.raw, text=_snippet(text), **where))
        elif _unit_conflict(token, allowed):
            issues.append(_issue("unit_mismatch", WARN, number=token.raw, text=_snippet(text), **where))
    return issues


def unsupported_numbers_by_page(root: Path, pages: list[str]) -> dict[int, list[str]]:
    """loose 모드로 쪽마다 사실 은행 밖 숫자를 모은다 (1부터 센 쪽 번호 → 숫자 목록)."""
    allowed = _bank_numbers(load_facts(root))
    found = {}
    for number, text in enumerate(pages, 1):
        bad = [i["number"] for i in check_numbers(text, allowed, {}) if i["type"] == "unsupported_number"]
        if bad:
            found[number] = bad
    return found


def _bank_numbers(bank: FactBank) -> list[NumberToken]:
    """loose 모드 허용 숫자: 모든 fact numbers + 경력 날짜의 연·월 + 연차 + 학점."""
    strings = [n for fact in bank.facts.values() for n in fact.get("numbers", [])]
    strings += [str(bank.years_stated()) + "년"]
    strings += [str(edu.get("gpa", "")) for edu in bank.education.values()]
    for exp in bank.experience.values():
        for label in (exp.get("start"), exp.get("end")):
            if label:
                year, month = label.split(".")
                strings += [f"{int(year)}", f"{int(month)}"]
    return tokens_of_all(strings)


def _fact_numbers(bank: FactBank, fact_ids: list[str]) -> list[NumberToken]:
    return tokens_of_all([n for fid in fact_ids if fid in bank.facts for n in bank.facts[fid].get("numbers", [])])


def _check_fact_ids(bank: FactBank, entry) -> list[dict]:
    issues = []
    for fid in entry.facts:
        fact = bank.facts.get(fid)
        if fact is None:
            issues.append(_issue("unknown_fact", fact=fid, path=entry.path))
        elif fact.get("confidence") == "check":
            issues.append(_issue("check_fact", fact=fid, path=entry.path))
    return issues


def _check_links(bank: FactBank, variant) -> list[dict]:
    issues = []
    for link_id in (variant.data.get("header") or {}).get("links", []):
        link = bank.links.get(link_id)
        if link is None:
            issues.append(_issue("unknown_link", link=link_id))
        elif link.get("public") is False:
            issues.append(_issue("private_link", link=link_id))
    return issues


def _check_skills(bank: FactBank, variant) -> list[dict]:
    allowed = bank.allowed_skill_labels()
    return [
        _issue("unsupported_skill", skill=str(item), group=group.get("group"))
        for group in variant.data.get("skills") or [] for item in group.get("items", [])
        if str(item).casefold() not in allowed
    ]


def _check_unconfirmed_refs(bank: FactBank, variant) -> list[dict]:
    issues = []
    for key, table in (("certifications", bank.certifications), ("education", bank.education)):
        for ref in variant.data.get(key) or []:
            if ref in table and table[ref].get("confidence") == "check":
                issues.append(_issue(f"unconfirmed_{key}", WARN, ref=ref, note=table[ref].get("note", "")))
    return issues


def forbidden_pattern_issues(root: Path, text: str) -> list[dict]:
    issues = []
    for rule in load_rules():
        if rule.get("type") != "forbidden_patterns":
            continue
        for pattern in rule.get("params", {}).get("patterns", []):
            match = re.search(pattern, text)
            if match:
                issues.append(_issue("forbidden_pattern", pattern=pattern, rule=rule["id"], text=_snippet(match.group())))
    return issues


def check_strict(root: Path, doc: Document) -> list[dict]:
    bank, variant = load_facts(root), doc.variant
    issues = list(variant.issues)
    for entry in variant.entries:
        issues += _check_fact_ids(bank, entry)
        issues += check_numbers(entry.text, _fact_numbers(bank, entry.facts), {"path": entry.path})
    return issues + _check_links(bank, variant) + _check_skills(bank, variant) + _check_unconfirmed_refs(bank, variant)


def claims(root: Path, doc: Document, strict: bool = False) -> dict:
    mode = "strict" if strict and doc.variant else "loose"
    if mode == "strict":
        issues = check_strict(root, doc)
    else:
        issues = check_numbers(doc.claim_text, _bank_numbers(load_facts(root)), {})
    issues += forbidden_pattern_issues(root, doc.text)
    return {
        "file": doc.path.name, "mode": mode, "ok": not any(i["severity"] == HIGH for i in issues),
        "high": sum(i["severity"] == HIGH for i in issues), "warnings": sum(i["severity"] == WARN for i in issues),
        "issues": issues,
    }
