import { expect, test } from '@playwright/test'

const roles = [
  { key: 'ka', label: '平台 KA', module: 'jbp-budget', title: '经营全景', budgetTitle: '一页预算方案' },
  { key: 'agency', label: '服务商', module: 'acquisition-delivery', title: '获客与交付全景', budgetTitle: '一页客户交付方案' },
  { key: 'cs', label: 'SaaS 客户成功', module: 'health-renewal', title: '客户健康全景', budgetTitle: '一页客户干预方案' },
] as const

test('role decision views change analysis and output structures while preserving shared facts', async ({ page }) => {
  await page.goto('/')
  const health: Record<string, { first: string; metrics: string[]; actions: string[]; facts: unknown }> = {}

  for (const role of roles) {
    await page.getByRole('button', { name: role.label, exact: true }).click()
    await expect(page.getByRole('heading', { name: role.title, exact: true })).toBeVisible()
    await expect(page.locator('[data-decision-module]')).toHaveAttribute('data-decision-module', role.module)
    health[role.key] = {
      first: await page.locator('.dimension').first().locator('h3').innerText(),
      metrics: await page.locator('.role-decision-metric').allTextContents(),
      actions: await page.locator('.role-next-actions .role-action').allTextContents(),
      facts: await page.locator('.dimension').evaluateAll((nodes) => nodes.map((node) => ({
        id: node.getAttribute('data-dimension-id'),
        fact: node.querySelector('.dimension-facts')?.textContent,
      })).sort((a, b) => String(a.id).localeCompare(String(b.id)))),
    }
  }

  expect(new Set(Object.values(health).map((item) => item.first)).size).toBe(3)
  expect(new Set(Object.values(health).map((item) => item.metrics.join('|'))).size).toBe(3)
  expect(new Set(Object.values(health).map((item) => item.actions.join('|'))).size).toBe(3)
  expect(health.agency.facts).toEqual(health.ka.facts)
  expect(health.cs.facts).toEqual(health.ka.facts)

  await page.getByRole('tab', { name: '预算方案' }).click()
  const budgets: Record<string, { sections: string[]; followUp: string; calculation: string }> = {}
  for (const role of roles) {
    await page.getByRole('button', { name: role.label, exact: true }).click()
    await expect(page.getByRole('heading', { name: role.budgetTitle, exact: true })).toBeVisible()
    await expect(page.locator('article.report [data-decision-module]')).toHaveAttribute('data-decision-module', role.module)
    budgets[role.key] = {
      sections: await page.locator('article.report .report-section h2').allTextContents(),
      followUp: await page.locator('.followup-table tbody tr').first().innerText(),
      calculation: await page.locator('.delta-row').innerText(),
    }
  }

  expect(new Set(Object.values(budgets).map((item) => item.sections.join('|'))).size).toBe(3)
  expect(new Set(Object.values(budgets).map((item) => item.followUp)).size).toBe(3)
  expect(budgets.agency.calculation).toBe(budgets.ka.calculation)
  expect(budgets.cs.calculation).toBe(budgets.ka.calculation)
})

test('customer success explicitly degrades when product usage is unavailable', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: '加载对照案例' }).click()
  await page.getByRole('button', { name: 'SaaS 客户成功', exact: true }).click()

  const module = page.locator('[data-decision-module="health-renewal"]')
  await expect(module).toContainText('未提供')
  await expect(module).toContainText('补充产品使用数据')
  await expect(module).toContainText('不生成续费风险等级')
  await expect(module).not.toContainText('高优先级')
})
