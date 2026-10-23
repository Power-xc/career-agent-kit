import tempfile
import unittest
from datetime import date
from pathlib import Path

from harness import dates
from harness.claims import claims
from harness.document import load_document
from harness.family import classify
from harness.jd import parse_jd
from harness.rules_data import load_scoring
from harness.score import score_resume
from harness.taxonomy import load_taxonomy
from harness.textio import STATED_YEARS_RE, number_tokens

ROOT = Path(__file__).resolve().parent / "fixtures" / "workspace"  # 가상 인물의 작업 폴더
SAMPLE_JD = ROOT / "jd/other/sample-co__senior-product-designer.md"
BASE_RESUME = ROOT / "profile/resume_base.yaml"


def strict_claims(path: Path) -> dict:
    return claims(ROOT, load_document(ROOT, path), strict=True)


class HarnessBehaviorTests(unittest.TestCase):
    def test_number_tokens_keep_units_skip_words_dates_and_compare_by_value(self):
        found = number_tokens("이탈률 36%→6%, 33,094명, 5.54%p, 1인 제작, 2026.07, 26.07, v1.9, 2023년")
        self.assertEqual(["36%", "6%", "33,094명", "5.54%p", "1인"], [t.raw for t in found])
        self.assertEqual(33094, found[2].value)
        self.assertEqual([], number_tokens("B2B NL2SQL GA4 E9PAY 3D S3"))

    def test_strict_claims_flags_invented_number_in_small_variant(self):
        variant = "experience:\n  - ref: exp_now\n    bullets:\n      - {text: '이탈률 40%→10%, 신규 999건', facts: [f_dropoff]}\n"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "variant.yaml"
            path.write_text(variant, encoding="utf-8")
            result = strict_claims(path)
        invented = [i["number"] for i in result["issues"] if i["type"] == "unsupported_number"]
        self.assertEqual(["999건"], invented)
        self.assertFalse(result["ok"])

    def test_strict_claims_passes_base_resume(self):
        result = strict_claims(BASE_RESUME)
        self.assertTrue(result["ok"], result["issues"])

    def test_jd_parsing_finds_minimum_years_and_concepts(self):
        jd = parse_jd(load_taxonomy(), SAMPLE_JD)
        self.assertEqual(7, jd["years_min"])
        self.assertIn("design_system", jd["concepts"]["requirements"])
        self.assertIn("figma", jd["concepts"]["requirements"])

    def test_score_weights_sum_to_one_hundred_and_result_has_band(self):
        self.assertEqual(100, sum(load_scoring()["weights"].values()))
        jd = parse_jd(load_taxonomy(), SAMPLE_JD)
        result = score_resume(ROOT, jd, load_document(ROOT, BASE_RESUME))
        self.assertTrue(result["band"])
        self.assertTrue(0 <= result["total"] <= 100)

    def test_family_ranks_a_target_family_first_for_base_resume(self):
        taxonomy = load_taxonomy()
        result = classify(load_document(ROOT, BASE_RESUME), taxonomy)
        first = result["ranking"][0]["id"]
        self.assertIn(first, taxonomy.target_family_ids())

    def test_total_months_count_inclusive_and_exclude_military_leave(self):
        text = "Experience\n2017.02 – 2021.07\n2021.07 ~ 2023.01 군 복무 휴직\n2023.02 ~ 현재\n"
        dates.set_today(date(2026, 10, 15))
        try:
            summary = dates.summarize(dates.find_ranges(text))
        finally:
            dates.set_today(None)
        self.assertEqual(99, summary["total_months"])
        self.assertEqual([], summary["gaps"])

    def test_stated_years_phrase_survives_line_breaks(self):
        self.assertEqual(["8"], STATED_YEARS_RE.findall("경력 8년의 AI Product Designer"))
        self.assertEqual(["8"], STATED_YEARS_RE.findall("· 경력\n총\n\n8년"))

    def test_hidden_text_detector_flags_white_text_on_white_page(self):
        try:
            import pymupdf as fitz
        except ImportError:
            try:
                import fitz
            except ImportError:
                self.skipTest("PyMuPDF가 없어 건너뜀")
        from harness.pdfchecks import find_hidden_text
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "white.pdf"
            doc = fitz.open()
            page = doc.new_page()
            page.insert_text((72, 100), "visible heading", fontsize=14, color=(0, 0, 0))
            page.insert_text((72, 140), "HIDDEN_TOKEN_TEST", fontsize=14, color=(1, 1, 1))
            doc.save(path)
            doc.close()
            result = find_hidden_text(path, min_font_pt=4, min_contrast=1.5)
        texts = [item["text"] for item in result["items"]]
        self.assertEqual(["HIDDEN_TOKEN_TEST"], texts)


if __name__ == "__main__":
    unittest.main()
