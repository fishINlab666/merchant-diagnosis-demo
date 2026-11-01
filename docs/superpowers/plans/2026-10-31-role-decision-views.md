# 三种角色决策视图 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让平台 KA、服务商、SaaS 客户成功在同一经营事实上获得不同的问题排序、决策模块、输出和跟进动作，并用结构测试禁止“只换文案”通过。

**Architecture:** 保留 `buildDiagnosis` 的确定性计算与 `analyzeBusinessHealth` 的六维事实，新增纯函数 `buildRolePerspective` 负责角色视图模型。新增 `RoleDecisionPanel` 复用角色证据；两个主视图只负责呈现。SaaS 使用行为作为可选独立输入，缺失时降级。

**Tech Stack:** React 19、TypeScript、Vite、Vitest、Playwright、现有 EVALS。

---

### Task 1: 角色视图模型与结构单元测试

**Files:**
- Create: `src/domain/rolePerspective.ts`
- Modify: `src/domain/types.ts`
- Modify: `src/domain/cases.ts`
- Create: `tests/role-perspective.spec.ts`

- [ ] **Step 1: 写失败测试**

覆盖三种角色模块 ID、六维顺序、共享事实、决策指标、SaaS 使用数据缺失降级：

```ts
const ka = buildRolePerspective('ka', mainCase, health, diagnosis, null)
const agency = buildRolePerspective('agency', mainCase, health, diagnosis, null)
const cs = buildRolePerspective('cs', mainCase, health, diagnosis, mainProductUsage)
expect(new Set([ka.module.id, agency.module.id, cs.module.id]).size).toBe(3)
expect(agency.dimensions.map((item) => item.id)).not.toEqual(ka.dimensions.map((item) => item.id))
expect(cs.usage.status).toBe('available')
expect(buildRolePerspective('cs', controlCase, controlHealth, controlDiagnosis, null).usage.status).toBe('missing')
```

- [ ] **Step 2: 验证测试失败**

Run: `npm run test:unit -- --run tests/role-perspective.spec.ts`
Expected: FAIL，提示无法导入 `rolePerspective`。

- [ ] **Step 3: 实现独立类型、合成使用数据和纯函数**

新增 `ProductUsage`、角色视图接口和 `buildRolePerspective`。每个角色返回固定模块 ID：`jbp-budget`、`acquisition-delivery`、`health-renewal`；六维排序按设计文档执行；原始 `merchant/comparison/evidence` 不改写。CS 没有 `ProductUsage` 时返回 `usage.status='missing'` 且不输出风险等级。

- [ ] **Step 4: 验证单元测试通过**

Run: `npm run test:unit -- --run tests/role-perspective.spec.ts`
Expected: 全部通过，且共享事实与计算未变化。

- [ ] **Step 5: 提交**

`git add src/domain tests/role-perspective.spec.ts && git commit -m "feat: add role decision view model"`

### Task 2: 角色化问题排序、话术与跟进表

**Files:**
- Modify: `src/domain/diagnosis.ts`
- Modify: `tests/diagnosis.spec.ts`
- Modify: `evals/cases.mts`

- [ ] **Step 1: 写失败测试**

```ts
const ka = buildDiagnosis(mainCase, assumptions, 'ka')
const agency = buildDiagnosis(mainCase, assumptions, 'agency')
const cs = buildDiagnosis(mainCase, assumptions, 'cs')
expect(agency.issues.map((issue) => issue.code)).not.toEqual(ka.issues.map((issue) => issue.code))
expect(new Set([ka.followUps[0].action, agency.followUps[0].action, cs.followUps[0].action]).size).toBe(3)
expect(ka.calculation).toEqual(agency.calculation)
expect(agency.calculation).toEqual(cs.calculation)
```

另用 `controlCase` 断言归因异常下三种角色仍有各自跟进动作，但 `recommendation/calculation` 均为空。

- [ ] **Step 2: 验证失败**

Run: `npm run test:unit -- --run tests/diagnosis.spec.ts`
Expected: 当前实现的问题顺序与跟进动作相同，结构断言失败。

- [ ] **Step 3: 实现最小角色逻辑**

为问题排序增加角色优先级，硬数据边界保持最高优先级；`makeFollowUps` 接收 `role` 并分别生成预算执行、客户交付、健康干预动作；所有话术分支均保留角色语义。不得修改 ROI、GMV、毛利公式。

- [ ] **Step 4: 运行测试与 EVALS**

Run: `npm run test:unit && npm run evals`
Expected: 单元测试通过；新增角色 EVALS 通过，既有业务规则不回归。

- [ ] **Step 5: 提交**

`git add src/domain/diagnosis.ts tests/diagnosis.spec.ts evals && git commit -m "feat: differentiate role priorities and follow-ups"`

### Task 3: 重构经营全景和预算输出

**Files:**
- Create: `src/components/RoleDecisionPanel.tsx`
- Modify: `src/components/BusinessHealthView.tsx`
- Modify: `src/components/ReportView.tsx`
- Modify: `src/App.tsx`
- Modify: `src/App.css`

- [ ] **Step 1: 写浏览器结构失败测试**

Create: `e2e/role-decision.spec.ts`。遍历三个角色，读取 `data-decision-module`、首个六维标题、角色指标和跟进动作，断言三组结构不同；同时断言净 GMV、订单和测算数字保持一致。

- [ ] **Step 2: 验证失败**

Run: `npm run test:e2e -- --grep "role decision"`
Expected: 找不到角色决策模块和角色化行动区域。

- [ ] **Step 3: 实现角色面板与两个主视图改造**

`RoleDecisionPanel` 输出角色标题、决策问题、三项指标和完整角色模块。经营全景按角色排序六维并追加角色解释、角色化竞店／城市说明和下一步动作；预算方案使用角色化标题、问题顺序、话术和跟进表。SaaS 缺数据时显示“未提供”和补数据动作。

- [ ] **Step 4: 加响应式与打印样式**

复用红／米白／黑变量；角色指标使用自适应网格，行动卡在移动端单列，打印时避免卡片内分页。不得增加大型依赖。

- [ ] **Step 5: 运行浏览器测试**

Run: `npm run test:e2e -- --grep "role decision"`
Expected: 三种角色结构断言和共享数字断言全部通过。

- [ ] **Step 6: 提交**

`git add src e2e/role-decision.spec.ts && git commit -m "feat: rebuild role decision views"`

### Task 4: 全量验证、视觉检查与部署

**Files:**
- Modify if required: `README.md`
- Verify: `src/**`、`tests/**`、`e2e/**`、`evals/**`

- [ ] **Step 1: 运行完整质量门禁**

Run: `npm run lint && npm run test:unit && npm run build && npm run test:e2e && npm run evals`
Expected: 所有命令退出码为 0。

- [ ] **Step 2: 检查实际渲染**

用浏览器分别检查三种角色的经营全景和预算方案、移动端、打印；确认差异来自模块和动作，不只是文案。保留关键截图。

- [ ] **Step 3: 提交文档并部署**

提交已确认的设计与计划文档，推送 `main`，等待 GitHub Pages 工作流成功，再验证正式站点三种角色。

- [ ] **Step 4: 最终核对**

确认合成数据标识仍在、真实上传无 SaaS 使用数据时降级、共享计算一致、公开链接可访问；如实列出任何未解决项。
