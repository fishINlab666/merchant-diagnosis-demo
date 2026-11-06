# 将分析交付为独立网页

先由实际 Agent 完成分析、计算、结构检查和业务复核，再用本地导出器呈现已有结果。导出命令不调用模型、不重新诊断、不执行商家动作，也不需要网页服务器或 API 密钥。

## 输入与命令

运行目录沿用 `S1/report.md` 至 `S5/report.md`。可以只有 S1，也可以直接从 S3 开始；导出器仅展示实际存在的阶段，不补造公开初诊或客户补数经历。各报告需保留输出协议 1.0 的标题、门店、数据范围、状态和正文。

在配置文件中明确列出本次要展示的商家和分析版本。以下路径为用法示例，应替换成自己的已有运行目录；所有相对路径都以配置文件所在目录为基准，与执行命令时的目录无关。

```json
{
  "title": "商户经营诊断",
  "cases": [
    {
      "id": "store-a",
      "title": "本次商家经营诊断",
      "label": "门店经营",
      "synthetic": false,
      "active_version": "current",
      "versions": [
        {
          "id": "current",
          "label": "本次分析",
          "run_dir": "runs/store-a"
        }
      ]
    }
  ]
}
```

在 Skill 目录运行：

```sh
python3 scripts/export_report.py --config catalog.json --output report.html
```

生成三个文件：

| 文件 | 用途 |
|---|---|
| `report.html` | 可直接打开、离线查看和分享的单文件网页；样式、交互与报告数据内嵌 |
| `report.json` | 同一份结构化展示数据，保留原始 Markdown、阶段顺序与指纹 |
| `report.manifest.json` | 导出来源与产物指纹，明确标记 `inference_executed: false` |

每次优先使用新输出文件名。默认拒绝覆盖其中任一现有文件；显式加 `--force` 仅可覆盖本工具生成、三份文件完整且 HTML／JSON 指纹未被外部修改的导出。参数、输入或模板校验失败时不写半份结果。多个文件的写入不是跨文件系统事务；普通写入异常会尝试回滚，进程被强制终止或磁盘故障仍需检查三个文件及指纹。

## 多版本和多商家

一个 `cases` 可以有多个商家；每个商家的 `versions` 可以包含初次分析、更正材料后的分析及后续复盘。不同商家的版本和指标相互独立。

- 每层 `id` 须唯一，只包含字母、数字、下划线、点或连字符，不使用路径分隔符。
- `active_version` 未指定时，默认最后列出的版本；指定不存在的版本会报错。
- 已被后续材料替换的版本显式写 `"superseded": true`，不删除旧报告，也不把旧正向收益用于新版本。
- `synthetic` 必须为布尔值，模拟材料显式写 `true`。缺省为 `false` 仅表示没有声明为合成，不构成真实商家数据或执行效果验收。
- `run_dir` 下优先读取 `execution.json`，不存在时才读取 `S5/execution.json` 中实际记录的 `executor` 和 `model_id`；缺记录显示“未记录”。准备清单中的宿主名称不作为已运行推理的证据。

## 可选经营看板数据

版本可增加 `"view_file": "views/current.json"`。该文件由本次分析执行者根据已有报告与计算整理；它不属于通用诊断规则，不能让渲染器根据品牌名套用数字。没有它仍能展示完整报告，图表区为空。

```json
{
  "highlights": [
    {
      "label": "待确认经营贡献",
      "value": null,
      "unit": "元",
      "note": "缺少对应成本，补齐后计算",
      "evidence": "本次周报.xlsx／sheet:经营数据!B3"
    }
  ],
  "charts": [
    {
      "id": "contribution",
      "type": "bars",
      "title": "经营贡献",
      "unit": "元",
      "caption": "示意结构；实际数值须来自本次计算",
      "series": [
        {"label": "待核门店", "value": null}
      ],
      "evidence": "本次周报.xlsx／sheet:经营数据!B3"
    }
  ]
}
```

`highlights.value`、`series.value` 只接受有限数值或明确的 `null`，拒绝字符串数字、布尔值、NaN 和无穷值。真实零、负值与未知值分别保留。图表类型为 `bars`、`stacked`、`waterfall`；序列可以另有文字型 `group` 和 `role`。每个指标与图表都须提供非空 `evidence` 字符串，通常为材料名、原始定位和相关口径。

导出器只检查这些字段的类型及来源文字是否填写，不自动证明数值、因果判断、引用含义或测算假设正确。交付前应将展示数字逐项与实际报告、计算结果核对；图表不能遗漏费用、负面情景、缺成本和试点范围。

## 前端数据协议 1.0

顶层为 `schema_version`、`title`、`cases`。商家包含 `id`、`title`、`label`、`synthetic`、`active_version`、`versions`。版本包含：

- `id`、`label`、`superseded`；
- 最新实际阶段的 `merchant`、`status`、`scope`；
- 实际运行记录中的 `executor`、`model_id`；
- `summary`：S5 的“一句话结论”；没有 S5 时使用最新阶段的首个正文段落；
- `takeaways`：S5“给老板的三句话”的列表；未生成时为空；
- `stages`：按 S1 至 S5 排列的实际阶段，每个阶段含 `stage`、`title`、`metadata`、`blocks`、`markdown`、`sha256`；
- `visuals`：`highlights` 和 `charts`；
- `sources`：已冻结材料的文件名与 SHA-256，保留同名不同指纹的版本，不包含原始材料正文。

`blocks` 按原文顺序保存：`heading` 与 `paragraph` 使用 `text`；`table` 使用 `headers`、`rows`；`list` 使用 `items`。表格前后段落同样属于结果，尤其是月度公式、费用包含关系、适用范围及未知执行状态，不能只渲染表格而丢掉这些内容。原始 Markdown 保留用于回查。

前端必须用 `textContent` 等文本方式插入报告字段，不能把材料或 Markdown 当作可执行 HTML。内嵌 JSON 已对 `<`、`>`、`&`、U+2028、U+2029 转义，避免内容闭合 script 标签。导出器读取 Skill 自带的 `assets/report.html`、`report.css`、`report.js`；HTML 模板须分别包含一次 `__REPORT_CSS__`、`__REPORT_JS__`、`__REPORT_DATA__` 标记。

## 可分享范围与验证

网页包含报告中已经写出的商家名称、业务数字、来源文件名及定位；分享前按商家授权与脱敏范围检查。导出器不嵌入整份原始表、模型提示、完整执行记录或用户电脑路径。清单使用商家／版本／阶段构成的逻辑来源。

运行导出回归：

```sh
python3 -m unittest discover -s tests -p test_export_report.py -v
```

另外将生成的 HTML 复制到其他目录，直接离线打开，核对版本切换、全部正文、证据、打印及窄屏显示。网页美化和导出完成不代表再次完成模型运行、真实商家验收或经营结果验证。
