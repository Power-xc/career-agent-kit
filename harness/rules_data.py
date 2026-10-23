"""rules/*.yaml 로드."""
from __future__ import annotations

from functools import lru_cache

from .extract import InputError
from .paths import ENGINE_ROOT
from .taxonomy import load_yaml


@lru_cache(maxsize=8)
def _load(name: str) -> dict:
    data = load_yaml(ENGINE_ROOT / "rules" / name)
    if not isinstance(data, dict):
        raise InputError(f"규칙 파일 형식이 잘못됐습니다: rules/{name}")
    return data


def load_rules() -> list[dict]:
    return _load("rules.yaml").get("rules", [])


def load_scoring() -> dict:
    return _load("scoring.yaml")


def load_platforms() -> list[dict]:
    return _load("platforms.yaml").get("platforms", [])
