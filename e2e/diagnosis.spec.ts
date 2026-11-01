import { expect, test } from '@playwright/test'
import { resolve } from 'node:path'

test('opens a merchant action plan and prints without external requests', async ({ page }) => {
  const external: string[] = []
  page.on('request', (request) => {
    const url = new URL(request.url())
    if (!['localhost', '127.0.0.1'].includes(url.hostname)) external.push(request.url())
  })

  await page.goto('/')
  await page.getByRole('button', { name: '快餐示例' }).click()
  await page.getByRole('tab', { name: '行动方案' }).click()
  await expect(page.getByRole('heading', { name: '我的下周行动方案' })).toBeVisible()
  await expect(page.locator('.issue-grid').getByText('点金推广 ROI 偏低', { exact: true })).toBeVisible()
  await expect(page.getByText(/2,560/).first()).toBeVisible()
  await expect(page.getByText(/1,152/).first()).toBeVisible()

  await page.evaluate(() => { window.print = () => { document.body.dataset.printCalled = 'true' } })
  await page.getByRole('button', { name: '打印／保存 PDF' }).click()
  await expect(page.locator('body')).toHaveAttribute('data-print-called', 'true')
  expect(external).toEqual([])
})

test('imports one CSV weekly report and generates the same budget recommendation', async ({ page }) => {
  await page.route('https://r.jina.ai/**', (route) => route.fulfill({ status: 503, body: 'unavailable' }))
  await page.goto('/')
  await page.getByLabel('店铺名称').fill('周报测试门店')
  await page.getByRole('button', { name: '开始经营诊断' }).click()
  await page.getByLabel('上传周报').setInputFiles(resolve('public/fixtures/main-weekly.csv'))
  await page.getByRole('button', { name: '确认映射并生成诊断' }).click()
  await page.getByRole('tab', { name: '行动方案' }).click()
  await expect(page.getByRole('heading', { name: '我的下周行动方案' })).toBeVisible()
  await expect(page.locator('.issue-grid').getByText('点金推广 ROI 偏低', { exact: true })).toBeVisible()
  await expect(page.getByText(/2,560/).first()).toBeVisible()
})

test('blocks ROI ranking when the control case has different attribution windows', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: '归因异常示例' }).click()
  await page.getByRole('tab', { name: '行动方案' }).click()
  await expect(page.locator('.issue-grid').getByText('工具归因口径不同', { exact: true })).toBeVisible()
  await expect(page.getByText('先统一归因口径，再谈预算', { exact: true })).toBeVisible()
  await expect(page.getByRole('heading', { name: '调整前后算账' })).toHaveCount(0)
})

test('recalculates immediately when amount and budget mode change', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: '快餐示例' }).click()
  await page.getByRole('tab', { name: '行动方案' }).click()
  await page.getByLabel('调整金额（元）').fill('500')
  await expect(page.getByText(/3,200/).first()).toBeVisible()
  await expect(page.getByText(/1,440/).first()).toBeVisible()
  await page.getByLabel('调整方式').selectOption('add')
  await expect(page.getByText(/7,200/).first()).toBeVisible()
  await expect(page.getByText(/2,740/).first()).toBeVisible()
})
