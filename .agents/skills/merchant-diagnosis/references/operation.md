# 输入与运行说明

运行需要能读取与写入文件、执行 Python 3.10+ 的 Agent。先让当前 Agent 读取同目录上一级的 SKILL.md；命令本身不生成诊断。所有命令从 Skill 根目录运行，文件路径由使用者替换，输出目录应位于宿主可写的工作区。不同产品的安装方式及验证状态见 [宿主兼容说明](compatibility.md)。

## 依赖

文本与 CSV／TSV 只需 Python 标准库；XLSX 使用 openpyxl，文本 PDF 使用 pypdf。可在自己的虚拟环境安装 `python3 -m pip install -r requirements.txt`。脚本不需要 API 密钥，也不自动上传文件；Agent 推理所用模型及其数据处理范围由当前宿主决定。

启动前运行 `python3 --version` 与 `python3 -c "import openpyxl, pypdf; print(openpyxl.__version__, pypdf.__version__)"` 核对环境。命令不可用或云端沙箱不允许安装依赖时，只继续受支持材料，并明确未读取的文件。宿主使用其他 Python 命令名时，替换为已确认的解释器路径；不要把本机绝对路径写进可复用配置。

本轮已验证环境：Python 3.12.14、openpyxl 3.1.5、pypdf 6.10.0。若测试输出出现 `skipped`，表示对应依赖缺失，不能把跳过的格式计为通过；安装依赖后再运行。

## 准备与验证

```sh
python3 scripts/prepare.py --stage S1 --input public.md --output runs/store-a/S1 --runtime "Codex"
python3 scripts/prepare.py --stage S3 --input weekly.xlsx definitions.md --history runs/store-a/S1/report.md runs/store-a/S2/report.md --output runs/store-a/S3 --runtime "Codex"
python3 scripts/validate.py --stage S3 --report runs/store-a/S3/draft-1.md --materials runs/store-a/S3/materials.json --history runs/store-a/S1/report.md runs/store-a/S2/report.md --output runs/store-a/S3/check-1.json
python3 -m unittest discover -s tests -v
```

上面的 `Codex` 是宿主参数示例；在其他 Agent 中运行时填写其实际名称。省略 `--runtime` 会记录“未声明”，不会自动推断为 Codex；该参数只是声明，`manifest.json` 的 `inference_executed` 仍为 `false`。完成实际推理后另存执行记录，填写真实宿主、可见客户端版本和底层 `model_id`；未知型号写“未暴露”。不修改历史记录中的执行者。

`prepare.py` 保存材料名、文件指纹和定位，原表头无需标准化；业务含义由当前 Agent 看表头、单元格、备注和前序回答理解。缺口不能靠填零消除。准备输出目录使用新的路径，避免覆盖已有运行。

批量准备时任一文件读取失败，脚本不会写出一份貌似完整的输入包。Agent 应记录失败文件和影响的判断，再用新目录准备其余可读材料并继续分析；失败文件作为待补项保留，不当成空表或零值。无需让客户为一份坏文件重做所有材料。

每个阶段至少保留原始输入指纹、首次输出、检查结果及最终报告。实际生成时另记执行时间和执行者；准备脚本不会宣称模型已运行。

1.3另冻结`decision-rules.md`。S4生成内部`decisions.json`，S5使用`--history`传入此文件及前序报告，另存带A编号的新副本；记录目标、基线、门店分组、策略取舍和执行状态。字段与校验命令见[业务决策链](decision-rules.md)。客户报告不新增栏目。

新商家可以在支持本 Skill 的 Agent 中直接说：读取本Skill，先用我指定的公开材料完成S1/S2；收到我的经营材料后从S3继续，保存原始报告、计算和决策记录。为每个商家使用新的运行目录。命令中的路径只是参数示意，实际传入已有文件。

合成验证材料分开使用：`examples/chain/`展示预算结构与月度情景；`examples/segmented/raw/`展示多店经营差异；`examples/segmented/variant/`替换前者的布局及单位；`examples/pet-care/raw/`展示无广告的预约服务。横排与纵排是同一批事实，不能同时加总。只给执行者原始材料，不给作者验算或别次运行答案。

## 可选网页交付

分析和校验完成后，可按 [报告导出说明](report-export.md) 准备展示配置，再执行：

```sh
python3 scripts/export_report.py --config runs/store-a/display-config.json --output runs/store-a/display/report.html
```

配置只能引用本次实际产生且已经核对的报告和证据。导出将这些产物整理成离线展示文件，不运行模型、不代替计算或语义验收，也不自动发布网站。未得到内部周报时保留初诊及补数状态；不得用案例答案补齐页面。生成网页之后仍需核对展示数字、来源和状态与报告一致。

## 支持边界

| 类型 | 处理方式 | 不满足时 |
|---|---|---|
| TXT／Markdown | 保留行位置与原文 | 编码或空内容错误时补可读文本 |
| CSV／TSV | 保留原行和列，不要求固定字段 | 不清楚的单位在 S3 定向确认 |
| 本地 HTML | 提取正文文字，不执行脚本 | 动态页面先由用户提供可见文字或截图 |
| XLSX | 保留工作表和单元格定位 | 公式缓存缺失不能当 0；要求重算导出或按原公式核对 |
| 有文字层 PDF | 逐页提取 | 扫描件转为可读文字或逐页图像处理 |
| 图片 | 本轮自动 OCR 不支持；解析器会明确报错 | 提供原始表或经核对的文字；若宿主视觉协助，另存转录与原图位置并单独核验，不算本轮自动读取通过 |
| 店铺链接 | 由宿主可用浏览工具读取并记录来源和时间 | 登录、动态页或不可访问时请提供页面内容；本脚本不绕过登录 |

格式读取通过只表示拿到了内容，不等于经营口径或模型理解已经验收。大型文件触发限制时需缩小当前相关范围或分批读取，不能静默截掉末尾再给完整结论。

读取限制：单文件 20 MB、提取文字 200 万字符、5 万片段；XLSX 解压后 100 MB、扫描 20 万单元格；PDF 200 页。超限整体报错。XLSX 图表、图片、批注与 PDF 图片内容不属于已读取证据；PDF 多栏和跨页表格须对照原件确认。

结构检查不能证明全部数字和因果判断正确。交付前仍需逐项核对计算、引用和动作依据；保留这一步的实际结论。

引用时将文件名与前面的中文动词用空格、冒号或括号隔开，例如“依据：周表.csv／row:2”，避免“依据周表.csv”被当成完整文件名。此限制只影响报告引用写法，不要求商家改原文件名；若触发检查，保留首稿并在允许的一次纠正中修正分隔。
