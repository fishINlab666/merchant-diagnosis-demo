import { expect, test } from '@playwright/test'
import { resolve } from 'node:path'

test('merchant self service starts with a shop name and produces reviewable public intake', async ({ page }) => {
  await page.route('https://r.jina.ai/**', async (route) => {
    await route.fulfill({ status: 200, contentType: 'text/plain', body: '# 测试煲仔饭\n评分：4.7\n人均 ¥28\n这是一段足够长的公开门店摘要，用来验证店名检索后需要人工确认来源和公开信息。' })
  })
  await page.goto('/')

  await expect(page.getByLabel('店铺名称')).toBeVisible()
  await expect(page.getByRole('button', { name: '开始经营诊断' })).toBeDisabled()
  await expect(page.getByRole('button', { name: '平台 KA', exact: true })).toHaveCount(0)
  await expect(page.getByRole('button', { name: '服务商', exact: true })).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'SaaS 客户成功', exact: true })).toHaveCount(0)
  await expect(page.locator('article.report')).toHaveCount(0)

  await page.getByLabel('店铺名称').fill('测试煲仔饭')
  await page.getByRole('button', { name: '开始经营诊断' }).click()

  await expect(page.getByRole('heading', { name: '公开信息初诊' })).toBeVisible()
  await expect(page.getByText('待确认', { exact: false }).first()).toBeVisible()
  await expect(page.getByText(/4\.7/).first()).toBeVisible()
  await expect(page.getByText('公开搜索：测试煲仔饭', { exact: true })).toBeVisible()
  await expect(page.getByLabel('上传周报')).toBeVisible()
})

test('merchant self service falls back to manual intake and still generates a full diagnosis', async ({ page }) => {
  await page.route('https://r.jina.ai/**', async (route) => {
    await route.fulfill({ status: 503, body: 'unavailable' })
  })
  await page.goto('/')
  await page.getByLabel('店铺名称').fill('我的测试门店')
  await page.getByRole('button', { name: '开始经营诊断' }).click()

  await expect(page.getByText('公开检索暂不可用', { exact: false }).first()).toBeVisible()
  await expect(page.getByLabel('公开评分')).toBeVisible()
  await page.getByLabel('公开评分').fill('4.5')
  await page.getByLabel('公开菜品观察').fill('一人食套餐 2 款，工作日午餐选择较少')
  await page.getByRole('button', { name: '生成公开初诊' }).click()
  await expect(page.getByText('公开事实：当前评分 4.5', { exact: false })).toBeVisible()

  await page.getByLabel('上传周报').setInputFiles(resolve('public/fixtures/main-weekly.csv'))
  await page.getByRole('button', { name: '确认映射并生成诊断' }).click()
  await expect(page.getByRole('heading', { name: '我的经营诊断' })).toBeVisible()
  await expect(page.locator('[data-decision-module="merchant-action"]')).toBeVisible()
  await expect(page.getByText('我的测试门店', { exact: true }).first()).toBeVisible()

  await page.getByRole('tab', { name: '行动方案' }).click()
  await expect(page.getByRole('heading', { name: '我的下周行动方案' })).toBeVisible()
  await expect(page.locator('.delta-row')).toContainText('2,560')
})

test('different demo stores produce different diagnoses instead of only changing the shop name', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: '正餐示例' }).click()
  await expect(page.getByRole('heading', { name: '我的经营诊断' })).toBeVisible()
  const fineDining = await page.locator('.role-module-card').first().innerText()
  await page.getByRole('button', { name: '快餐示例' }).click()
  const fastFood = await page.locator('.role-module-card').first().innerText()
  expect(fineDining).not.toBe(fastFood)

  await page.getByRole('button', { name: '归因异常示例' }).click()
  await expect(page.locator('[data-decision-module="merchant-action"]')).toContainText('先统一数据口径')
  await page.getByRole('tab', { name: '行动方案' }).click()
  await expect(page.locator('.delta-row')).toHaveCount(0)
})

test('header mapping requires confirmation before diagnosis and blocks missing required fields', async ({ page }) => {
  await page.route('https://r.jina.ai/**', (route) => route.fulfill({ status: 503, body: 'unavailable' }))
  await page.goto('/')
  await page.getByLabel('店铺名称').fill('映射预览门店')
  await page.getByRole('button', { name: '开始经营诊断' }).click()
  await page.getByLabel('上传周报').setInputFiles(resolve('public/fixtures/main-weekly.csv'))

  await expect(page.getByRole('heading', { name: '表头映射预览' })).toBeVisible()
  await expect(page.locator('.mapping-table')).toContainText('门店ID')
  await expect(page.locator('.mapping-modules')).toContainText('经营与投放')
  await expect(page.locator('article.report')).toHaveCount(0)
  await page.getByRole('button', { name: '确认映射并生成诊断' }).click()
  await expect(page.getByRole('heading', { name: '我的经营诊断' })).toBeVisible()

  await page.getByLabel('上传周报').setInputFiles(resolve('public/fixtures/invalid-weekly.csv'))
  await expect(page.locator('.mapping-missing')).toContainText('缺少必需字段')
  await expect(page.getByRole('button', { name: '确认映射并生成诊断' })).toBeDisabled()
})

test('manual header mapping resolves unknown fields and recalculates conflicts', async ({ page }) => {
  await page.route('https://r.jina.ai/**', (route) => route.fulfill({ status: 503, body: 'unavailable' }))
  await page.goto('/')
  await page.getByLabel('店铺名称').fill('手动映射门店')
  await page.getByRole('button', { name: '开始经营诊断' }).click()
  await page.getByLabel('上传周报').setInputFiles(resolve('public/fixtures/manual-weekly.csv'))

  await expect(page.locator('.mapping-missing')).toContainText('净GMV')
  await expect(page.getByRole('button', { name: '确认映射并生成诊断' })).toBeDisabled()
  await page.getByLabel('门店总GMV映射到标准字段').selectOption('净GMV')
  await expect(page.locator('.upload-status.ready')).toContainText('映射已更新')
  await expect(page.getByRole('button', { name: '确认映射并生成诊断' })).toBeEnabled()
  await page.getByRole('button', { name: '确认映射并生成诊断' }).click()
  await expect(page.getByRole('heading', { name: '我的经营诊断' })).toBeVisible()
  await expect(page.locator('.role-decision-metrics')).toContainText('60,000')

  await page.getByLabel('门店总GMV映射到标准字段').selectOption('订单')
  await expect(page.locator('.mapping-missing')).toContainText('重复映射：订单')
  await expect(page.getByRole('button', { name: '确认映射并生成诊断' })).toBeDisabled()
  await page.getByLabel('门店总GMV映射到标准字段').selectOption('净GMV')
  await expect(page.getByRole('button', { name: '确认映射并生成诊断' })).toBeEnabled()
})
