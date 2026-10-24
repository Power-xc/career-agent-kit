"""tools/ 의 포트폴리오 PDF 도구 검사 (가짜 PDF만 사용)."""
from __future__ import annotations

import contextlib
import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from harness.cli import main as cli_main

try:
    import pymupdf
except ImportError:  # pragma: no cover
    pymupdf = None

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS / "figma"))
sys.path.insert(0, str(TOOLS))


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


class RenderResumeWorkspaceTests(unittest.TestCase):
    def test_html_only_reads_profile_of_the_workspace_made_by_onboard(self):
        import os
        import shutil
        fixture = Path(__file__).resolve().parent / "fixtures" / "workspace" / "profile"
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp) / "ws"
            self.assertEqual(0, cli_main(["onboard", str(ws), "--name", "Sample Person"]))
            for name in ("facts.yaml", "resume_master_ko.yaml"):
                shutil.copy(fixture / name, ws / "profile" / name)
            env = {**os.environ, "HARNESS_PYTHON": sys.executable}
            proc = subprocess.run(["bin/kit-python", "tools/render_resume.py", "profile/resume_master_ko.yaml", "--html-only"],
                                  cwd=ws, env=env, capture_output=True, text=True)
            self.assertEqual(0, proc.returncode, proc.stderr)
            html_files = list((ws / "out").rglob("*.html"))
            self.assertEqual(1, len(html_files), proc.stdout)
            self.assertIn("가나다", html_files[0].read_text(encoding="utf-8"))

    def test_chrome_env_var_overrides_lookup(self):
        import os
        import render_resume
        with tempfile.TemporaryDirectory() as tmp:
            fake = Path(tmp) / "chrome"
            fake.write_text("", encoding="utf-8")
            old = os.environ.get("CHROME")
            os.environ["CHROME"] = str(fake)
            try:
                self.assertEqual(str(fake), render_resume.find_chrome())
                os.environ["CHROME"] = str(fake) + "-missing"
                with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                    render_resume.find_chrome()
            finally:
                os.environ.pop("CHROME", None)
                if old is not None:
                    os.environ["CHROME"] = old
