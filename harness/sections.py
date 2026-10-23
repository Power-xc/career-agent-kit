"""이력서 섹션 제목 인식 (평문과 pdftotext -layout 모두)."""
from __future__ import annotations

import re

# 제목은 줄 시작에서 줄 끝이나 공백 2칸 이상(layout 2단)이나 콜론 앞까지 와야 한다.
HEADING_PATTERNS = {
    "summary": r"about\s*me|summary|profile|소개|요약|자기\s*소개",
    "experience": r"work\s*experience|experience|경력(?:\s*사항)?|업무\s*경력",
    "projects": r"projects?|프로젝트",
    "skills": r"skills?|스킬|역량|기술\s*스택",
    "education": r"education|학력",
    "certifications": r"(?:awards\s*(?:&|and)\s*)?certifications?|자격증?|자격\s*사항",
    "awards": r"awards?(?:\s*(?:&|and))?|수상(?:\s*경력)?",
    "strengths": r"strengths?|강점",
    "motivation": r"(?:application\s+)?motivation|application|지원\s*동기",
    "links": r"links?|링크",
}
_COMPILED = {
    key: re.compile(rf"^\s*(?:{pattern})\s*(?::|\s{{2,}}|$)", re.I)
    for key, pattern in HEADING_PATTERNS.items()
}
# certifications가 awards보다 먼저 검사돼야 'Awards & Certifications'가 한 제목으로 잡힌다.
_ORDER = ("certifications", "awards", *[k for k in HEADING_PATTERNS if k not in ("certifications", "awards")])
MAX_HEADING_ONLY_CHARS = 40  # 제목 뒤에 내용이 없는 줄은 짧아야 제목이다


def heading_of(line: str) -> str | None:
    stripped = line.strip()
    if not stripped:
        return None
    for key in _ORDER:
        match = _COMPILED[key].match(line)
        if match:
            rest = line[match.end():]
            if rest.strip() or len(stripped) <= MAX_HEADING_ONLY_CHARS:
                return key
    return None


def find_headings(text: str) -> list[tuple[int, str]]:
    """(줄 번호, 섹션 키) 목록. 같은 키가 연속으로 잡히면 첫 번째만 남긴다."""
    found: list[tuple[int, str]] = []
    for number, line in enumerate(text.split("\n")):
        key = heading_of(line)
        if key and (not found or found[-1][1] != key):
            found.append((number, key))
    return found


def section_resolver(text: str):
    """줄 번호 → 그 줄이 속한 섹션 키(없으면 None)."""
    headings = find_headings(text)

    def resolve(line_number: int) -> str | None:
        current = None
        for number, key in headings:
            if number > line_number:
                break
            current = key
        return current

    return resolve


def split_sections(text: str) -> dict[str, str]:
    lines = text.split("\n")
    headings = find_headings(text)
    parts: dict[str, list[str]] = {}
    for i, (number, key) in enumerate(headings):
        end = headings[i + 1][0] if i + 1 < len(headings) else len(lines)
        parts.setdefault(key, []).extend(lines[number:end])
    return {key: "\n".join(value) for key, value in parts.items()}
