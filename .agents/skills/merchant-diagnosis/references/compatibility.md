# 跨 Agent 使用与验证状态

官方资料核对日期：2026-11-06。本说明随 `merchant-diagnosis` 完整文件夹分发，安装入口可能随客户端版本调整。

这套 Skill 提供经营方法、老板报告接口、计算脚本和校验规则；Agent 宿主负责加载文件、调用模型和执行脚本。支持 `SKILL.md` 说明宿主可以加载规则，不代表已经装齐依赖，也不代表不同模型对陌生周报会得出同样可靠的判断。

**1.7 默认短流程已完成 Codex 合成材料实跑；本包独立 DeepSeek API 已真实接通，但本轮未通过可直接交付老板的内容验收。**单店、连锁、宠物服务、门店分层、包装反向与缺成本均有运行记录。另一个独立连锁会话用时 152.9 秒，8 次工具操作全部成功，首稿导出；部分来源定位到标题而非正文，记为有条件通过。正式连锁与单店看板另经业务复核和浏览器检查。API 自动复核曾漏掉费用、商品份数和继续条件问题，最终重试也未生成合格成稿；不能把模型 `approved` 等同于业务验收通过。具体见[1.7 验收记录](release-status.md)。Claude Code 实机验收由用户推迟，本轮不再尝试。

独立 API 客户端不等于 DeepSeek Harness 或其他 Agent 宿主通过验收。下表中的“官方支持”指查阅官方资料确认了相应能力，不等于本项目已在该产品中完成运行；Claude、Kimi、DeepSeek Harness、WorkBuddy 仍待项目实跑，商家执行效果另行验证。1.6 同一合成案例的公开初诊、周报方案与更正改判保留为历史记录，其中包含人工辅助续跑和复核，不代表无人值守稳定完成。

## 共同运行条件

完整复制文件夹，保留 `SKILL.md`、`references/`、`scripts/`、`assets/` 和 `requirements.txt` 的相对位置。仅复制一个 Markdown 文件无法运行数据读取和校验流程；网页导出另需完整保留 assets 模板。

| 条件 | 本 Skill 的要求 | 缺少时如何处理 |
|---|---|---|
| 文件能力 | 能读取本次指定原始材料、相对引用文件，并写入独立运行目录 | 明确缺少哪个文件或权限；不把无法读取视为零值 |
| 命令执行 | 能执行本包的 Python 读取、计算和校验脚本 | 只读规则的会话不能标为完整运行通过 |
| Python | Python 3.10 或更高版本 | 在宿主实际执行环境检查，不凭本机安装情况推断云端容器可用 |
| XLSX | `openpyxl>=3.1,<4` | 准备依赖，或由用户提供 CSV；不能把替代格式计为 XLSX 验收 |
| 文本 PDF | `pypdf>=5,<7` | 准备依赖，或提供可读文字；扫描件不计入已验证自动解析范围 |
| 模型与上下文 | 能读取本次材料、遵守报告接口，并根据新增数据更新判断 | 材料超限时分批处理；不得静默截断后给完整结论 |
| 运行记录 | 记录实际宿主、实际模型（可知时）、时间、输入指纹、计算和校验结果 | 未暴露的模型 ID 写“未暴露”，不根据客户端名称猜模型 |

依赖及数据格式边界以[输入与运行说明](operation.md)和[依赖文件](../requirements.txt)为准。命令应在宿主可访问的 Skill 根目录执行，输出目录另选有写权限的新位置。1.7 默认入口见[短流程](quick-workflow.md)及[老板报告协议](boss-output.md)，原分阶段深度流程保留在[服务运行说明](service-operation.md)。使用当前 Agent 时，材料在该宿主环境中分析；显式运行本包独立 API 模式时，会向配置的模型服务发送本次材料。

## 各宿主入口

