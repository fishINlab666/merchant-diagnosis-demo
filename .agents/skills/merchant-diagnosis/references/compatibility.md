# 跨 Agent 使用与验证状态

官方资料核对日期：2026-11-06。本说明随 `merchant-diagnosis` 完整文件夹分发，安装入口可能随客户端版本调整。

这套 Skill 提供经营方法、阶段输出、计算脚本和校验规则；Agent 宿主负责加载文件、调用模型和执行脚本。支持 `SKILL.md` 说明宿主可以加载规则，不代表已经装齐依赖，也不代表不同模型对陌生周报会得出同样可靠的判断。

**当前项目实际运行验证仅覆盖 Codex 与合成材料。**下表中的“官方支持”指查阅官方资料确认了相应能力，不等于本项目已在该产品中完成运行。Claude、Kimi、DeepSeek、WorkBuddy 的项目验收均待进行；现有记录也不代表真实商家执行效果。

## 共同运行条件

完整复制文件夹，保留 `SKILL.md`、`references/`、`scripts/`、`assets/` 和 `requirements.txt` 的相对位置。仅复制一个 Markdown 文件无法运行数据读取和校验流程；网页导出另需完整保留 assets 模板。

| 条件 | 本 Skill 的要求 | 缺少时如何处理 |
|---|---|---|
| 文件能力 | 能读取本次指定原始材料、相对引用文件，并写入独立运行目录 | 明确缺少哪个文件或权限；不把无法读取视为零值 |
| 命令执行 | 能执行本包的 Python 读取、计算和校验脚本 | 只读规则的会话不能标为完整运行通过 |
| Python | Python 3.10 或更高版本 | 在宿主实际执行环境检查，不凭本机安装情况推断云端容器可用 |
| XLSX | `openpyxl>=3.1,<4` | 准备依赖，或由用户提供 CSV；不能把替代格式计为 XLSX 验收 |
| 文本 PDF | `pypdf>=5,<7` | 准备依赖，或提供可读文字；扫描件不计入已验证自动解析范围 |
| 模型与上下文 | 能读取阶段材料、遵守输出协议，并根据新增数据更新判断 | 材料超限时分批处理；不得静默截断后给完整结论 |
| 运行记录 | 记录实际宿主、实际模型（可知时）、时间、输入指纹、计算和校验结果 | 未暴露的模型 ID 写“未暴露”，不根据客户端名称猜模型 |

依赖及数据格式边界以[输入与运行说明](operation.md)和[依赖文件](../requirements.txt)为准。命令应在宿主可访问的 Skill 根目录执行，输出目录另选有写权限的新位置。客户材料只在选定运行环境中分析；本包不自带模型 API 接入器。

## 各宿主入口

| 宿主／产品形态 | 官方确认的导入与使用方式 | 本项目状态与边界 |
|---|---|---|
| Codex | 将完整文件夹放入项目 `.agents/skills/merchant-diagnosis/` 或用户 `~/.agents/skills/merchant-diagnosis/`，再在会话中明确调用。官方文档列出项目和用户技能目录。[官方说明](https://learn.chatgpt.com/docs/build-skills) | 已有 Codex 合成材料实跑记录。换电脑、容器或模型后，仍需核对依赖并复跑；目录被发现不等于业务验收通过。 |
| Claude Code（本地） | 放入项目 `.claude/skills/merchant-diagnosis/` 或用户 `~/.claude/skills/merchant-diagnosis/`，通过 `/merchant-diagnosis` 调用。官方支持附带脚本和参考文件。[官方说明](https://code.claude.com/docs/en/skills) | 官方能力具备，项目未实跑。须允许读取材料及运行 Python。Cowork／云端会话的加载规则不同，不能假设它们会读取本机用户目录。 |
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
2. **输出协议**：阶段报告、`decisions.json` 及校验记录是否完整，首稿失败是否保留；不为通过校验补造数据。
3. **业务判断**：能否根据门店差异排序、给明确动作；缺数据时是否只暂停相关判断；更正材料或负面结果能否撤回原建议。
4. **交付**：生成的文件能否下载、迁移后能否打开。网页展示应读取实际报告产物，不能拿已有案例代替此次模型输出。

同一输入不要求不同模型逐字一致，但要求关键事实、计算口径、缺口处理、决策依据和输出结构符合共享规则。完成以上检查并保存运行证据后，才将对应“宿主＋模型＋版本”标记为本项目已验证；商家实际执行与经营效果另行记录。
