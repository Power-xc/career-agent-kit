#!/usr/bin/env python3
"""엔진을 allowlist로 복사해 배포용 키트 폴더를 만든다 (개인 데이터 없음, 새 git 이력).

사용: python tools/export_kit.py <dest> [--source <작업 폴더>]
종료 코드: 0 정상, 1 개인 토큰 발견(경로:줄:토큰 출력), 2 입력 오류.

내보내는 것: harness/ bin/ rules/ taxonomy/ templates/ tools/ tests/ .claude/skills .claude/agents AGENTS.md
  pyproject.toml LICENSE docs/contract.md docs/company-research.md docs/assets, 그리고 README.kit.md→README.md,
  CLAUDE.kit.md→CLAUDE.md, gitignore.kit→.gitignore.
내보내지 않는 것: profile/ jd/ companies/ out/ records/ research/ docs/research/ README.md CLAUDE.md, tests/personal/.

tools/ 에서 뺀 개인용 사본: tools/figma/, tools/portfolio_replace.py, tools/portfolio_subset.py.
  키트는 같은 이름의 범용 버전을 따로 싣는다. 범용 버전은 파일 키와 노드 id를 profile/figma_map.yaml과
  명령줄 인자(ARGS)에서 읽는다.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

import yaml

ENGINE_ROOT = Path(__file__).resolve().parents[1]
EXIT_OK, EXIT_HITS, EXIT_INPUT = 0, 1, 2
ALLOW_DIRS = ("harness", "bin", "rules", "taxonomy", "templates", "tools", "tests", ".claude/skills", ".claude/agents",
              "docs/assets")
ALLOW_FILES = ("AGENTS.md", "pyproject.toml", "LICENSE", "docs/contract.md", "docs/company-research.md")
EXCLUDE = ("tests/personal", "tools/figma", "tools/portfolio_replace.py", "tools/portfolio_subset.py",
           "__pycache__", ".pytest_cache", ".venv", ".DS_Store")
RENAMES = {"README.kit.md": "README.md", "CLAUDE.kit.md": "CLAUDE.md", "gitignore.kit": ".gitignore"}
SCANNED_SUFFIXES = {".py", ".md", ".yaml", ".yml", ".json", ".toml", ".txt", ".js", ".mjs", ".css", ".html", ".sh", ""}
MIN_TOKEN_CHARS = 2
GENERIC_TOKENS = {"ko", "en", "none", "null", "true", "false", "yes", "no", "email", "phone", "name",
                  "company", "school", "design", "designer", "product", "figma", "github", "linkedin"}


def _scalars(node) -> list[str]:
    if isinstance(node, dict):
        return [s for value in node.values() for s in _scalars(value)]
    if isinstance(node, list):
        return [s for value in node for s in _scalars(value)]
    return [] if node is None or isinstance(node, bool) else [str(node)]


def _load(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8")) if path.is_file() else None


def personal_tokens(source: Path) -> list[str]:
    """작업 폴더의 사실 은행·연락처·Figma 지도에서 개인을 가리키는 값을 모은다."""
    facts = _load(source / "profile/facts.yaml") or {}
    raw = _scalars((facts.get("person") or {}).get("name"))
    for exp in facts.get("experience") or []:
        if exp.get("kind") == "job":
            raw += _scalars(exp.get("company"))
    for project in facts.get("projects") or []:
        raw += _scalars(project.get("name"))
    for edu in facts.get("education") or []:
        raw += _scalars([edu.get("school"), edu.get("school_aliases")])
    raw += _scalars(_load(source / "profile/contact.local.yaml"))
    figma = _load(source / "profile/figma_map.yaml") or {}
    raw += _scalars(figma.get("file_key"))
    tokens = {t.strip() for t in raw}
    tokens = {t.replace("(주)", "").strip() for t in tokens} | tokens
    return sorted(t for t in tokens if len(t) >= MIN_TOKEN_CHARS and t.casefold() not in GENERIC_TOKENS)


def _excluded(rel: str) -> bool:
    parts = rel.split("/")
    return any(rel == e or rel.startswith(e + "/") or e in parts for e in EXCLUDE)


def copy_allowlist(engine: Path, dest: Path) -> list[Path]:
    copied = []
    for item in ALLOW_DIRS + ALLOW_FILES:
        src = engine / item
        if not src.exists() and not src.is_symlink():
            continue
        for path in ([src] if src.is_file() else sorted(p for p in src.rglob("*") if p.is_file())):
            rel = path.relative_to(engine).as_posix()
            if _excluded(rel):
                continue
            target = dest / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
            copied.append(target)
    for old, new in RENAMES.items():
        for src in (engine / old, engine / "templates" / old):
            if src.is_file():
                shutil.copy2(src, dest / new)
                copied.append(dest / new)
                break
    return copied


def scrub(files: list[Path], dest: Path, tokens: list[str]) -> list[str]:
    """내보낸 파일에서 개인 토큰이 보이는 곳을 "경로:줄:토큰"으로 모은다 (대소문자 무시)."""
    hits = []
    lowered = [(t, t.casefold()) for t in tokens]
    for path in files:
        if path.suffix not in SCANNED_SUFFIXES:
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (UnicodeDecodeError, OSError):
            continue
        for number, line in enumerate(lines, 1):
            low = line.casefold()
            hits += [f"{path.relative_to(dest).as_posix()}:{number}:{token}" for token, key in lowered if key in low]
    return hits


def export_kit(dest: Path, source: Path, engine: Path = ENGINE_ROOT) -> tuple[int, list[str]]:
    if dest.exists() and (not dest.is_dir() or any(dest.iterdir())):
        raise ValueError(f"비어 있지 않은 폴더에는 내보낼 수 없습니다: {dest}")
    dest.mkdir(parents=True, exist_ok=True)
    files = copy_allowlist(engine, dest)
    hits = scrub(files, dest, personal_tokens(source))
    return (EXIT_HITS if hits else EXIT_OK), hits


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="엔진 allowlist를 배포용 키트 폴더로 내보낸다")
    parser.add_argument("dest", type=Path)
    parser.add_argument("--source", type=Path, default=ENGINE_ROOT, help="개인 토큰을 읽을 작업 폴더 (기본: 엔진 루트)")
    args = parser.parse_args(argv)
    try:
        code, hits = export_kit(args.dest, args.source)
    except (ValueError, OSError, yaml.YAMLError) as exc:
        print(f"입력 오류: {exc}", file=sys.stderr)
        return EXIT_INPUT
    for hit in hits:
        print(hit)
    print(f"키트를 만들었습니다: {args.dest}" if not hits else f"개인 토큰 {len(hits)}건 발견: 위 경로를 고치세요 (키트는 {args.dest}에 만들어졌습니다).")
    return code


if __name__ == "__main__":
    sys.exit(main())
