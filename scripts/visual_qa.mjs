import { chromium } from '@playwright/test'
import { mkdir, writeFile } from 'node:fs/promises'
import { resolve } from 'node:path'

const root = resolve(import.meta.dirname, '..')
const out = resolve(root, 'artifacts')
await mkdir(out, { recursive: true })
const browser = await chromium.launch({
  headless: true,
  executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
})
const results = {}
try {
  for (const [name, viewport] of [['desktop', { width: 1440, height: 1000 }], ['mobile', { width: 390, height: 844 }]]) {
    const page = await browser.newPage({ viewport })
    const consoleErrors = []
    const failedResponses = []
    page.on('console', (message) => {
      if (message.type() === 'error') consoleErrors.push(`${message.text()} ${JSON.stringify(message.location())}`)
    })
    page.on('response', (response) => { if (response.status() >= 400) failedResponses.push(`${response.status()} ${response.url()}`) })
    await page.goto('http://127.0.0.1:7100', { waitUntil: 'networkidle' })
    await page.getByRole('button', { name: '加载主案例' }).click()
    await page.getByRole('heading', { name: '一页预算方案' }).waitFor()
    if (name === 'desktop') {
      await page.screenshot({ path: resolve(out, 'desktop-viewport.jpg'), type: 'jpeg', quality: 85 })
    }
    await page.screenshot({ path: resolve(out, `${name}-main.jpg`), fullPage: true, type: 'jpeg', quality: 85 })
    results[name] = {
      horizontalOverflow: await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth),
      consoleErrors,
      failedResponses,
    }
    if (name === 'desktop') {
      await page.emulateMedia({ media: 'print' })
      await page.pdf({ path: resolve(out, 'main-report.pdf'), format: 'A4', printBackground: true })
      await page.screenshot({ path: resolve(out, 'print-main.jpg'), fullPage: true, type: 'jpeg', quality: 85 })
      results.print = { horizontalOverflow: await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth) }
    }
    await page.close()
  }
} finally {
  await browser.close()
}
await writeFile(resolve(out, 'visual-qa.json'), `${JSON.stringify(results, null, 2)}\n`)
console.log(JSON.stringify(results, null, 2))
if (Object.values(results).some((value) => value.horizontalOverflow || value.consoleErrors?.length)) process.exitCode = 1
