# Three Role Decision Views Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add structurally different merchant-owner, platform-KA and SaaS-customer-success decision views without changing shared diagnosis facts or inventing missing evidence.

**Architecture:** Extend the existing diagnosis/perspective pipeline rather than creating three calculators. Build role-specific pure models and focused components for city segmentation and customer health, then integrate a persistent role switch in `App`.

**Tech Stack:** React 19, TypeScript, Vite, Vitest, Playwright, existing SVG chart and CSS system.

---

### Task 1: Role perspective model

**Files:** Create `src/domain/rolePerspectives.ts`; modify `src/domain/types.ts`, `src/domain/diagnosis.ts`, `src/domain/merchantPerspective.ts`; test `tests/role-perspectives.spec.ts`.

- [ ] Write failing tests proving three different module IDs, six-dimension orders, decision metrics and follow-ups while calculations stay equal.
- [ ] Run `npx vitest run tests/role-perspectives.spec.ts`; expect missing-export failure.
- [ ] Implement:

```ts
export type DecisionRole = 'merchant' | 'ka' | 'cs'
export function buildRolePerspective(
  role: DecisionRole,
  report: WeeklyReport,
  health: BusinessHealthResult,
  diagnosis: DiagnosisResult,
): MerchantPerspective
```

- [ ] Add `merchant` as a diagnosis alias for the existing merchant/KA rules; preserve legacy `agency` behavior and all default calculations.
- [ ] Run role, perspective and diagnosis unit tests; expect PASS.
- [ ] Commit `feat: add role decision perspective model`.

### Task 2: KA city segmentation

**Files:** Create `src/domain/citySegments.ts`, `src/components/CitySegmentation.tsx`; test `tests/city-segments.spec.ts`.

- [ ] Write failing tests for four strategies, exact sample counts and empty real-data input.
- [ ] Implement `buildCitySegments(cities: CityAnalysis[]): CitySegment[]` using growth 5% and UE 0 thresholds already used by the business-health rules.
- [ ] Render an accessible growth × UE quadrant, four counts, city labels and an action table; do not create random store points.
- [ ] Run unit tests and build; expect PASS.
- [ ] Commit `feat: add KA city resource segmentation`.

### Task 3: SaaS customer health

**Files:** Create `src/domain/customerHealth.ts`, `src/components/CustomerHealth.tsx`; modify `src/domain/types.ts`, `src/domain/cases.ts`; test `tests/customer-health.spec.ts`.

- [ ] Write failing tests for deterministic score, signal rows, renewal window and missing-usage `--` degradation.
- [ ] Implement optional `ProductUsage` and `buildCustomerHealth(report, health, usage?)`.
- [ ] Use transparent deductions for low-ROI spread, subsidy above eligible-peer median, missing weekly import, low follow-up completion and inactivity. Never infer usage from GMV.
- [ ] Add explicit synthetic usage to `mainCase`; leave parsed real reports without usage.
- [ ] Render gauge, score explanation and signal table; missing usage shows `--` and `未提供`.
- [ ] Run unit tests; expect PASS.
- [ ] Commit `feat: add customer health intervention model`.

### Task 4: Role switch and view integration

**Files:** Modify `src/App.tsx`, `src/components/MerchantDecisionPanel.tsx`, `src/components/BusinessHealthView.tsx`, `src/components/ReportView.tsx`, `src/components/BossQuestions.tsx` only if role-key reset is needed; test `e2e/three-role-views.spec.ts`.

- [ ] Write failing browser tests that switch all three roles and assert different modules, signals, dimension order and follow-ups.
- [ ] Add `role` state, pass it to `buildDiagnosis` and `buildRolePerspective`, and add three `aria-pressed` switch buttons.
- [ ] Insert `CitySegmentation` only for KA and `CustomerHealth` only for CS in the action plan; owner keeps the existing layout.
- [ ] Keep real-upload synthetic modules closed and preserve report/assumptions during role switching.
- [ ] Run focused E2E and the existing suite; expect PASS.
- [ ] Commit `feat: integrate three role decision views`.

### Task 5: Visual, print, full gate and deployment

**Files:** Modify `src/App.css`; add `scripts/role_view_capture.mjs` and screenshots under ignored `artifacts/three-role-views/`.

- [ ] Style quadrant, health gauge and signal tables with the existing Google flat tokens and mobile single-column rules.
- [ ] Verify 1440px and 390px screenshots, keyboard focus, role-specific print output and no horizontal overflow.
- [ ] Run `npm run lint && npm run test:unit && npm run build && npm run test:e2e && npm run evals && git diff --check`.
- [ ] Review the diff for data-boundary or role-consistency defects; fix any P0/P1 with a failing regression test first.
- [ ] Merge into `main`, push, and verify all three roles on the public URL.

## Self-review

- Every requested reference-image module maps to a task: owner base plan, KA segmentation/JBP, CS health/signals/intervention.
- No 186-store random simulation or fabricated renewal field is introduced.
- `DecisionRole`, `buildRolePerspective`, `buildCitySegments`, `buildCustomerHealth`, and `ProductUsage` names are consistent across tasks.
- Shared `buildDiagnosis` remains the only budget formula and gate path.
