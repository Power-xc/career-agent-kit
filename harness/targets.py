"""조사한 공고 목록(unit YAML)을 합치고, 이미 지원한 회사를 빼고, 공고별 점수로 줄 세운다."""
from __future__ import annotations

from pathlib import Path

import yaml

from .document import load_document
from .extract import InputError
from .gaps import concept_gap_rows
from .jd import parse_jd
from .score import score_resume
from .taxonomy import load_taxonomy

ROLE_LIST_KEYS = ("roles", "jobs", "targets", "positions")
CHANCE_RANK = {"상": 0, "중": 1, "하": 2}
VERDICT_RANK = {"적합": 0, "도전": 1, "낮음": 2}
UNRANKED = 9
APPLICATIONS_FILE = "records/applications.yaml"
SCOPE_COMPANY, SCOPE_GROUP = "company", "group"
SUPPORTED = "supported"
ENTITY_NOISE = ("(주)", "주식회사", " ")


def normalize_name(name: object) -> str:
    text = str(name or "").lower()
    for noise in ENTITY_NOISE:
        text = text.replace(noise, "")
    return text


def base_name(name: object) -> str:
    """역할의 회사명에서 첫 "(" 앞부분만 쓴다. "LINE Pay Plus (LINE Plus 그룹)"의 괄호 속 그룹명은 보지 않는다."""
    return normalize_name(name).split("(")[0]


def load_exclusions(root: Path) -> list[dict]:
    path = root / APPLICATIONS_FILE
    if not path.is_file():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    if not isinstance(data, list):
        raise InputError(f"{APPLICATIONS_FILE}: 목록이어야 합니다.")
    return [entry for entry in data if isinstance(entry, dict) and entry.get("company")]


def is_excluded(company: object, applications: list[dict]) -> bool:
    base = base_name(company)
    if not base:
        return False
    for entry in applications:
        names = [normalize_name(n) for n in [entry["company"], *(entry.get("aliases") or [])]]
        for name in filter(None, names):
            if base == name or (entry.get("scope") == SCOPE_GROUP and name in base):
                return True
    return False


def load_roles(path: Path) -> list[dict]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        for key in ROLE_LIST_KEYS:
            if isinstance(data.get(key), list):
                return data[key]
        raise InputError(f"{path}: 역할 목록 키({', '.join(ROLE_LIST_KEYS)})를 찾을 수 없습니다. 있는 키: {sorted(data)}")
    if not isinstance(data, list):
        raise InputError(f"{path}: 목록이어야 하는데 {type(data).__name__} 입니다.")
    return data


def resolve_jd(jd_file: str | None, roots: list[Path]) -> Path | None:
    if not jd_file:
        return None
    candidate = Path(jd_file).expanduser()
    if candidate.is_absolute():
        return candidate if candidate.exists() else None
    return next((root / candidate for root in roots if (root / candidate).exists()), None)


def score_jd(root: Path, jd_path: Path, resume_path: Path) -> dict:
    jd = parse_jd(load_taxonomy(), jd_path)
    result = score_resume(root, jd, load_document(root, resume_path))
    missing = result["components"]["required"].get("missing", [])
    status = {gap["concept"]: gap["status"] for gap in result["gaps"]}
    return {
        "total": result["total"], "band": result["band"], "missing": missing,
        "fixable": [m for m in missing if status.get(m) == SUPPORTED],
        "real_gap": [m for m in missing if status.get(m) != SUPPORTED],
    }


def rank_key(role: dict) -> tuple:
    return (CHANCE_RANK.get(str(role.get("chance")), UNRANKED), VERDICT_RANK.get(str(role.get("verdict")), UNRANKED),
            -((role.get("harness") or {}).get("total") or 0))


def merge_targets(root: Path, resume_path: Path, units: list[Path]) -> dict:
    applications = load_exclusions(root)
    merged, excluded = [], []
    for unit in units:
        for role in load_roles(unit):
            if is_excluded(role.get("company", ""), applications):
                excluded.append({"company": role.get("company"), "role": role.get("role"), "unit": unit.stem})
                continue
            jd = resolve_jd(role.get("jd_file"), [root, unit.resolve().parent, *unit.resolve().parents[2:3]])
            scored = score_jd(root, jd, resume_path) if jd else None
            merged.append({**role, "unit": unit.stem, "jd_path": str(jd) if jd else None, "harness": scored})
    merged.sort(key=rank_key)
    return {"targets": merged, "excluded": excluded}


def render_lines(result: dict) -> list[str]:
    lines = [f"지원 이력으로 제외: {e['company']} | {e['role']}" for e in result["excluded"]]
    for role in result["targets"]:
        h = role.get("harness") or {}
        lines.append(f"{role.get('chance', '?')} {role.get('verdict', '?')} {h.get('total', '-'):>4} "
                     f"{role.get('company')} | {role.get('role')} | real_gap={h.get('real_gap', '-')}")
    return lines
