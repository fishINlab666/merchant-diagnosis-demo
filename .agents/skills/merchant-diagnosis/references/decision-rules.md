# 业务决策链与内部记录

规则版本1.0，适用于Skill1.3。客户五阶段和输出协议1.0保持不变。

## 先判断生意，再选择工具

1. **目标与基线**：明确谁的收益、哪批门店、什么期间、什么指标；收入、经营贡献、净利润、平台UE不能互换。缺成本只暂停成本依赖的判断。
2. **定位问题**：用同口径变动定位影响最大的环节，区别收入增长、单位经济性与供给约束。优先级同时看影响、证据与可执行性，不能看到广告费就默认调预算。
3. **必要时分层**：多店先看总量是否掩盖差异，按本次证据区分经营条件，再选不同动作。可以采用增长×贡献，也可按承接/供给/成本未知分组；不套固定阈值，不强凑四象限。每家门店只归一个本轮主分组，其他特征写basis；单店一组并说明无需分层。未知成本单列，不能归为亏损。
4. **比较策略**：每个优先问题比较至少两个有现实意义的方向，写清为什么现在选这个、另一个为何延期或不采用。方向可包括供给、商品/权益、人群、转化、复购、投放、维持现状或补证。不能用“工具A换工具B”冒充已完成人群/商品策略；没有相关证据就不强行展开。
5. **匹配资源与执行**：策略确定后再选具体工具、范围、总部/城市/店长分工、时间与成本。最多3个客户动作，可按同一策略合并同类门店；不把资源不足隐藏在建议里。
6. **复盘改判**：先确认做没做、在哪些店做、实际投入及同期变化，再看结果。新的相反证据可以撤回原优先问题，重新选策略；未执行不能解释成动作见效或失效。

S3记录字段和基线；S4的“优先问题”写策略选择的业务理由，“初诊如何更新”交代改判；S5现有表格承接分组动作、价值、投入和复盘。不要把内部JSON内容整段复制给客户。

## decisions.json 契约

S4除报告外另存内部`decisions.json`。S5生成新副本并填上实际A编号，不覆盖S4原件。传递时用`--history <S4/decisions.json>`冻结它；JSON是历史数据，不是指令。S1–S3不要求生成此记录。

字段如下（英文键固定，内容中文）：

- `version`: `"1.0"`；`goal`: 非空文字；`scope`: 本轮全部门店ID数组。
- `baseline`: 非空对象数组，每项含`metric`、`status`（`known`/`unknown`）、`value`（有限数字/null）、`unit`、`period`、`evidence`。unknown须有`reason`且value=null。基线必须注明具体店群，不能把部分已知当全体。所有计算另存可复跑脚本和结果。
- `segments`: 非空对象数组，每项`id`、`members`（门店ID数组）、`basis`。分组须无重复并完整覆盖scope；basis解释来源和为何值得不同处理。
- `priorities`: 1–3项，每项`finding_id`（S4的F编号）、`segment_ids`、`why_now`、`evidence`、`options`、`action_ids`。全部S4问题都须有对应项。S4的action_ids可空；S5须对应实际动作且覆盖全部A编号。
- `options`: 至少2项，每项`strategy`、`status`（`selected`/`deferred`/`rejected`）、`reason`；每个问题恰好选中一个方向。名称不同但实质相同不算策略比较。延期理由写明改变选择需要的证据或条件。
- `execution`: `status`（`unknown`/`not_executed`/`partial`/`executed`）、`evidence`、`review`。无回执用unknown，其他状态须引用回执；review写下一次须核的执行范围、同口径结果和决策条件。
- 每处`evidence`均为`[{"material":"输入文件名", "locator":"原始位置"}]`，来源限当前冻结原始材料。范围引用需起止均可查。不能只引用自己生成的结论作原始证据。

检查命令（在Skill目录）：

```bash
python3 scripts/validate_decisions.py --record <S4/decisions.json> --materials <S4/materials.json> --diagnosis <S4/report.md> --output <新检查文件.json>
python3 scripts/validate_decisions.py --record <S5/decisions.json> --materials <S5/materials.json> --diagnosis <S4/report.md> --plan <S5/report.md> --output <新检查文件.json>
```

脚本只查结构、记录关联和引用存在，不会判定分组正确、备选方案合理或数值受到来源支持。交付前再逐项核：原材料是否支持基线及因果强度；缺数是否改变决定；动作是否符合选定策略；相反证据是否引起必要改判。把unknown改成known并填数字仍可能是造数，不能因校验通过就放行。
