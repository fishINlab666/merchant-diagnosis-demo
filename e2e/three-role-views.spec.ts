import { expect, test } from '@playwright/test'
import { resolve } from 'node:path'

test('switches merchant, KA and SaaS customer success with structurally different modules', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: '快餐示例' }).click()
  const roleSwitch = page.getByRole('group', { name: '决策视角' })
  await expect(roleSwitch.getByRole('button')).toHaveCount(3)
  await expect(roleSwitch.getByRole('button', { name: '商家老板' })).toHaveAttribute('aria-pressed', 'true')

  await roleSwitch.getByRole('button', { name: '平台 KA', exact: true }).click()
  await expect(page.getByRole('heading', { name: '平台 KA 经营诊断' })).toBeVisible()
  await expect(page.locator('.dimension').nth(1)).toHaveAttribute('data-dimension-id', 'subsidy')
  await page.getByRole('tab', { name: '行动方案' }).click()
  await expect(page.getByRole('heading', { name: '预算调整与 JBP 方案' })).toBeVisible()
  await expect(page.locator('.city-segmentation')).toContainText('4 个合成城市样本')
  await expect(page.locator('.city-segment-table')).toContainText('加码')
  await expect(page.locator('.delta-row')).toContainText('1,152')

  await roleSwitch.getByRole('button', { name: 'SaaS 客户成功' }).click()
  await expect(page.getByRole('heading', { name: '客户健康与续费干预方案' })).toBeVisible()
  await expect(page.locator('.customer-health')).toBeVisible()
  await expect(page.locator('.health-score')).toHaveText('45')
  await expect(page.locator('.health-signal-table tbody tr')).toHaveCount(6)
  await expect(page.locator('.health-signal-table')).toContainText('45 天后')
  await expect(page.locator('.city-segmentation')).toHaveCount(0)
  await expect(page.locator('.delta-row')).toContainText('1,152')
  await page.getByRole('tab', { name: '经营诊断' }).click()
  await expect(page.locator('.dimension').first()).toHaveAttribute('data-dimension-id', 'users')

  await roleSwitch.getByRole('button', { name: '商家老板' }).click()
  await expect(page.getByRole('heading', { name: '我的经营诊断' })).toBeVisible()
  await page.getByRole('tab', { name: '行动方案' }).click()
  await expect(page.locator('.customer-health')).toHaveCount(0)
  await expect(page.locator('.city-segmentation')).toHaveCount(0)
})

test('real uploads degrade KA city and SaaS usage modules without synthetic scores', async ({ page }) => {
  await page.route('https://r.jina.ai/**', (route) => route.fulfill({ status: 503, body: 'unavailable' }))
  await page.goto('/')
  await page.getByLabel('店铺名称').fill('真实上传门店')
  await page.getByRole('button', { name: '开始经营诊断' }).click()
  await page.getByLabel('上传周报').setInputFiles(resolve('public/fixtures/main-weekly.csv'))
  await page.getByRole('button', { name: '确认映射并生成诊断' }).click()
  await page.getByRole('tab', { name: '行动方案' }).click()

  await page.getByRole('button', { name: 'SaaS 客户成功' }).click()
  await expect(page.locator('.health-score')).toHaveText('--')
  await expect(page.locator('.health-signal-table')).toContainText('未提供')
  await page.getByRole('button', { name: '平台 KA', exact: true }).click()
  await expect(page.locator('.city-segmentation')).toContainText('缺少同口径增长与 UE 样本')
  await expect(page.locator('.city-quadrant-chart')).toHaveCount(0)
})
