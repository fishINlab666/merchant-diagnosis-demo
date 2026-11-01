import { chromium } from '@playwright/test'
import { mkdir, writeFile } from 'node:fs/promises'
import { resolve } from 'node:path'

const root = resolve(import.meta.dirname, '..')
const out = resolve(root, 'artifacts', 'role-views')
await mkdir(out, { recursive: true })
const browser = await chromium.launch({ headless: true, executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' })
const roles = [
  ['ka', '平台 KA'],
  ['agency', '服务商'],
  ['cs', 'SaaS 客户成功'],
]
const results = { desktop: {}, mobile: {}, errors: [] }

async function inspect(page, key) {
  const state = await page.evaluate(() => ({
    overflow: document.documentElement.scrollWidth > window.innerWidth,
    module: document.querySelector('[data-decision-module]')?.getAttribute('data-decision-module'),
    firstDimension: document.querySelector('.dimension h3')?.textContent,
    metrics: document.querySelectorAll('.role-decision-metric').length,
    smallButtons: [...document.querySelectorAll('button')].map((element) => {
      const rect = element.getBoundingClientRect()
      return { text: element.textContent?.trim(), width: Math.round(rect.width), height: Math.round(rect.height) }
    }).filter((item) => item.width < 44 || item.height < 44),
  }))
  if (state.overflow) results.errors.push(`${key}: horizontal overflow`)
  if (!state.module) results.errors.push(`${key}: missing decision module`)
  if (state.metrics !== 3) results.errors.push(`${key}: expected 3 role metrics`)
  return state
}

try {
  for (const [key, label] of roles) {
    const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } })
    page.on('console', (message) => { if (message.type() === 'error') results.errors.push(`${key}: ${message.text()}`) })
    page.on('response', (response) => { if (response.status() >= 400) results.errors.push(`${key}: ${response.status()} ${response.url()}`) })
    await page.goto('http://127.0.0.1:7100', { waitUntil: 'networkidle' })
    await page.getByRole('button', { name: label, exact: true }).click()
    results.desktop[key] = { health: await inspect(page, `desktop-${key}-health`) }
    await page.screenshot({ path: resolve(out, `desktop-${key}-health.jpg`), fullPage: true, type: 'jpeg', quality: 84 })
    await page.emulateMedia({ media: 'print' })
    await page.pdf({ path: resolve(out, `${key}-health.pdf`), format: 'A4', printBackground: true })
    await page.emulateMedia({ media: 'screen' })
    await page.getByRole('tab', { name: '预算方案' }).click()
    results.desktop[key].budget = await inspect(page, `desktop-${key}-budget`)
    await page.screenshot({ path: resolve(out, `desktop-${key}-budget.jpg`), fullPage: true, type: 'jpeg', quality: 84 })
    await page.emulateMedia({ media: 'print' })
    await page.pdf({ path: resolve(out, `${key}-budget.pdf`), format: 'A4', printBackground: true })
    await page.close()

    const mobile = await browser.newPage({ viewport: { width: 390, height: 844 } })
    await mobile.goto('http://127.0.0.1:7100', { waitUntil: 'networkidle' })
    await mobile.getByRole('button', { name: label, exact: true }).click()
    results.mobile[key] = { health: await inspect(mobile, `mobile-${key}-health`) }
    await mobile.screenshot({ path: resolve(out, `mobile-${key}-health.jpg`), fullPage: true, type: 'jpeg', quality: 84 })
    await mobile.getByRole('tab', { name: '预算方案' }).click()
    results.mobile[key].budget = await inspect(mobile, `mobile-${key}-budget`)
    await mobile.screenshot({ path: resolve(out, `mobile-${key}-budget.jpg`), fullPage: true, type: 'jpeg', quality: 84 })
    await mobile.close()
  }
} finally {
  await browser.close()
}

await writeFile(resolve(out, 'checks.json'), `${JSON.stringify(results, null, 2)}\n`)
console.log(JSON.stringify(results, null, 2))
if (results.errors.length > 0) process.exitCode = 1
