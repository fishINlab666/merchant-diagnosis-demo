# 商家自助经营诊断工具 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将角色报告演示重构为店名触发、公开初诊可降级、周报可复用的商家自助经营诊断工具。

**Architecture:** 公共检索仅处理公开信息，周报继续在本机做确定性计算。新增检索适配器与公开初诊模型，商家视角决策模型替代三角色视图；失败与缺字段均走显式降级。

**Tech Stack:** React、TypeScript、Vite、Vitest、Playwright、Jina Reader 可选公共读取适配器。

---

### Task 1: 公开检索适配器与公开初诊

**Files:**
- Create: `src/domain/publicSearch.ts`
- Modify: `src/domain/intake.ts`
- Create: `tests/public-search.spec.ts`
- Modify: `tests/intake.spec.ts`

- [ ] **Step 1: 写成功、无结果、超时和无效内容测试**

```ts
const result = await searchPublicMerchant(profile, async () => new Response('# 示例门店\n评分 4.6\n人均 ¥35'))
expect(result.status).toBe('review')
expect(result.sources[0].url).toContain('http')
expect(result.observations.join(' ')).toContain('待确认')

const failed = await searchPublicMerchant(profile, async () => { throw new Error('timeout') })
expect(failed.status).toBe('manual')
expect(failed.sources).toEqual([])
expect(failed.error).toContain('timeout')
```

- [ ] **Step 2: 验证失败**

Run: `npm run test:unit -- --run tests/public-search.spec.ts`
Expected: 模块不存在。

- [ ] **Step 3: 实现可注入 fetch 的检索适配器**

使用 `searchPublicMerchant(profile, fetcher)`，生成带店名／城市／品类的 Jina 搜索 URL，设置超时；解析公开摘要、评分和人均价仅为待确认信息，保留来源与采集日期。任何失败返回 `status='manual'`，不生成公开事实。

- [ ] **Step 4: 实现公开初诊与数据清单**

`buildInitialObservations` 输出公开事实、待验证假设和下一步所需周报，不出现 ROI／利润结论；只有店名没有其他证据时明确提示信息不足。

- [ ] **Step 5: 测试并提交**

Run: `npm run test:unit -- --run tests/public-search.spec.ts tests/intake.spec.ts`
Expected: 全部通过后提交 `feat: add public merchant intake and search fallback`。

### Task 2: 商家视角决策模型与多店铺通用性

**Files:**
- Create: `src/domain/merchantPerspective.ts`
- Modify: `src/domain/diagnosis.ts`
- Modify: `src/domain/cases.ts`
- Create: `tests/merchant-perspective.spec.ts`
- Modify: `evals/cases.mts`

- [ ] **Step 1: 写多商家结构测试**

创建高客单正餐与缺字段／归因异常案例，断言：

```ts
expect(fastFood.module.id).toBe('merchant-action')
expect(fastFood.decisionQuestion).toContain('我的店')
expect(fastFood.followUps).not.toEqual(fineDining.followUps)
expect(missingData.dimensions.filter((item) => item.status === 'missing')).not.toHaveLength(0)
expect(missingData.calculation).toBeNull()
```

另断言同一案例不同角色文案不再进入商家产品主流程。

- [ ] **Step 2: 验证失败**

Run: `npm run test:unit -- --run tests/merchant-perspective.spec.ts`
Expected: 商家视角模型不存在。

- [ ] **Step 3: 实现商家决策模型**

统一为“我的店怎么样、钱漏在哪、下周先改什么”；诊断顺序固化经营结果→P1／P2→工具→补贴毛利→菜品人群→动作。所有数值来自输入；缺字段只关闭对应模块。

- [ ] **Step 4: 增加 EVALS 并验证**

新增不同商家不只换店名、缺失降级、口径阻断、动作停止条件等评测。Run: `npm run test:unit && npm run evals`。

- [ ] **Step 5: 提交**

`git add src/domain tests evals && git commit -m "feat: generalize merchant diagnosis across store cases"`

### Task 3: 商家自助主流程与页面重构

**Files:**
- Create: `src/components/MerchantIntake.tsx`
- Create: `src/components/MerchantDecisionPanel.tsx`
- Modify: `src/App.tsx`
- Modify: `src/components/BusinessHealthView.tsx`
- Modify: `src/components/ReportView.tsx`
- Modify: `src/App.css`
- Delete from active UI: 三角色切换与角色专属视图

- [ ] **Step 1: 写浏览器失败测试**

首屏店名输入为空且没有默认报告；输入店名后触发检索；模拟失败可转人工；公开初诊在周报前可见；上传不同店铺周报后标题、指标和动作改变；页面不出现三角色按钮。

- [ ] **Step 2: 验证失败**

Run: `npm run test:e2e -- --grep "merchant self service"`
Expected: 默认合成报告和角色控件仍存在。

- [ ] **Step 3: 实现主流程**

状态明确为 `intake → public → full`；店名必填，检索状态包含 `idle/searching/review/manual/error`；公开初诊和人工补充共用同一档案；真实上传后清除合成使用数据。

- [ ] **Step 4: 统一商家页面与行动输出**

经营全景改为商家决策面板和六维分析；预算方案改为“我的下周行动方案”；合成案例只在“试用示例”中加载；保留上传、打印和移动端报告优先。

- [ ] **Step 5: 运行测试并提交**

Run: `npm run test:e2e -- --grep "merchant self service" && npm run build`
Expected: 全部通过后提交 `feat: turn demo into merchant self-service tool`。

### Task 4: 全量门禁、视觉验收与部署

- [ ] **Step 1: 完整验证**

Run: `npm run lint && npm run test:unit && npm run build && npm run test:e2e && npm run evals`
Expected: 全绿。

- [ ] **Step 2: 实际检索与降级检查**

验证公共读取不可用、无结果和人工补充路径；如公共读取在浏览器跨域失败，保留明确错误和人工入口，不宣称联网检索稳定可用。

- [ ] **Step 3: 多商家视觉检查**

检查三类店铺桌面、移动和打印，保留截图；确认不是只换店名。

- [ ] **Step 4: 合并部署并核对公开站点**

合并到 `main`，等待 Pages 成功，逐一验证首屏、公开初诊降级和不同店铺完整诊断。
