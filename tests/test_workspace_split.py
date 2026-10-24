"""엔진/작업 폴더 분리: targets, onboard, export_kit."""
import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

from harness.cli import find_root, main
from harness.paths import ENGINE_ROOT
from harness.targets import is_excluded, load_exclusions, merge_targets

sys.path.insert(0, str(ENGINE_ROOT / "tools"))
import export_kit  # noqa: E402

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "workspace"
SAMPLE_JD = "jd/other/sample-co__senior-product-designer.md"
RESUME = "profile/resume_master_ko.yaml"


def run_cli(*argv: str) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(list(argv))
    return code, out.getvalue(), err.getvalue()


def applied(company: str, scope: str = "company", aliases: tuple = ()) -> dict:
    return {"company": company, "scope": scope, "aliases": list(aliases)}


class ExclusionTests(unittest.TestCase):
    def test_group_scope_drops_affiliates_by_containment(self):
        self.assertTrue(is_excluded("토스플레이스", [applied("토스", "group")]))
        self.assertTrue(is_excluded("Toss Bank", [applied("토스", "group", ("toss",))]))

    def test_company_scope_matches_exact_name_only(self):
        rules = [applied("카카오", aliases=("kakao corp",))]
        for name in ("카카오", "(주)카카오", "카카오 (본사)", "Kakao Corp"):
            self.assertTrue(is_excluded(name, rules), name)
        for name in ("카카오뱅크", "카카오페이", "카카오페이 (같은 그룹 카카오 지원 이력)"):
            self.assertFalse(is_excluded(name, rules), name)

    def test_note_in_parentheses_does_not_match_the_applied_company(self):
        self.assertFalse(is_excluded("LINE Pay Plus (LINE Plus 그룹)", [applied("LINE Plus")]))

    def test_missing_records_file_means_no_exclusions(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual([], load_exclusions(Path(tmp)))


def make_targets_workspace(tmp: Path, applications: str | None) -> Path:
    root = tmp / "ws"
    (root / "profile").mkdir(parents=True)
    for name in ("facts.yaml", "resume_master_ko.yaml"):
        (root / "profile" / name).write_text((FIXTURE / "profile" / name).read_text(encoding="utf-8"), encoding="utf-8")
    (root / "jd/other").mkdir(parents=True)
    (root / SAMPLE_JD).write_text((FIXTURE / SAMPLE_JD).read_text(encoding="utf-8"), encoding="utf-8")
    if applications is not None:
        (root / "records").mkdir()
        (root / "records/applications.yaml").write_text(applications, encoding="utf-8")
    return root


UNIT = """\
- {company: "지원한회사", role: "PD", verdict: "적합", chance: "상", jd_file: null}
- {company: "낮은회사", role: "x", verdict: "낮음", chance: "하", jd_file: null}
- {company: "중간회사", role: "PD", verdict: "도전", chance: "중", jd_file: null}
- {company: "점수회사", role: "PD", verdict: "적합", chance: "상", jd_file: "jd/other/sample-co__senior-product-designer.md"}
- {company: "점수없음", role: "PD", verdict: "적합", chance: "상", jd_file: null}
"""


class TargetsTests(unittest.TestCase):
    def merge(self, applications: str | None) -> dict:
        with tempfile.TemporaryDirectory() as tmp:
            root = make_targets_workspace(Path(tmp), applications)
            unit = root / "research/targets/unit.yaml"
            unit.parent.mkdir(parents=True)
            unit.write_text(UNIT, encoding="utf-8")
            return merge_targets(root, root / RESUME, [unit])

    def test_ranks_by_chance_then_verdict_then_score_and_drops_applied(self):
        result = self.merge("- {company: 지원한회사}\n")
        self.assertEqual(["점수회사", "점수없음", "중간회사", "낮은회사"], [r["company"] for r in result["targets"]])
        self.assertEqual(["지원한회사"], [e["company"] for e in result["excluded"]])

    def test_role_without_jd_file_stays_unscored_and_scored_role_has_gap_split(self):
        targets = {r["company"]: r for r in self.merge(None)["targets"]}
        self.assertIsNone(targets["점수없음"]["harness"])
        scored = targets["점수회사"]["harness"]
        self.assertTrue(0 < scored["total"] <= 100)
        self.assertEqual(set(scored["missing"]), set(scored["fixable"]) | set(scored["real_gap"]))
        self.assertIn("지원한회사", targets)

    def test_jd_file_relative_to_the_unit_folder_is_scored(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_targets_workspace(Path(tmp), None)
            unit = root / "research/targets/unit.yaml"
            (unit.parent / "jd/other").mkdir(parents=True)
            (unit.parent / SAMPLE_JD).write_text((FIXTURE / SAMPLE_JD).read_text(encoding="utf-8"), encoding="utf-8")
            (root / SAMPLE_JD).unlink()
            unit.write_text(UNIT, encoding="utf-8")
            targets = {r["company"]: r for r in merge_targets(root, root / RESUME, [unit])["targets"]}
            self.assertIsNotNone(targets["점수회사"]["harness"])

    def test_cli_writes_json_with_out(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_targets_workspace(Path(tmp), None)
            unit = root / "research/targets/unit.yaml"
            unit.parent.mkdir(parents=True)
            unit.write_text(UNIT, encoding="utf-8")
            code, out, err = run_cli("--root", str(root), "targets", str(unit), "--out", str(root / "t.json"))
            self.assertEqual(0, code, err)
            self.assertEqual(5, len(json.loads((root / "t.json").read_text(encoding="utf-8"))))
            self.assertIn("점수회사", out)


def make_template(tmp: Path) -> Path:
    template = tmp / "template"
    (template / "profile").mkdir(parents=True)
    (template / "CLAUDE.workspace.md").write_text("# {{name}} 의 작업 폴더\n", encoding="utf-8")
    (template / "gitignore").write_text("out/\n", encoding="utf-8")
    for name in ("facts.example.yaml", "resume_master_ko.example.yaml"):
        (template / "profile" / name).write_text("x: 1\n", encoding="utf-8")
    return template


class OnboardTests(unittest.TestCase):
    def test_creates_workspace_with_renames_links_dirs_and_git(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "ws"
            code, out, _ = run_cli("onboard", str(dest), "--name", "테스터", "--template-dir", str(make_template(Path(tmp))))
            self.assertEqual(0, code)
            self.assertIn("다음 단계", out)
            self.assertEqual("# 테스터 의 작업 폴더\n", (dest / "CLAUDE.md").read_text(encoding="utf-8"))
            self.assertTrue((dest / ".gitignore").is_file() and (dest / "profile/facts.yaml").is_file())
            self.assertFalse((dest / "CLAUDE.workspace.md").exists() or (dest / "gitignore").exists())
            for link in ("bin/harness", ".claude/skills", ".claude/agents"):
                self.assertTrue((dest / link).is_symlink(), link)
                self.assertTrue((dest / link).resolve().exists(), link)
            for folder in ("jd", "companies", "out", "research/targets"):
                self.assertTrue((dest / folder).is_dir(), folder)
            self.assertTrue((dest / ".git").exists())

    def test_refuses_non_empty_destination(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "ws"
            dest.mkdir()
            (dest / "keep.txt").write_text("x", encoding="utf-8")
            code, _, err = run_cli("onboard", str(dest), "--name", "a", "--template-dir", str(make_template(Path(tmp))))
            self.assertEqual(2, code)
            self.assertIn("비어 있지 않은", err)

    def test_find_root_uses_facts_marker_and_names_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(Exception) as ctx:
                find_root(Path(tmp))
            self.assertIn("profile/facts.yaml", str(ctx.exception))
            self.assertEqual(FIXTURE, find_root(FIXTURE / "jd/other"))


class WrapperTests(unittest.TestCase):
    def test_wrapper_runs_from_workspace_through_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "ws"
            run_cli("onboard", str(dest), "--name", "t", "--template-dir", str(make_template(Path(tmp))))
            (dest / "profile/facts.yaml").write_text((FIXTURE / "profile/facts.yaml").read_text(encoding="utf-8"), encoding="utf-8")
            (dest / "jd/s.md").write_text((FIXTURE / SAMPLE_JD).read_text(encoding="utf-8"), encoding="utf-8")
            env = {**os.environ, "HARNESS_PYTHON": sys.executable}
            proc = subprocess.run(["bin/harness", "jd", "jd/s.md", "--json"], cwd=dest, env=env, capture_output=True, text=True)
            self.assertEqual(0, proc.returncode, proc.stderr)
            self.assertEqual(7, json.loads(proc.stdout)["years_min"])

    def test_wrapper_exits_two_with_venv_hint_when_python_cannot_import_harness(self):
        env = {**os.environ, "HARNESS_PYTHON": "/usr/bin/false"}
        proc = subprocess.run([str(ENGINE_ROOT / "bin/harness"), "--help"], env=env, capture_output=True, text=True)
        self.assertEqual(2, proc.returncode)
        self.assertIn(".venv", proc.stderr)


def make_export_fixture(tmp: Path) -> tuple[Path, Path]:
    source = tmp / "source"
    (source / "profile").mkdir(parents=True)
    owner = "Zorbulon Quint"
    facts = {"person": {"name": {"ko": "조르불론", "en": owner}},
             "experience": [{"kind": "job", "company": {"ko": "(주)플럼바고", "en": "Plumbago"}}],
             "projects": [{"name": {"ko": "글림 프로젝트", "en": "Glim"}}],
             "education": [{"school": "벨벳대학교", "school_aliases": []}]}
    (source / "profile/facts.yaml").write_text(yaml.safe_dump(facts, allow_unicode=True), encoding="utf-8")
    (source / "profile/contact.local.yaml").write_text("email: zq@" + "mail.example\nphone: '020-" + "9999-0000'\n", encoding="utf-8")
    (source / "profile/figma_map.yaml").write_text("file_key: ZZKEY12345\n", encoding="utf-8")
    engine = tmp / "engine"
    for rel, body in {"harness/a.py": "x = 1\n", "bin/harness": "#!/bin/sh\n", "rules/r.yaml": "a: 1\n",
                      "tests/test_a.py": "pass\n", "tests/personal/p.py": "플럼바고\n", "tools/figma/f.js": "ZZKEY12345\n",
                      "tools/ok.py": "pass\n", "AGENTS.md": "rules\n", "pyproject.toml": "[x]\n", "docs/contract.md": "c\n",
                      "docs/research/r.md": "플럼바고\n", "profile/facts.yaml": "플럼바고\n", "README.kit.md": "kit\n",
                      "CLAUDE.kit.md": "kit claude\n", "gitignore.kit": "out/\n", "README.md": "owner\n"}.items():
        (engine / rel).parent.mkdir(parents=True, exist_ok=True)
        (engine / rel).write_text(body, encoding="utf-8")
    return source, engine


class ExportKitTests(unittest.TestCase):
    def test_allowlist_copy_renames_and_leaves_personal_paths_out(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, engine = make_export_fixture(Path(tmp))
            dest = Path(tmp) / "kit"
            code, hits = export_kit.export_kit(dest, source, engine)
            self.assertEqual((0, []), (code, hits))
            exported = {p.relative_to(dest).as_posix() for p in dest.rglob("*") if p.is_file()}
            self.assertEqual({"harness/a.py", "bin/harness", "rules/r.yaml", "tests/test_a.py", "tools/ok.py", "AGENTS.md",
                              "pyproject.toml", "docs/contract.md", "README.md", "CLAUDE.md", ".gitignore"}, exported)
            self.assertEqual("kit\n", (dest / "README.md").read_text(encoding="utf-8"))

    def test_scrub_reports_path_line_token_and_exit_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, engine = make_export_fixture(Path(tmp))
            (engine / "tools/ok.py").write_text("pass\n# written by zorbulon quint\nphone 020-" + "9999-0000\n", encoding="utf-8")
            code, hits = export_kit.export_kit(Path(tmp) / "kit", source, engine)
            self.assertEqual(1, code)
            self.assertIn("tools/ok.py:2:Zorbulon Quint", hits)
            self.assertIn("tools/ok.py:3:020-" + "9999-0000", hits)

    def test_tokens_skip_short_and_generic_values_and_refuse_non_empty_dest(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, engine = make_export_fixture(Path(tmp))
            (source / "profile/contact.local.yaml").write_text("email: a\nlabel: Figma\n", encoding="utf-8")
            tokens = export_kit.personal_tokens(source)
            self.assertNotIn("a", tokens)
            self.assertNotIn("Figma", tokens)
            self.assertIn("플럼바고", tokens)
            self.assertIn("ZZKEY12345", tokens)
            busy = Path(tmp) / "busy"
            busy.mkdir()
            (busy / "x").write_text("x", encoding="utf-8")
            with self.assertRaises(ValueError):
                export_kit.export_kit(busy, source, engine)


if __name__ == "__main__":
    unittest.main()
