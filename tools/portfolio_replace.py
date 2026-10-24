#!/usr/bin/env python3
"""전체 포트폴리오 PDF에서 몇 쪽만 새로 내보낸 PDF로 바꿔 끼운다 (Figma 슬롯을 고친 슬라이드만 다시 내보낸 경우).

사용: bin/kit-python tools/portfolio_replace.py --base <기준 전체 포트폴리오.pdf> \\
          --page 1=out/example-co/portfolio_s01.pdf --page 2=out/example-co/portfolio_s02.pdf --out out/example-co/portfolio_example-co.pdf
--base는 profile/figma_map.yaml의 portfolio.base_pdf 값을 쓴다. --page 쪽 번호는 portfolio.replaces 값이다.
바꿔 끼운 쪽의 링크는 지운다 (기준 PDF를 만들 때처럼 슬라이드 링크는 남기지 않는다). 다른 쪽과 메타데이터는 그대로 둔다.
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

MB = 1024 * 1024


def parse_replacement(spec: str) -> tuple[int, Path]:
    number, sep, path = spec.partition("=")
    if not sep or not number.strip().isdigit():
        sys.exit(f"--page 형식은 '쪽번호=파일.pdf'입니다: '{spec}'")
    src = Path(path).expanduser()
    if not src.is_file():
        sys.exit(f"바꿔 끼울 PDF가 없습니다: {src}")
    return int(number), src


def main() -> int:
    ap = argparse.ArgumentParser(description="포트폴리오 PDF의 일부 쪽을 새 PDF로 바꿔 끼웁니다.")
    ap.add_argument("--base", required=True, type=Path, help="기준 전체 포트폴리오 PDF")
    ap.add_argument("--page", action="append", required=True, help="'쪽번호=한 쪽짜리 PDF' (여러 번 가능)")
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()

    base_path = args.base.expanduser()
    if not base_path.is_file():
        sys.exit(f"기준 PDF가 없습니다: {base_path}")
    base = fitz.open(base_path)
    replacements = dict(parse_replacement(s) for s in args.page)
    for number in replacements:
        if not 1 <= number <= base.page_count:
            sys.exit(f"쪽 번호가 문서 범위(1-{base.page_count})를 벗어납니다: {number}")

    # 새 문서에 쪽을 차례로 붙인다 (delete_page 뒤 저장하면 끊긴 참조로 실패한다)
    doc = fitz.open()
    for number in range(1, base.page_count + 1):
        src = replacements.get(number)
        if src is None:
            doc.insert_pdf(base, from_page=number - 1, to_page=number - 1)
            continue
        with fitz.open(src) as part:
            if part.page_count != 1:
                sys.exit(f"한 쪽짜리 PDF만 바꿔 끼울 수 있습니다: {src} ({part.page_count}쪽)")
            doc.insert_pdf(part)
        page = doc[number - 1]
        for link in page.get_links():
            page.delete_link(link)
    doc.set_metadata(base.metadata)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    doc.save(args.out, garbage=4, deflate=True)  # clean=True는 이미 정리된 기준 PDF를 다시 저장할 때 실패한다
    size = args.out.stat().st_size
    print(f"저장: {args.out} ({doc.page_count}쪽, {size / MB:.1f} MB, 바꾼 쪽 {sorted(replacements)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
