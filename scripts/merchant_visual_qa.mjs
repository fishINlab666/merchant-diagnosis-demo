import { chromium } from '@playwright/test'
import { mkdir, writeFile } from 'node:fs/promises'
import { resolve } from 'node:path'

const root = resolve(import.meta.dirname, '..')
const out = resolve(root, 'artifacts', 'merchant-tool')
await mkdir(out, { recursive: true })
const browser = await chromium.launch({ headless: true, executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' })
const results = { screens: {}, errors: [] }

async function inspect(page, key) {
  const state = await page.evaluate(() => ({
    overflow: document.documentElement.scrollWidth > window.innerWidth,
    module: document.querySelector('[data-decision-module]')?.getAttribute('data-decision-module') ?? null,
    title: document.querySelector('h1')?.textContent ?? null,
    smallButtons: [...document.querySelectorAll('button')].map((element) => {
      const rect = element.getBoundingClientRect()
      return { text: element.textContent?.trim(), width: Math.round(rect.width), height: Math.round(rect.height) }
    }).filter((item) => item.width < 44 || item.height < 44),
  }))
  results.screens[key] = state
  if (state.overflow) results.errors.push(`${key}: horizontal overflow`)
  if (state.smallButtons.length) results.errors.push(`${key}: ${state.smallButtons.length} small buttons`)
  return state
}

try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } })
  page.on('console', (message) => { if (message.type() === 'error') results.errors.push(message.text()) })
  await page.goto('http://127.0.0.1:7100', { waitUntil: 'networkidle' })
  await inspect(page, 'desktop-intake')
  await page.screenshot({ path: resolve(out, 'desktop-intake.jpg'), fullPage: true, type: 'jpeg', quality: 85 })

  await page.route('https://r.jina.ai/**', (route) => route.fulfill({ status: 200, contentType: 'text/plain', body: '# 测试门店\n评分：4.7\n人均 ¥28\n这是一段足够长的公开门店摘要，用于检查公开信息初诊的来源、评分和人工确认流程。' }))
  await page.getByLabel('店铺名称').fill('测试煲仔饭')
  await page.getByRole('button', { name: '开始经营诊断' }).click()
  await page.getByRole('heading', { name: '公开信息初诊' }).waitFor()
  await inspect(page, 'desktop-public')
  await page.screenshot({ path: resolve(out, 'desktop-public.jpg'), fullPage: true, type: 'jpeg', quality: 85 })
  await page.close()

  for (const [key, label] of [['fast', '快餐示例'], ['fine', '正餐示例'], ['control', '归因异常示例']]) {
    const desktop = await browser.newPage({ viewport: { width: 1440, height: 1000 } })
    await desktop.goto('http://127.0.0.1:7100', { waitUntil: 'networkidle' })
    await desktop.getByRole('button', { name: label }).click()
    await desktop.getByRole('heading', { name: '我的经营诊断' }).waitFor()
    await inspect(desktop, `desktop-${key}-health`)
    await desktop.screenshot({ path: resolve(out, `desktop-${key}-health.jpg`), fullPage: true, type: 'jpeg', quality: 85 })
    await desktop.getByRole('tab', { name: '行动方案' }).click()
    await inspect(desktop, `desktop-${key}-budget`)
    await desktop.screenshot({ path: resolve(out, `desktop-${key}-budget.jpg`), fullPage: true, type: 'jpeg', quality: 85 })
    await desktop.emulateMedia({ media: 'print' })
    await desktop.pdf({ path: resolve(out, `${key}-budget.pdf`), format: 'A4', printBackground: true })
    await desktop.close()

    const mobile = await browser.newPage({ viewport: { width: 390, height: 844 } })
    await mobile.goto('http://127.0.0.1:7100', { waitUntil: 'networkidle' })
    await mobile.getByRole('button', { name: label }).click()
    await inspect(mobile, `mobile-${key}-health`)
    await mobile.screenshot({ path: resolve(out, `mobile-${key}-health.jpg`), fullPage: true, type: 'jpeg', quality: 85 })
    await mobile.getByRole('tab', { name: '行动方案' }).click()
    await inspect(mobile, `mobile-${key}-budget`)
    await mobile.screenshot({ path: resolve(out, `mobile-${key}-budget.jpg`), fullPage: true, type: 'jpeg', quality: 85 })
    await mobile.close()
  }
} finally {
  await browser.close()
}

await writeFile(resolve(out, 'checks.json'), `${JSON.stringify(results, null, 2)}\n`)
console.log(JSON.stringify(results, null, 2))
if (results.errors.length > 0) process.exitCode = 1
