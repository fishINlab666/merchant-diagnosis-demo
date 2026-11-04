import { expect, test } from '@playwright/test'

test('builds a public intake from pasted facts, review themes and explicit competitors', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: '填入合成店铺页示例' }).click()
  await page.getByRole('button', { name: '提取公开信息并初诊' }).click()

  await expect(page.getByRole('heading', { name: '公开信息初诊' })).toBeVisible()
  await expect(page.locator('.public-fact-grid')).toContainText('42 分钟')
  await expect(page.locator('.review-theme-list')).toContainText('配送慢')
  await expect(page.locator('.public-comparison')).toContainText('老广记煲仔饭')
  await expect(page.locator('.public-candidate')).toHaveCount(3)
  await expect(page.locator('.public-candidate').first()).toContainText('待验证')
  await expect(page.getByRole('heading', { name: '上传一份周报，生成完整诊断' })).toBeVisible()
})

test('shows eight-week trends, tool efficiency and one shared scenario breakdown', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: '快餐示例' }).click()

  await expect(page.locator('.weekly-trend')).toBeVisible()
  await expect(page.locator('.weekly-trend')).toContainText('W8')
  await expect(page.locator('.tool-efficiency')).toContainText('ROI 18')
  await page.getByRole('tab', { name: '行动方案' }).click()
  await expect(page.locator('.decision-summary')).toBeVisible()
  await expect(page.locator('.merchant-report .role-decision-panel')).toHaveCount(0)
  await expect(page.locator('.budget-mix')).toContainText('现在')
  await expect(page.locator('.budget-mix')).toContainText('建议')
  await expect(page.locator('.profit-waterfall')).toContainText('预算结构贡献')

  await page.getByLabel('测算周期').selectOption('month')
  await expect(page.locator('.delta-row')).toContainText('11,008')
  await page.getByLabel('商家补贴变化（元）').fill('-1000')
  await expect(page.locator('.profit-waterfall')).toContainText('订单流失影响')
  await expect(page.locator('.delta-row')).toContainText('9,288')
})

test('runs the complete guided demo automatically with reduced motion', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.goto('/')
  await page.getByRole('button', { name: '面试演示：预填并下一步' }).click()
  await expect(page.getByRole('button', { name: '一键完整演示' })).toBeEnabled()
  await page.getByRole('button', { name: '一键完整演示' }).click()

  await expect(page.getByRole('heading', { name: '我的经营诊断' })).toBeVisible()
  await expect(page.locator('.weekly-trend')).toBeVisible()
})

test('answers boss questions offline and offers manual copy when clipboard is unavailable', async ({ page }) => {
  await page.addInitScript(() => Object.defineProperty(navigator, 'clipboard', { value: undefined }))
  await page.route('https://text.pollinations.ai/**', (route) => route.abort())
  await page.goto('/')
  await page.getByRole('button', { name: '快餐示例' }).click()
  await page.getByRole('tab', { name: '行动方案' }).click()

  await page.getByRole('button', { name: '为什么不直接加预算？' }).click()
  await expect(page.locator('.boss-answer')).toContainText('点金推广')
  await expect(page.locator('.boss-answer-source')).toHaveText('离线预置回答')
  await page.getByRole('button', { name: '复制三句话' }).click()
  await expect(page.getByLabel('手动复制三句话')).toBeVisible()
  await expect(page.getByLabel('手动复制三句话')).toContainText('点金推广')
})

test('applies the Google flat visual system without losing error semantics', async ({ page }) => {
  await page.goto('/')
  await expect(page.locator('.app-shell')).toHaveClass(/google-theme/)
  await page.getByLabel('店铺名称').fill('主题测试门店')
  await expect(page.locator('.intake-start')).toBeEnabled()
  await expect(page.locator('.intake-start')).toHaveCSS('background-color', 'rgb(66, 133, 244)')
  const tokens = await page.evaluate(() => {
    const style = getComputedStyle(document.documentElement)
    return {
      brand: style.getPropertyValue('--brand').trim().toUpperCase(),
      error: style.getPropertyValue('--red').trim().toUpperCase(),
      success: style.getPropertyValue('--green').trim().toUpperCase(),
      primaryBackground: getComputedStyle(document.querySelector('.intake-start')!).backgroundColor,
      primaryImage: getComputedStyle(document.querySelector('.intake-start')!).backgroundImage,
    }
  })
  expect(tokens).toEqual({
    brand: '#4285F4',
    error: '#EA4335',
    success: '#34A853',
    primaryBackground: 'rgb(66, 133, 244)',
    primaryImage: 'none',
  })
})
