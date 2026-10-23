"""figma_text.yaml 점검: 슬롯 존재, 글자·줄 수 상한, 하이픈 단어 분리, 사실 은행 근거 (contract 3.3, 5장)."""
from __future__ import annotations

import re
from pathlib import Path

from .claims import _fact_numbers, check_numbers
from .extract import InputError, require_file
from .facts import load_facts
from .taxonomy import load_yaml

LINE_BREAKS_RE = re.compile(r"[\n ]")
SPLIT_WORD_RE = re.compile(r"[A-Za-z0-9가-힣]-$")  # 줄 끝이 하이픈이면 단어가 다음 줄로 이어진다 (Human-in-the-/Loop)


def _slot_map(root: Path) -> dict[str, dict]:
    data = load_yaml(require_file(root / "profile/figma_map.yaml"))
    return {slot["id"]: slot for slot in (data or {}).get("slots") or [] if "id" in slot}


def _entries(path: Path) -> list[dict]:
    data = load_yaml(require_file(path))
    entries = data.get("slots") if isinstance(data, dict) else None
    if not isinstance(entries, list):
        raise InputError(f"figma_text.yaml 최상위에 slots 목록이 필요합니다: {path}")
    return entries


def _text_problems(text: str, slot: dict) -> list[str]:
    problems = []
    chars = len(LINE_BREAKS_RE.sub("", text))
    if slot.get("max_chars") and chars > slot["max_chars"]:
        problems.append(f"글자 수 {chars}자가 상한 {slot['max_chars']}자를 넘습니다")
    lines = LINE_BREAKS_RE.split(text.strip("\n "))
    if slot.get("lines") and len(lines) > slot["lines"]:
        problems.append(f"줄 수 {len(lines)}줄이 상한 {slot['lines']}줄을 넘습니다")
    problems += [f"{n}번째 줄이 하이픈으로 끝나 단어가 줄 사이에서 끊깁니다: '{line.strip()[-20:]}'"
                 for n, line in enumerate(lines[:-1], 1) if SPLIT_WORD_RE.search(line.rstrip())]
    return problems


def _fact_problems(bank, entry: dict, text: str) -> list[str]:
    fact_ids = entry.get("facts") or []
    problems = []
    for fid in fact_ids:
        fact = bank.facts.get(fid)
        if fact is None:
            problems.append(f"사실 은행에 없는 fact id: {fid}")
        elif fact.get("confidence") == "check":
            problems.append(f"확인 전 사실(confidence: check)은 쓸 수 없습니다: {fid}")
    unsupported = [i["number"] for i in check_numbers(text, _fact_numbers(bank, fact_ids), {}) if i["type"] == "unsupported_number"]
    if unsupported:
        problems.append(f"나열한 사실에 없는 숫자: {unsupported}")
    return problems


def check_figma_text(root: Path, path: Path) -> dict:
    slots, bank, results = _slot_map(root), load_facts(root), []
    for index, entry in enumerate(_entries(path), 1):
        slot_id = str(entry.get("id", f"#{index}"))
        text = entry.get("text")
        if slot_id not in slots:
            problems = [f"figma_map.yaml에 없는 슬롯입니다: {slot_id}"]
        elif not isinstance(text, str) or not text.strip():
            problems = ["text가 비어 있습니다"]
        else:
            problems = _text_problems(text, slots[slot_id]) + _fact_problems(bank, entry, text)
        results.append({"id": slot_id, "ok": not problems, "problems": problems})
    bad = [r for r in results if not r["ok"]]
    return {"file": path.name, "checked": len(results), "ok": not bad, "violations": len(bad), "entries": results}
