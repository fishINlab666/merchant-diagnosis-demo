import { chromium } from '@playwright/test'
import { mkdir, writeFile } from 'node:fs/promises'
import { resolve } from 'node:path'

const root = resolve(import.meta.dirname, '..')
const out = resolve(root, 'artifacts', 'guided-demo')
await mkdir(out, { recursive: true })
const browser = await chromium.launch({ headless: true, executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' })
const checks = { errors: [] }

async function capture(page, name) {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth)
  if (overflow) checks.errors.push(`${name}: horizontal overflow`)
  await page.screenshot({ path: resolve(out, `${name}.jpg`), fullPage: true, type: 'jpeg', quality: 85 })
}

try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } })
  await page.goto('http://127.0.0.1:7100', { waitUntil: 'networkidle' })
  await page.getByRole('button', { name: '面试演示：预填并下一步' }).click()
  await capture(page, 'desktop-01-profile')
  await page.getByRole('button', { name: '下一步' }).click()
  await page.getByRole('heading', { name: '预填周报与字段映射' }).waitFor()
  await capture(page, 'desktop-02-mapping')
  await page.getByRole('button', { name: '开始分析' }).click()
  await page.waitForTimeout(1300)
  await capture(page, 'desktop-03-running')
  await page.getByRole('button', { name: '查看分析结果' }).waitFor({ timeout: 10000 })
  await capture(page, 'desktop-04-complete')
  await page.getByRole('button', { name: '查看分析结果' }).click()
  await page.getByRole('heading', { name: '我的经营诊断' }).waitFor()
  await capture(page, 'desktop-05-result')
  await page.close()

  const mobile = await browser.newPage({ viewport: { width: 390, height: 844 } })
  await mobile.goto('http://127.0.0.1:7100', { waitUntil: 'networkidle' })
  await mobile.getByRole('button', { name: '面试演示：预填并下一步' }).click()
  await capture(mobile, 'mobile-01-profile')
  await mobile.getByRole('button', { name: '下一步' }).click()
  await capture(mobile, 'mobile-02-mapping')
  await mobile.getByRole('button', { name: '开始分析' }).click()
  await mobile.waitForTimeout(1300)
  await capture(mobile, 'mobile-03-running')
  await mobile.getByRole('button', { name: '查看分析结果' }).waitFor({ timeout: 10000 })
  await capture(mobile, 'mobile-04-complete')
  await mobile.getByRole('button', { name: '查看分析结果' }).click()
  await capture(mobile, 'mobile-05-result')
  await mobile.close()
} finally {
  await browser.close()
}

await writeFile(resolve(out, 'checks.json'), `${JSON.stringify(checks, null, 2)}\n`)
console.log(JSON.stringify(checks, null, 2))
if (checks.errors.length > 0) process.exitCode = 1
