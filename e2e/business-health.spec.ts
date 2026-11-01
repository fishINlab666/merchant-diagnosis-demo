import { expect, test } from '@playwright/test'

test('opens merchant diagnosis and preserves the action plan as an optional view', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: '快餐示例' }).click()
  await expect(page.getByRole('heading', { name: '我的经营诊断' })).toBeVisible()
  for (const title of ['门店基建', '流量承接', '商业化结构', '补贴与毛利', '用户经营', '城市与门店分层']) {
    await expect(page.getByText(title, { exact: true })).toBeVisible()
  }
  await expect(page.getByText(/4 家合格样本/)).toBeVisible()
  await expect(page.getByText('优先加码', { exact: true })).toBeVisible()
  await expect(page.getByText('先修转化', { exact: true })).toBeVisible()
  await expect(page.getByText('先修毛利', { exact: true })).toBeVisible()
  await expect(page.getByText('先修基建', { exact: true })).toBeVisible()
  await expect(page.getByText(/城市／商圈不一致/)).toBeVisible()

  await page.getByRole('tab', { name: '行动方案' }).click()
  await expect(page.getByRole('heading', { name: '我的下周行动方案' })).toBeVisible()
  await expect(page.getByRole('tab', { name: '行动方案' })).toHaveAttribute('aria-selected', 'true')
})

test('keeps merchant diagnosis readable on mobile', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/')
  await page.getByRole('button', { name: '快餐示例' }).click()
  await expect(page.getByRole('heading', { name: '我的经营诊断' })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
  await expect(page.getByText(/本店位置/).first()).toBeVisible()
})
