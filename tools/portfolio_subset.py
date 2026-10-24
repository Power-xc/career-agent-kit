#!/usr/bin/env python3
"""전체 포트폴리오 PDF에서 지정한 쪽만 뽑아 용량이 작은 lite 버전을 만든다 (링크 주석 유지).

사용: python tools/portfolio_subset.py <full.pdf> --pages 1-3,8,15-20 --out out/base/portfolio_lite.pdf
      --pages를 생략하면 앞 2쪽 + 균등 간격으로 고른 쪽을 합쳐 KEY_PAGE_COUNT쪽을 고른다.
종료 코드: 0 정상, 2 입력·환경 오류. 쪽 번호는 1부터 센다.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    import pymupdf as fitz
except ImportError:
    try:
        import fitz  # 구버전 pymupdf
    except ImportError:
        sys.exit("pymupdf가 필요합니다: pip install pymupdf")

KEY_PAGE_COUNT = 15
KEEP_FIRST_PAGES = 2
MB = 1024 * 1024


def parse_pages(spec: str, total: int) -> list[int]:
    """'1-3,8,15-20' → 0부터 시작하는 쪽 인덱스 목록 (입력 순서 유지, 중복 제거)."""
    pages: list[int] = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            lo, _, hi = part.partition("-")
            start, end = int(lo), int(hi or lo)
        except ValueError:
            sys.exit(f"쪽 범위를 읽을 수 없습니다: '{part}' (예: 1-3,8,15-20)")
        if start < 1 or end < start or end > total:
            sys.exit(f"쪽 범위가 문서 범위(1-{total})를 벗어납니다: '{part}'")
        pages.extend(i for i in range(start - 1, end) if i not in pages)
    if not pages:
        sys.exit("선택된 쪽이 없습니다.")
    return pages


def default_pages(total: int) -> list[int]:
    """앞 쪽 + 나머지에서 균등 간격 표본. 사용자가 --pages로 직접 고르는 것이 더 좋다."""
    head = list(range(min(KEEP_FIRST_PAGES, total)))
    rest = list(range(len(head), total))
    need = max(0, KEY_PAGE_COUNT - len(head))
    if need >= len(rest):
        return head + rest
    step = len(rest) / need
    return head + sorted({rest[int(i * step)] for i in range(need)})


def build_subset(src: Path, pages: list[int], out: Path, title: str | None) -> None:
    doc = fitz.open(src)
    sub = fitz.open()
    for index in pages:
        sub.insert_pdf(doc, from_page=index, to_page=index, links=True, annots=True)
    meta = dict(doc.metadata or {})
    meta.update({"title": title or (meta.get("title") or src.stem) + " (lite)", "keywords": ""})
    sub.set_metadata(meta)
    out.parent.mkdir(parents=True, exist_ok=True)
    sub.save(out, garbage=3, deflate=True)
    sub.close()
    doc.close()


def main() -> int:
    ap = argparse.ArgumentParser(description="포트폴리오 PDF의 일부 쪽으로 lite 버전을 만듭니다.")
    ap.add_argument("pdf", type=Path)
    ap.add_argument("--pages", help="유지할 쪽 (1부터, 예: 1-3,8,15-20)")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--title", help="PDF 제목 메타데이터")
    ap.add_argument("--max-mb", type=float, default=10.0, help="이 용량을 넘으면 경고 (기본 10)")
    args = ap.parse_args()

    if not args.pdf.is_file():
        print(f"파일이 없습니다: {args.pdf}", file=sys.stderr)
        return 2
    try:
        total = fitz.open(args.pdf).page_count
    except Exception as exc:  # pymupdf는 여러 예외 타입을 던진다
        print(f"PDF를 열 수 없습니다: {exc.__class__.__name__}", file=sys.stderr)
        return 2
    pages = parse_pages(args.pages, total) if args.pages else default_pages(total)
    build_subset(args.pdf, pages, args.out, args.title)

    size_mb = args.out.stat().st_size / MB
    print(f"원본 {total}쪽 {args.pdf.stat().st_size / MB:.1f} MB → lite {len(pages)}쪽 {size_mb:.1f} MB")
    print("선택한 쪽: " + ",".join(str(i + 1) for i in pages))
    if size_mb > args.max_mb:
        print(f"경고: {args.max_mb:g} MB를 넘습니다. 쪽을 줄이거나 이미지가 큰 쪽을 빼세요.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
