import { chromium } from '@playwright/test'
import { mkdir, writeFile } from 'node:fs/promises'
import { resolve } from 'node:path'

const stage = process.argv[2] ?? 'before'
const root = resolve(import.meta.dirname, '..')
const out = resolve(root, 'artifacts', `ux-${stage}`)
await mkdir(out, { recursive: true })
const browser = await chromium.launch({
  headless: true,
  executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
})
const results = { stage, screens: [], checks: {} }

async function openPage(viewport) {
  const page = await browser.newPage({ viewport })
  await page.goto('http://127.0.0.1:7100', { waitUntil: 'networkidle' })
  return page
}

async function capture(page, name, fullPage = true) {
  const target = resolve(out, `${name}.jpg`)
  await page.screenshot({ path: target, fullPage, type: 'jpeg', quality: 86 })
  results.screens.push(target)
}

async function interactionMetrics(page) {
  return page.evaluate(() => ({
    smallTargets: [...document.querySelectorAll('button')].map((element) => {
      const rect = element.getBoundingClientRect()
      return { text: element.textContent?.trim(), width: Math.round(rect.width), height: Math.round(rect.height) }
    }).filter((item) => item.width < 44 || item.height < 44),
    fields: [...document.querySelectorAll('input, select, textarea')].map((element) => ({
      type: element.getAttribute('type') ?? element.tagName.toLowerCase(),
      name: element.getAttribute('name'),
      autocomplete: element.getAttribute('autocomplete'),
      ariaLabel: element.getAttribute('aria-label'),
    })),
    horizontalOverflow: document.documentElement.scrollWidth > window.innerWidth,
  }))
}

try {
  const desktop = await openPage({ width: 1440, height: 1000 })
  await capture(desktop, 'desktop-initial-viewport', false)
  await capture(desktop, 'desktop-initial-full')
  results.checks.initial = await interactionMetrics(desktop)

  const mainButton = desktop.getByRole('button', { name: '加载主案例' })
  await mainButton.focus()
  await desktop.keyboard.press('Enter')
  await desktop.getByRole('heading', { name: '一页预算方案' }).waitFor()
  results.checks.keyboardMainCase = true
  await capture(desktop, 'desktop-report-viewport', false)
  await capture(desktop, 'desktop-report-full')
  results.checks.report = await interactionMetrics(desktop)
  await desktop.emulateMedia({ media: 'print' })
  await desktop.pdf({ path: resolve(out, 'main-report.pdf'), format: 'A4', printBackground: true })
  await capture(desktop, 'print-report')
  await desktop.close()

  const mobile = await openPage({ width: 390, height: 844 })
  await capture(mobile, 'mobile-initial-full')
  await mobile.getByRole('button', { name: '加载主案例' }).click()
  await mobile.getByRole('heading', { name: '一页预算方案' }).waitFor()
  await capture(mobile, 'mobile-report-full')
  results.checks.mobile = await interactionMetrics(mobile)
  await mobile.close()

  const upload = await openPage({ width: 1280, height: 900 })
  await upload.getByLabel('上传周报').setInputFiles(resolve(root, 'public/fixtures/main-weekly.csv'))
  results.checks.uploadBefore = await upload.evaluate(() => ({
    fileName: document.querySelector('input[type="file"]')?.value,
    generateDisabled: document.querySelector('button.primary-action:disabled') !== null,
  }))
  await upload.getByRole('button', { name: '生成一页方案' }).click()
  await upload.getByRole('heading', { name: '一页预算方案' }).waitFor()
  results.checks.uploadSuccess = true
  await upload.close()
} finally {
  await browser.close()
}

await writeFile(resolve(out, 'checks.json'), `${JSON.stringify(results, null, 2)}\n`)
console.log(JSON.stringify(results, null, 2))