| 宿主／产品形态 | 官方确认的导入与使用方式 | 本项目状态与边界 |
|---|---|---|
| Codex | 将完整文件夹放入项目 `.agents/skills/merchant-diagnosis/` 或用户 `~/.agents/skills/merchant-diagnosis/`，再在会话中明确调用。官方文档列出项目和用户技能目录。[官方说明](https://learn.chatgpt.com/docs/build-skills) | 1.7 正式单店及四项补充场景已完成合成材料实跑，含宿主自查。首次准备路径曾修正，不能称全程一次无误。换电脑、容器或模型后，仍需核对依赖并复跑。 |
| Claude Code（本地） | 放入项目 `.claude/skills/merchant-diagnosis/` 或用户 `~/.claude/skills/merchant-diagnosis/`，通过 `/merchant-diagnosis` 调用。官方支持附带脚本和参考文件。[官方说明](https://code.claude.com/docs/en/skills) | 实机待验证，用户已推迟，本轮不再尝试。后续须允许读取材料及运行 Python。Cowork／云端会话的加载规则不同，不能假设它们会读取本机用户目录。 |
| Claude（上传 ZIP） | 将完整 `merchant-diagnosis/` 文件夹打为 ZIP，进入 **Customize → Skills → + → Create skill → Upload a skill** 上传；启用 Code execution and file creation。ZIP 内保留技能文件夹这一层。[使用说明](https://support.claude.com/en/articles/12512180-use-skills-in-claude)、[打包说明](https://support.claude.com/en/articles/12512198-how-to-create-custom-skills) | 官方支持自定义技能及代码执行，项目未实跑。上传技能后还要向会话提供商家材料，并核对云端 Python 依赖、输出可下载性和组织权限；不能沿用本机材料路径。 |
| Kimi Code CLI | 放入项目 `.agents/skills/merchant-diagnosis/` 或用户 `~/.agents/skills/merchant-diagnosis/`；官方也支持 `.kimi-code/skills/`。通过 `/skill:merchant-diagnosis` 调用。目录形式可携带脚本和资料。[技能说明](https://www.kimi.com/code/docs/en/kimi-code-cli/customization/skills.html) | 官方提供文件读写与 Bash 工具，执行受宿主权限控制；项目未实跑。须检查 Python 及依赖。[工具说明](https://www.kimi.com/code/docs/en/kimi-code-cli/reference/tools.html) |
| Kimi Agent 模式 | 可用输入框 `/` 或 ➕ 菜单选择已有 Skill；可从 Skills 面板将办公文档转为 Skill，或通过 `/skill-creator` 创建。[官方说明](https://www.kimi.com/en/help/plugins-and-skills/use-skills-in-agent) | 官方确认可创建和调用 Skill；本次核验页面未明确说明本包 ZIP 原样导入和完整执行附带 Python 的方式。不能据此保证零改动运行。完整包迁移优先按 Kimi Code CLI 路径验证。 |
| DeepSeek Harness | 官方本地技能提供器支持项目 `.dsh/skills/merchant-diagnosis/`、`.agents/skills/merchant-diagnosis/` 等目录，识别 `SKILL.md` 中的 `name`、`description`；需要宿主启用对应技能能力。[技能说明](https://github.com/deepseek-ai/deepseek-harness/blob/master/packages/skill/skill-filesystem/README.md) | 官方宿主支持工作区读写与命令执行；项目未实跑。加载本包后检查 Python、依赖和执行权限。[运行说明](https://deepseek-harness.github.io/deepseek-harness/en/guide/quickstart) |
| DeepSeek API ＋ Agent 宿主 | 先选择能运行本包的宿主，再按该宿主的官方集成方式配置模型。DeepSeek 提供 [Codex 集成](https://api-docs.deepseek.com/quick_start/agent_integrations/codex/)及 [WorkBuddy 集成](https://api-docs.deepseek.com/quick_start/agent_integrations/workbuddy/)说明。 | 项目未接入验收。API 的工具调用由客户端实际执行；仅 API 请求或普通聊天粘贴规则不构成完整工作流。[工具调用说明](https://api-docs.deepseek.com/guides/tool_calls/) 普通 DeepSeek 聊天产品是否能原生导入并运行本包，本轮未确认。 |
| WorkBuddy | 客户端 Skills 区域选择 **Add Skill → Upload Skill**，导入本地技能包。官方技能结构包含 `SKILL.md`、`references/`、`scripts/`，脚本由 Bash 执行。[客户端导入](https://intl.cloud.tencent.com/ind/document/product/1316/84503)、[技能结构](https://open.workbuddy.cn/docs/skill) | 官方能力具备，项目未实跑。检查当前客户端的文件访问、Python 及依赖。发布到技能市场另有展示名称、介绍、作者等字段要求，本地导入与市场上架分别验收。 |

这里的安装目录是官方产品约定；不要将某台电脑的绝对路径写入共享报告或分发包。表中的安装／上传操作需要在目标客户端实际完成，本说明不会自动安装或修改模型配置。

## 首次迁移怎样验收

先确认宿主显示 `merchant-diagnosis`，能读到引用文件，再检查 Python 和两项依赖。随后在新的运行目录中执行同一组材料，分别记录以下结果：

1. **读取与计算**：多工作表、混合单位、汇总行和缺失值是否被正确理解；引用能否定位到原单元格，数值能否独立复算。
2. **输出协议**：默认短流程的 `report.json`、`report.html`、计算及校验记录是否完整，首稿失败是否保留；不为通过校验补造数据。独立 API 业务复核与宿主自查分别记录；旧分阶段流程的报告和 `decisions.json` 按其原协议另验。
3. **业务判断**：能否根据门店差异排序、给明确动作；缺数据时是否只暂停相关判断；更正材料或负面结果能否撤回原建议。
4. **交付**：生成的文件能否下载、迁移后能否打开。网页展示应读取实际报告产物，不能拿已有案例代替此次模型输出。

同一输入不要求不同模型逐字一致，但要求关键事实、计算口径、缺口处理、决策依据和输出结构符合共享规则。完成以上检查并保存运行证据后，才将对应“宿主＋模型＋版本”标记为本项目已验证；商家实际执行与经营效果另行记录。
