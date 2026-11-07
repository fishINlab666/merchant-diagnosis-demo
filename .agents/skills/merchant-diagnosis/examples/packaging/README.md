# 暖禾热饭包装案例（全部合成）

这是独立于原凉餐样本的合成单店、零广告案例。品牌、订单、老板说明、分组、温度及历史试行均虚构。材料用来检验模型能否采纳明确口径、判断有充分支持的主要可控原因、扣齐成本，并在相反材料到来时改判；不是实际客户或 Skill 已实现的经营效果。

## 输入边界

| 阶段 | 提交材料 | 不提交 |
|---|---|---|
| S1/S2 | `raw/public.md` | 内部表、老板成本说明、独立验算及此说明 |
| S3–S5 | 前序有效报告、`raw/暖禾热饭_模拟原始台账.xlsx`、`raw/definitions.md` | CSV镜像、生成脚本、独立验算及预期答案 |
| 等价CSV适配 | 用 `raw/` 内5份CSV与 `definitions.md` 替代 XLSX | 不能把 XLSX 和 CSV 叠加当两批订单 |
| 缺包材成本 | 只用 `counterinputs/missing-cost/` 内3份文件，加 `raw/public.md`、`raw/温度抽查.csv` | 不提供主 XLSX、原成本CSV、报价CSV、主definitions或其历史报告 |
| 相反机制更正 | 主输入及前序报告，再给 `counterinputs/reverse_mechanism.md`、`reverse_trial.csv`、`reverse_wait_strata.csv` | 不沿用被撤回的同窗记录、温度表及规划退款假设 |

`raw/` 有28条历史日记录、14条同窗组日记录、42条对应成本和14条温度抽样记录。成本行与温度抽样不是新增订单。XLSX保留重复表头、阶段小计、横排成本及万元／元混用，供实际读表适配。原表只包含台账、报价和老板规划参数，没有月度诊断答案。

独立验算脚本与结果位于项目根目录 `runs/merchant-v17-independent-checks/packaging/`。该目录不得进入受测模型输入。目录中的预览为原表版式核对，不是客户经营看板。

## 可复现生成

使用 Codex `load_workspace_dependencies` 返回的 Node 和 node_modules。临时目录应有指向该 bundled node_modules 的符号链接，随后设置 `MERCHANT_ARTIFACT_RUNTIME` 指向临时目录。脚本仅使用 Artifact Tool 生成 XLSX，CSV和业务记录随脚本确定性生成。

```sh
MERCHANT_ARTIFACT_RUNTIME=/path/to/artifact-runtime \
  node \
  skills/merchant-diagnosis/examples/packaging/generate.mjs
python3 runs/merchant-v17-independent-checks/packaging/verify_packaging.py
```

换机器时由依赖加载器返回路径替换上述本机运行库路径。首次创建工作簿前按 Spreadsheets 技能执行 `mark_artifact_operation_started.mjs`；重复修正构造时不重复标记。本次只生成一份主 XLSX，缺成本和反向测试为紧凑替换材料。

复现保证业务记录、字段、计算与校验一致，不承诺 XLSX 打包元数据逐字节相同。生成器只改本案例目录和独立核对目录，不修改原 chain、Skill 或模型运行历史。
