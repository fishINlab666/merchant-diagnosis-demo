# 格式读取测试材料

全部为合成材料，仅验证读取，不代表真实商家或经营效果。

- `format_weekly.xlsx`：使用 Artifact Tool 导出的真实 XLSX。两张工作表，包含自定义表头、备注、90／10 的数字与 `SUM(B2:B3)` 公式；缓存结果为 100。
- `format_no_cache.xlsx`：相同文件，移除该公式的缓存值，验证不补造结果。
- `format_hidden.xlsx`：相同文件，将口径说明表设为隐藏，验证仍读取内容。
- `format_wrong_dimensions.xlsx`：相同文件，故意把周报的 dimension 元数据改为 A1:A1，验证不丢弃 B4 等实际单元格。
- `format_report.pdf`：ReportLab 生成的三页 PDF，第 1、3 页有文字，第 2 页空白。
- `format_scan.pdf`：仅嵌入截图的 PDF，没有文字层，必须明确要求补文字或先 OCR。
- `format_screenshot.png`：Pillow 生成的真实截图，包含两渠道 90／10；当前版本应明确拒绝并给出文字／原表替代方式。

2026-11-06 在本机试验过 macOS Vision OCR：Swift 正常执行，但对该 PNG 的普通模式及 CPU 模式均返回 `nilError`。未交付未验证的识别成功路径，也不把降级测试通过描述为 OCR 已跑通。

表格两张工作表与 PDF 第一页已渲染检查；原始截图已打开检查。测试以原始二进制文件为输入，不 mock 文件解析结果。
