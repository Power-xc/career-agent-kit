"""날짜 범위 추출, 총 경력 개월 계산, 공백·겹침 보고."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

LEAVE_RE = re.compile(r"휴직|군\s*복무|military|\bleave\b", re.I)
RANGE_RE = re.compile(
    r"(?<!\d)((?:19|20)\d{2})\s*[.\-/]\s*(\d{1,2})\s*[~∼–—−\-]+\s*"
    r"(현재|재직\s*중|present|now|current|(?:19|20)\d{2}\s*[.\-/]\s*\d{1,2})(?!\d)",
    re.I,
)
SINGLE_DATE_RE = re.compile(r"(?<!\d)((?:19|20)\d{2})\s*[.\-/]\s*(\d{1,2})(?!\d)")
PRESENT_WORDS = ("현재", "재직", "present", "now", "current")
EXPERIENCE_SECTIONS = (None, "experience")
BOUNDARY_OVERLAP_MONTHS = 1  # 이어지는 직장의 경계 월 공유는 겹침으로 보지 않는다


@dataclass(frozen=True)
class DateRange:
    start: int
    end: int
    line: int
    is_leave: bool
    section: str | None
    raw: str

    def label(self) -> str:
        return f"{index_label(self.start)} ~ {index_label(self.end)}"


_today_override: date | None = None


def set_today(value: date | None) -> None:
    """테스트용: 현재 날짜 고정."""
    global _today_override
    _today_override = value


def today_index() -> int:
    today = _today_override or date.today()
    return today.year * 12 + today.month - 1


def month_index(label: str) -> int:
    year, month = re.split(r"[.\-/]", label.strip())[:2]
    return int(year) * 12 + int(month) - 1


def index_label(index: int) -> str:
    return f"{index // 12}.{index % 12 + 1:02d}"


def _is_present(word: str) -> bool:
    return any(word.lower().startswith(p) for p in PRESENT_WORDS)


def find_ranges(text: str, section_of_line=None) -> list[DateRange]:
    """텍스트의 'YYYY.MM ~ YYYY.MM|현재' 범위. 휴직 근처 범위는 is_leave=True."""
    lines = text.split("\n")
    found: list[DateRange] = []
    for number, line in enumerate(lines):
        for match in RANGE_RE.finditer(line):
            start = int(match.group(1)) * 12 + int(match.group(2)) - 1
            tail = match.group(3)
            end = today_index() if _is_present(tail) else month_index(tail)
            if end < start:
                continue
            section = section_of_line(number) if section_of_line else None
            found.append(DateRange(start, end, number, _near_leave(lines, number), section, match.group()))
    return found


def _near_leave(lines: list[str], number: int) -> bool:
    """같은 줄, 또는 날짜 없는 바로 이웃(앞뒤 비어 있지 않은 줄)에 휴직 표현이 있으면 휴직."""
    if LEAVE_RE.search(lines[number]):
        return True
    for step in (-1, 1):
        index = number + step
        while 0 <= index < len(lines) and not lines[index].strip():
            index += step
        if 0 <= index < len(lines) and LEAVE_RE.search(lines[index]) and not RANGE_RE.search(lines[index]):
            return True
    return False


def job_ranges(ranges: list[DateRange]) -> list[DateRange]:
    return [r for r in ranges if not r.is_leave and r.section in EXPERIENCE_SECTIONS]


def total_months(spans: list[tuple[int, int]]) -> int:
    """월 단위로 양 끝을 포함해 합치고(겹침은 한 번만) 센다."""
    months: set[int] = set()
    for start, end in spans:
        months.update(range(start, end + 1))
    return len(months)


def gaps_and_overlaps(jobs: list[DateRange], leaves: list[DateRange]) -> tuple[list[dict], list[dict]]:
    """직장 범위 사이의 공백(휴직으로 메워진 달은 제외)과 2개월 이상 겹침."""
    ordered = sorted(jobs, key=lambda r: r.start)
    covered = set()
    for r in (*jobs, *leaves):
        covered.update(range(r.start, r.end + 1))
    gaps, overlaps = [], []
    for before, after in zip(ordered, ordered[1:]):
        shared = before.end - after.start + 1
        if shared > BOUNDARY_OVERLAP_MONTHS:
            overlaps.append({"a": before.label(), "b": after.label(), "months": shared})
        missing = [m for m in range(before.end + 1, after.start) if m not in covered]
        if missing:
            gaps.append({"from": index_label(missing[0]), "to": index_label(missing[-1]), "months": len(missing)})
    return gaps, overlaps


def summarize(ranges: list[DateRange]) -> dict:
    jobs = job_ranges(ranges)
    leaves = [r for r in ranges if r.is_leave]
    gaps, overlaps = gaps_and_overlaps(jobs, leaves)
    return {
        "ranges": [{"range": r.label(), "line": r.line, "leave": r.is_leave, "section": r.section} for r in ranges],
        "total_months": total_months([(r.start, r.end) for r in jobs]),
        "leave_months": total_months([(r.start, r.end) for r in leaves]),
        "gaps": gaps,
        "overlaps": overlaps,
    }


def non_standard_dates(text: str, pattern: str) -> list[str]:
    """YYYY.MM 형식이 아닌 날짜 표기."""
    standard = re.compile(pattern)
    bad = []
    for match in SINGLE_DATE_RE.finditer(text):
        token = re.sub(r"\s+", "", match.group())
        if not standard.fullmatch(token):
            bad.append(token)
    return bad
