"""공고 파일(front matter + '## ' 섹션) 파싱."""
from __future__ import annotations

import re
from pathlib import Path

import yaml

from .extract import InputError, require_file
from .taxonomy import Haystack, Taxonomy, parse_yaml
from .textio import normalize_text

SECTION_ALIASES = {
    "responsibilities": r"responsibilit|주요\s*업무|담당\s*업무|하는\s*일|업무",
    "requirements": r"requirement|qualification|자격\s*요건|지원\s*자격|필수",
    "preferred": r"preferred|nice|bonus|우대",
    "process": r"process|채용\s*절차|전형",
    "documents": r"documents?|제출\s*서류",
    "notes": r"notes?|참고|비고",
}
YEARS_PATTERNS = (
    re.compile(r"(\d{1,2})\s*년\s*이상"),
    re.compile(r"경력\s*(\d{1,2})\s*년"),
    re.compile(r"(\d{1,2})\s*\+\s*years?", re.I),
    re.compile(r"(\d{1,2})\s*(?:or more|\+)?\s*years?\s+of\s+experience", re.I),
    re.compile(r"(\d{1,2})\s*[~\-–]\s*\d{1,2}\s*년"),
)
CONCEPT_SECTIONS = ("responsibilities", "requirements", "preferred")
FRONT_MATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.S)


def _section_key(title: str) -> str:
    for key, pattern in SECTION_ALIASES.items():
        if re.search(pattern, title, re.I):
            return key
    return title.strip().lower()


def years_min(sections: dict[str, str]) -> int | None:
    """최소 연차. 자격 요건 섹션을 먼저 보고, 없으면 우대 제외 나머지 본문."""
    scopes = [sections.get("requirements", ""), "\n".join(v for k, v in sections.items() if k != "preferred")]
    for scope in scopes:
        values = [int(m.group(1)) for p in YEARS_PATTERNS for m in p.finditer(scope)]
        if values:
            return min(values)
    return None


def parse_jd(taxonomy: Taxonomy, path: Path) -> dict:
    raw = normalize_text(require_file(path).read_text(encoding="utf-8"))
    meta, body = {}, raw
    match = FRONT_MATTER_RE.match(raw)
    if match:
        try:
            meta = parse_yaml(match.group(1)) or {}
        except yaml.YAMLError as exc:
            raise InputError(f"공고 front matter 형식이 잘못됐습니다: {path} ({exc})") from exc
        body = raw[match.end():]
    sections: dict[str, str] = {}
    current = None
    for line in body.split("\n"):
        heading = re.match(r"##\s+(.+)", line)
        if heading:
            current = _section_key(heading.group(1))
            sections.setdefault(current, "")
        elif current:
            sections[current] += line + "\n"
    concepts = {}
    for name in CONCEPT_SECTIONS:
        found = taxonomy.concepts_in(Haystack(sections.get(name, "")))
        concepts[name] = found
    title = str(meta.get("title", ""))
    family = taxonomy.normalize_title(re.sub(r"\(.*?\)", "", title))
    return {
        "file": path.name, "company": meta.get("company"), "title": title, "family": family,
        "language": meta.get("language", "ko"), "seniority": meta.get("seniority"),
        "years_min": years_min(sections), "meta": meta,
        "sections": {k: v.strip() for k, v in sections.items()},
        "concepts": {name: sorted(found) for name, found in concepts.items()},
        "concept_terms": concepts,
    }


def required_concepts(jd: dict) -> list[str]:
    """업무 + 자격 요건에서 나온 개념 (중복 제거, 순서 유지)."""
    seen: dict[str, None] = {}
    for name in ("requirements", "responsibilities"):
        seen.update(dict.fromkeys(jd["concepts"].get(name, [])))
    return list(seen)


def preferred_concepts(jd: dict) -> list[str]:
    required = set(required_concepts(jd))
    return [c for c in jd["concepts"].get("preferred", []) if c not in required]
