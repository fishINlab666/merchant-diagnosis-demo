# 经营诊断服务运行说明（1.6 本地版）

使用者是服务商家的操作者。客户提供材料和执行反馈；你核对 AI 草稿、和客户确认行动，再交付报告。HTML 是交付文件，项目目录保存连续服务记录。本版新增 DeepSeek API 客户端；代码与模拟传输测试通过不等于真实接口验收。

所有命令从 Skill 根目录运行，Python 3.10+；CSV、文本用标准库，XLSX/PDF 依赖见 `requirements.txt`。原材料的语义由模型判断，算术走受控计算器；不支持的文件先转换，扫描件仍需 OCR，不宣称任意表格都能无条件读取。

1.6 为 API 注册原生 `calculate` 函数：模型提出带来源的公式，运行器执行受控算术，再按工具调用编号返回结果。只开放该函数，不执行模型生成的脚本、文件操作或网络请求；仍兼容旧 JSON 计算请求。思考模式所需的模型上下文仅在内部请求记录中保留，不进入客户报告。工具结果验证算术和来源位置，字段抄取、口径和建议仍需复核。

## 1. 本机配置一次

在你自己的交互式终端执行，按提示隐藏输入新密钥，不要在聊天里发送或把密钥作为命令参数：

```sh
python3 scripts/service.py configure --model deepseek-flash
```

默认保存在用户目录 `.config/merchant-diagnosis/credentials.json`，目录 700、文件 600。若文件已存在，先在本机移走旧文件再重新配置；不自动覆盖。配置成功只说明保存成功，不代表账号或模型可用。文件不要放进 Skill、材料目录或 Git。

