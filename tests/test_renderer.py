"""Real layout/parser invariants. All data are synthetic, not course records."""
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/render_report.py"
spec = importlib.util.spec_from_file_location("lab_renderer", SCRIPT)
renderer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(renderer)
HAS_MATH = importlib.util.find_spec("matplotlib") is not None


class RendererTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.source = self.root / "合成验收源稿.md"
        self.pdf = self.root / "合成验收输出.pdf"

    def tearDown(self):
        self.tmp.cleanup()

    def render(self, text):
        self.source.write_text(text, encoding="utf-8")
        renderer.render(self.source, self.pdf)
        return PdfReader(self.pdf)

    def test_chinese_a4_roundtrip_and_source_unchanged(self):
        text = "# 合成验收材料\n\n待补充草稿，全部数值均为模拟。\n\n## 五、数据记录\n\n| 长度 (mm) | 说明 |\n| --- | --- |\n| 1.20 | 保留原始精度 |\n\n结果尚需本人分析。\n"
        pdf = self.render(text)
        self.assertEqual(self.source.read_text(encoding="utf-8"), text)
        extracted = pdf.pages[0].extract_text()
        for term in ["合成验收材料", "待补充草稿", "1.20", "保留原始精度"]:
            self.assertIn(term, extracted)
        self.assertAlmostEqual(float(pdf.pages[0].mediabox.width), renderer.PAGE_WIDTH, places=3)
        self.assertAlmostEqual(float(pdf.pages[0].mediabox.height), renderer.PAGE_HEIGHT, places=3)

    def test_multipage_table_repeats_header_and_keeps_last_row(self):
        rows = [f"| {n:03} | 1.20 | 合成测试记录，绝非真实读数 |" for n in range(1, 101)]
        pdf = self.render("# 模拟表格验收\n\n| 序号 | 长度 (mm) | 说明 |\n| --- | --- | --- |\n" + "\n".join(rows))
        self.assertGreater(len(pdf.pages), 1)
        for page in pdf.pages:
            self.assertIn("长度", page.extract_text())
        self.assertIn("100", pdf.pages[-1].extract_text())

    def test_existing_output_not_overwritten(self):
        self.source.write_text("# 合成测试", encoding="utf-8")
        self.pdf.write_bytes(b"existing-output")
        with self.assertRaisesRegex(renderer.ReportError, "拒绝覆盖"):
            renderer.render(self.source, self.pdf)
        self.assertEqual(self.pdf.read_bytes(), b"existing-output")

    def test_invalid_inputs_never_leave_a_partial_pdf(self):
        cases = [
            "# 模拟\n\n$$\nx^2", "# 模拟\n\n公式 $x",
            "# 模拟\n\n| a | b |\n| --- | --- |\n| one |",
            "# 模拟\n\n  - 嵌套项目", "# 模拟\n\n<script>bad</script>",
            "# 模拟\n\n![远程图](https://example.invalid/test.png)",
            "# 模拟\n\n![丢失图](not-found.png)",
        ]
        for text in cases:
            with self.subTest(text=text):
                self.source.write_text(text, encoding="utf-8")
                with self.assertRaises((renderer.ReportError, ValueError)):
                    renderer.render(self.source, self.pdf)
                self.assertFalse(self.pdf.exists())

    def test_missing_glyph_is_detected(self):
        with self.assertRaisesRegex(renderer.ReportError, "缺少字符"):
            self.render("# 模拟\n\n\U0010ffff")
        self.assertFalse(self.pdf.exists())

    def test_math_dependency_failure_is_explicit(self):
        if HAS_MATH:
            self.skipTest("MathText 已安装，单独验证实际公式")
        with self.assertRaisesRegex(renderer.ReportError, "缺少 matplotlib"):
            self.render("# 模拟\n\n$$\nx^2\n$$")
        self.assertFalse(self.pdf.exists())

    @unittest.skipUnless(HAS_MATH, "当前环境无 Matplotlib，尚待公式渲染验收")
    def test_math_fraction_subscript_and_greek(self):
        pdf = self.render("# 公式合成验收\n\n内联 $x_i^2$，独立公式如下。\n\n$$\nu_A=\\frac{\\sigma_x}{\\sqrt{n}}\n$$")
        resources = pdf.pages[0]["/Resources"]
        self.assertIn("/XObject", resources)
        self.assertGreaterEqual(len(resources["/XObject"]), 2)

    @unittest.skipUnless(HAS_MATH, "当前环境无 Matplotlib")
    def test_unsupported_math_fails_without_partial_output(self):
        with self.assertRaises(renderer.ReportError):
            self.render("# 模拟\n\n$$\n\\notasupportedcommand{x}\n$$")
        self.assertFalse(self.pdf.exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
