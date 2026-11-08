# 禾序饭盒 v18 定向展示与证据修订记录

## 性质与范围

本稿基于真实 Codex 独立会话已完成的 `runs/merchant-v18-acceptance/full/run/report.json` 做定向修订。它是原首稿之后的修订稿，不是原首稿，也未重新进行经营分析。原 `full` 目录未覆盖、未修改。

本轮仅调整四项方法的事实概括与引用、六组人群的依据与验收文字及引用，以及滨江先核让利与成本、加盟商确认后限量验证的表达。六组名称本身简短，继续保留。金额、图表、计算 ID、economics、商家范围、analysis 核心逻辑与方法 targets 原样保留。

## 逐项修订

- 门店分层：补六店本周单均经营贡献、相对前周净收入增长以及本轮目标；补学府供货、城西排班、社区零广告、滨江加盟承担与权限原件。计算用原运行结果，引用覆盖本周收入/费用/完成单及前周净收入。
- 人群×商品×权益：方法概括改为六群同窗经营贡献对照，并保留高频无券少单代价。各群 basis 分别给定义、固定分组每臂人数、原菜单/候选商品与券、完成单、原运行贡献、广告差异。潜客广告是300对500元，未写成广告相同；沉睡为每臂400元。
- 高频引用：显式使用现行有券第14行和候选无券第13行，移除误指沉睡的第15行，不采用行号加一生成对照。其他群依次为7/8、9/10、11/12、5/6、15/16。
- 工具组合：补科创首屏只露出单人餐、套餐权益规格及四个拟试群广告、学府供货和城西午餐排班的原件事实，保留原 actions[0]、actions[1] 关联。
- 执行复盘：补总部/店长/财务/加盟商权限、分时容量、7天复盘、420单预算触发及执行回执要求。
- 验收：首购关注第二单核销；留存两群关注双主菜、专券、库存、替代；高频关注有券基线下的减单与贡献；潜客关注额外广告成本；沉睡关注晚餐供给与召回。420单/千人只保留在高频相关验收中。
- 滨江：首屏与发现先核让利和商品成本，行动明确加盟商确认后限量对照验证；未预设必须减券，未添加该店收益金额。

## 全部改动字段

- `headline`
- `findings[0].detail`
- `findings[0].evidence`
- `actions[2].title`
- `actions[2].timing`
- `actions[2].budget`
- `actions[2].stop`
- `audience_plan[0].validation`
- `audience_plan[0].basis`
- `audience_plan[0].evidence`
- `audience_plan[1].validation`
- `audience_plan[1].basis`
- `audience_plan[1].evidence`
- `audience_plan[2].validation`
- `audience_plan[2].basis`
- `audience_plan[2].evidence`
- `audience_plan[3].validation`
- `audience_plan[3].basis`
- `audience_plan[3].evidence`
- `audience_plan[4].validation`
- `audience_plan[4].basis`
- `audience_plan[4].evidence`
- `audience_plan[5].validation`
- `audience_plan[5].basis`
- `audience_plan[5].evidence`
- `method_usage[0].decision`
- `method_usage[0].evidence_summary`
- `method_usage[0].evidence`
- `method_usage[1].evidence_summary`
- `method_usage[1].evidence`
- `method_usage[2].evidence_summary`
- `method_usage[2].evidence`
- `method_usage[3].evidence_summary`
- `method_usage[3].evidence`

## 语义与范围自查

- 六群比较均来自两店同一合成观察窗口，各臂1,000人；定义、固定快照和费用口径留在 basis 或其证据中，未将触达次数当人数。
- 各群贡献引用原 `arm_5` 至 `arm_16` 计算，分别为510、754、2130、3676、2616、3610.4、3912、5114.4、6990、4964、572、716元。此处为模拟观察，不是计划月度贡献或商家实绩。
- 高频现行基线仍为有券470单；无券观察450单与预算420单未混用。新稿只修展示引用，不修改原测算。
- 四项方法仍为 applied，reason、targets 原样保留。method0 decision 仅将滨江执行条件说完整。
- money、charts、merchant、analysis 全对象相等；四个 economics 全对象相等；所有数字类型叶节点均未变。方法和人群新增文字中的数值来自原件或已有 calculations。
- 新增/替换的所有引用均在原 materials.json 中找到确切 material+locator；四项 method_usage 引用均不超过100条。
- 已完成 JSON 解析、允许字段集合、冻结字段、证据定位和原输入哈希检查。这是文字与材料语义核对；未执行 prepare/calculate/finish，未生成新 HTML，也未声称商家执行。
- 主代理后续统一 prepare/calculate/finish 生成新的可审计运行；本稿不替代原 full 的独立业务审阅记录。

## 原始输入指纹

- `runs/merchant-v18-acceptance/full/run/report.json`：`fe5a5ab71c080b1cef3f1beb1e02ac8c8a75a10964a7bde9ae5d1953fe9abaac`
- `runs/merchant-v18-acceptance/full/run/materials.json`：`649f084577fc4ea38ebe5e7b0e65afc5f86281c8ec1af7228d88b787a81e9b13`
- `runs/merchant-v18-acceptance/full/run/calculations.json`：`b6a412ec4f1be301c34d0fe314f6b8d9164da80c049e87aa52871951b95b97e2`
- `runs/merchant-v18-acceptance/full/run/requests.json`：`0672b687ece0bc2e7acb6dad6cbc83e57929e45f669ce4bd4eb54fd860dbd7c8`
- `runs/merchant-v18-acceptance/full/input/definitions.md`：`fb14c7da36536c9f3542e65fa1b0e2fba6dce5491bac5064bd0285ea9a08993e`
- `runs/merchant-v18-acceptance/full/input/manager-notes.md`：`e342955c1a6c0931c4094fe9404e7a927bb652a85ba136ee93f99b053dc305f3`
- `runs/merchant-v18-acceptance/full/input/public.md`：`aa2a19457d50f3a871741d97596822409629265c6b216bb04841ed0aded9b522`
- `runs/merchant-v18-acceptance/full/input/禾序饭盒_混排周报与人群观察.xlsx`：`2efb2f3eb6ff268718c9937edde1a5a0e8d7211a3406091b45789026f7bf53ca`
