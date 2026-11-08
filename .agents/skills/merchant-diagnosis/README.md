# 商户经营诊断 Skill

把店铺资料与现有周报交给 Agent，得到「哪里有问题、钱差在哪里、先做什么」的老板看板。**默认三步：读取材料 → 判断并计算 → 导出 HTML**。客户不用先把周报改成固定表头。

## 哪些是作者的 KA 经验

[KA 经营打法](references/ka-playbook.md)是默认运行实际加载的业务方法，具体规定：

- 按收益质量 × 增长给不同门店不同资源动作，而非只报品牌均值。
- 将客群与场景、商品和权益串起来，区分触达问题与下单承接问题。
- 先选经营策略再配工具；用诊断、培训、接口人和回传推动无直接管理权的门店执行。

原经历中的平台 UE 已改写为本次商户的贡献口径；边际约束、执行留痕和扩围条件是根据复盘补强的当前设计。方法文件不带私人履历、历史业绩数字或固定商家答案。1.7.1 将它冻结进宿主/API分析与独立API复核；三步操作和老板报告格式不变。

## 第一次使用

完整复制 `merchant-diagnosis/` 文件夹到项目技能目录：

- Codex：`.agents/skills/merchant-diagnosis/`
- Claude Code：`.claude/skills/merchant-diagnosis/`

需要 Python 3.10+。请让 Agent 在技能目录运行一次：

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

后续执行脚本使用技能目录的 `.venv/bin/python`，避免系统里多套Python装错依赖。

然后只发这段话（首次体验可直接用自带合成案例）：

```text
使用 merchant-diagnosis，分析技能目录 examples/chain/raw/ 的 public.md、definitions.md、经营周报.xlsx 三份材料。
这是新的独立合成演示实例；只读原始材料，不读既有报告或验算答案。
按默认 quick 流程完成实际计算，直接给我老板看板 report.html。
先说最值得做的事；主卡用本次策略在审慎情况下的月度贡献改善差额，再给负责人和止损线。
区分新增与总预算，继续条件看相对可比基线的贡献差额；其他问题只列会改变决定的补数。
把本次文件保存在新的运行目录；遇到缺口仅暂停受影响的金额，其余继续交付。
execution_receipts.md 是后续复盘材料，本次不加载；CSV是工作簿镜像，不重复计入。
```

换单店：将输入替换为 `examples/packaging/raw/` 的店铺资料、老板口径、乱格式工作簿；CSV镜像不再重复计入。换真实商家：把自己的资料和目标一并交给 Agent。只给公开页面也能先出初诊和定向补数，不编造内部经营数据。

Agent 自动完成准备、计算、导出；不用你逐个复制 JSON。输出目录内的 `report.html` 可双击、转发或用浏览器打印，旁边保存原始资料索引、计算和报告JSON。

## 无需 Agent 的独立 API 入口

已经安全配置 `DEEPSEEK_API_KEY` 时，在技能目录运行（替换为账户可用模型）：

```sh
.venv/bin/python scripts/quick_run.py api \
  --input examples/chain/raw/public.md examples/chain/raw/definitions.md examples/chain/raw/经营周报.xlsx \
  --merchant '榕味小馆30店·独立演示' --scope '30家门店' \
  --goal '预算总额不增，找出可试行的月度经营贡献改善' \
  --synthetic --model deepseek-v4-pro --output runs/chain-new
```

本命令真实调用模型并执行计算，会把指定材料发给 DeepSeek。当前 Agent 模式使用宿主本身的模型，不需要这项配置。模型ID以账户实际可用项为准；密钥不要写入命令文本、仓库或聊天。

每次模型请求默认等待最多 120 秒，可用 `--timeout 1` 至 `--timeout 120` 调整。网络或模型响应过慢仍可能失败；失败记录会保留，不会改用预置报告冒充完成。

## 支持与处理方式

| 情况 | 怎么处理 |
| --- | --- |
| 表头不同、横竖排混用、多工作表、万元/元混用 | 保留原位置，由模型结合备注解释并计算，不匹配固定列名 |
| 成本占比、净结算口径由老板说明 | 直接采用并记录来源；实质冲突才追问 |
| 缺成本、缺某一张表 | 暂停受影响净额，继续交发现、可确定动作及需要补的字段 |
| 标题/编号/可选字段格式差异 | 程序规范化，不再要求五套阶段表反复返工 |
| 图片、扫描件、链接 | 由宿主识图/OCR/联网获取；内置读取器不声称已解析看不到的内容 |
| 收到更正数据或实际执行结果 | 新建一轮，加 `--previous-report <前轮/report.json>` 带上原判断，重新算受影响部分，明确保留/调整/撤回 |

支持的文件是UTF-8文本、CSV/TSV、XLSX、文本PDF、已保存HTML。“任意格式周报”指这些文件内的不同布局，不代表损坏文件、扫描件或超限材料可无条件解析。

业务方法见 [SKILL.md](SKILL.md)，实际兼容与测试状态见 [验收记录](references/release-status.md)。五阶段档案模式保留在 [服务说明](references/service-operation.md)，首次体验无需使用。

## 本地检查

```sh
.venv/bin/python -m unittest discover -s tests -v
```

软件测试、模型实跑、页面检查与商家执行分别记录。示例为合成材料；历史试行记录不是这个 Skill 促成的经营效果。
