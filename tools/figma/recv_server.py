#!/usr/bin/env python3
"""Figma 탭에서 보낸 파일 바이트를 받아 out/ 아래에 저장하는 localhost 수신 서버.

사용: python tools/figma/recv_server.py --dir out/<slug> [--port 8765]
      python tools/figma/recv_server.py --merge out/<slug>/resume_ko.pdf out/<slug>/resume_ko_p1.pdf out/<slug>/resume_ko_p2.pdf
127.0.0.1에만 열고, 저장 위치는 현재 폴더(워크스페이스 루트)의 out/ 안으로 제한한다. Origin이 있으면 figma.com 계열만 받는다.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path.cwd().resolve()  # 워크스페이스 루트에서 실행한다
OUT_ROOT = ROOT / "out"
HOST = "127.0.0.1"
DEFAULT_PORT = 8765
MAX_BYTES = 100 * 1024 * 1024
SAFE_NAME = re.compile(r"^[\w.\-]+\.(pdf|png|svg)$")
ALLOWED_ORIGIN = re.compile(r"^https://([\w-]+\.)*figma\.com$")


def make_handler(target_dir: Path):
    class Handler(BaseHTTPRequestHandler):
        def _cors(self) -> None:
            origin = self.headers.get("Origin", "")
            if ALLOWED_ORIGIN.match(origin):
                self.send_header("Access-Control-Allow-Origin", origin)
                self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "Content-Type")
                self.send_header("Access-Control-Allow-Private-Network", "true")

        def _reply(self, code: int, body: dict) -> None:
            data = json.dumps(body, ensure_ascii=False).encode()
            self.send_response(code)
            self._cors()
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_OPTIONS(self) -> None:  # noqa: N802
            self.send_response(204)
            self._cors()
            self.end_headers()

        def do_POST(self) -> None:  # noqa: N802
            origin = self.headers.get("Origin", "")
            if origin and not ALLOWED_ORIGIN.match(origin):
                return self._reply(403, {"error": "허용되지 않은 Origin"})
            name = parse_qs(urlparse(self.path).query).get("name", [""])[0]
            if not SAFE_NAME.match(name):
                return self._reply(400, {"error": "name은 영숫자·_-. 와 pdf/png/svg 확장자만 가능"})
            length = int(self.headers.get("Content-Length") or 0)
            if length <= 0 or length > MAX_BYTES:
                return self._reply(400, {"error": f"본문 크기가 올바르지 않음 (최대 {MAX_BYTES // 1024 // 1024} MB)"})
            target_dir.mkdir(parents=True, exist_ok=True)
            path = target_dir / name
            path.write_bytes(self.rfile.read(length))
            print(f"저장: {path.relative_to(ROOT)} ({length / 1024:.0f} KB)", flush=True)
            self._reply(200, {"saved": str(path.relative_to(ROOT)), "bytes": length})

        def log_message(self, *_args) -> None:  # 요청 로그는 저장 메시지로 대체
            pass

    return Handler


def merge_pdfs(out: Path, parts: list[Path]) -> int:
    try:
        import pymupdf
    except ImportError:
        print("pymupdf가 필요합니다: pip install pymupdf", file=sys.stderr)
        return 2
    missing = [p for p in parts if not p.is_file()]
    if missing:
        print("없는 파일: " + ", ".join(str(p) for p in missing), file=sys.stderr)
        return 2
    merged = pymupdf.open()
    for part in parts:
        with pymupdf.open(part) as doc:
            merged.insert_pdf(doc)
    merged.save(out, garbage=3, deflate=True)
    print(f"합침: {out} ({merged.page_count}쪽)")
    return 0


def resolve_inside_out(path: Path) -> Path:
    resolved = (ROOT / path).resolve() if not path.is_absolute() else path.resolve()
    if OUT_ROOT.resolve() not in resolved.parents and resolved != OUT_ROOT.resolve():
        sys.exit(f"out/ 밖에는 저장하지 않습니다: {path}")
    return resolved


def main() -> int:
    ap = argparse.ArgumentParser(description="Figma 내보내기 수신 서버 / PDF 합치기")
    ap.add_argument("--dir", type=Path, default=OUT_ROOT, help="저장 폴더 (out/ 안)")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--merge", nargs="+", type=Path, metavar=("OUT", "PART"), help="OUT.pdf 뒤에 합칠 PDF를 순서대로")
    args = ap.parse_args()

    if args.merge:
        if len(args.merge) < 2:
            sys.exit("--merge OUT.pdf PART1.pdf [PART2.pdf ...] 형식으로 쓰세요.")
        out, *parts = (resolve_inside_out(p) for p in args.merge)
        return merge_pdfs(out, parts)

    target = resolve_inside_out(args.dir)
    server = HTTPServer((HOST, args.port), make_handler(target))
    print(f"수신 대기: http://{HOST}:{args.port}/save → {target.relative_to(ROOT)} (Ctrl+C로 종료)", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("종료")
    return 0


if __name__ == "__main__":
    sys.exit(main())
