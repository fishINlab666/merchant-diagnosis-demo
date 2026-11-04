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
