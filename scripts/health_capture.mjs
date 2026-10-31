import { chromium } from '@playwright/test'
import { mkdir, writeFile } from 'node:fs/promises'
import { resolve } from 'node:path'

const root = resolve(import.meta.dirname, '..')
const out = resolve(root, 'artifacts', 'health-after')
await mkdir(out, { recursive: true })
const browser = await chromium.launch({ headless: true, executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' })
const checks = { screens: [], overflow: {}, smallTargets: {} }

async function capture(page, name) {
  const target = resolve(out, `${name}.jpg`)
  await page.screenshot({ path: target, fullPage: true, type: 'jpeg', quality: 86 })
  checks.screens.push(target)
}

async function metrics(page, key) {
  checks.overflow[key] = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth)
  checks.smallTargets[key] = await page.evaluate(() => [...document.querySelectorAll('button')].map((element) => {
    const rect = element.getBoundingClientRect()
    return { text: element.textContent?.trim(), width: Math.round(rect.width), height: Math.round(rect.height) }
  }).filter((item) => item.width < 44 || item.height < 44))
}

try {
  const desktop = await browser.newPage({ viewport: { width: 1440, height: 1000 } })
  await desktop.goto('http://127.0.0.1:7100', { waitUntil: 'networkidle' })
  await desktop.getByRole('heading', { name: '经营全景' }).waitFor()
  await capture(desktop, 'desktop-health-full')
  await metrics(desktop, 'desktop')
  await desktop.getByRole('tab', { name: '预算方案' }).click()
  await desktop.getByRole('heading', { name: '一页预算方案' }).waitFor()
  await capture(desktop, 'desktop-budget-full')
  await desktop.emulateMedia({ media: 'print' })
  await desktop.pdf({ path: resolve(out, 'main-report.pdf'), format: 'A4', printBackground: true })
  await desktop.close()

  const mobile = await browser.newPage({ viewport: { width: 390, height: 844 } })
  await mobile.goto('http://127.0.0.1:7100', { waitUntil: 'networkidle' })
  await mobile.getByRole('heading', { name: '经营全景' }).waitFor()
  await capture(mobile, 'mobile-health-full')
  await metrics(mobile, 'mobile')
  await mobile.getByRole('tab', { name: '预算方案' }).click()
  await mobile.getByRole('heading', { name: '一页预算方案' }).waitFor()
  await capture(mobile, 'mobile-budget-full')
  await mobile.close()
} finally {
  await browser.close()
}

await writeFile(resolve(out, 'checks.json'), `${JSON.stringify(checks, null, 2)}\n`)
console.log(JSON.stringify(checks, null, 2))
