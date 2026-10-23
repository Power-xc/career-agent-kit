"""python -m harness <command>. 종료 코드: 0 정상, 1 high 발견, 2 입력 오류."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

from . import audit as audit_mod
from .claims import claims
from .consistency import check_consistency
from .document import load_document
from .extract import InputError
from .figma_check import check_figma_text
from .gaps import concept_gap_rows
from .jd import parse_jd
from .rules import RuleContext, classify_doc
from .runner import render_summary, run_all, run_corpus, run_exit_code, write_run
from .score import score_resume
from .onboard import onboard
from .targets import merge_targets, render_lines
from .taxonomy import load_taxonomy
from .textio import redact_obj

EXIT_OK, EXIT_FINDINGS, EXIT_INPUT = 0, 1, 2
DEFAULT_RESUME = "profile/resume_master_ko.yaml"
ROOT_MARKER = "profile/facts.yaml"
NO_ROOT_COMMANDS = ("onboard",)


def find_root(start: Path) -> Path:
    for folder in (start, *start.parents):
        if (folder / ROOT_MARKER).is_file():
            return folder
    raise InputError(f"작업 폴더를 찾을 수 없습니다({ROOT_MARKER} 가 있는 상위 폴더). --root 로 지정하세요.")


def _path(root: Path, value: Path) -> Path:
    """cwd 기준으로 먼저 찾고, 없으면 레포 루트 기준."""
    return value if value.exists() or value.is_absolute() else (root / value if (root / value).exists() else value)


def _check_max_mb(args) -> None:
    if args.max_mb is not None and args.max_mb <= 0:
        raise InputError("--max-mb 는 0보다 큰 값이어야 합니다.")


def _cmd_audit(root, args):
    _check_max_mb(args)
    result = audit_mod.run_audit(root, _path(root, args.file), args.kind, args.platform, args.out, args.max_mb)
    return result, EXIT_FINDINGS if result["high_failure"] else EXIT_OK


def _cmd_jd(root, args):
    result = parse_jd(load_taxonomy(), _path(root, args.file))
    result.pop("concept_terms", None)
    return result, EXIT_OK


def _cmd_family(root, args):
    doc = load_document(root, _path(root, args.file))
    return classify_doc(RuleContext(root, doc, "resume")), EXIT_OK


def _cmd_claims(root, args):
    doc = load_document(root, _path(root, args.file))
    result = claims(root, doc, strict=args.strict)
    return result, EXIT_OK if result["ok"] else EXIT_FINDINGS


def _cmd_gaps(root, args):
    taxonomy = load_taxonomy()
    jd = parse_jd(taxonomy, _path(root, args.jd))
    rows = concept_gap_rows(root, taxonomy, jd)
    return {"jd": jd["file"], "gaps": rows, "no_evidence": [r["concept"] for r in rows if r["status"] == "no_evidence"]}, EXIT_OK


def _cmd_consistency(root, args):
    docs = [load_document(root, _path(root, f)) for f in args.files]
    return check_consistency(root, docs), EXIT_OK


def _cmd_score(root, args):
    taxonomy = load_taxonomy()
    jd = parse_jd(taxonomy, _path(root, args.jd))
    resume = load_document(root, _path(root, args.resume))
    portfolio_audit = None
    if args.portfolio:
        portfolio = load_document(root, _path(root, args.portfolio))
        portfolio_audit = audit_mod.audit_document(root, portfolio, "portfolio")
    return score_resume(root, jd, resume, portfolio_audit=portfolio_audit), EXIT_OK


def _cmd_run(root, args):
    _check_max_mb(args)
    portfolio = _path(root, args.portfolio) if args.portfolio else None
    bundle = run_all(root, _path(root, args.jd), _path(root, args.resume), portfolio, args.max_mb, args.out)
    bundle["written"] = write_run(args.out, bundle)
    return bundle, run_exit_code(bundle)


def _cmd_targets(root, args):
    units = [_path(root, unit) for unit in args.units]
    result = merge_targets(root, _path(root, args.resume) if args.resume else root / DEFAULT_RESUME, units)
    if args.out:
        args.out.write_text(json.dumps(redact_obj(result["targets"]), ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    return result, EXIT_OK


def _cmd_onboard(root, args):
    return onboard(args.dest, args.name, args.template_dir), EXIT_OK


def _cmd_figma_check(root, args):
    result = check_figma_text(root, _path(root, args.file))
    return result, EXIT_OK if result["ok"] else EXIT_FINDINGS


def _cmd_corpus(root, args):
    return run_corpus(root, _path(root, args.jd_dir), _path(root, args.resume)), EXIT_OK


COMMANDS = {"audit": _cmd_audit, "jd": _cmd_jd, "family": _cmd_family, "claims": _cmd_claims, "gaps": _cmd_gaps,
            "consistency": _cmd_consistency, "score": _cmd_score, "run": _cmd_run, "corpus": _cmd_corpus,
            "figma-check": _cmd_figma_check, "targets": _cmd_targets, "onboard": _cmd_onboard}


MAX_MB_ARG = (["--max-mb"], {"type": float, "help": "R-SIZE-01 용량 제한(MB)을 플랫폼 값 대신 이 값으로 (회사 조사 파일의 제한)"})


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--root", type=Path, default=argparse.SUPPRESS, help="작업 폴더 (기본: profile/facts.yaml이 있는 상위 폴더)")
    common.add_argument("--json", action="store_true", help="JSON 하나를 표준 출력으로 낸다")
    parser = argparse.ArgumentParser(prog="python -m harness", description="AI 서류 심사 하네스 (코어, 네트워크 미사용)")
    parser.add_argument("--root", type=Path, default=None, help="작업 폴더")
    sub = parser.add_subparsers(dest="command", required=True, metavar="<command>")

    def add(name, help_text, *specs):
        p = sub.add_parser(name, parents=[common], help=help_text)
        for flags, kwargs in specs:
            p.add_argument(*flags, **kwargs)
        return p

    add("audit", "PDF 감사", (["file"], {"type": Path}), (["--kind"], {"choices": ["resume", "portfolio"], "default": "resume"}),
        (["--platform"], {}), (["--out"], {"type": Path}), MAX_MB_ARG)
    add("jd", "공고 파싱", (["file"], {"type": Path}))
    add("family", "직군 신호 분포", (["file"], {"type": Path}))
    add("claims", "근거 없는 숫자·사실 검사", (["file"], {"type": Path}), (["--strict"], {"action": "store_true"}))
    add("gaps", "공고 개념별 근거", (["--jd"], {"type": Path, "required": True}))
    add("consistency", "문서 간 표기 일관성", (["files"], {"type": Path, "nargs": "+"}))
    add("score", "매칭 점수", (["--jd"], {"type": Path, "required": True}), (["--resume"], {"type": Path, "required": True}),
        (["--portfolio"], {"type": Path}))
    add("run", "전체 검사와 report 작성", (["--jd"], {"type": Path, "required": True}), (["--resume"], {"type": Path, "required": True}),
        (["--portfolio"], {"type": Path}), (["--out"], {"type": Path, "required": True}), MAX_MB_ARG)
    add("figma-check", "figma_text.yaml 슬롯 점검", (["file"], {"type": Path}))
    add("corpus", "공고 묶음 점수표", (["--jd-dir"], {"type": Path, "required": True}), (["--resume"], {"type": Path, "required": True}))
    add("targets", "조사한 공고 목록을 합쳐 지원 이력 제외·점수·순위를 낸다", (["units"], {"type": Path, "nargs": "+", "metavar": "unit.yaml"}),
        (["--resume"], {"type": Path, "help": f"기본: {DEFAULT_RESUME}"}), (["--out"], {"type": Path, "help": "순위 JSON 목록을 이 파일에 쓴다"}))
    add("onboard", "새 작업 폴더 만들기", (["dest"], {"type": Path}), (["--name"], {"required": True}),
        (["--template-dir"], {"type": Path}))
    return parser


def _print_human(command: str, result: dict) -> None:
    if command == "figma-check":
        for entry in result["entries"]:
            print(f"{'통과' if entry['ok'] else '위반'}  {entry['id']}" + "".join(f"\n      - {p}" for p in entry["problems"]))
        print(f"슬롯 {result['checked']}개 중 위반 {result['violations']}개")
        return
    if command == "targets":
        print("\n".join(render_lines(result)))
        return
    if command == "onboard":
        print(f"{result['name']} 님의 작업 폴더를 만들었습니다: {result['dest']}\n다음 단계:")
        print("\n".join(f"  {i}. {step}" for i, step in enumerate(result["next_steps"], 1)))
        return
    if command == "run":
        print(render_summary(redact_obj(result)))
        return
    keep = {k: v for k, v in result.items() if k not in ("concept_terms", "sections")} if command == "jd" else result
    print(yaml.safe_dump(redact_obj(keep), allow_unicode=True, sort_keys=False, width=100))


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        root = None if args.command in NO_ROOT_COMMANDS else (args.root or find_root(Path.cwd())).resolve()
        result, code = COMMANDS[args.command](root, args)
    except InputError as exc:
        print(f"입력 오류: {exc}", file=sys.stderr)
        return EXIT_INPUT
    except (OSError, KeyError, ValueError, yaml.YAMLError) as exc:
        print(f"입력 오류: {type(exc).__name__}: {exc}", file=sys.stderr)
        return EXIT_INPUT
    if args.json:
        print(json.dumps(redact_obj(result), ensure_ascii=False, indent=2, default=str))
    else:
        _print_human(args.command, result)
    return code
