# 老板看板接口 1.0

只生成一个 JSON 对象；不用 Markdown 表格、五阶段标题或内部行号。可以直接提交 report 本体，也可包为 `{"kind":"final","report":{...}}`。

产品界面统一使用「老板看板／产品讲解」命名。对外字段、标题、提示和说明服务经营决策，不得使用面试/求职/应聘定位或对面试官说话；职业准备留在内部。方法讲解对应本轮证据和实际动作，不虚构已采用的方法；商家原始经营事实不因禁词删改。

| 字段 | 类型与要求 |
| --- | --- |
| merchant | `{name,scope,period,synthetic}`；前三个为文字，synthetic 为布尔值。与本轮商家一致 |
| headline | 一句具体判断，说明问题和行动方向，避免空泛“有优化空间” |
| money | `{label,calc_id,value,unit,period,note,basis,evidence}`；有数值必须关联实际 calculate 的 calc_id，程序填入 value；未知用 value:null。label 说清指标，unit 通常元，period 说清期间，note 集中说明条件一次，basis 用人话解释计算口径 |
| findings | 最多3项 `{title,detail,basis,evidence}`；basis 为自然语言，evidence 为 `[{material,locator}]` |
| actions | 1–3项 `{title,owner,timing,budget,success,stop}`，均文字。按优先级保留最多三项，相关门店动作可合并；其他执行细节放 analysis.execution 或 followup。第一项自动成为首屏“先做这件事”，不另填重复字段 |
| followup | `{when,collect,decision}`；when/decision 文字，collect 为文字列表，说明回传资料改变哪个决定 |
| charts | 最多3项 `{type,title,unit,caption,series}`，type 用 bar/stacked/waterfall；series 为 `[{label,value,calc_id,role,group,evidence}]`。有 calc_id 时由计算记录绑定值；原始数值可用 value+evidence；未知用 null。role 可选 total/increase/decrease；group 可选组名 |
| analysis | 内部记录 `{goal,chosen_strategy,alternatives,execution,assumptions}`；goal/chosen_strategy/execution 为文字；alternatives/assumptions 为文字列表，不进入客户HTML |
| gaps | `[{item,why}]`；只有真实影响决定的缺口才列，没缺口填[] |

其余可选值可省略，程序补空文本或空列表。不返回示例答案，不写DEF、F1、A1、D1之类内部编号；证据位置、计算ID不放入客户正文。

先让主金额回答本轮目标：问“这个方案每月能多留多少钱”时，主卡必须是审慎月度贡献差额，不能用全店原有贡献存量或短周期金额替代。原有规模可放次要图表；差额缺依据就保持未知。

金额不需要在多处复制。主要钱数放 money，图表引用计算ID；描述里的数字保持与计算输出一致。不把 null 展示为零。已知收入但成本缺失时可以显示收入规模或受影响退款金额，必须明确指标含义，不冒称净改善。

首屏只放一句结论、一个核心钱数、第一项行动。提醒在 money.note 一处集中，其他区域说明各自的执行条件，不反复写“非实测”“不是收益承诺”。合成案例由 merchant.synthetic 统一显示一次。客户看板不包含原始材料全文、模型协议或内部 analysis；这些保存在旁边的运行记录。

## 阅读密度

让老板30秒读懂：headline建议不超过45个汉字；money.label用短指标名（建议20字内），期间放period、计算展开用basis；money.note建议80字内，只保留会影响本次决定的条件；actions[0].title建议35字内，金额/日期/负责人与验收条件放各自字段，不把整份方案塞进标题。三张图分别讲预算/经营变化/收益拆解，优先用客户能读懂的类别名，避免W01、T01、C01等材料记录号。长度为写作目标，不为过关截断事实。
