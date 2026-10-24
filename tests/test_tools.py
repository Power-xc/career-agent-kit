"""tools/ 의 포트폴리오 PDF 도구 검사 (가짜 PDF만 사용)."""
from __future__ import annotations

import contextlib
import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

try:
    import pymupdf
except ImportError:  # pragma: no cover
    pymupdf = None

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS / "figma"))


def make_pdf(path: Path, pages: int, label: str = "Page") -> None:
    doc = pymupdf.open()
    for number in range(1, pages + 1):
        doc.new_page().insert_text((72, 72), f"{label} {number}")
    doc.save(path)


def page_texts(path: Path) -> list[str]:
    with pymupdf.open(path) as doc:
        return [page.get_text().strip() for page in doc]


def run_tool(script: str, *args: object) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(TOOLS / script), *map(str, args)], capture_output=True, text=True)


@unittest.skipIf(pymupdf is None, "pymupdf 필요")
class PortfolioToolsTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.full = self.tmp / "full.pdf"
        make_pdf(self.full, 6)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_subset_keeps_only_requested_pages_in_order(self) -> None:
        out = self.tmp / "lite.pdf"
        result = run_tool("portfolio_subset.py", self.full, "--pages", "1-2,5", "--out", out)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(page_texts(out), ["Page 1", "Page 2", "Page 5"])

    def test_subset_rejects_out_of_range_pages(self) -> None:
        result = run_tool("portfolio_subset.py", self.full, "--pages", "9", "--out", self.tmp / "x.pdf")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("범위", result.stderr)

    def test_subset_warns_when_over_max_mb_but_still_writes(self) -> None:
        out = self.tmp / "lite.pdf"
        result = run_tool("portfolio_subset.py", self.full, "--pages", "1", "--out", out, "--max-mb", "0.0000001")
        self.assertEqual(result.returncode, 0)
        self.assertTrue(out.is_file())
        self.assertIn("경고", result.stderr)
        quiet = run_tool("portfolio_subset.py", self.full, "--pages", "1", "--out", out, "--max-mb", "10")
        self.assertNotIn("경고", quiet.stderr)

    def test_replace_swaps_only_named_page(self) -> None:
        part = self.tmp / "part.pdf"
        make_pdf(part, 1, label="New")
        out = self.tmp / "replaced.pdf"
        result = run_tool("portfolio_replace.py", "--base", self.full, "--page", f"2={part}", "--out", out)
        self.assertEqual(result.returncode, 0, result.stderr)
        texts = page_texts(out)
        self.assertEqual(len(texts), 6)
        self.assertEqual(texts[1], "New 1")
        self.assertEqual(texts[0], "Page 1")

    def test_recv_server_merge_joins_parts_in_order(self) -> None:
        import recv_server

        first, second = self.tmp / "a.pdf", self.tmp / "b.pdf"
        make_pdf(first, 1, label="A")
        make_pdf(second, 2, label="B")
        out = self.tmp / "merged.pdf"
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(recv_server.merge_pdfs(out, [first, second]), 0)
        self.assertEqual(page_texts(out), ["A 1", "B 1", "B 2"])


if __name__ == "__main__":
    unittest.main()
