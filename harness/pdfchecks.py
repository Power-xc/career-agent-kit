"""PDF 전용 검사: 숨김 텍스트, 읽기 순서 어긋남, 한글 무결성 (PyMuPDF 필요)."""
from __future__ import annotations

import re
import statistics
import unicodedata
from collections import Counter
from pathlib import Path

from .extract import load_pymupdf
from .textio import compact, redact

INVISIBLE_RENDER_TYPE = 3
RENDER_ZOOM = 0.5  # 대비 측정용 저해상도 렌더
MIN_UNDRAWN_CHARS = 3  # 이 길이 이상인데 아무것도 그려지지 않았으면 선언 색과 무관하게 숨김
DETAIL_ZOOM = 4  # 의심 span만 확대해 다시 재는 배율
DETAIL_PAD_PT = 3.0
RING_PAD_PX = 2  # 글자 bbox 바깥 배경 샘플 두께(렌더 픽셀)
OFFPAGE_TOLERANCE_PT = 2.0
HIDDEN_EXAMPLES = 3
MOCKUP_MIN_TINY_SPANS = 20  # 한 쪽에 초소형 span이 이만큼 이상이면 축소된 UI 캡처로 본다
PARAGRAPH_CHARS = 40  # 이 길이 이상의 흰 글씨는 장식이 아니라 숨긴 문단으로 본다
NEAR_WHITE = 0.92  # 채널 값이 이 이상이면 흰색에 가깝다
RECOMMENDATIONS = {
    "mockup_text": "목업은 이미지로 평탄화하거나 화면 밖 텍스트를 지우세요",
    "tiny": "글자를 키우거나 지우세요",
    "offpage": "페이지 밖·잘린 텍스트를 지우세요",
    "low_contrast": "글자색을 배경과 구분되게 하거나 지우세요",
    "invisible": "보이지 않는 텍스트를 지우세요",
    "transparent": "투명 텍스트를 지우세요",
}
SNIPPET_CHARS = 60
READING_MAX_REPORTED = 30
READING_MIN_SEGMENT_CHARS = 4
LINE_TOLERANCE_RATIO = 0.5  # 같은 줄: 세로 중심 차이 ≤ 글자 높이의 이 비율
GAP_JOIN_RATIO = 1.5  # 같은 세그먼트: 가로 간격 ≤ 글자 높이의 이 비율
SPACE_GAP_RATIO = 0.15
EXTRACTOR_MIN_WORD_CHARS = 2
EXTRACTOR_EXAMPLES = 5
EXTRACTOR_MAX_PAGES = 5
DIGIT_RE = re.compile(r"\d")


def _linear(channel: int) -> float:
    c = channel / 255
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


_LINEAR = [_linear(i) for i in range(256)]


def _lum8(r: int, g: int, b: int) -> float:
    return 0.2126 * _LINEAR[r] + 0.7152 * _LINEAR[g] + 0.0722 * _LINEAR[b]


def _ratio(l1: float, l2: float) -> float:
    hi, lo = (l1, l2) if l1 >= l2 else (l2, l1)
    return (hi + 0.05) / (lo + 0.05)