模型名依据本轮查阅的 [DeepSeek 官方接口文档](https://api-docs.deepseek.com/api/create-chat-completion/)，账号权限以实际响应为准。`run --model deepseek-v4-pro` 可为本次显式选择模型，不修改私有配置，也不自动切换到其他模型。协议采用 [JSON Output](https://api-docs.deepseek.com/guides/json_mode/)，无效或截断内容不会作为报告接收。正常结束但内容 JSON 错误、已识别的计算参数字段错误、报告结构错误，共享本阶段唯一一次格式修正；错误计算参数不执行，仍失败则停止。工具身份、未知函数、重复键、非有限工具 JSON 等异常不进入参数修正分支。

运行时显式传 `--config "$HOME/.config/merchant-diagnosis/credentials.json"`；不传则只读取 `DEEPSEEK_API_KEY` 和 `DEEPSEEK_MODEL` 环境变量，两种来源不混用。程序不接收自定义 API 地址、不跟随重定向、不自动网络重试。

复杂报表可显式使用 `run --model deepseek-v4-pro --thinking enabled`。依据同一官方接口文档，启用低强度思考、默认输出上限 16,384 tokens、网络等待超时 120 秒；不是严格的总墙钟截止。默认保留非思考模式、8,192 tokens、60 秒网络超时。若实际记录表明输出被截断，可用 `--max-tokens 32768` 显式设置本次上限；本地允许 1–32,768，不自动扩大，也不修改配置。运行记录保存请求型号、模式及限制，成功响应另记实际型号和用量；不声称启用思考就一定正确。切换后仍须完整验收。

## 2. 一家商家单独建档

以下商家名与路径是占位示例，须换成实际对象。仅演示合成案例时添加 `--synthetic`；真实公开研究不得混入模拟经营数。

```sh
python3 scripts/service.py init --project projects/store-a --name "实际门店名" --goal "核对购买选择与经营改善机会"
python3 scripts/service.py add --project projects/store-a --file public.md --slot public-page --kind public --period "本次公开资料采集日期"
python3 scripts/service.py status --project projects/store-a
python3 scripts/service.py run --project projects/store-a --phase public --config "$HOME/.config/merchant-diagnosis/credentials.json"
```

`public` 只读取 public 材料，完成 S1/S2。公开材料不足就输出具体核实和补数用途，不能编造近期差评、竞店价格或商家内部预算。运行会把本阶段冻结材料及前序报告发送给 DeepSeek；仅导入你允许用于此次分析的材料。

## 3. 收数后诊断，再连续复盘

```sh
python3 scripts/service.py add --project projects/store-a --file weekly-w1.xlsx --slot weekly-w1 --kind business --period "W1 的实际起止日期"
python3 scripts/service.py add --project projects/store-a --file definitions.md --slot definitions --kind definition --period "本次有效口径"
python3 scripts/service.py run --project projects/store-a --phase diagnosis --config "$HOME/.config/merchant-diagnosis/credentials.json"
```

先按下节复核本轮。之后回传下一期周报和动作回执：

```sh
python3 scripts/service.py add --project projects/store-a --file weekly-w2.xlsx --slot weekly-w2 --kind business --period "W2 的实际起止日期"
python3 scripts/service.py add --project projects/store-a --file receipt-w2.md --slot receipt-w2 --kind receipt --period "W2 的实际起止日期"
python3 scripts/service.py run --project projects/store-a --phase followup --config "$HOME/.config/merchant-diagnosis/credentials.json"
```

`diagnosis` 和 `followup` 均跑 S3/S4/S5，默认带入本商家最近已复核运行，可用 `--previous <运行ID>` 指定。复盘必须有已复核前序和新增/更正材料。回执未提供时可以做数据复核，但不能认定动作执行，更不能把变化归因给方案。连续复盘只载入所选上一轮报告，长期趋势必须提供对应原始期间数据。

新期间用新 slot 和含期间的文件名。修正同一份旧报表用原 slot 加 `--replace`；旧原件与旧报告不覆盖。相同内容不会重复登记，同名不同材料会提示更名。新增/更正后，旧批准结果不再允许作为当前交付导出。

## 4. 人工复核后交付

查看命令返回的 `runs/<运行ID>/`：S1–S5 的报告、计算、首稿、修正、结构检查，以及根目录 `execution.json`。核对证据原文、字段定义、时间范围、成本、方案与实际执行；结构校验不替代这些判断。没有算术错误不代表模型抄数或业务归因正确。

```sh
python3 scripts/service.py review --project projects/store-a --run <运行ID> --reviewer "实际复核人" --decision approve --note "填写核对过的证据、计算和业务边界"
python3 scripts/service.py export --project projects/store-a --run <运行ID>
```

不通过用 `--decision reject` 并记录原因。相同材料版本、相同 phase 的重跑会带入最新拒绝意见并重新核对原件；新材料版本不自动继承旧拒绝意见。指定前序运行的复核意见也随历史传入，防止有条件批准被当作所有事实已确认。意见不是新增原始事实，仍须回查材料。

若 S3/S4 的字段、算术和策略已经复核，只是完整生成的 S5 被退回，可显式只修订最终方案：

```sh
python3 scripts/service.py run --project projects/store-a --phase diagnosis --revise-final <被退回运行ID> --config "$HOME/.config/merchant-diagnosis/credentials.json"
```

该入口限定同商家、同阶段、同材料及目标快照，来源须完整生成 S3/S4/S5 且最新复核为退回。它校验文件指纹，原样复制 S3/S4，保留前序关系，只将新的 S5 发给模型；旧 S5 不作为已验证历史。记录分别列 source_run、reused_stages、fresh_stages，本轮推理标记只按新调用计算。不能借此更改 S4 策略，也不能把测试替身来源升级为 API 成果。字段、策略或材料改变时须重新跑完整诊断；并非任意失败的自动续跑。

不能自动替客户确认；复核是操作者对交付内容的检查。由 Agent 做的预审应明确署名及范围，不能写成用户／商家验收。导出新目录下的 `report.html`；完整 `project/` 和请求记录属于内部服务材料，不直接打包发给客户。

当前自动导出包含本轮报告正文；有核对过的图表配置时可使用原 `export_report.py` 生成经营看板。未自动生成或核对图表，不冒充已经完成图形化经营分析。

## 证据、消费和失败

- 每阶段最多 8 次调用，可用 `--max-calls 1..12` 调整；最多一次格式修正。预算是调用次数上限，不是金额承诺；token 用量以接口返回为准，尚未核对费用计价。
- 输入快照、模型请求/有效响应、计算、结构错误、报告及哈希都保留。测试替身明确标注 `test_double`；准备脚本成功不等于模型运行。
- 失败诊断只记录解析阶段、结束原因、长度、用量、JSON错误类别及行列，不保存原始无效响应或服务端错误体。模型已生成有用量的响应但报告无效时，记录已推理且运行失败；不能称未调用，也不能称阶段成功。用量不等于已核实账单。
- S5 只能补 S4 的动作映射，不得暗改策略、分组或基线；要改判断就新建诊断运行。
- 请求失败或格式仍不合格，返回失败状态，保留已完成阶段，不生成预置替代报告。修正后重新运行会重新调用模型，不做自动续跑；只有上节限定条件可显式复用 S3/S4 修订最终方案。
- 没有安全本机凭证时，停在已建档/待 API 验收；不使用聊天中的凭证代填配置。

首轮沟通与持续服务用 [服务范围与报价](../assets/service-templates/服务范围与报价.md)、[行动回传](../assets/service-templates/行动回传.md)、[周度复盘](../assets/service-templates/周度复盘.md)、[首单进度](../assets/service-templates/首单进度.md)。报价、商家采纳、执行和付款分别记录实际证据。
