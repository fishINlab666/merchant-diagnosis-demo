# 连锁预算主案例（全部合成）

本目录模拟一家约 200 店品牌的 30 家成熟直营店，展示公开初诊、补数、预算判断、30 天经营贡献情景和执行回执。品牌、门店、日期、评价、台账和执行情况全部虚构，不能作为真实客户数量、个人业绩或商家经营效果。

## 分阶段输入

| 阶段 | 本轮允许的业务输入 | 不应提前输入 |
|---|---|---|
| S1、S2 | `raw/public.md` | 内部表、预算说明、参考答案、numeric JSON |
| S3–S5 | 先前有效报告、`raw/经营周报.xlsx`、`raw/definitions.md` | `execution_receipts.md`、书面参考答案、numeric JSON |
| 执行复盘 | 先前有效报告、再加入 `raw/execution_receipts.md` | 将模拟回执称为真实商家执行 |
| 负向反例 | 用 `counterinputs/negative_trial.csv` 覆盖旧 T01–T03，原基线与成本口径不变 | 继续引用旧试行系数作为当前事实 |
| 缺成本反例 | 使用下述成本缺失材料替换包，移除旧成本表及口径 | 把旧成本或 60% 当作默认值 |

`经营周报.xlsx` 有“周报／渠道／边际试行”三张表，原字段从第 3 行开始，记录从第 4 行开始。它与 `internal_weekly.csv`、`channel_mix.csv`、`trial_observations.csv` 是**同一份 9 条业务记录的不同封装**；正式 S3 只喂 XLSX，CSV 保留用于独立核算和格式适配比较，不能重复计数。金额原字段包含万元与元，不能直接相加。

缺成本测试时应只输入 `counterinputs/missing_cost.md`、对应删除成本列的报表以及 public 和渠道数据；不得输入原 definitions.md 的 DEF02、DEF06 或原表成本列。`numeric/missing_cost.json` 是计算器的独立空值测试，不代替模型原始材料测试。

## 算术工具

`calculate_scenario.py` 只计算已经人工或模型核对的输入，不识别字段、不生成诊断、不读取参考答案。函数接口为 `calculate(payload: dict) -> dict`。CLI 把计算结果写到标准输出：

```bash
python3 scripts/calculate_scenario.py examples/chain/numeric/scenario.json
python3 scripts/calculate_scenario.py examples/chain/numeric/negative.json
python3 scripts/calculate_scenario.py examples/chain/numeric/missing_cost.json
python3 -m unittest discover -s tests -p test_scenario.py -v
```

输入为同范围、同周期的商户净结算收入、订单变动成本、A/B 预算、调拨上限，以及逐情景的新增 B 入账系数、减少 A 入账损失系数、两侧变动成本比例与额外执行费；成本未知写 `null` 或省略对应成本键。输出保留负数；缺成本时状态为 `needs_cost_data`，受影响贡献值为 `null`，仍返回可算的收入与预算。脚本不会按品牌 200 店倍乘。

`numeric/` 是作者独立复算的示例入参，不作为受测 Codex 的初始输入。受测 Codex 应从原表自行推导并写自己的 calculation input，再调用同一工具。书面 S1–S5 参考只在 `docs/商户经营诊断_连锁主案例.md`，不在原始输入目录。

## 验证层级

本目录数据身份是合成；脚本测试证明算术与缺数分支；原文件读取记录证明实际读了文件；独立 Codex 的运行记录另存于 Skill 运行目录。四者都不等于商家实际执行或真实经营结果。
