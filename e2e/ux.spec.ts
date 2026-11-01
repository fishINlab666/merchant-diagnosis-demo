import { expect, test } from '@playwright/test'
import { resolve } from 'node:path'

test('opens merchant diagnosis and keeps the third step available', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: '快餐示例' }).click()
  await expect(page.getByRole('heading', { name: '我的经营诊断' })).toBeVisible()
  const thirdStep = page.getByRole('button', { name: /03\s*经营诊断/ })
  await expect(thirdStep).toBeEnabled()
  await page.getByRole('tab', { name: '行动方案' }).click()
  await expect(page.getByRole('heading', { name: '我的下周行动方案' })).toBeVisible()
  await expect(thirdStep).toBeEnabled()
})

test('exposes recalculation feedback', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: '快餐示例' }).click()
  await page.getByRole('tab', { name: '行动方案' }).click()
  await page.getByLabel('调整金额（元）').fill('500')
  await expect(page.getByRole('status').filter({ hasText: '假设已更新，报告已重算' })).toBeVisible()
  await expect(page.getByText(/3,200/).first()).toBeVisible()
})

test('shows selected filename, success and recoverable upload failure', async ({ page }) => {
  await page.route('https://r.jina.ai/**', (route) => route.fulfill({ status: 503, body: 'unavailable' }))
  await page.goto('/')
  await page.getByLabel('店铺名称').fill('上传测试门店')
  await page.getByRole('button', { name: '开始经营诊断' }).click()
  await page.getByLabel('上传周报').setInputFiles(resolve('public/fixtures/main-weekly.csv'))
  await expect(page.getByText(/表头已读取/)).toBeVisible()
  await page.getByRole('button', { name: '确认映射并生成诊断' }).click()
  await expect(page.getByText(/周报解析成功/)).toBeVisible()

  await page.getByLabel('上传周报').setInputFiles(resolve('public/fixtures/invalid-weekly.csv'))
  await expect(page.locator('.mapping-missing')).toContainText('缺少必需字段')
  await expect(page.getByRole('button', { name: '确认映射并生成诊断' })).toBeDisabled()
})

test('keeps mobile report content before process controls and does not overflow', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/')
  await page.getByRole('button', { name: '快餐示例' }).click()
  await expect(page.getByRole('heading', { name: '我的经营诊断' })).toBeVisible()
  await page.getByRole('tab', { name: '行动方案' }).click()
  await expect(page.getByRole('heading', { name: '我的下周行动方案' })).toBeVisible()
  const order = await page.evaluate(() => {
    const main = document.querySelector('.main-canvas')
    const intake = document.querySelector('.intake-sidebar')
    return main && intake ? main.compareDocumentPosition(intake) : 0
  })
  expect(order).toBe(4)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
  await expect(page.locator('.followup-table td[data-label="实际结果"]').first()).toBeVisible()
})
