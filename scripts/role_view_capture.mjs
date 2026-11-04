import { chromium } from '@playwright/test'
import { mkdir, writeFile } from 'node:fs/promises'
import { resolve } from 'node:path'

const root = resolve(import.meta.dirname, '..')
const out = resolve(root, 'artifacts', 'three-role-views')
await mkdir(out, { recursive: true })
const browser = await chromium.launch({ headless: true, executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' })
const checks = { screens: {}, errors: [] }

async function inspect(page, key) {
  checks.screens[key] = await page.evaluate(() => ({
    title: document.querySelector('h1')?.textContent ?? '',
    role: document.querySelector('.role-switch button.active')?.textContent ?? '',
    specialModule: document.querySelector('.role-special-module')?.className ?? null,
    overflow: document.documentElement.scrollWidth > innerWidth,
    width: innerWidth,
    scrollWidth: document.documentElement.scrollWidth,
  }))
  if (checks.screens[key].overflow) checks.errors.push(`${key}: horizontal overflow`)
}

async function shot(page, name) {
  await page.screenshot({ path: resolve(out, `${name}.jpg`), type: 'jpeg', quality: 84, fullPage: true })
}

try {
  for (const viewport of [{ name: 'desktop', width: 1440, height: 1000 }, { name: 'mobile', width: 390, height: 844 }]) {
    const page = await browser.newPage({ viewport })
    page.on('pageerror', (error) => checks.errors.push(error.message))
    await page.goto('http://127.0.0.1:7100', { waitUntil: 'networkidle' })
    await page.getByRole('button', { name: '快餐示例' }).click()
    for (const role of [{ key: 'merchant', name: '商家老板' }, { key: 'ka', name: '平台 KA' }, { key: 'cs', name: 'SaaS 客户成功' }]) {
      await page.getByRole('button', { name: role.name, exact: true }).click()
      await page.getByRole('tab', { name: '行动方案' }).click()
      await inspect(page, `${viewport.name}-${role.key}-budget`)
      await shot(page, `${viewport.name}-${role.key}-budget`)
      if (viewport.name === 'desktop' && role.key !== 'merchant') {
        await page.emulateMedia({ media: 'print' })
        await page.pdf({ path: resolve(out, `${role.key}-budget-a4.pdf`), format: 'A4', printBackground: true })
        await page.emulateMedia({ media: 'screen' })
      }
      await page.getByRole('tab', { name: '经营诊断' }).click()
      await inspect(page, `${viewport.name}-${role.key}-health`)
      if (role.key !== 'merchant') await shot(page, `${viewport.name}-${role.key}-health`)
    }
    await page.close()
  }
} finally {
  await browser.close()
}
await writeFile(resolve(out, 'checks.json'), `${JSON.stringify(checks, null, 2)}\n`)
console.log(JSON.stringify(checks, null, 2))
if (checks.errors.length) process.exitCode = 1