def contrast_ratio(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    """WCAG 대비. 입력은 0~1 RGB."""
    return _ratio(_lum8(*(round(c * 255) for c in a)), _lum8(*(round(c * 255) for c in b)))


def _to_rgb(color) -> tuple[float, float, float]:
    if not color:
        return (0.0, 0.0, 0.0)
    if len(color) == 1:
        return (color[0],) * 3
    if len(color) == 4:  # CMYK
        c, m, y, k = color
        return ((1 - c) * (1 - k), (1 - m) * (1 - k), (1 - y) * (1 - k))
    return tuple(color[:3])


def _pixel_box(pix, rect, zoom: float, pad: int) -> tuple[int, int, int, int]:
    return (max(0, int(rect[0] * zoom) - pad), max(0, int(rect[1] * zoom) - pad),
            min(pix.width, int(rect[2] * zoom) + pad + 1), min(pix.height, int(rect[3] * zoom) + pad + 1))


def _rgb_at(samples, width: int, x: int, y: int) -> tuple[int, int, int]:
    i = (y * width + x) * 3
    return samples[i], samples[i + 1], samples[i + 2]


def _ring_background(pix, rect, zoom: float) -> tuple[int, int, int]:
    """글자 bbox 바로 바깥 테두리(고리)의 채널별 중앙값. 글자 자체 픽셀이 섞이지 않는다."""
    outer, inner = _pixel_box(pix, rect, zoom, RING_PAD_PX), _pixel_box(pix, rect, zoom, 0)
    samples, width, channels = pix.samples, pix.width, ([], [], [])
    for y in range(outer[1], outer[3]):
        for x in range(outer[0], outer[2]):
            if inner[0] <= x < inner[2] and inner[1] <= y < inner[3]:
                continue
            for channel, value in zip(channels, _rgb_at(samples, width, x, y)):
                channel.append(value)
    if not channels[0]:
        return (255, 255, 255)
    return tuple(int(statistics.median(c)) for c in channels)


def _visible_contrast(pix, rect, zoom: float, background: tuple[int, int, int], enough: float) -> float:
    """bbox 안에서 배경과 가장 대비가 큰 픽셀의 대비. 글자가 실제로 그려졌는지 본다. enough 이상이면 바로 멈춘다."""
    x0, y0, x1, y1 = _pixel_box(pix, rect, zoom, 0)
    samples, width, bg_lum, best = pix.samples, pix.width, _lum8(*background), 1.0
    for y in range(y0, y1):
        for x in range(x0, x1):
            best = max(best, _ratio(_lum8(*_rgb_at(samples, width, x, y)), bg_lum))
            if best >= enough:
                return best
    return best


def _outside(bbox, page_rect) -> bool:
    tol = OFFPAGE_TOLERANCE_PT
    return (bbox[2] < page_rect.x0 - tol or bbox[0] > page_rect.x1 + tol
            or bbox[3] < page_rect.y0 - tol or bbox[1] > page_rect.y1 + tol)


def _span_reasons(span: dict, page_rect, min_font_pt: float) -> list[str]:
    reasons = []
    if span["type"] == INVISIBLE_RENDER_TYPE:
        reasons.append("invisible")
    if span.get("opacity", 1.0) == 0:
        reasons.append("transparent")
    if span.get("size", 99) < min_font_pt:
        reasons.append("tiny")
    if _outside(span["bbox"], page_rect):
        reasons.append("offpage")
    return reasons


def _drawn_contrast(pix, bbox, zoom: float, min_contrast: float) -> tuple[tuple[int, int, int], float]:
    background = _ring_background(pix, bbox, zoom)
    return background, _visible_contrast(pix, bbox, zoom, background, min_contrast)


def _contrast_reasons(page, pix, span: dict, text: str, min_contrast: float) -> list[str]:
    """선언된 글자색이 배경과 비슷하고 실제로도 그려지지 않았으면 숨김.

    Type3 글꼴은 선언 색을 믿을 수 없어 그려진 픽셀 대비(drawn)를 본다. 저해상도에서 작은 글자는
    번져 대비가 낮게 나오므로, 의심되는 span만 확대해서 다시 잰다.
    """
    fitz = load_pymupdf()
    bbox = span["bbox"]
    background, drawn = _drawn_contrast(pix, bbox, RENDER_ZOOM, min_contrast)
    if drawn >= min_contrast:
        return []
    clip = fitz.Rect(bbox) + (-DETAIL_PAD_PT, -DETAIL_PAD_PT, DETAIL_PAD_PT, DETAIL_PAD_PT)
    detail = page.get_pixmap(matrix=fitz.Matrix(DETAIL_ZOOM, DETAIL_ZOOM), clip=clip, colorspace=fitz.csRGB, alpha=False)
    local = (bbox[0] - clip.x0, bbox[1] - clip.y0, bbox[2] - clip.x0, bbox[3] - clip.y0)
    background, drawn = _drawn_contrast(detail, local, DETAIL_ZOOM, min_contrast)
    declared = contrast_ratio(_to_rgb(span["color"]), tuple(c / 255 for c in background))
    if drawn < min_contrast and (declared < min_contrast or len(text) >= MIN_UNDRAWN_CHARS):
        return [f"low_contrast(declared {declared:.2f}, drawn {drawn:.2f})"]
    return []


def _near_white(color, background: tuple[int, int, int] | None = None) -> bool:
    channels = _to_rgb(color)
    return all(c >= NEAR_WHITE for c in channels) and (background is None or all(c / 255 >= NEAR_WHITE for c in background))


def _is_hard_fail(text: str, reason: str, span: dict, patterns) -> bool:
    """프롬프트 인젝션 패턴이거나, 문단 길이의 흰 글씨(흰 배경 위)면 high."""
    if any(re.search(p, text) for p in patterns):
        return True
    return reason == "low_contrast" and len(text) >= PARAGRAPH_CHARS and _near_white(span["color"])


def _group_candidates(candidates: list[dict]) -> list[dict]:
    """(쪽, 이유)별로 묶는다. 초소형 span이 한 쪽에 MOCKUP_MIN_TINY_SPANS개 이상이면 축소된 화면 캡처(mockup_text)로 본다."""
    tiny_per_page = Counter(c["page"] for c in candidates if c["reason"] == "tiny")
    groups: dict[tuple[int, str], dict] = {}
    for c in candidates:
        reason = "mockup_text" if c["reason"] == "tiny" and tiny_per_page[c["page"]] >= MOCKUP_MIN_TINY_SPANS else c["reason"]
        group = groups.setdefault((c["page"], reason), {"page": c["page"], "reason": reason, "count": 0, "size_min": c["size"],
                                                        "examples": [], "recommendation": RECOMMENDATIONS[reason]})
        group["count"] += 1
        group["size_min"] = min(group["size_min"], c["size"])
        if len(group["examples"]) < HIDDEN_EXAMPLES:
            group["examples"].append(redact(c["text"][:SNIPPET_CHARS]))
            group["text"] = group["examples"][0]
    return sorted(groups.values(), key=lambda g: (g["page"], g["reason"]))


def find_hidden_text(path: Path, min_font_pt: float, min_contrast: float, injection_patterns=()) -> dict:
    """숨김 텍스트 후보. status: ok(없음) | warn(후보 있음) | fail(인젝션·문단 길이 흰 글씨) | skipped(PyMuPDF 없음).

    size는 MuPDF span 크기로 텍스트 행렬(확대·축소 프레임)이 이미 반영된 렌더 크기다.
    """
    fitz = load_pymupdf()
    if fitz is None:
        return {"status": "skipped", "reason": "pymupdf 없음", "count": 0, "items": []}
    candidates, hard = [], 0
    with fitz.open(path) as doc:
        for page in doc:
            pix = None
            for span in page.get_texttrace():
                text = "".join(chr(c[0]) for c in span["chars"]).strip()
                if not text:
                    continue
                reasons = _span_reasons(span, page.rect, min_font_pt)
                if not reasons:
                    if pix is None:
                        pix = page.get_pixmap(matrix=fitz.Matrix(RENDER_ZOOM, RENDER_ZOOM), colorspace=fitz.csRGB, alpha=False)
                    reasons += _contrast_reasons(page, pix, span, text, min_contrast)
                if not reasons:
                    continue
                reason = reasons[0].split("(")[0]
                hard += _is_hard_fail(text, reason, span, injection_patterns)
                candidates.append({"page": page.number + 1, "reason": reason, "size": round(span["size"], 1), "text": text})
    items = _group_candidates(candidates)
    by_reason = Counter()
    for group in items:
        by_reason[group["reason"]] += group["count"]
    status = "fail" if hard else ("warn" if candidates else "ok")
    return {"status": status, "count": len(candidates), "hard_fail": hard, "by_reason": dict(by_reason), "items": items}


def _page_segments(words: list) -> list[str]:
    """같은 줄에서 가로 간격이 작은 단어를 이어 붙인 기하 세그먼트."""
    words = sorted(words, key=lambda w: ((w[1] + w[3]) / 2, w[0]))
    lines: list[list] = []
    for word in words:
        center, height = (word[1] + word[3]) / 2, max(word[3] - word[1], 1)
        if lines and abs(lines[-1][0] - center) <= height * LINE_TOLERANCE_RATIO:
            lines[-1][1].append(word)
        else:
            lines.append([center, [word]])
    segments = []
    for _, line_words in lines:
        line_words.sort(key=lambda w: w[0])
        current = line_words[0][4]
        for prev, word in zip(line_words, line_words[1:]):
            height = max(word[3] - word[1], 1)
            gap = word[0] - prev[2]
            if gap <= height * GAP_JOIN_RATIO:
                current += (" " if gap > height * SPACE_GAP_RATIO else "") + word[4]
            else:
                segments.append(current)
                current = word[4]
        segments.append(current)
    return segments


def find_reading_order_issues(path: Path, default_pages: list[str]) -> dict:
    """숫자가 든 기하 세그먼트가 pdftotext 기본 출력의 같은 쪽에 없는 경우.

    kind=digit_changed: 숫자만 빼면 같은 글이 있다 (예: '관리자 43화면' → '관리자 3화면').
    kind=reordered: 글 자체가 다른 순서로 추출됨.
    """
    fitz = load_pymupdf()
    if fitz is None:
        return {"status": "skipped", "reason": "pymupdf 없음", "count": 0, "items": []}
    found = []
    with fitz.open(path) as doc:
        for page in doc:
            haystack = compact(default_pages[page.number]) if page.number < len(default_pages) else ""
            no_digits = DIGIT_RE.sub("", haystack)
            for segment in _page_segments(page.get_text("words")):
                key = compact(segment)
                if len(key) < READING_MIN_SEGMENT_CHARS or not DIGIT_RE.search(key) or key in haystack:
                    continue
                stripped = DIGIT_RE.sub("", key)
                kind = "digit_changed" if stripped and stripped in no_digits else "reordered"
                found.append({"page": page.number + 1, "kind": kind, "segment": redact(segment)})
    found.sort(key=lambda item: item["kind"] != "digit_changed")
    return {"status": "ok", "count": len(found), "digit_changed": sum(i["kind"] == "digit_changed" for i in found),
            "items": found[:READING_MAX_REPORTED]}


def find_extractor_disagreement(path: Path, default_pages: list[str], min_share: float) -> dict:
    """MuPDF 단어 중 pdftotext 기본 출력에 공백 단위 토큰으로 온전히 있는 비율이 낮은 쪽.

    Poppler가 단어를 쪼개면(Figma 내보내기 등) 다른 파서도 같은 단어를 못 읽을 수 있다.
    """
    fitz = load_pymupdf()
    if fitz is None:
        return {"status": "skipped", "reason": "pymupdf 없음", "pages": [], "count": 0}
    rows = []
    with fitz.open(path) as doc:
        for page in doc:
            tokens = set(unicodedata.normalize("NFC", default_pages[page.number]).split()) if page.number < len(default_pages) else set()
            words = [unicodedata.normalize("NFC", w[4]) for w in page.get_text("words") if len(w[4]) >= EXTRACTOR_MIN_WORD_CHARS]
            if not words:
                continue
            broken = [w for w in words if w not in tokens]
            rows.append({"page": page.number + 1, "share": round(1 - len(broken) / len(words), 4), "words": len(words),
                         "examples": [redact(w) for w in dict.fromkeys(broken)][:EXTRACTOR_EXAMPLES]})
    low = sorted((r for r in rows if r["share"] < min_share), key=lambda r: r["share"])
    return {"status": "ok", "count": len(low), "min_share": min_share, "pages": low[:EXTRACTOR_MAX_PAGES],
            "worst_share": min((r["share"] for r in rows), default=1.0)}


_JAMO_RE = re.compile(r"[ᄀ-ᇿꥠ-꥿ힰ-퟿]")
_COMPAT_JAMO_RE = re.compile(r"[㄰-㆏]")
_PRIVATE_USE_RE = re.compile(r"[-]")
_SPACED_SYLLABLES_RE = re.compile(r"(?<![가-힣])(?:[가-힣] ){4,}[가-힣](?![가-힣])")


def hangul_integrity(text: str) -> dict:
    checks = {
        "decomposed_jamo": len(_JAMO_RE.findall(text)),
        "compatibility_jamo": len(_COMPAT_JAMO_RE.findall(text)),
        "replacement_char": text.count("�"),
        "private_use": len(_PRIVATE_USE_RE.findall(text)),
        "spaced_syllables": len(_SPACED_SYLLABLES_RE.findall(text)),
    }
    return {"ok": not any(checks.values()), **checks}
