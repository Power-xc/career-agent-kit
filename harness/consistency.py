"""문서 간 일관성: facts.yaml canonical의 정본 표기와 다른 표기를 찾는다."""
from __future__ import annotations

import re
from pathlib import Path

from .document import Document
from .facts import FactBank, load_facts
from .taxonomy import Haystack
from .textio import STATED_YEARS_RE, compact

CERT_FIELD_RE = re.compile(r"^cert\.(?P<id>[^.]+)\.date$")
CERT_WINDOW_LINES = 2  # 자격 이름이 나온 줄과 그 다음 줄까지 본다


def _cert_window(doc: Document, bank: FactBank, cert_id: str) -> str:
    cert = bank.certifications.get(cert_id)
    if not cert:
        return ""
    name, lines = compact(cert["name"]), doc.text.split("\n")
    chunks = [
        "\n".join(lines[i:i + CERT_WINDOW_LINES])
        for i, line in enumerate(lines) if name and name in compact(line)
    ]
    return "\n".join(chunks)


def _scope_text(doc: Document, bank: FactBank, field: str) -> str:
    match = CERT_FIELD_RE.match(field)
    return _cert_window(doc, bank, match["id"]) if match else doc.text


def _forms_found(scope: str, entry: dict) -> list[dict]:
    if not scope:
        return []
    haystack = Haystack(scope)
    found = []
    if entry.get("value") and haystack.has(entry["value"]):
        found.append({"form": entry["value"], "kind": "canonical"})
    found += [{"form": v, "kind": "variant"} for v in entry.get("variants", []) if haystack.has(v)]
    return found


def _stated_years_issue(doc: Document, bank: FactBank) -> list[dict]:
    stated = bank.years_stated()
    wrong = sorted({int(n) for n in STATED_YEARS_RE.findall(doc.text) if int(n) != stated})
    return [{"field": "experience.total", "file": doc.path.name, "found": f"경력 {n}년",
             "canonical": f"{stated}년", "note": "서류에 쓰는 총 경력 연수(years_stated)와 다름"} for n in wrong]


def check_consistency(root: Path, docs: list[Document], only_fields: list[str] | None = None) -> dict:
    bank = load_facts(root)
    fields, issues = [], []
    for entry in bank.canonical:
        if only_fields and entry["field"] not in only_fields:
            continue
        per_file = {}
        for doc in docs:
            forms = _forms_found(_scope_text(doc, bank, entry["field"]), entry)
            if forms:
                per_file[doc.path.name] = forms
            issues += [{"field": entry["field"], "file": doc.path.name, "found": f["form"],
                        "canonical": entry.get("value"), "note": entry.get("note", "")}
                       for f in forms if f["kind"] == "variant"]
        fields.append({"field": entry["field"], "canonical": entry.get("value"), "found": per_file})
    if not only_fields or "experience.total" in only_fields:
        for doc in docs:
            issues += _stated_years_issue(doc, bank)
    return {"files": [d.path.name for d in docs], "ok": not issues, "fields": fields, "issues": issues}
