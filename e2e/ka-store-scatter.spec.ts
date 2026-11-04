import { expect, test } from '@playwright/test'

test('shows 186 store points and four action groups in the KA action plan', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: '快餐示例' }).click()
  await page.getByRole('button', { name: '平台 KA', exact: true }).click()
  await page.getByRole('tab', { name: '行动方案' }).click()

  await expect(page.locator('.store-segmentation')).toContainText('186 家合成门店')
  await expect(page.locator('circle.store-point')).toHaveCount(186)
  await expect(page.locator('.store-segment-table tbody tr')).toHaveCount(4)
  await expect(page.locator('.store-segment-table')).toContainText('加码')
  await expect(page.locator('.store-segment-table')).toContainText('收缩整改')
  await expect(page.locator('.trend-issue')).toContainText('8 周')
  await expect(page.locator('.trend-issue')).toContainText('38.9%')
})

test('shows the store scatter directly in KA health before switching tabs', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: '快餐示例' }).click()
  await page.getByRole('button', { name: '平台 KA', exact: true }).click()

  await expect(page.getByRole('heading', { name: '平台 KA 经营诊断' })).toBeVisible()
  await expect(page.getByRole('tab', { name: '经营诊断' })).toHaveAttribute('aria-selected', 'true')
  await expect(page.locator('.store-segmentation')).toBeVisible()
  await expect(page.locator('.store-segmentation')).toContainText('186 家合成门店')
  await expect(page.locator('circle.store-point')).toHaveCount(186)
})

test('does not show synthetic store points or a trend card for real uploads', async ({ page }) => {
  await page.route('https://r.jina.ai/**', (route) => route.fulfill({ status: 503, body: 'unavailable' }))
  await page.goto('/')
  await page.getByLabel('店铺名称').fill('真实上传门店')
  await page.getByRole('button', { name: '开始经营诊断' }).click()
  await page.getByLabel('上传周报').setInputFiles('public/fixtures/main-weekly.csv')
  await page.getByRole('button', { name: '确认映射并生成诊断' }).click()
  await page.getByRole('button', { name: '平台 KA', exact: true }).click()
  await page.getByRole('tab', { name: '行动方案' }).click()

  await expect(page.locator('circle.store-point')).toHaveCount(0)
  await expect(page.locator('.store-segmentation')).toContainText('缺少同口径增长与 UE 样本')
  await expect(page.locator('.trend-issue')).toHaveCount(0)
})
