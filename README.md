# 商户经营诊断 Skill

把店铺资料和现有周报交给 Agent，得到一页「发现、钱账、先做什么」的老板看板。支持单店、连锁、有投放和无投放场景；老板已说明的口径直接采用，缺数只暂停受影响的测算。

[打开演示看板](https://fishinlab666.github.io/merchant-diagnosis-demo/) · [首次运行录屏](public/media/first-run.mp4) · [下载 v1.7](releases/merchant-diagnosis-v1.7.zip) · [验收记录](ACCEPTANCE.md)

![连锁经营看板](public/media/chain-firstfold.png)
![单店经营看板](public/media/single-firstfold.png)

## 安装

下载并解压，将完整的 `merchant-diagnosis/` 放入项目目录：Codex 用 `.agents/skills/merchant-diagnosis/`；Claude Code 用 `.claude/skills/merchant-diagnosis/`。本轮已完成 Codex CLI 实跑，Claude Code 验收由用户推迟。

需要 Python 3.10+。以 Codex 目录为例，安装一次依赖：

```sh
cd .agents/skills/merchant-diagnosis
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

安装后执行技能脚本统一使用技能目录的 `.venv/bin/python`。Claude Code 使用对应安装目录。

## 复制这段话开始

```text
使用 merchant-diagnosis，分析技能目录 examples/chain/raw/ 的 public.md、definitions.md、经营周报.xlsx 三份材料。
这是新的独立合成演示实例；只读原始材料，不读既有报告或验算答案。
按默认 quick 流程完成实际计算，直接给我老板看板 report.html。
先说最值得做的事；主卡用本次策略在审慎情况下的月度贡献改善差额，再给负责人和止损线。
区分新增与总预算，继续条件看相对可比基线的贡献差额；其他问题只列会改变决定的补数。
把本次文件保存在新的运行目录；遇到缺口仅暂停受影响的金额，其余继续交付。
execution_receipts.md 是后续复盘材料，本次不加载；CSV 是工作簿镜像，不重复计入。
```

Agent 完成读取材料、判断并计算、导出 HTML 三个核心动作；这不等于三次工具或模型调用。产物在本轮新目录的 `report.html`，可用浏览器打开、转发或打印。你不用逐项复制 JSON。

## 换成自己的材料

将提示词中的路径换成店铺资料、老板口径和现有周报，并说明本轮目标。不要求固定表头。仅有公开资料时先给初诊和定向补数，不编内部营收或利润；图片、扫描件和在线页面由宿主获取与识别。

自带材料都在技能目录的 `examples/` 下：

| 场景 | 原始材料目录 |
| --- | --- |
| 连锁餐饮 | `examples/chain/raw/` |
| 单店外卖与包装取舍 | `examples/packaging/raw/` |
| 六店分层、局部缺成本 | `examples/segmented/raw/` |
| 无投放宠物洗护 | `examples/pet-care/raw/` |

录屏为真实 Codex CLI 会话：原始全程约 202 秒，等待段 1.25 倍速，交付片 2:50。过程中包含模型自行修复，详见验收记录。

[Skill 使用说明](.agents/skills/merchant-diagnosis/README.md)含独立 API 入口、文件范围与更正数据的用法。示例均为模拟商家；已做软件测试与模型实跑，尚无真实商家执行效果。

## 展示层与历史版本

当前首页是固定面试展示页，打开报告不会启动分析；新材料由 Agent 或独立 API 处理后再导出。`src/` 保留早期网页源码，当前发布用 `python3 scripts/build-showcase.py` 构建静态展示，不依赖前端框架。历史 v1.4 报告与安装包仍保留，首次体验请使用 v1.7。
