# 老板看板接口 1.1

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
| method_usage | 新准备的运行必填四项方法记录，规则见下方；由 Agent 写，客户不用填。旧报告保持兼容 |
| audience_plan | 可选，最多6项人群方案；有证据才展示，缺少分群数据时省略或填[]。行结构见下方 |

其余可选值可省略，程序补空文本或空列表。不返回示例答案，不写DEF、F1、A1、D1之类内部编号；证据位置、计算ID不放入客户正文。

先让主金额回答本轮目标：问“这个方案每月能多留多少钱”时，主卡必须是审慎月度贡献差额，不能用全店原有贡献存量或短周期金额替代。原有规模可放次要图表；差额缺依据就保持未知。

金额不需要在多处复制。主要钱数放 money，图表引用计算ID；描述里的数字保持与计算输出一致。不把 null 展示为零。已知收入但成本缺失时可以显示收入规模或受影响退款金额，必须明确指标含义，不冒称净改善。

首屏只放一句结论、一个核心钱数、第一项行动。提醒在 money.note 一处集中，其他区域说明各自的执行条件，不反复写“非实测”“不是收益承诺”。合成案例由 merchant.synthetic 统一显示一次。客户看板不包含原始材料全文、模型协议或内部 analysis；这些保存在旁边的运行记录。默认「老板看板」，开启「产品讲解」后解释本轮方法记录；两种视图共用同一判断和金额。

## 方法使用记录

`method_usage` 按以下四项各记录一次，不能仅写方法名表示用过：

| method（只用于内部绑定） | 方法 |
| --- | --- |
| store_segmentation | 按增长与收益质量分店/分场景配置资源 |
| audience_offer | 人群×商品×权益 |
| tool_mix | 先选策略，再配工具组合 |
| execution_followup | 推进执行与回传复盘 |

每项结构为 `{method,status,reason,decision,evidence_summary,evidence,targets}`。`status` 只用 `applied`（采用）、`adapted`（按本店改写）、`not_applicable`（不适用）、`needs_data`（缺数据）。`reason` 说明适用判断；`decision` 说明改变了哪个决定，未采用则写当前能决定什么或需何种信息。两者均非空。`evidence_summary` 用可公开的人话概括关键事实，不含私人路径、客户个人信息或内部记录号；不用重复免责声明。

`evidence` 仍为 `[{material,locator}]`；采用/改写必须有本轮可回查的证据。`targets` 为 `[{section,index}]`，section 取 `money`、`findings`、`actions`、`charts`、`audience_plan`；index 从0起，money只能0，必须实际存在。采用/改写至少关联一个真实落点；缺数据/不适用可为空，不能为了凑三圈点编结论。程序按实际采用记录显示最多三个圈点，其余记录仍可展开。

方法确实落成动作时，targets 同时关联该项 actions，讲解即可显示对应负责人、时间与执行要求。没有行动依据不补造关联。

讲解的材料依据必须转述直接支持判断的原件事实；有可比数字时写出关键对照及其口径。不要把 reason 与 decision 拼接充当 evidence_summary，也不要只写“数据齐备”“存在差异”。人群方案的 basis 按各群实际观察分别写，validation 也按该群动作写；不能给所有人群复制同一句依据或无关止损线。对应 evidence 要覆盖这些事实，而不只引用工作表上的名称或单个无关单元格。若关键证据不宜公开，省略公开概括并保留内部记录，不编造可讲解事实。

记录体现「为什么这次用了、如何改变建议」，不能写假想的“没用方法时AI一定会答错”或把当前补强写成当年已完整实施。程序验证结构与引用；语义仍须对照材料复核。新轮输出旁保存 `method-usage.json` 供查阅。

## 人群×商品×权益

`audience_plan` 每行 `{audience,product,benefit,decision,validation,basis?,evidence,economics?}`。前五项为非空文字：给谁、让其买什么、采用/取消什么权益、为何这样选、如何验收。`basis` 可选，用人话概括可公开的关键证据；`evidence` 引用本轮真实分群/商品/费用材料，原始定位留在运行记录。不要凭商圈名字编画像。

`economics` 可选，为 `{label,unit,calc_id,value,evidence}`；派生数值引用本轮实际计算，未知用null。指标名区分历史观察的贡献差额、计划试行金额和未来月度情景，不能混为已实现增量。各群的触达、成交分母与成本口径须可比，核商家承担让利、食材包材、平台/配送、广告和执行费，净实收已扣券或退款的不重复扣。高频客不自动发券；无证据的权益只可列待检验方向，不编收益。

## 阅读密度

让老板30秒读懂：headline建议不超过45个汉字；money.label用短指标名（建议20字内），期间放period、计算展开用basis；money.note建议80字内，只保留会影响本次决定的条件；actions[0].title建议35字内，金额/日期/负责人与验收条件放各自字段，不把整份方案塞进标题。三张图分别讲预算/经营变化/收益拆解，优先用客户能读懂的类别名，避免W01、T01、C01等材料记录号。长度为写作目标，不为过关截断事实。
