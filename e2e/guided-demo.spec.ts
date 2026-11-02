import { expect, test } from '@playwright/test'

test('guided demo walks from prefilled data through six analysis stages to results', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.goto('/')
  await page.getByRole('button', { name: '面试演示：预填并下一步' }).click()

  await expect(page.getByRole('heading', { name: '演示门店信息' })).toBeVisible()
  await expect(page.getByText('合成餐饮品牌 A', { exact: true })).toBeVisible()
  await expect(page.getByText('合成演示数据', { exact: false }).first()).toBeVisible()
  await page.getByRole('button', { name: '下一步' }).click()

  await expect(page.getByRole('heading', { name: '预填周报与字段映射' })).toBeVisible()
  await expect(page.locator('.mapping-identity')).toContainText('文件门店ID：S1')
  await expect(page.locator('.mapping-table')).toContainText('归因净GMV')
  await page.getByRole('button', { name: '开始分析' }).click()

  await expect(page.getByRole('heading', { name: '逐步分析' })).toBeVisible()
  await expect(page.locator('.demo-stage')).toHaveCount(6)
  await expect(page.locator('.demo-stage.complete').last()).toContainText('预计 GMV +2,560 元 · 毛利 +1,152 元')
  await page.getByRole('button', { name: '查看分析结果' }).click()
  await expect(page.getByRole('heading', { name: '我的经营诊断' })).toBeVisible()
})
