# 本机录屏入口

用于演示“选入材料 → 真实模型分析和计算 → 本次看板”，只监听本机地址。它是录屏辅助入口；日常直接按仓库 README 将材料交给 Agent 即可。

## Codex（本次交付录屏使用）

先按 Skill README 安装 Python 依赖，并确保本机 Codex CLI 已登录。从仓库根目录运行：

```sh
.agents/skills/merchant-diagnosis/.venv/bin/python tools/recording-server.py --backend codex
```

打开终端给出的地址，选择 `public.md`、`definitions.md`、`经营周报.xlsx` 三份连锁示例材料，再启动。默认寻找 PATH 中的 `codex`；找不到时用 `--codex-bin` 指定你本机的实际可执行文件。此模式创建独立 Codex 会话和新输出目录，使用当前 Codex 模型与本地计算脚本，不另调用 DeepSeek。

录屏已准备 Python 依赖；安装耗时不包含在演示内。每次任务写入 `tools/recorded-runs/`，失败保留原件，不回退到预置报告。此目录不进入版本库。

## 独立 DeepSeek API（仍需逐稿业务复核）

在本机配置 `DEEPSEEK_API_KEY` 后运行：

```sh
.agents/skills/merchant-diagnosis/.venv/bin/python tools/recording-server.py --backend deepseek
```

也可通过 `--config` 指定专用本机配置文件，不要在浏览器上传配置文件。选中的材料会发送给模型服务并产生账户费用；默认深度思考开启、输出额度 24576、总调用上限 8。用 `--model` 指定可用模型。API 技术链路已有真实运行，但本轮业务成稿未通过交付验收，具体失败与修订见仓库 ACCEPTANCE.md；本页不会把预置报告当作失败后的替代结果。

## 本机回归

```sh
python3 -B -m unittest discover -s tools/tests -p 'test_recording_server.py' -v
```

使用临时文件和假 CLI 验证依赖解释器、并发任务及退出状态，不调用真实模型。
