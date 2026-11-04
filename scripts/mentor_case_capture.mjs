import { chromium } from '@playwright/test'
import { mkdir, writeFile } from 'node:fs/promises'
import { resolve } from 'node:path'

const root = resolve(import.meta.dirname, '..')
const out = resolve(root, 'artifacts', 'mentor-case-google')
await mkdir(out, { recursive: true })
const browser = await chromium.launch({ headless: true, executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' })
const checks = { screens: {}, errors: [] }

async function inspect(page, key) {
  await page.evaluate(() => document.fonts.ready)
  checks.screens[key] = await page.evaluate(() => ({
    title: document.querySelector('h1')?.textContent ?? '',
    overflow: document.documentElement.scrollWidth > window.innerWidth,
    width: window.innerWidth,
    scrollWidth: document.documentElement.scrollWidth,
    gradients: [...document.querySelectorAll('button, .decision-summary, .role-decision-heading')].map((element) => getComputedStyle(element).backgroundImage).filter((value) => value.includes('gradient')),
  }))
  if (checks.screens[key].overflow) checks.errors.push(`${key}: horizontal overflow`)
  if (checks.screens[key].gradients.length) checks.errors.push(`${key}: gradient found`)
}

async function shot(page, name, fullPage = true) {
  await page.screenshot({ path: resolve(out, `${name}.jpg`), type: 'jpeg', quality: 82, fullPage })
}

try {
  const desktop = await browser.newPage({ viewport: { width: 1440, height: 1000 } })
  desktop.on('pageerror', (error) => checks.errors.push(error.message))
  await desktop.route('https://text.pollinations.ai/**', (route) => route.abort())
  await desktop.goto('http://127.0.0.1:7100', { waitUntil: 'networkidle' })
  await inspect(desktop, 'desktop-intake')
  await shot(desktop, '01-desktop-intake')
  await desktop.getByRole('button', { name: '填入合成店铺页示例' }).click()
  await desktop.getByRole('button', { name: '提取公开信息并初诊' }).click()
  await desktop.getByRole('heading', { name: '公开信息初诊' }).waitFor()
  await inspect(desktop, 'desktop-public-intake')
  await shot(desktop, '02-desktop-public-intake')

  await desktop.getByRole('button', { name: '快餐示例' }).click()
  await desktop.getByRole('heading', { name: '我的经营诊断' }).waitFor()
  await inspect(desktop, 'desktop-health')
  await shot(desktop, '03-desktop-health')
  await desktop.getByRole('tab', { name: '行动方案' }).click()
  await inspect(desktop, 'desktop-budget')
  await shot(desktop, '04-desktop-budget')
  await desktop.getByRole('button', { name: '为什么不直接加预算？' }).click()
  await desktop.locator('.boss-answer').filter({ hasText: '点金推广' }).waitFor()
  await shot(desktop, '05-desktop-boss-answer')
  await desktop.emulateMedia({ media: 'print' })
  await desktop.pdf({ path: resolve(out, '06-budget-a4.pdf'), format: 'A4', printBackground: true })
  await desktop.emulateMedia({ media: 'screen' })

  await desktop.getByRole('button', { name: '诊断另一家门店' }).click()
  await desktop.getByRole('button', { name: '面试演示：预填并下一步' }).click()
  await shot(desktop, '07-demo-profile')
  await desktop.getByRole('button', { name: '下一步', exact: true }).click()
  await shot(desktop, '08-demo-mapping')
  await desktop.getByRole('button', { name: '开始分析' }).click()
  await desktop.getByRole('button', { name: '查看分析结果' }).waitFor()
  await shot(desktop, '09-demo-stages')
  await desktop.close()

  const mobile = await browser.newPage({ viewport: { width: 390, height: 844 } })
  mobile.on('pageerror', (error) => checks.errors.push(error.message))
  await mobile.goto('http://127.0.0.1:7100', { waitUntil: 'networkidle' })
  await inspect(mobile, 'mobile-intake')
  await shot(mobile, '10-mobile-intake')
  await mobile.getByRole('button', { name: '填入合成店铺页示例' }).click()
  await mobile.getByRole('button', { name: '提取公开信息并初诊' }).click()
  await inspect(mobile, 'mobile-public-intake')
  await shot(mobile, '11-mobile-public-intake')
  await mobile.getByRole('button', { name: '快餐示例' }).click()
  await inspect(mobile, 'mobile-health')
  await shot(mobile, '12-mobile-health')
  await mobile.getByRole('tab', { name: '行动方案' }).click()
  await inspect(mobile, 'mobile-budget')
  await shot(mobile, '13-mobile-budget')
  await mobile.close()
} finally {
  await browser.close()
}

await writeFile(resolve(out, 'checks.json'), `${JSON.stringify(checks, null, 2)}\n`)
console.log(JSON.stringify(checks, null, 2))
if (checks.errors.length) process.exitCode = 1
