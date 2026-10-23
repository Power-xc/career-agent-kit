"""h-fix-core: 첫 end-to-end 실행에서 나온 버그의 회귀 테스트."""
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from harness.cli import main
from harness.document import load_document
from harness.runner import run_exit_code
from harness.pdfchecks import find_extractor_disagreement, find_hidden_text
from harness.textio import number_tokens

ROOT = Path(__file__).resolve().parent / "fixtures" / "workspace"  # 가상 인물의 작업 폴더
DETECTOR_FILLER = "QZXQZXQZXQZXQZXQZXQZXQZXQZXQZXQZXQZXQZXQZX"  # 탐지기 테스트용 의미 없는 문자열
JD_UNQUOTED_DATE = "---\ncompany: 테스트사\ntitle: Product Designer\naccessed: 2026-10-23\n---\n## 자격 요건\n- 경력 5년 이상\n"


def run_cli(*argv: str) -> tuple[int, str]:
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
        code = main(["--root", str(ROOT), *argv])
    return code, out.getvalue()


def fitz_module():
    try:
        import pymupdf as fitz
    except ImportError:
        try:
            import fitz
        except ImportError:
            raise unittest.SkipTest("PyMuPDF가 없어 건너뜀")
    return fitz


def make_pdf(path: Path, draw) -> Path:
    doc = fitz_module().open()
    draw(doc.new_page())
    doc.save(path)
    doc.close()
    return path


