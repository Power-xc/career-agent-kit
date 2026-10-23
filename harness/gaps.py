"""공고 개념별로 사실 은행의 뒷받침(evidence)을 찾는다. 근거 없는 개념은 쓰지 않는다."""
from __future__ import annotations

from pathlib import Path

from .facts import FactBank, load_facts
from .jd import preferred_concepts, required_concepts
from .taxonomy import Taxonomy

NO_EVIDENCE_HINT = "사실 은행에 근거 없음: 서류에 쓰지 않는다. 사실이면 출처와 함께 facts.yaml에 먼저 추가"


def evidence_for(bank: FactBank, concept_id: str) -> list[str]:
    """concept을 가진 fact id (확인 필요 제외) + skills.evidence에 묶인 fact id."""
    ids = [fid for fid, fact in bank.facts.items()
           if concept_id in fact.get("concepts", []) and fact.get("confidence") != "check"]
    for skill in bank.skills:
        if skill.get("concept") == concept_id:
            ids += [f for f in skill.get("evidence", []) if f in bank.facts and f not in ids]
    return ids


def concept_gap_rows(root: Path, taxonomy: Taxonomy, jd: dict) -> list[dict]:
    bank = load_facts(root)
    rows = []
    for importance, concepts in (("required", required_concepts(jd)), ("preferred", preferred_concepts(jd))):
        for concept_id in concepts:
            direct = evidence_for(bank, concept_id)
            related = [f for rel in taxonomy.concept_by_id.get(concept_id, {}).get("related", [])
                       for f in evidence_for(bank, rel)]
            related = [f for f in dict.fromkeys(related) if f not in direct]
            status = "supported" if direct else ("related_only" if related else "no_evidence")
            rows.append({"concept": concept_id, "importance": importance, "status": status,
                         "evidence_facts": direct, "related_facts": related,
                         "suggestion": "" if direct else (NO_EVIDENCE_HINT if not related else "직접 근거는 없고 관련 사실만 있음: 관련 사실의 범위 안에서만 표현")})
    return rows
