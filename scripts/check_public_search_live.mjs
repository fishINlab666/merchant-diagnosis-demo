import { chromium } from '@playwright/test'
import { mkdir } from 'node:fs/promises'
import { resolve } from 'node:path'

const out = resolve(import.meta.dirname, '..', 'artifacts', 'merchant-tool')
await mkdir(out, { recursive: true })
const browser = await chromium.launch({ headless: true, executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' })
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } })
  await page.goto('http://127.0.0.1:7100', { waitUntil: 'networkidle' })
  await page.getByLabel('店铺名称').fill('肯德基')
  await page.getByRole('button', { name: '开始经营诊断' }).click()
  await page.getByRole('heading', { name: '公开信息初诊' }).waitFor({ timeout: 20000 })
  const result = await page.locator('.public-intake-result').innerText()
  console.log(JSON.stringify({ result: result.slice(0, 1800) }, null, 2))
  await page.screenshot({ path: resolve(out, 'live-public-search.jpg'), fullPage: true, type: 'jpeg', quality: 85 })
} finally {
  await browser.close()
}
