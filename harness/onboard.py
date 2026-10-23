"""사용자의 작업 폴더(워크스페이스)를 템플릿에서 만든다. 엔진은 심볼릭 링크로 공유한다."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from .extract import InputError
from .paths import ENGINE_ROOT

TEMPLATE_DIR = ENGINE_ROOT / "templates" / "workspace"
RENAMES = {"CLAUDE.workspace.md": "CLAUDE.md", "gitignore": ".gitignore",
           "profile/facts.example.yaml": "profile/facts.yaml",
           "profile/resume_master_ko.example.yaml": "profile/resume_master_ko.yaml"}
NAME_PLACEHOLDER = "{{name}}"
LINKS = {"bin/harness": "bin/harness", ".claude/skills": ".claude/skills", ".claude/agents": ".claude/agents"}
MADE_DIRS = ("jd", "companies", "out", "research/targets")


def _rename(dest: Path) -> None:
    for old, new in RENAMES.items():
        if (dest / old).exists():
            (dest / old).rename(dest / new)


def _link_engine(dest: Path) -> None:
    for link, target in LINKS.items():
        source = ENGINE_ROOT / target
        if not source.exists():
            raise InputError(f"엔진에 {target} 이(가) 없습니다: {source}")
        path = dest / link
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.is_symlink() or path.is_file():
            path.unlink()
        elif path.is_dir():
            shutil.rmtree(path)
        path.symlink_to(source)


def onboard(dest: Path, name: str, template_dir: Path | None = None) -> dict:
    template = (template_dir or TEMPLATE_DIR).resolve()
    if not name.strip():
        raise InputError("--name 에 이름을 넣어 주세요.")
    if not template.is_dir():
        raise InputError(f"템플릿 폴더가 없습니다: {template}")
    if dest.exists() and (not dest.is_dir() or any(dest.iterdir())):
        raise InputError(f"비어 있지 않은 폴더에는 만들 수 없습니다: {dest}")
    shutil.copytree(template, dest, dirs_exist_ok=True)
    _rename(dest)
    claude_md = dest / "CLAUDE.md"
    if claude_md.is_file():
        claude_md.write_text(claude_md.read_text(encoding="utf-8").replace(NAME_PLACEHOLDER, name.strip()), encoding="utf-8")
    _link_engine(dest)
    for folder in MADE_DIRS:
        (dest / folder).mkdir(parents=True, exist_ok=True)
    git = subprocess.run(["git", "init", "-q", str(dest)], capture_output=True, text=True)
    if git.returncode != 0:
        raise InputError(f"git init 실패: {git.stderr.strip()}")
    return {"dest": str(dest.resolve()), "name": name.strip(), "next_steps": [
        f"cd {dest.resolve()}",
        "profile/facts.yaml 을 본인 사실로 채운다 (경력·숫자·스킬은 출처가 있는 것만).",
        "bin/harness jd jd/<공고>.md 로 공고를 읽어 본다.",
    ]}
