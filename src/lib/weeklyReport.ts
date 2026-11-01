import { readSheet, type CellValue } from 'read-excel-file/universal'
import type { StoreProfile, WeeklyReport } from '../domain/types'
import { STANDARD_REQUIRED, type HeaderMapping } from './reportMapping'

type Cell = CellValue | null

const REQUIRED = [...STANDARD_REQUIRED]
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

function normalize(headers: string[], rows: Cell[][], store: StoreProfile, mapping: HeaderMapping[]): WeeklyReport {
  const normalizedHeaders = headers.map((header, index) => {
    const cleaned = (index === 0 ? header.replace(/^\uFEFF/, '') : header).trim()
    return mapping.find((item) => item.source === cleaned)?.standard ?? cleaned
  })
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
  const sourceStoreId = text(first['门店ID'])
  if (!sourceStoreId) throw new Error('门店ID不能为空')
  return {
    synthetic: false,
    sourceStoreId,
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

export function readCsvWeeklyReportHeaders(input: string): string[] {
  const [headers] = parseCsvRows(input)
  return (headers ?? []).map((header) => header.trim())
}

export async function readXlsxWeeklyReportHeaders(file: Blob): Promise<string[]> {
  const [headers] = await readSheet(file)
  return (headers ?? []).map(text)
}

export function readCsvWeeklyReportStoreId(input: string, mapping: HeaderMapping[]): string {
  const [headers, ...rows] = parseCsvRows(input)
  const source = mapping.find((item) => item.standard === '门店ID')?.source ?? '门店ID'
  const index = (headers ?? []).findIndex((header) => header.trim() === source)
  return index >= 0 ? text(rows[0]?.[index] ?? null) : ''
}

export async function readXlsxWeeklyReportStoreId(file: Blob, mapping: HeaderMapping[]): Promise<string> {
  const [headers, ...rows] = await readSheet(file)
  const source = mapping.find((item) => item.standard === '门店ID')?.source ?? '门店ID'
  const index = (headers ?? []).findIndex((header) => text(header) === source)
  return index >= 0 ? text(rows[0]?.[index] ?? null) : ''
}

export function parseCsvWeeklyReport(input: string, store: StoreProfile, mapping: HeaderMapping[] = []): WeeklyReport {
  const [headers, ...rows] = parseCsvRows(input)
  return normalize(headers ?? [], rows, store, mapping)
}

export async function parseXlsxWeeklyReport(file: Blob, store: StoreProfile, mapping: HeaderMapping[] = []): Promise<WeeklyReport> {
  const rows = await readSheet(file)
  const [headers, ...dataRows] = rows
  return normalize((headers ?? []).map(text), dataRows, store, mapping)
}
