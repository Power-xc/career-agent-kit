"""사실 은행과 이력서 변형(YAML) 로드, 변형을 섹션별 텍스트로 펴기."""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from .extract import InputError
from .taxonomy import load_yaml

YAML_SUFFIXES = (".yaml", ".yml")
HEADER_LINK_SECTION = "links"


@dataclass
class Entry:
    """주장 검사의 단위: 문장 하나와 그 문장이 인용하는 fact id."""
    section: str
    text: str
    facts: list[str]
    path: str


@dataclass
class Variant:
    data: dict
    sections: dict[str, str] = field(default_factory=dict)
    entries: list[Entry] = field(default_factory=list)
    bullets: list[str] = field(default_factory=list)  # 경력·프로젝트 bullet (정량 비율용)
    issues: list[dict] = field(default_factory=list)  # 구조 문제 (없는 ref, 직함 불일치 등)


class FactBank:
    def __init__(self, data: dict):
        self.data = data
        self.facts = {f["id"]: f for f in data.get("facts", [])}
        self.experience = {e["id"]: e for e in data.get("experience", [])}
        self.projects = {p["id"]: p for p in data.get("projects", [])}
        self.certifications = {c["id"]: c for c in data.get("certifications", [])}
        self.education = {e["id"]: e for e in data.get("education", [])}
        self.awards = {a["id"]: a for a in data.get("awards", [])}
        self.links = {link["id"]: link for link in data.get("person", {}).get("links", [])}
        self.skills = data.get("skills", [])
        self.canonical = data.get("canonical", [])

    def allowed_skill_labels(self) -> set[str]:
        labels = set()
        for skill in self.skills:
            labels.update((skill.get("display") or {}).values())
            labels.update(skill.get("aliases") or [])
        return {str(label).casefold() for label in labels}

    def years_stated(self) -> int:
        return int(self.data.get("person", {}).get("years_stated", 0))


@lru_cache(maxsize=4)
def load_facts(root: Path) -> FactBank:
    data = load_yaml(root / "profile/facts.yaml")
    if not isinstance(data, dict):
        raise InputError("profile/facts.yaml 형식이 잘못됐습니다")
    return FactBank(data)


def load_variant(path: Path, bank: FactBank) -> Variant:
    data = load_yaml(path)
    if not isinstance(data, dict):
        raise InputError(f"이력서 변형 YAML 형식이 잘못됐습니다: {path}")
    variant = Variant(data)
    _flatten_header(data, bank, variant)
    _flatten_blocks(data, variant)
    _flatten_experience(data, bank, variant)
    _flatten_skills_and_refs(data, bank, variant)
    for name, parts in _group(variant).items():
        variant.sections[name] = "\n".join(parts)
    return variant


def _group(variant: Variant) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for entry in variant.entries:
        grouped.setdefault(entry.section, []).append(entry.text)
    for name, text in variant.sections.items():
        grouped.setdefault(name, []).insert(0, text)
    return grouped


def _add(variant: Variant, section: str, text, facts, path: str) -> None:
    if text:
        variant.entries.append(Entry(section, str(text), list(facts or []), path))


def _flatten_header(data: dict, bank: FactBank, variant: Variant) -> None:
    header = data.get("header") or {}
    variant.sections["header"] = "\n".join(str(header[k]) for k in ("name", "title", "tagline", "location") if header.get(k))
    labels = [bank.links[i]["label"] for i in header.get("links", []) if i in bank.links]
    if labels:
        variant.sections[HEADER_LINK_SECTION] = " ".join(labels)


def _flatten_blocks(data: dict, variant: Variant) -> None:
    for i, item in enumerate(data.get("summary") or []):
        _add(variant, "summary", item.get("text"), item.get("facts"), f"summary[{i}]")
    for i, item in enumerate(data.get("strengths") or []):
        text = f"{item.get('title', '')}\n{item.get('text', '')}"
        _add(variant, "strengths", text, item.get("facts"), f"strengths[{i}]")
    motivation = data.get("motivation") or {}
    _add(variant, "motivation", motivation.get("text"), motivation.get("facts"), "motivation")


def _flatten_experience(data: dict, bank: FactBank, variant: Variant) -> None:
    for i, block in enumerate(data.get("experience") or []):
        ref = block.get("ref")
        exp = bank.experience.get(ref)
        if exp is None:
            variant.issues.append({"type": "unknown_ref", "ref": ref, "path": f"experience[{i}]"})
            continue
        _check_title(block, exp, variant, i)
        title = block.get("title_display") or exp["title"]["ko"]
        period = f"{exp['start']} ~ {exp.get('end') or '현재'}"
        header = f"{title}\n{exp['company']['ko']} / {exp['unit']['ko']}\n{period}"
        variant.sections["experience"] = (variant.sections.get("experience", "") + "\n" + header).strip()
        for j, bullet in enumerate(block.get("bullets") or []):
            _add(variant, "experience", bullet.get("text"), bullet.get("facts"), f"experience[{i}].bullets[{j}]")
            variant.bullets.append(str(bullet.get("text", "")))
    for i, block in enumerate(data.get("projects") or []):
        for j, bullet in enumerate(block.get("bullets") or []):
            _add(variant, "projects", bullet.get("text"), bullet.get("facts"), f"projects[{i}].bullets[{j}]")
            variant.bullets.append(str(bullet.get("text", "")))


def _check_title(block: dict, exp: dict, variant: Variant, index: int) -> None:
    shown = block.get("title_display")
    if not shown:
        return
    allowed = {exp["title"]["ko"], exp["title"]["en"], *exp.get("title_aliases", [])}
    if shown not in allowed:
        variant.issues.append({"type": "unsupported_title", "title": shown, "path": f"experience[{index}].title_display"})


def _flatten_skills_and_refs(data: dict, bank: FactBank, variant: Variant) -> None:
    groups = data.get("skills") or []
    variant.sections["skills"] = "\n".join(f"{g.get('group', '')}: " + ", ".join(map(str, g.get("items", []))) for g in groups)
    refs = (("awards", bank.awards, _award_line), ("certifications", bank.certifications, _cert_line), ("education", bank.education, _edu_line))
    for key, table, render in refs:
        variant.sections[key] = "\n".join(render(table[i]) for i in data.get(key, []) if i in table)
        for ref in data.get(key, []):
            if ref not in table:
                variant.issues.append({"type": "unknown_ref", "ref": ref, "path": key})


def _award_line(award: dict) -> str:
    return f"{award['name']} {award.get('date', '')}".strip()


def _cert_line(cert: dict) -> str:
    suffix = "취득 예정" if cert.get("status") == "planned" else ""
    return f"{cert['name']} / {cert['date']} {suffix}".strip()


def _edu_line(edu: dict) -> str:
    return f"{edu['school']} {edu['major']} {edu['start']} ~ {edu['end']}"


def variant_job_spans(data: dict, bank: FactBank) -> list[tuple[int, int]]:
    """변형이 인용한 경력(휴직 제외)의 (시작, 끝) 월 인덱스."""
    from .dates import month_index, today_index
    spans = []
    for block in data.get("experience") or []:
        exp = bank.experience.get(block.get("ref"))
        if exp and exp.get("kind") == "job":
            end = month_index(exp["end"]) if exp.get("end") else today_index()
            spans.append((month_index(exp["start"]), end))
    return spans
