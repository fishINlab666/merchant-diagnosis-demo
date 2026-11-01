import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'
import { demoStore } from '../src/domain/cases'
import { buildHeaderMapping } from '../src/lib/reportMapping'
import { parseCsvWeeklyReport, parseXlsxWeeklyReport, readCsvWeeklyReportHeaders, readXlsxWeeklyReportHeaders } from '../src/lib/weeklyReport'

const csv = `门店ID,周开始,订单,净GMV,商家补贴,平台补贴,投放工具,消耗,归因净GMV,归因窗口,归因定义,导出时间
S1,2026-10-12,1200,60000,4000,1500,点金推广,1000,10000,7,点击归因,2026-10-26T00:00:00+08:00
S1,2026-10-12,1200,60000,4000,1500,搜索推广,800,14400,7,点击归因,2026-10-26T00:00:00+08:00`

describe('weekly report import', () => {
  it('reads store totals once and calculates tool ROI from attributed GMV and spend', () => {
    const report = parseCsvWeeklyReport(csv, demoStore)

    expect(report.orders).toBe(1200)
    expect(report.netGmv).toBe(60000)
    expect(report.tools.map((tool) => tool.roi)).toEqual([10, 18])
    expect(report.synthetic).toBe(false)
  })

  it('rejects duplicate tools instead of double counting them', () => {
    expect(() => parseCsvWeeklyReport(`${csv}\nS1,2026-10-12,1200,60000,4000,1500,点金推广,1000,10000,7,点击归因,2026-10-26T00:00:00+08:00`, demoStore))
      .toThrow('投放工具重复')
  })

  it('maps optional funnel and user metrics when the columns are present', () => {
    const enriched = csv
      .replace('归因定义,导出时间', '归因定义,导出时间,曝光,进店,复购率,会员占比')
      .replace(/,2026-10-26T00:00:00\+08:00/g, ',2026-10-26T00:00:00+08:00,120000,12000,0.28,0.24')
    const report = parseCsvWeeklyReport(enriched, demoStore)

    expect(report.exposure).toBe(120000)
    expect(report.visits).toBe(12000)
    expect(report.repeatCustomerRate).toBe(0.28)
    expect(report.memberShare).toBe(0.24)
  })

  it('reads an XLSX workbook through the same internal schema', async () => {
    const file = new File([readFileSync(resolve('tests/fixtures/main-report.xlsx'))], 'main-report.xlsx')
    const report = await parseXlsxWeeklyReport(file, demoStore)

    expect(report.orders).toBe(1200)
    expect(report.netGmv).toBe(60000)
    expect(report.tools.map((tool) => tool.roi)).toEqual([10, 18, 12])
  })

  it('applies confirmed aliases and reads CSV headers before parsing', () => {
    const aliasCsv = csv
      .replace('门店ID', '门店编号')
      .replace('订单', '订单量')
      .replace('净GMV', '净交易额')
      .replace('归因净GMV', '归因GMV')
    const headers = readCsvWeeklyReportHeaders(aliasCsv)
    const preview = buildHeaderMapping(headers)
    const report = parseCsvWeeklyReport(aliasCsv, demoStore, preview.mappings)

    expect(headers).toContain('门店编号')
    expect(preview.canGenerate).toBe(true)
    expect(report.orders).toBe(1200)
    expect(report.netGmv).toBe(60000)
  })

  it('reads XLSX headers without generating a report', async () => {
    const file = new File([readFileSync(resolve('tests/fixtures/main-report.xlsx'))], 'main-report.xlsx')
    const headers = await readXlsxWeeklyReportHeaders(file)

    expect(headers).toContain('门店ID')
    expect(buildHeaderMapping(headers).canGenerate).toBe(true)
  })
})
