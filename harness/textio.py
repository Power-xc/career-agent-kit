"""텍스트 정규화, 개인정보 가림, 숫자 토큰 추출 (contract 4장)."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"01[016789][- .]?[0-9]{3,4}[- .]?[0-9]{4}")
# "경력 8년", "총 경력 8년", 시각 배치 때문에 줄이 나뉜 "경력\n총\n8년" (포트폴리오 2쪽)
STATED_YEARS_RE = re.compile(r"경력[\s·:]*(?:총[\s·:]*)?(\d{1,2})\s*년")

_ZERO_WIDTH = dict.fromkeys(map(ord, "​‌‍⁠﻿"))
# 마지막 두 개는 경계가 필요한 라틴 단위
UNITS = r"%p|%|개월|명|건|분|초|주|년|개|곳|회|배|단계|화면|종|인|(?:px|min|x)(?![A-Za-z])"
_NUMBER = r"(?:\d{1,3}(?:,\d{3})++(?:\.\d++)?|\d++(?:\.\d++)?)"
_TOKEN_RE = re.compile(rf"(?<![A-Za-z\d])(?<!\d[.,])(?P<num>{_NUMBER})(?:(?P<unit>{UNITS})|(?![A-Za-z]))")

_URL_RE = re.compile(r"(?:https?://|www\.)\S+")
_VERSION_RE = re.compile(r"\bv\d+(?:\.\d+)*", re.I)
_FULL_DATE_RE = re.compile(r"(?<![\d.])(?:19|20)\d{2}\s*[.\-/]\s*\d{1,2}(?:\s*[.\-/]\s*\d{1,2})?(?!\d)")
_YEAR_WORD_RE = re.compile(r"(?<!\d)(?:19|20)\d{2}\s*년")
_SHORT_DATE_RE = re.compile(r"(?<![\d.,])(\d{2})\.(0[1-9]|1[0-2])(?![\d%.])")
_MONTH_RE = re.compile(r"(?<!\d)\d{1,2}\s*월")
_TIME_RE = re.compile(r"(?<!\d)\d{1,2}:\d{2}(?::\d{2})?(?!\d)")
_ID_RE = re.compile(r"(?<![\d:])\d+:\d+(?![\d:])")  # Figma 노드 id(848:11605) 같은 콜론 숫자 쌍
_RRN_RE = re.compile(r"(?<!\d)\d{6}-\d{7}(?!\d)")  # 주민번호 형식 (보안 제품 목업의 예시 데이터)
_LIST_MARKER_RE = re.compile(r"(?m)^(\s*)\d{1,2}[.)](?=\s)")
_PLAIN_YEAR_RE = re.compile(rf"(?<![\d.,])(?:19|20)\d{{2}}(?!\d)(?!\.\d)(?!\s?(?:{UNITS}))")
_SHORT_DATE_YEARS = range(15, 30)


@dataclass(frozen=True)
class NumberToken:
    raw: str
    value: float
    unit: str

    def __str__(self) -> str:
        return self.raw


def normalize_text(text: str) -> str:
    """NFC, 제로폭 문자 제거, 줄바꿈 통일. U+2028은 줄바꿈으로 본다."""
    text = unicodedata.normalize("NFC", text).translate(_ZERO_WIDTH)
    return text.replace("\r\n", "\n").replace("\r", "\n").replace(" ", "\n")


def compact(text: str) -> str:
    """공백을 모두 없애고 소문자로 만든 비교용 문자열."""
    return re.sub(r"\s+", "", text).casefold()


def redact(text: str) -> str:
    return PHONE_RE.sub("[PHONE]", EMAIL_RE.sub("[EMAIL]", text))


def redact_obj(obj: Any) -> Any:
    """JSON으로 내보낼 구조 안의 모든 문자열을 가린다."""
    if isinstance(obj, str):
        return redact(obj)
    if isinstance(obj, dict):
        return {key: redact_obj(value) for key, value in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [redact_obj(value) for value in obj]
    return obj


def _blank(match: re.Match[str]) -> str:
    return " " * len(match.group())


def _blank_short_date(match: re.Match[str]) -> str:
    return _blank(match) if int(match.group(1)) in _SHORT_DATE_YEARS else match.group()


def _mask_non_claims(text: str) -> str:
    """날짜, 버전, URL, 연도, 시각·id, 전화·주민번호 형식, 목록 번호를 같은 길이의 공백으로 지운다."""
    for pattern in (_URL_RE, _VERSION_RE, _FULL_DATE_RE, _YEAR_WORD_RE, _MONTH_RE, _TIME_RE, _ID_RE, PHONE_RE, _RRN_RE):
        text = pattern.sub(_blank, text)
    text = _SHORT_DATE_RE.sub(_blank_short_date, text)
    text = _LIST_MARKER_RE.sub(lambda m: m.group(1) + "  ", text)
    return _PLAIN_YEAR_RE.sub(_blank, text)


def number_tokens(text: str) -> list[NumberToken]:
    """주장 검사 대상 숫자 토큰. 영문자와 붙은 숫자(B2B, GA4)는 제외한다."""
    tokens = []
    for match in _TOKEN_RE.finditer(_mask_non_claims(text)):
        value = float(match.group("num").replace(",", ""))
        tokens.append(NumberToken(match.group(), value, match.group("unit") or ""))
    return tokens


def tokens_of_all(strings: list[str]) -> list[NumberToken]:
    return [token for text in strings for token in number_tokens(text)]
