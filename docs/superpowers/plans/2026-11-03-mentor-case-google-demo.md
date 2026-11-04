# Mentor Case + Google Demo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the mentor case's evidence-led intake, decision visuals and guided presentation to the existing single-merchant diagnostic tool, with a flat Google-color interface.

**Architecture:** Keep domain calculations as pure TypeScript and add focused React views. Reuse `buildDiagnosis` as the only budget/profit formula source, gate synthetic history behind `report.synthetic`, and render charts with local SVG/HTML rather than adding dependencies.

**Tech Stack:** React 19, TypeScript 7, Vite 8, Vitest 5, Playwright, existing CSV/XLSX parsers and CSS.

---

### Task 1: Public text intake

**Files:**
- Modify: `src/domain/intake.ts`
- Create: `src/components/PublicIntakeView.tsx`
- Modify: `src/components/MerchantIntake.tsx`, `src/App.tsx`
- Test: `tests/public-intake.spec.ts`

- [ ] Write failing tests for field extraction, review quotes, user-supplied competitor medians, three-candidate cap and empty-evidence behavior.
- [ ] Run `npx vitest run tests/public-intake.spec.ts`; expect missing-export failure.
- [ ] Implement this public contract and parser without network calls:

```ts
export interface PublicIntakeAnalysis {
  facts: { name: string; rating: number | null; monthlySales: number | null; averagePrice: number | null; minimumOrder: number | null; deliveryFee: number | null; deliveryMinutes: number | null; menuItems: string[] }
  themes: Array<{ id: string; label: string; count: number; quotes: string[] }>
  competitors: Array<{ name: string; rating: number | null; monthlySales: number | null; averagePrice: number | null; deliveryMinutes: number | null }>
  candidates: Array<{ title: string; evidence: string; hypothesis: string; action: string; quote?: string }>
}
export function parsePublicIntake(text: string): PublicIntakeAnalysis
```

- [ ] Connect the view through `App` state; fill only confirmable profile fields and keep the existing manual/search fallback.
- [ ] Run intake tests and existing `tests/intake.spec.ts`; expect PASS.
- [ ] Commit `feat: add evidence-led public shop intake`.

### Task 2: Deterministic trend and chart primitives

**Files:**
- Create: `src/domain/demoSeries.ts`, `src/components/Charts.tsx`
- Modify: `src/components/BusinessHealthView.tsx`, `src/components/ReportView.tsx`
- Test: `tests/demo-series.spec.ts`

- [ ] Write failing tests proving eight deterministic points, exact current-week reconciliation and `[]` for real reports.
- [ ] Run the test; expect missing-module failure.
- [ ] Implement:

```ts
export interface DemoWeek { weekStart: string; netGmv: number; spend: number; roi: number }
export function buildDemoSeries(report: WeeklyReport): DemoWeek[]
```

- [ ] Add `WeeklyTrend`, `ToolEfficiencyBars`, `BudgetMix`, and `ProfitWaterfall`; every chart gets an accessible name and visible values.
- [ ] Render history only for synthetic reports; tool bars remain valid for real current-week data.
- [ ] Run chart/domain tests and build; expect PASS.
- [ ] Commit `feat: add decision charts and synthetic trends`.

### Task 3: Calculation assumptions and contribution breakdown

**Files:**
- Modify: `src/domain/types.ts`, `src/domain/diagnosis.ts`, `src/components/AssumptionsPanel.tsx`, `src/App.tsx`
- Test: `tests/diagnosis.spec.ts`

- [ ] Add failing tests: existing defaults remain `2560/1152`, monthly uses 4.3, negative subsidy delta creates a GMV/profit deduction, zero subsidy delta creates no deduction.
- [ ] Run tests; expect missing-field/value failures.
- [ ] Extend types compatibly:

```ts
period?: 'week' | 'month'
subsidyOrderLossRate?: number
// Calculation optional contributions:
budgetContribution?: number
subsidyContribution?: number
orderLossContribution?: number
```

- [ ] Use one `makeCalculation` path for display, talk tracks, waterfall and validation. Do not change attribution gates or recommendation rules.
- [ ] Add constrained sliders paired with numeric inputs; retain labels `调整金额（元）`, `毛利率（%）`, `边际 ROI 折算（%）`, and `商家补贴变化（元）`.
- [ ] Run all unit tests; expect PASS including legacy calculations.
- [ ] Commit `feat: add transparent scenario contributions`.

### Task 4: Boss questions, copy and guided auto-demo

**Files:**
- Create: `src/domain/bossQuestions.ts`, `src/components/BossQuestions.tsx`
- Modify: `src/components/DemoWalkthrough.tsx`, `src/components/ReportView.tsx`
- Test: `tests/boss-questions.spec.ts`, `e2e/mentor-case.spec.ts`

- [ ] Write failing tests for four evidence-bound offline answers, fallback on fetch failure, and rejection of added numbers or guarantee wording.
- [ ] Implement `buildOfflineBossAnswers`, `validateBossAnswer`, and `requestBossAnswer`; only synthetic context may use the optional AI route.
- [ ] Add four question buttons, visible answer-source badge, copy confirmation and manual-copy fallback.
- [ ] Add one-click full demo with narration and reduced-motion zero delays; retain manual next-step flow.
- [ ] Run focused unit/E2E tests; expect PASS.
- [ ] Commit `feat: add boss Q&A and full guided demo`.

### Task 5: Google flat visual system and responsive QA

**Files:**
- Modify: `src/index.css`, `src/App.css`, relevant component class names only
- Test: `e2e/mentor-case.spec.ts`, existing E2E suite

- [ ] Define brand/error/success/warning variables independently.
- [ ] Style primary actions, tabs, decision headers, charts, cards and statuses with flat surfaces; no gradients, glass or decorative shadows.
- [ ] Verify 1440px desktop, 390px mobile, keyboard focus, reduced motion and A4 print.
- [ ] Run `npm run lint && npm run test:unit && npm run build && npm run test:e2e && npm run evals`.
- [ ] Save before/after screenshots under `artifacts/mentor-case-google` and inspect the generated images.
- [ ] Commit `feat: apply Google flat design system`.

### Task 6: Deploy and verify

**Files:**
- Modify only if a verified defect requires it.

- [ ] Re-run the complete verification command and check `git diff --check`.
- [ ] Merge the feature branch into `main`, push `origin main`, and wait for the existing Pages workflow.
- [ ] Verify the public URL, public intake, guided demo, report charts and mobile layout.
- [ ] Report the public URL, changed modules, verification counts, screenshot path and any remaining limitation honestly.

## Self-review

- Every reference-case capability selected in the design maps to Tasks 1–4; visual and delivery requirements map to Tasks 5–6.
- Excluded reference content remains excluded: role switching, 186-store quadrant, renewal health, random evidence and causal/guaranteed claims.
- Property names are consistent: `parsePublicIntake`, `buildDemoSeries`, `buildOfflineBossAnswers`, `subsidyOrderLossRate`, and contribution fields are used unchanged across domain, views and tests.
- No placeholders or alternative formula path are introduced.
