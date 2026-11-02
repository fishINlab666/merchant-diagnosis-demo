# 四项 P1 验收修复 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复店名身份、合成样本、公开检索和 AI 能力四个验收阻断项。

**Architecture:** 文件身份进入预览并确认归属；真实上传不使用合成样本；公共检索多提供方降级；AI 仅做白名单方向选择，规则负责所有事实和计算。

**Tech Stack:** React、TypeScript、Vitest、Playwright、Bing／DuckDuckGo 公共读取、受限文本模型接口。

---

### Task 1: 门店身份确认

- [ ] 为 `WeeklyReport` 增加 `sourceStoreId`，为 `StoreProfile` 增加 `storeId`，写文件身份保留、空 ID 拒绝、档案不一致阻断测试。
- [ ] 文件预览读取文件门店 ID，展示档案与文件身份；未填时确认后绑定，不一致时禁止生成。
- [ ] 浏览器验证错 ID 不生成，未填 ID 确认后绑定。
- [ ] 提交 `fix: verify merchant identity before diagnosis`。

### Task 2: 真实数据与合成样本隔离

- [ ] 写真实上传不出现合成竞店和城市分层、合成案例保留样本的测试。
- [ ] `App` 仅对 `report.synthetic` 传入合成 peers/cities，真实上传对应模块不渲染。
- [ ] 运行 E2E 并提交 `fix: isolate synthetic benchmarks from real reports`。

### Task 3: 多提供方公开检索

- [ ] 写首个提供方失败后切换、验证码拒绝、全部失败转人工测试。
- [ ] 按 Bing → DuckDuckGo 实现提供方 fallback，保留真实来源。
- [ ] 实测线上公开检索，确认不再固定返回 Google 403。
- [ ] 提交 `fix: add resilient public merchant search`。

### Task 4: 受约束 AI 与回退

- [ ] 写合法 ID 使用、未知 ID 回退、请求失败回退、真实周报零 AI 请求测试。
- [ ] AI 仅从四个白名单方向选择，所有解释和数字由本地规则生成。
- [ ] 在公开初诊中标注 AI 使用或规则回退原因。
- [ ] 提交 `feat: add constrained AI public intake fallback`。

### Task 5: 全量验证与部署

- [ ] 运行 lint、单元测试、E2E、EVALS、构建和视觉检查。
- [ ] 合并 `main`，线上复核四个 P1 的真实行为和合成案例回归。
