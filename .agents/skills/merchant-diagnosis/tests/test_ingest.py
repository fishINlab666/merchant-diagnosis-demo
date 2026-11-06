"""Real-file extraction tests; all materials are synthetic fixtures."""

import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
FIXTURES = Path(__file__).parent / "fixtures"
sys.path.insert(0, str(SCRIPTS))
if (SCRIPTS / "ingest.py").exists():
    import ingest
else:
    ingest = None


class IngestTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(ingest, "原始文件读取器 ingest.py 尚未实现")
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)

    def write(self, name, content):
        path = self.directory / name
        path.write_bytes(content if isinstance(content, bytes) else content.encode("utf-8"))
        return path

    def read_fixture(self, name):
        return ingest.read_material(FIXTURES / name)

    def test_csv_preserves_unknown_headers_notes_and_multiline_fields(self):
        path = self.write("周表.csv", '\ufeff怪名字,未命名字段,备注\n入口甲,90,"首行\n次行"\n备注：已扣退款,,\n')
        material = ingest.read_material(path)
        rows = [json.loads(fragment["text"]) for fragment in material["fragments"]]
        self.assertEqual(rows, [["怪名字", "未命名字段", "备注"], ["入口甲", "90", "首行\n次行"], ["备注：已扣退款", "", ""]])
        self.assertEqual(material["fragments"][2]["locator"], "row:3")

    def test_tsv_preserves_leading_zero_identifiers(self):
        path = self.write("period.tsv", "门店编号\t费用\n001\t0\n")
        material = ingest.read_material(path)
        self.assertEqual(json.loads(material["fragments"][1]["text"]), ["001", "0"])

    def test_text_returns_basename_hash_and_original_line_numbers(self):
        path = self.write("记录.md", "# 合成记录\n\n  顾客说不是配送慢，而是等出餐。  \n")
        material = ingest.read_material(str(path))
        self.assertEqual(set(material), {"name", "sha256", "fragments", "warnings"})
        self.assertEqual(material["name"], "记录.md")
        self.assertEqual(material["sha256"], hashlib.sha256(path.read_bytes()).hexdigest())
        self.assertEqual(material["fragments"][1], {"locator": "line:3", "text": "  顾客说不是配送慢，而是等出餐。  "})
        self.assertNotIn(str(self.directory), json.dumps(material))

    def test_local_html_extracts_visible_text_and_never_script_content(self):
        path = self.write("店铺.html", '<html><head><style>.x {color:red}</style><script>secret_script()</script></head><body><h1>合成店铺</h1><p>不冷，<b>但要等</b>&amp;退款</p><div hidden>隐藏诱导</div><div style="display: none">隐藏指标</div></body></html>')
        material = ingest.read_material(path)
        text = "\n".join(item["text"] for item in material["fragments"])
        for value in ("合成店铺", "不冷，", "但要等", "&退款"):
            self.assertIn(value, text)
        for value in ("secret_script", "隐藏诱导", "隐藏指标", "color:red"):
            self.assertNotIn(value, text)

    @unittest.skipUnless(importlib.util.find_spec("openpyxl"), "XLSX tests require openpyxl")
    def test_real_xlsx_all_sheets_cells_and_formula_cache_are_preserved(self):
        material = self.read_fixture("format_weekly.xlsx")
        fragments = {item["locator"]: item["text"] for item in material["fragments"]}
        self.assertIn("自定义渠道名", fragments["sheet:周报!A1"])
        self.assertIn("未扣商品成本", fragments["sheet:口径说明!B1"])
        formula = json.loads(fragments["sheet:周报!B4"])
        self.assertEqual(formula["formula"], "=SUM(B2:B3)")
        self.assertEqual(formula["cached_value"], 100)
        self.assertTrue(any("缓存" in value for value in material["warnings"]))

    @unittest.skipUnless(importlib.util.find_spec("openpyxl"), "XLSX tests require openpyxl")
    def test_formula_without_cache_is_not_invented(self):
        material = self.read_fixture("format_no_cache.xlsx")
        formula = next(item for item in material["fragments"] if item["locator"] == "sheet:周报!B4")
        self.assertIsNone(json.loads(formula["text"])["cached_value"])
        self.assertTrue(any("无缓存" in value for value in material["warnings"]))

    @unittest.skipUnless(importlib.util.find_spec("openpyxl"), "XLSX tests require openpyxl")
    def test_hidden_sheet_content_is_not_dropped(self):
        material = self.read_fixture("format_hidden.xlsx")
        self.assertTrue(any(item["locator"] == "sheet:口径说明!B2" for item in material["fragments"]))
        self.assertTrue(any("隐藏" in value for value in material["warnings"]))

    @unittest.skipUnless(importlib.util.find_spec("openpyxl"), "XLSX tests require openpyxl")
    def test_incorrect_excel_dimension_does_not_silently_drop_cells(self):
        material = self.read_fixture("format_wrong_dimensions.xlsx")
        self.assertTrue(any(item["locator"] == "sheet:周报!B4" for item in material["fragments"]))

    @unittest.skipUnless(importlib.util.find_spec("openpyxl"), "XLSX tests require openpyxl")
    def test_cell_limit_also_applies_when_xlsx_has_no_dimension_metadata(self):
        with patch.object(ingest, "MAX_XLSX_CELLS", 3):
            with self.assertRaisesRegex(ingest.MaterialError, "超限"):
                self.read_fixture("format_weekly.xlsx")

    @unittest.skipUnless(importlib.util.find_spec("pypdf"), "PDF tests require pypdf")
    def test_real_pdf_extracts_each_page_with_blank_page_warning(self):
        material = self.read_fixture("format_report.pdf")
        fragments = {item["locator"]: item["text"] for item in material["fragments"]}
        self.assertIn("Channel A spend 90", fragments["page:1"])
        self.assertIn("Costs are missing", fragments["page:3"])
        self.assertTrue(any("page:2" in value for value in material["warnings"]))

    @unittest.skipUnless(importlib.util.find_spec("pypdf"), "PDF tests require pypdf")
    def test_image_only_pdf_requires_text_or_ocr_instead_of_success(self):
        with self.assertRaisesRegex(ingest.MaterialError, "文字|OCR"):
            self.read_fixture("format_scan.pdf")

    def test_real_png_is_explicitly_unsupported_with_text_fallback(self):
        with self.assertRaises(ingest.MaterialError) as raised:
            self.read_fixture("format_screenshot.png")
        self.assertRegex(str(raised.exception), "OCR.*未启用")
        self.assertRegex(str(raised.exception), "CSV|文字")

    def test_empty_text_csv_and_html_never_claim_success(self):
        for name, content in [("empty.txt", ""), ("blank.md", " \n\n"), ("empty.csv", ",,\n"), ("hidden.html", "<script>not evidence</script>")]:
            with self.subTest(name=name), self.assertRaises(ingest.MaterialError):
                ingest.read_material(self.write(name, content))

    def test_non_utf8_text_is_explicit_error(self):
        with self.assertRaisesRegex(ingest.MaterialError, "UTF-8"):
            ingest.read_material(self.write("legacy.csv", "门店,金额".encode("gbk")))

    def test_unsupported_format_has_conversion_guidance(self):
        with self.assertRaisesRegex(ingest.MaterialError, "不支持.*xlsx|不支持.*CSV"):
            ingest.read_material(self.write("legacy.xls", b"binary"))

    def test_missing_path_errors_do_not_leak_local_absolute_path(self):
        with self.assertRaises(ingest.MaterialError) as raised:
            ingest.read_material(self.directory / "missing.csv")
        self.assertNotIn(str(self.directory), str(raised.exception))

    def test_invalid_csv_is_not_partially_read(self):
        with self.assertRaises(ingest.MaterialError):
            ingest.read_material(self.write("broken.csv", 'a,b\n"unclosed,b\n'))

    def test_input_byte_limit_is_explicit_not_truncation(self):
        with patch.object(ingest, "MAX_FILE_BYTES", 8):
            with self.assertRaisesRegex(ingest.MaterialError, "超限"):
                ingest.read_material(self.write("large.txt", "123456789"))

    def test_extracted_character_limit_is_explicit_not_truncation(self):
        with patch.object(ingest, "MAX_TEXT_CHARACTERS", 5):
            with self.assertRaisesRegex(ingest.MaterialError, "超限"):
                ingest.read_material(self.write("long.txt", "123456"))

    def test_fragment_limit_is_explicit_not_truncation(self):
        with patch.object(ingest, "MAX_FRAGMENTS", 1):
            with self.assertRaisesRegex(ingest.MaterialError, "超限"):
                ingest.read_material(self.write("rows.txt", "a\nb"))

    def test_corrupt_binary_files_raise_material_error(self):
        for name in ("broken.xlsx", "broken.pdf", "broken.png"):
            with self.subTest(name=name), self.assertRaises(ingest.MaterialError):
                ingest.read_material(self.write(name, b"not a real document"))


if __name__ == "__main__":
    unittest.main()
