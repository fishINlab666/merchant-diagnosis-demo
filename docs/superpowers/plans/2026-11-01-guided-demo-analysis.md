# 分步演示分析流程 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为面试提供预填数据、逐步分析和结果展示的完整演示流程。

**Architecture:** 新增纯函数生成六步证据，`DemoWalkthrough` 管理信息、周报、分析和结果四个阶段。实际计算复用现有引擎，完成后调用现有 `loadCase` 进入诊断。

**Tech Stack:** React、TypeScript、Vitest、Playwright。

---

### Task 1: 六步证据模型

- Files: `src/domain/demoWalkthrough.ts`、`tests/demo-walkthrough.spec.ts`
- [ ] 写六步数量、真实 ROI／GMV／毛利、样本数、异常案例无测算测试。
- [ ] 验证模块不存在后实现 `buildDemoStages(report, diagnosis, health)`。
- [ ] 运行单元测试并提交 `feat: add guided analysis evidence model`。

### Task 2: 分步演示组件

- Files: `src/components/DemoWalkthrough.tsx`、`src/components/MerchantIntake.tsx`、`src/App.tsx`、`src/App.css`
- [ ] 写浏览器测试：点击演示按钮后看到预填信息，下一步看到映射，开始分析后出现六步状态，查看结果进入现有诊断。
- [ ] 实现预填门店、实际 fixture 映射、逐步揭示证据和结果衔接。
- [ ] 支持减少动态效果、运行中禁止重复启动、移动端单列。
- [ ] 运行 E2E 和构建并提交 `feat: add guided merchant analysis demo`。

### Task 3: 验收与部署

- [ ] 运行完整质量门禁并保存信息页、映射页、分析中、结果页截图。
- [ ] 合并 `main`，线上按同一路径验收。
