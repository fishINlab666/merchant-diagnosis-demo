import { readSheet, type CellValue } from 'read-excel-file/universal'
import type { StoreProfile, WeeklyReport } from '../domain/types'

type Cell = CellValue | null

const REQUIRED = ['门店ID', '周开始', '订单', '净GMV', '商家补贴', '平台补贴', '投放工具', '消耗', '归因净GMV', '归因窗口', '归因定义', '导出时间']
const STORE_FIELDS = ['门店ID', '周开始', '订单', '净GMV', '商家补贴', '平台补贴', '导出时间']

function parseCsvRows(input: string): string[][] {
  const rows: string[][] = []
  let row: string[] = []
  let field = ''
  let quoted = false
  for (let index = 0; index < input.length; index += 1) {
    const char = input[index]
    if (quoted) {
      if (char === '"' && input[index + 1] === '"') {
        field += '"'
        index += 1
      } else if (char === '"') {
        quoted = false
      } else {
        field += char
      }
    } else if (char === '"' && field === '') {
      quoted = true
    } else if (char === ',') {
      row.push(field)
      field = ''
    } else if (char === '\n') {
      row.push(field.replace(/\r$/, ''))
      rows.push(row)
      row = []
      field = ''
    } else {
      field += char
    }
  }
  row.push(field.replace(/\r$/, ''))
  rows.push(row)
  return rows.filter((item) => item.some((value) => value.trim() !== ''))
}

function text(value: Cell): string {
  return value === null ? '' : String(value).trim()
}

function number(value: Cell, field: string): number {
  const parsed = Number(value)
  if (!Number.isFinite(parsed)) throw new Error(`${field} 不是有效数字`)
  if (parsed < 0) throw new Error(`${field} 不能为负`)
  return parsed
}

function optionalNumber(record: Record<string, Cell>, field: string): number | undefined {
  const cell = record[field]
  if (cell === undefined || cell === null || text(cell) === '') return undefined
  return number(cell, field)
}

function optionalRatio(record: Record<string, Cell>, field: string): number | undefined {
  const value = optionalNumber(record, field)
  if (value !== undefined && (value < 0 || value > 1)) throw new Error(`${field} 须为 0—1 的小数`)
  return value
}

function normalize(headers: string[], rows: Cell[][], store: StoreProfile): WeeklyReport {
  const normalizedHeaders = headers.map((header, index) => index === 0 ? header.replace(/^\uFEFF/, '') : header)
  const missing = REQUIRED.filter((field) => !normalizedHeaders.includes(field))
  if (missing.length > 0) throw new Error(`周报缺少字段：${missing.join('、')}`)
  if (rows.length === 0) throw new Error('周报没有数据行')
  const records = rows.map((row) => Object.fromEntries(normalizedHeaders.map((header, index) => [header, row[index] ?? null])))
  const first = records[0]
  for (const record of records) {
    for (const field of STORE_FIELDS) {
      if (text(record[field]) !== text(first[field])) throw new Error(`门店汇总字段不一致：${field}`)
    }
  }
  const toolNames = records.map((record) => text(record['投放工具']))
  if (new Set(toolNames).size !== toolNames.length) throw new Error('投放工具重复，请保留每个工具的一行周汇总')
  return {
    synthetic: false,
    store,
    weekStart: text(first['周开始']),
    exportedAt: text(first['导出时间']),
    orders: number(first['订单'], '订单'),
    netGmv: number(first['净GMV'], '净GMV'),
    merchantSubsidy: number(first['商家补贴'], '商家补贴'),
    platformSubsidy: number(first['平台补贴'], '平台补贴'),
    exposure: optionalNumber(first, '曝光'),
    visits: optionalNumber(first, '进店'),
    repeatCustomerRate: optionalRatio(first, '复购率'),
    memberShare: optionalRatio(first, '会员占比'),
    tools: records.map((record) => {
      const spend = number(record['消耗'], '消耗')
      const attributedGmv = number(record['归因净GMV'], '归因净GMV')
      if (spend === 0 && attributedGmv > 0) throw new Error('消耗为 0 时归因净GMV 不能大于 0')
      return {
        toolName: text(record['投放工具']),
        spend,
        attributedGmv,
        roi: spend === 0 ? 0 : Math.round(attributedGmv / spend * 100) / 100,
        attributionWindowDays: number(record['归因窗口'], '归因窗口'),
        attributionDefinition: text(record['归因定义']),
      }
    }),
  }
}

export function parseCsvWeeklyReport(input: string, store: StoreProfile): WeeklyReport {
  const [headers, ...rows] = parseCsvRows(input)
  return normalize(headers ?? [], rows, store)
}

export async function parseXlsxWeeklyReport(file: Blob, store: StoreProfile): Promise<WeeklyReport> {
  const rows = await readSheet(file)
  const [headers, ...dataRows] = rows
  return normalize((headers ?? []).map(text), dataRows, store)
}
