import { expect, test } from '@playwright/test'
import { resolve } from 'node:path'

test('walks from public intake to the main case, role talk tracks and print', async ({ page }) => {
  const external: string[] = []
  page.on('request', (request) => {
    const url = new URL(request.url())
    if (!['localhost', '127.0.0.1'].includes(url.hostname)) external.push(request.url())
  })

  await page.goto('/')
  await page.getByRole('button', { name: /01\s*公开信息/ }).click()
  await expect(page.getByRole('heading', { name: '公开信息初诊' })).toBeVisible()
  await page.getByRole('button', { name: '生成数据清单' }).click()
  await expect(page.getByText('平台后台周报表（CSV／XLSX）', { exact: true })).toBeVisible()

  await page.getByRole('button', { name: '加载主案例' }).click()
  await page.getByRole('tab', { name: '预算方案' }).click()
  await expect(page.getByRole('heading', { name: '一页预算方案' })).toBeVisible()
  await expect(page.getByText('点金推广 ROI 偏低', { exact: true })).toBeVisible()
  await expect(page.getByText(/2,560/).first()).toBeVisible()
  await expect(page.getByText(/1,152/).first()).toBeVisible()

  await page.getByRole('button', { name: 'SaaS 客户成功' }).click()
  await expect(page.getByText(/续费风险/).first()).toBeVisible()
  await page.evaluate(() => { window.print = () => { document.body.dataset.printCalled = 'true' } })
  await page.getByRole('button', { name: '打印／保存 PDF' }).click()
  await expect(page.locator('body')).toHaveAttribute('data-print-called', 'true')
  expect(external).toEqual([])
})

test('imports one CSV weekly report and generates the same budget recommendation', async ({ page }) => {
  await page.goto('/')
  await page.getByLabel('上传周报').setInputFiles(resolve('public/fixtures/main-weekly.csv'))
  await page.getByRole('button', { name: '生成一页方案' }).click()
  await page.getByRole('tab', { name: '预算方案' }).click()
  await expect(page.getByRole('heading', { name: '一页预算方案' })).toBeVisible()
  await expect(page.getByText('点金推广 ROI 偏低', { exact: true })).toBeVisible()
  await expect(page.getByText(/2,560/).first()).toBeVisible()
})

test('blocks ROI ranking when the control case has different attribution windows', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: '加载对照案例' }).click()
  await page.getByRole('tab', { name: '预算方案' }).click()
  await expect(page.getByText('工具归因口径不同', { exact: true })).toBeVisible()
  await expect(page.getByText('先统一归因口径，再谈预算', { exact: true })).toBeVisible()
  await expect(page.getByRole('heading', { name: '调整前后算账' })).toHaveCount(0)
})

test('recalculates immediately when amount and budget mode change', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: '加载主案例' }).click()
  await page.getByRole('tab', { name: '预算方案' }).click()
  await page.getByLabel('调整金额（元）').fill('500')
  await expect(page.getByText(/3,200/).first()).toBeVisible()
  await expect(page.getByText(/1,440/).first()).toBeVisible()
  await page.getByLabel('调整方式').selectOption('add')
  await expect(page.getByText(/7,200/).first()).toBeVisible()
  await expect(page.getByText(/2,740/).first()).toBeVisible()
})
