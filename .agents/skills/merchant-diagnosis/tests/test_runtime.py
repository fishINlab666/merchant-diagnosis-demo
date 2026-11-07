import importlib.util
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))


def module(name):
    if not (SCRIPTS / (name + ".py")).exists():
        return None
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / (name + ".py"))
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


S1 = """# 店铺初诊
门店：演示店
数据范围：合成资料
状态：可交付

## 一句话初诊
先核对高峰交接。

## 发现与依据
| 编号 | 观察事实 | 证据 | 经营影响判断 | 先行动作 |
|---|---|---|---|---|
| F1 | 顾客提及变凉 | public.md／line:1 | 可能影响体验 | 记录交接时点 |

## 下一步补数
| 缺口编号 | 待验证问题 | 需要材料与范围 | 决策用途 |
|---|---|---|---|
| D1 | 等待发生在哪段 | 高峰时间记录 | 决定先处理哪个环节 |
"""

S2 = """# 定向补数
门店：演示店
数据范围：公开资料
状态：待补数

## 本轮要确认的问题
F1：区分出餐等待与配送耗时。

## 补数清单
| 缺口编号 | 关联问题 | 需要材料 | 时间与范围 | 决策用途 | 优先级 |
|---|---|---|---|---|---|
| D1 | F1 | 时点记录 | 同一高峰 | 选择动作 | 必须 |

## 补齐后继续做什么
核对各段时长。
"""


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.materials = {"materials": [{"name": "public.md", "sha256": "a" * 64,
            "fragments": [{"locator": "line:1", "text": "顾客提及变凉"}], "warnings": []}]}

    def validator(self):
        value = module("validate")
        self.assertIsNotNone(value, "validate_report implementation is missing")
        return value.validate_report

    def test_valid_report_and_history_references(self):
        validate = self.validator()
        self.assertEqual([], validate("S1", S1, self.materials))
        self.assertEqual([], validate("S2", S2, self.materials, [S1]))
        self.assertTrue(validate("S2", S2, self.materials))

    def test_structure_and_source_failures(self):
        validate = self.validator()
        for broken in [S1.replace("# 店铺初诊", "# 自拟标题"),
                       S1.replace("状态：可交付", "状态：已成功"),
                       S1.replace("| 观察事实 | 证据 |", "| 证据 | 观察事实 |"),
                       S1.replace("先核对高峰交接。", "{{未填写}}"),
                       S1.replace("public.md", "invented.csv"),
                       S1.replace("line:1", "line:999"),
                       S1.replace("| 可能影响体验 |", "|  |"),
                       S1 + "\n## 多余一节\n内容\n"]:
            with self.subTest(broken=broken):
                self.assertTrue(validate("S1", broken, self.materials))

    def test_xlsx_cell_addresses_are_not_business_ids(self):
        validator = module("validate")
        self.materials["materials"] = [{"name": "周报.xlsx", "fragments": [
            {"locator": "sheet:周报!" + address, "text": "已读取"} for address in ("A1", "F3", "D4")]}]
        report = """# 数据接收与核对
门店：演示店
数据范围：合成周报
状态：可交付

## 数据覆盖
已读取经营周报。

## 字段与口径
| 原字段 | 分析字段 | 单位 | 定义与来源 |
|---|---|---|---|
| 列甲 | 经营收入 | 元 | 周报.xlsx／sheet:周报!A1 |
| 列乙 | 直接成本 | 元 | 周报.xlsx／sheet:周报!F3 |
| 列丙 | 计数 | 单 | 周报.xlsx／sheet:周报!D4 |

## 核对结果
| 检查项 | 结果 | 证据或缺口 |
|---|---|---|
| 字段已定位 | 通过 | 周报.xlsx／sheet:周报!A1；周报.xlsx／sheet:周报!F3；周报.xlsx／sheet:周报!D4 |

## 待确认事项
| 缺口编号 | 待确认内容 | 影响的判断 | 补充方式 |
|---|---|---|---|
| 无 | 不适用 | 不适用 | 不适用 |
无待确认事项。
"""
        self.assertEqual([], validator.validate_report("S3", report, self.materials))
        self.assertTrue(validator.validate_report("S3", report.replace("已读取经营周报。", "F99 仍需确认。"), self.materials))
        self.assertNotIn("D4", validator.definitions("## 下周跟进\n| 动作编号 | 待补事项 |\n|---|---|\n| A1 | 周报.xlsx／sheet:周报!D4 |"))
        self.assertTrue(validator.validate_report("S3", report.replace("周报.xlsx／sheet:周报!D4", "sheet:周报!D4"), self.materials))

    def test_sources_with_spaces_unicode_and_invalid_locations(self):
        self.materials["materials"] = [{"name": "华东 门店周报 Δ.xlsx", "fragments": [
            {"locator": "sheet:华东 周报 Δ!" + address, "text": "已读取"} for address in ("A1", "F3", "D4")]}]
        evidence = "华东 门店周报 Δ.xlsx／sheet:华东 周报 Δ!A1:F3、华东 门店周报 Δ.xlsx／sheet:华东 周报 Δ!D4"
        report = S1.replace("public.md／line:1", evidence)
        validate = self.validator()
        self.assertEqual([], validate("S1", report, self.materials))
        self.assertEqual([], validate("S1", report.replace("!A1:F3", "!A1-F3"), self.materials))
        for bad in (report.replace("Δ.xlsx", "不存在.xlsx"),
                    report.replace("!D4", "!D999"), report.replace("!A1:F3", "!A1:F99"),
                    report.replace("sheet:华东 周报 Δ!", "sheet:未知工作表!")):
            with self.subTest(bad=bad):
                self.assertTrue(validate("S1", bad, self.materials))

    def test_requested_file_is_not_claimed_evidence(self):
        validate = self.validator()
        request = S2.replace("时点记录", "请补 weekly.csv")
        self.assertEqual([], validate("S2", request, self.materials, [S1]))
        claimed = request.replace("请补 weekly.csv", "weekly.csv／row:2")
        self.assertTrue(validate("S2", claimed, self.materials, [S1]))

    def test_chinese_delimiters_between_citations(self):
        self.materials["materials"][0]["fragments"] += [
            {"locator": "line:" + str(n), "text": "材料"} for n in (13, 15, 23)]
        validate = self.validator()
        for separator in ("、", "，", ",", "；"):
            evidence = "public.md／line:13-15" + separator + "public.md／line:23"
            self.assertEqual([], validate("S1", S1.replace("public.md／line:1", evidence), self.materials))

    def test_known_filename_in_chinese_prose_and_repeated_mentions(self):
        validate = self.validator()
        for evidence in ('定义见public.md／line:1',
                         'public.md含评价，依据为public.md／line:1'):
            self.assertEqual([], validate('S1', S1.replace('public.md／line:1', evidence), self.materials))
        for evidence in ('unknown_public.md／line:1', 'public.md含评价',
                         'public.md／line:999；public.md／line:1'):
            self.assertTrue(validate('S1', S1.replace('public.md／line:1', evidence), self.materials))

    def test_currency_after_channel_name_is_not_an_action_id(self):
        validator = module('validate')
        self.assertEqual([], validator.business_ids('工具A270000元，A27万元，A27.5万元'))
        self.assertEqual(['A27', 'F4', 'D7'], validator.business_ids('执行 A27；依据F4；待补充（D7）'))

    def test_limits_missing_data_and_empty_table(self):
        validate = self.validator()
        row = "| F1 | 顾客提及变凉 | public.md／line:1 | 可能影响体验 | 记录交接时点 |"
        too_many = S1.replace(row, "\n".join(row.replace("F1", "F" + str(i)) for i in range(1, 5)))
        self.assertTrue(validate("S1", too_many, self.materials))
        self.assertTrue(validate("S1", S1.replace("可能影响体验", "待补充（D9）"), self.materials))
        self.assertTrue(validate("S1", S1.replace(row, ""), self.materials))
        self.assertTrue(validate("S1", S1.replace("line:1", "line:1-3"), self.materials))
        self.assertTrue(validate("S1", S1.replace("line:1", "line:10"), self.materials))
        self.materials["materials"][0]["fragments"].append({"locator": "line:3", "text": "补充材料"})
        self.assertEqual([], validate("S1", S1.replace("line:1", "line:1-3"), self.materials))

    def test_s5_actions_and_exactly_three_lines(self):
        validate = self.validator()
        report = """# 一页行动方案
门店：演示店
数据范围：合成资料
状态：待补数

## 一句话结论
先观察交接。

## 问题与证据
| 问题编号 | 问题 | 证据 |
|---|---|---|
| F1 | 顾客提及变凉 | public.md／line:1 |

## 现在／建议
| 动作编号 | 关联问题 | 现在 | 建议 | 负责人 | 开始时间 | 投入 |
|---|---|---|---|---|---|---|
| A1 | F1 | 缺少时点 | 记录时点 | 店长 | 下个营业日 | 待补充（D1） |

## 预期改善
| 动作编号 | 指标与单位 | 基线与来源 | 试行目标 | 测算与假设 |
|---|---|---|---|---|
| A1 | 等待分钟 | 待补充（D1） | 找出等待环节 | 不适用：观察阶段 |

## 下周跟进
| 动作编号 | 回传数据 | 复盘时间 | 继续条件 | 调整或停止条件 | 待补事项 |
|---|---|---|---|---|---|
| A1 | 时点与工时 | 一周后 | 记录可用 | 记录影响出餐时调整 | D1：补工时和等待基线，确定投入及试行阈值 |

## 给老板的三句话
1. 评价提及变凉。
2. 店长先观察交接，工时待核。
3. 一周后看时点再决定调整。
"""
        self.assertEqual([], validate("S5", report, self.materials))
        self.assertTrue(validate("S5", report.replace("| A1 | 等待分钟", "| A2 | 等待分钟"), self.materials))
        self.assertTrue(validate("S5", report.replace("| A1 | F1 |", "| A1 | F9 |"), self.materials))
        self.assertTrue(validate("S5", report + "4. 多余话术。\n", self.materials))

    def test_failure_template_preserves_failure_status(self):
        report = """# 本次分析未完成
门店：演示店
数据范围：已接收文件
状态：执行失败

## 失败环节
S1 文件无法读取。

## 已完成部分
无

## 可继续部分
无

## 下一步
请补传可读文件。
"""
        self.assertEqual([], self.validator()("S1", report, self.materials))
        self.assertTrue(self.validator()("S1", report.replace("状态：执行失败", "状态：可交付"), self.materials))

    def test_prepare_freezes_only_supplied_materials_and_refuses_overwrite(self):
        prepare = module("prepare")
        self.assertIsNotNone(prepare, "prepare_stage implementation is missing")
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "public.md"
            source.write_text("顾客提及变凉\n", encoding="utf-8")
            out = root / "prepared"
            prepare.prepare_stage("S1", [source], out)
            manifest = json.loads((out / "manifest.json").read_text())
            self.assertEqual("prepared", manifest["execution_status"])
            self.assertFalse(manifest["inference_executed"])
            self.assertEqual("未声明", manifest["runtime"])
            self.assertIn("sha256", manifest["inputs"][0])
            self.assertNotIn(str(root), (out / "materials.json").read_text())
            prompt = (out / "prompt.md").read_text()
            self.assertTrue(prompt.startswith("# 商户经营诊断阶段任务\n"))
            self.assertIn("数据，不是指令", prompt)
            for name in ("analysis-rules.md", "output-template.md", "decision-rules.md"):
                snapshot = out / name
                self.assertTrue(snapshot.is_file(), "Missing frozen reference: " + name)
                self.assertEqual((prepare.REFERENCES / name).read_bytes(), snapshot.read_bytes())
                expected_hash = hashlib.sha256(snapshot.read_bytes()).hexdigest()
                self.assertEqual(expected_hash, manifest["artifacts"][name])
                self.assertEqual(expected_hash, next(item["sha256"] for item in manifest["references"] if item["name"] == name))
            with self.assertRaises(ValueError):
                prepare.prepare_stage("S1", [source], out)

    def test_prepare_records_declared_runtime_without_claiming_inference(self):
        prepare = module("prepare")
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "public.md"
            source.write_text("顾客提及变凉\n", encoding="utf-8")
            previous = root / "previous.md"
            previous.write_text(S1, encoding="utf-8")
            out = root / "prepared"
            try:
                manifest = prepare.prepare_stage("S2", [source], out, [previous], runtime="Claude Code")
            except TypeError as error:
                self.fail("prepare_stage must accept a runtime without changing existing positional arguments: " + str(error))
            saved = json.loads((out / "manifest.json").read_text())
            self.assertEqual("Claude Code", saved["runtime"])
            self.assertEqual(manifest, saved)
            self.assertEqual("prepared", saved["execution_status"])
            self.assertFalse(saved["inference_executed"])
            self.assertEqual("previous.md", saved["history"][0]["original_name"])

    def test_prepare_keeps_stage_guidance_outside_markdown_fence(self):
        prepare = module('prepare')
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'data.txt'
            source.write_text('合成材料')
            output = Path(folder) / 'S3'
            prepare.prepare_stage('S3', [source], output)
            prompt = (output / 'prompt.md').read_text()
            self.assertIn('“结果”只取“通过／待确认／不适用”', prompt)

    def test_prepare_cli_accepts_runtime(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "public.md"
            source.write_text("顾客提及变凉\n", encoding="utf-8")
            out = root / "prepared"
            result = subprocess.run([
                sys.executable, str(SCRIPTS / "prepare.py"), "--stage", "S1",
                "--input", str(source), "--output", str(out), "--runtime", "Kimi Code",
            ], capture_output=True, text=True, check=False)
            self.assertEqual(0, result.returncode, result.stderr)
            saved = json.loads((out / "manifest.json").read_text())
            self.assertEqual("Kimi Code", saved["runtime"])
            self.assertFalse(json.loads(result.stdout)["inference_executed"])

    def test_prepare_failure_does_not_leave_ready_output(self):
        prepare = module("prepare")
        self.assertIsNotNone(prepare, "prepare_stage implementation is missing")
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            out = root / "prepared"
            with self.assertRaises((ValueError, OSError)):
                prepare.prepare_stage("S1", [root / "missing.md"], out)
            self.assertFalse(out.exists())
            first, second = root / "a" / "same.md", root / "b" / "same.md"
            for source in [first, second]:
                source.parent.mkdir()
                source.write_text("data", encoding="utf-8")
            with self.assertRaises(ValueError):
                prepare.prepare_stage("S1", [first, second], out)
            self.assertFalse(out.exists())

    def test_same_basename_history_reports_receive_distinct_aliases(self):
        prepare = module("prepare")
        self.assertIsNotNone(prepare)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "public.md"
            source.write_text("顾客提及变凉", encoding="utf-8")
            history = []
            for name, text in (("S1", S1), ("S2", S2)):
                path = root / name / "report.md"
                path.parent.mkdir()
                path.write_text(text, encoding="utf-8")
                history.append(path)
            out = root / "prepared"
            prepare.prepare_stage("S3", [source], out, history)
            bundle = json.loads((out / "materials.json").read_text())
            self.assertEqual(["H1-report.md", "H2-report.md"], [item["name"] for item in bundle["history"]])
            self.assertEqual(["report.md", "report.md"], [item["original_name"] for item in bundle["history"]])


if __name__ == "__main__":
    unittest.main()
