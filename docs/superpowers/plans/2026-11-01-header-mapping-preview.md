# 表头映射预览 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 上传后先展示字段映射、缺失项和模块开放状态，用户确认后再生成诊断。

**Architecture:** 新增独立映射纯函数和预览组件；文件读取只负责表头，确认后的映射传入现有 `normalize`，不修改指标公式。

**Tech Stack:** React、TypeScript、Vitest、Playwright。

---

### Task 1: 映射规则与解析

**Files:** `src/lib/reportMapping.ts`、`src/lib/weeklyReport.ts`、`tests/report-mapping.spec.ts`、`tests/weekly-report.spec.ts`

- [ ] 写精确匹配、规则别名、缺必需字段、重复映射、可选模块关闭测试。
- [ ] 运行 `npm run test:unit -- --run tests/report-mapping.spec.ts`，确认模块不存在而失败。
- [ ] 实现 `buildHeaderMapping(headers)`，返回 `mappings/missingRequired/duplicateStandards/modules/canGenerate`。
- [ ] 为 CSV／XLSX 增加表头读取函数，并允许 `parseCsvWeeklyReport`／`parseXlsxWeeklyReport` 接收确认映射。
- [ ] 运行全部单元测试并提交 `feat: add weekly report header mapping`。

### Task 2: 上传预览与确认界面

**Files:** `src/components/HeaderMappingPreview.tsx`、`src/components/MerchantIntake.tsx`、`src/App.tsx`、`src/App.css`、`e2e/merchant-self-service.spec.ts`

- [ ] 写浏览器测试：选择文件后先出现预览，报告尚未生成；缺失字段时确认按钮禁用；确认后才进入诊断。
- [ ] 运行 `npm run test:e2e -- --grep "header mapping"`，确认失败。
- [ ] 实现预览组件和 App 状态：`mappingPreview/file/uploadState`，换文件清空旧映射。
- [ ] 在公开初诊和完整报告的上传区复用预览，按钮改为“确认映射并生成诊断”。
- [ ] 运行全部浏览器测试、构建并提交 `feat: add header mapping confirmation flow`。

### Task 3: 验证与部署

- [ ] 运行 `npm run lint && npm run test:unit && npm run build && npm run test:e2e && npm run evals`。
- [ ] 检查桌面、移动和打印；保留映射预览截图。
- [ ] 合并 `main`，等待 Pages 成功并核对线上预览和确认流程。
