import { expect, test } from '@playwright/test'
import { resolve } from 'node:path'

test('opens business health directly and keeps the third step available', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('heading', { name: '经营全景' })).toBeVisible()
  const thirdStep = page.getByRole('button', { name: /03\s*预算方案/ })
  await expect(thirdStep).toBeEnabled()
  await page.getByRole('tab', { name: '预算方案' }).click()
  await expect(page.getByRole('heading', { name: '一页预算方案' })).toBeVisible()
  await expect(thirdStep).toBeEnabled()
})

test('exposes role selection and recalculation feedback', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: '加载主案例' }).click()
  await page.getByRole('tab', { name: '预算方案' }).click()
  const roleButton = page.getByRole('button', { name: 'SaaS 客户成功' })
  await roleButton.click()
  await expect(roleButton).toHaveAttribute('aria-pressed', 'true')
  await expect(page.getByRole('status').filter({ hasText: '已切换为 SaaS 客户成功版' })).toBeVisible()
  await page.getByLabel('调整金额（元）').fill('500')
  await expect(page.getByRole('status').filter({ hasText: '假设已更新，报告已重算' })).toBeVisible()
  await expect(page.getByText(/3,200/).first()).toBeVisible()
})

test('shows selected filename, success and recoverable upload failure', async ({ page }) => {
  await page.goto('/')
  await page.getByLabel('上传周报').setInputFiles(resolve('public/fixtures/main-weekly.csv'))
  await expect(page.getByText(/已选择 main-weekly\.csv/)).toBeVisible()
  await page.getByRole('button', { name: '生成一页方案' }).click()
  await expect(page.getByText(/周报解析成功/)).toBeVisible()

  await page.getByLabel('上传周报').setInputFiles(resolve('public/fixtures/invalid-weekly.csv'))
  await page.getByRole('button', { name: '生成一页方案' }).click()
  await expect(page.getByText(/解析失败/).first()).toBeVisible()
  await expect(page.getByText(/请检查字段后重试/)).toBeVisible()
})

test('keeps mobile report content before process controls and does not overflow', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/')
  await expect(page.getByRole('heading', { name: '经营全景' })).toBeVisible()
  await page.getByRole('tab', { name: '预算方案' }).click()
  await expect(page.getByRole('heading', { name: '一页预算方案' })).toBeVisible()
  const order = await page.evaluate(() => {
    const main = document.querySelector('.main-canvas')
    const intake = document.querySelector('.intake-sidebar')
    return main && intake ? main.compareDocumentPosition(intake) : 0
  })
  expect(order).toBe(4)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
  await expect(page.locator('.followup-table td[data-label="实际结果"]').first()).toBeVisible()
})
