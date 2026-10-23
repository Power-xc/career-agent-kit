"""택소노미 로드와 용어 매칭 (contract 3.4)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml

from .extract import InputError
from .paths import ENGINE_ROOT
from .textio import compact

SHORT_ACRONYM_MAX = 2
HANGUL_RE = re.compile(r"[가-힣]")
SHORT_ACRONYM_RE = re.compile(r"[A-Za-z0-9]{1,%d}" % SHORT_ACRONYM_MAX)
TITLE_STRIP_RE = re.compile(r"[^0-9a-z가-힣]+")
# skills.yaml에 없을 때만 추가하는 개념. 공고의 언어 요건(영어 커뮤니케이션)을 갭으로 잡기 위해 쓴다.
BUILTIN_CONCEPTS = [
    {"id": "english", "category": "collab", "terms": {"ko": ["영어"], "en": ["English"]}, "related": []},
]


class _IsoDateLoader(yaml.SafeLoader):
    """따옴표 없는 날짜(2026-10-23)를 date가 아니라 문자열로 읽는다. JSON·비교에서 모두 문자열로 쓴다."""


_IsoDateLoader.add_constructor("tag:yaml.org,2002:timestamp", lambda loader, node: loader.construct_scalar(node))


def parse_yaml(text: str):
    return yaml.load(text, Loader=_IsoDateLoader)


def load_yaml(path: Path):
    try:
        return parse_yaml(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise InputError(f"파일을 읽을 수 없습니다: {path} ({exc.strerror})") from exc
    except yaml.YAMLError as exc:
        raise InputError(f"YAML 형식이 잘못됐습니다: {path} ({exc})") from exc


class Haystack:
    """한 번 정규화해 두고 여러 용어를 찾는 검색 대상 텍스트."""

    def __init__(self, text: str):
        self.text = text
        self.lower = text.casefold()
        self.compact = compact(text)

    def find(self, term: str) -> int:
        """용어가 나온 횟수. 규칙은 contract 3.4."""
        term = term.strip()
        if not term:
            return 0
        if HANGUL_RE.search(term):
            needle = compact(term)
            return self.compact.count(needle) if needle else 0
        if SHORT_ACRONYM_RE.fullmatch(term):
            pattern = r"(?<![A-Za-z0-9])" + re.escape(term) + r"(?![A-Za-z0-9])"
            return len(re.findall(pattern, self.text))
        pieces = [re.escape(piece) for piece in term.split()]
        pattern = r"(?<![A-Za-z0-9])" + r"\s+".join(pieces) + r"(?![A-Za-z0-9])"
        return len(re.findall(pattern, self.text, re.I))

    def has(self, term: str) -> bool:
        return self.find(term) > 0


@dataclass
class Taxonomy:
    families: list[dict] = field(default_factory=list)
    concepts: list[dict] = field(default_factory=list)

    @property
    def family_by_id(self) -> dict[str, dict]:
        return {f["id"]: f for f in self.families}

    @property
    def concept_by_id(self) -> dict[str, dict]:
        return {c["id"]: c for c in self.concepts}

    def target_family_ids(self) -> list[str]:
        return [f["id"] for f in self.families if f.get("target")]

    def concept_terms(self, concept_id: str) -> list[str]:
        concept = self.concept_by_id.get(concept_id, {})
        return [t for terms in (concept.get("terms") or {}).values() for t in terms]

    def concepts_in(self, haystack: Haystack) -> dict[str, list[str]]:
        """텍스트에서 발견된 개념 id → 매칭된 용어."""
        found = {}
        for concept in self.concepts:
            hits = [t for t in self.concept_terms(concept["id"]) if haystack.has(t)]
            if hits:
                found[concept["id"]] = hits
        return found

    def normalize_title(self, title: str) -> str | None:
        """직함 → 직군 id. 완전 일치가 우선이고, 아니면 가장 긴 표기가 단어 경계로 포함된 직군."""
        needle = TITLE_STRIP_RE.sub("", title.casefold())
        if not needle:
            return None
        lowered, best, best_len = title.casefold(), None, 0
        for family in self.families:
            for label in family.get("titles", []):
                key = TITLE_STRIP_RE.sub("", label.casefold())
                if key == needle:
                    return family["id"]
                if len(key) > best_len and _label_inside(label, lowered, needle):
                    best, best_len = family["id"], len(key)
        return best

def _label_inside(label: str, lowered_title: str, compact_title: str) -> bool:
    """직함 표기가 제목 안에 있는가. 영문은 단어 경계, 한글은 공백 무시."""
    if HANGUL_RE.search(label):
        return TITLE_STRIP_RE.sub("", label.casefold()) in compact_title
    pieces = [re.escape(p) for p in label.casefold().split()]
    return bool(re.search(r"(?<![a-z0-9])" + r"\s+".join(pieces) + r"(?![a-z0-9])", lowered_title))


@lru_cache(maxsize=4)
def load_taxonomy() -> Taxonomy:
    families = load_yaml(ENGINE_ROOT / "taxonomy/job_families.yaml") or {}
    concepts = load_yaml(ENGINE_ROOT / "taxonomy/skills.yaml") or {}
    loaded = concepts.get("concepts", [])
    known = {c["id"] for c in loaded}
    return Taxonomy(families.get("families", []), loaded + [c for c in BUILTIN_CONCEPTS if c["id"] not in known])
