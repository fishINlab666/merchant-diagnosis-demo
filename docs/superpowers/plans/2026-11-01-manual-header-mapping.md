# 手动表头映射校正 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 允许用户在表头预览中手动校正标准字段，并实时更新可生成状态。

**Architecture:** `buildHeaderMapping` 负责自动匹配，`evaluateHeaderMappings` 负责根据当前字段列表计算缺失、重复和模块状态。预览组件回调修改列表，App 保存重算后的同一映射供解析使用。

**Tech Stack:** React、TypeScript、Vitest、Playwright。

---

### Task 1: 手动映射评估

- Files: `src/lib/reportMapping.ts`、`tests/report-mapping.spec.ts`
- [ ] 写未知列手动映射为净 GMV、手动排除必需字段、手动重复映射测试。
- [ ] 运行测试确认 `evaluateHeaderMappings` 不存在而失败。
- [ ] 抽取评估函数，新增 `match='manual'` 和标准字段选项列表，自动匹配继续复用同一评估逻辑。
- [ ] 运行全部单元测试并提交 `feat: support manual header mapping evaluation`。

### Task 2: 下拉校正与浏览器流程

- Files: `src/components/HeaderMappingPreview.tsx`、`src/components/MerchantIntake.tsx`、`src/App.tsx`、`src/App.css`、`public/fixtures/manual-weekly.csv`、`e2e/merchant-self-service.spec.ts`
- [ ] 新增未知列测试文件，写浏览器测试：未知列先阻断，下拉映射为净 GMV 后按钮启用，确认后生成；制造重复后再次禁用。
- [ ] 运行测试确认当前无法修改映射而失败。
- [ ] 实现行内下拉和 `onMappingChange`，实时重算预览，最终解析使用手动映射。
- [ ] 运行全部浏览器测试和生产构建，提交 `feat: allow editing header mappings`。

### Task 3: 验证与部署

- [ ] 运行 lint、全部单元测试、浏览器测试、业务评测和构建。
- [ ] 检查桌面、移动、打印与线上流程，合并到 `main` 并验证公开站点。