class FrontMatterDateTests(unittest.TestCase):
    def test_jd_with_unquoted_date_exits_zero_and_date_is_iso_string(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "co__pd.md"
            path.write_text(JD_UNQUOTED_DATE, encoding="utf-8")
            code, out = run_cli("jd", str(path), "--json")
        self.assertEqual(0, code)
        self.assertEqual("2026-10-23", json.loads(out)["meta"]["accessed"])


class ExtractorAgreementTests(unittest.TestCase):
    def share(self, path: Path) -> float:
        fitz_module()
        doc = load_document(ROOT, path)
        return find_extractor_disagreement(path, doc.pages, 0.95)["worst_share"]

    def test_plain_text_pdf_has_full_agreement(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = make_pdf(Path(tmp) / "plain.pdf", lambda page: page.insert_text((72, 100), "Plain heading words stay whole", fontsize=14))
            self.assertEqual(1.0, self.share(path))


class HiddenTextGroupingTests(unittest.TestCase):
    def hidden(self, draw) -> dict:
        with tempfile.TemporaryDirectory() as tmp:
            return find_hidden_text(make_pdf(Path(tmp) / "h.pdf", draw), 4, 1.5)

    def test_clean_page_is_ok_without_candidates(self):
        result = self.hidden(lambda page: page.insert_text((72, 100), "Visible heading", fontsize=14))
        self.assertEqual(("ok", 0), (result["status"], result["count"]))

    def test_many_tiny_spans_on_one_page_group_as_mockup_text_warning(self):
        def draw(page):
            for i in range(25):
                page.insert_text((72, 40 + i * 12), f"label {i}", fontsize=3)
        result = self.hidden(draw)
        self.assertEqual("warn", result["status"])
        self.assertEqual([("mockup_text", 25)], [(g["reason"], g["count"]) for g in result["items"]])
        self.assertIn("이미지로 평탄화", result["items"][0]["recommendation"])

    def test_paragraph_sized_white_text_is_a_hard_fail(self):
        result = self.hidden(lambda page: page.insert_text((72, 140), DETECTOR_FILLER, fontsize=14, color=(1, 1, 1)))
        self.assertEqual("fail", result["status"])


class PdfClaimTextTests(unittest.TestCase):
    def test_pdf_claims_use_mupdf_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = make_pdf(Path(tmp) / "c.pdf", lambda page: page.insert_text((72, 100), "Worked 2023.02 to 2024.03 on tools", fontsize=12))
            doc = load_document(ROOT, path)
        self.assertEqual("\n".join(doc.mupdf_pages), doc.claim_text)
        self.assertIn("2023.02", doc.claim_text)


BULLET_TEXT = """경력

Senior Product Designer

(주)테스트 디자인팀 · 책임 · 2026.07 – 현재

• 첫 번째 성과 문장은 줄 끝까지 차서 다음 줄로 넘어가는 긴 문장입니다 이어 붙어야 합니다
뒤따르는 이어진 줄
• 짧지만 열다섯 글자를 넘는 두 번째 문장
• 육군 병장 만기전역 · 재직 중 휴직 항목
"""


class BulletDetectionTests(unittest.TestCase):
    def test_marker_lines_start_bullets_wrapped_lines_join_and_titles_and_leave_are_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "resume.txt"
            path.write_text(BULLET_TEXT, encoding="utf-8")
            bullets = load_document(ROOT, path).bullets
        self.assertEqual(2, len(bullets))
        self.assertTrue(bullets[0].endswith("이어 붙어야 합니다 뒤따르는 이어진 줄"))
        self.assertFalse(any(b.startswith("•") for b in bullets))


class RunAndSizeTests(unittest.TestCase):
    def pdf(self, tmp: str, name: str = "r.pdf") -> Path:
        return make_pdf(Path(tmp) / name, lambda page: page.insert_text((72, 100), "Senior Product Designer 경력 8년", fontsize=14))

    def test_run_exit_code_is_one_when_only_the_portfolio_audit_has_a_high_failure(self):
        ok = {"high_failure": False}
        bundle = {"audit": ok, "claims": {"ok": True}, "portfolio_audit": {"high_failure": True}}
        self.assertEqual(1, run_exit_code(bundle))
        self.assertEqual(0, run_exit_code({**bundle, "portfolio_audit": ok}))

    def test_max_mb_overrides_platform_limit_and_says_so(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, out = run_cli("audit", str(self.pdf(tmp)), "--max-mb", "0.000001", "--json")
        rule = next(r for r in json.loads(out)["rules"] if r["id"] == "R-SIZE-01")
        self.assertEqual("fail", rule["status"])
        self.assertIn("--max-mb", rule["message"])

    def test_run_writes_redacted_default_and_mupdf_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "out"
            code, _ = run_cli("run", "--jd", str(ROOT / "jd/other/sample-co__senior-product-designer.md"),
                              "--resume", str(self.pdf(tmp)), "--out", str(out_dir))
            names = sorted(p.name for p in out_dir.iterdir())
        self.assertIn(code, (0, 1))
        self.assertIn("text_default.txt", names)
        self.assertIn("text_mupdf.txt", names)


class FigmaCheckTests(unittest.TestCase):
    def check(self, body: str) -> tuple[int, dict]:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "figma_text.yaml"
            path.write_text(body, encoding="utf-8")
            code, out = run_cli("figma-check", str(path), "--json")
        return code, json.loads(out)

    def test_valid_slot_passes(self):
        code, result = self.check('slots:\n  - {id: resume.header.title, text: "Senior Product Designer · 경력 8년", facts: [f_years], reason: r}\n')
        self.assertEqual((0, True), (code, result["ok"]))

    def test_overlong_split_word_unknown_fact_and_unsupported_number_are_reported(self):
        long_title = "Senior Product Designer " * 3 + "이탈률 99%"
        body = (f'slots:\n  - {{id: resume.header.title, text: "{long_title}", facts: [f_years], reason: r}}\n'
                '  - {id: resume.about.lead, text: "Human-in-the-\\u2028Loop", facts: [f_nope], reason: r}\n')
        code, result = self.check(body)
        problems = " ".join(p for e in result["entries"] for p in e["problems"])
        self.assertEqual(1, code)
        for expected in ("상한 50자", "99%", "하이픈", "f_nope"):
            self.assertIn(expected, problems)

    def test_missing_file_is_an_input_error(self):
        code, _ = run_cli("figma-check", "/nonexistent/figma_text.yaml")
        self.assertEqual(2, code)



class PortfolioClaimTests(unittest.TestCase):
    def truth_rule(self, page_texts: list[str]) -> dict:
        fitz = fitz_module()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "p.pdf"
            doc = fitz.open()
            for text in page_texts:
                doc.new_page().insert_text((72, 100), text, fontsize=12)
            doc.save(path)
            doc.close()
            _, out = run_cli("audit", str(path), "--kind", "portfolio", "--json")
        return next(r for r in json.loads(out)["rules"] if r["id"] == "R-TRUTH-03")

    def test_unsupported_number_on_a_page_the_harness_edits_fails(self):
        self.assertEqual("fail", self.truth_rule(["Handled 777 cases", "Cover", "Case"])["status"])

    def test_unsupported_number_only_on_other_pages_warns(self):
        self.assertEqual("warn", self.truth_rule(["Cover", "Profile", "Handled 777 cases"])["status"])

    def test_node_ids_phone_and_resident_number_shapes_are_not_claims(self):
        sample_phone, sample_rrn = "010-" + "1234-5678", "900101-" + "1234567"  # 패턴 검사기에 걸리지 않게 나눠 쓴 예시 값
        text = f"Figma 848:11605 / {sample_phone} / {sample_rrn} / 36%"
        self.assertEqual(["36%"], [token.raw for token in number_tokens(text)])

if __name__ == "__main__":
    unittest.main()
