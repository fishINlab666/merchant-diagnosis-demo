export const STANDARD_REQUIRED = ['门店ID', '周开始', '订单', '净GMV', '商家补贴', '平台补贴', '投放工具', '消耗', '归因净GMV', '归因窗口', '归因定义', '导出时间'] as const

const FIELD_ALIASES: Record<string, string[]> = {
  门店ID: ['门店编号', '店铺ID', 'store_id'],
  周开始: ['周期开始', 'week_start'],
  订单: ['订单量', 'orders'],
  净GMV: ['净交易额', 'net_gmv'],
  商家补贴: ['商家补贴金额'],
  平台补贴: ['平台补贴金额'],
  投放工具: ['工具名称', '广告工具'],
  消耗: ['花费', '广告消耗', 'spend'],
  归因净GMV: ['归因GMV', '广告归因净GMV'],
  归因窗口: ['归因窗口天数', '归因天数'],
  归因定义: ['归因口径'],
  导出时间: ['导出日期', '数据导出时间'],
  曝光: ['曝光量'],
  进店: ['进店量', '访问量'],
  复购率: ['复购比例'],
  会员占比: ['会员用户占比'],
}

export const STANDARD_FIELDS = Object.keys(FIELD_ALIASES)

export interface HeaderMapping {
  source: string
  standard: string | null
  match: 'exact' | 'alias' | 'unmapped' | 'manual'
}

export interface ModulePreview {
  id: 'operations' | 'traffic' | 'users'
  label: string
  available: boolean
  reason: string
}

export interface HeaderMappingPreview {
  mappings: HeaderMapping[]
  missingRequired: string[]
  duplicateStandards: string[]
  modules: ModulePreview[]
  canGenerate: boolean
}

function normalized(header: string): string {
  return header.replace(/^\uFEFF/, '').trim().toLowerCase()
}

function standardFor(source: string): { standard: string | null; match: HeaderMapping['match'] } {
  const value = normalized(source)
  for (const [standard, aliases] of Object.entries(FIELD_ALIASES)) {
    if (normalized(standard) === value) return { standard, match: 'exact' }
    if (aliases.some((alias) => normalized(alias) === value)) return { standard, match: 'alias' }
  }
  return { standard: null, match: 'unmapped' }
}

export function evaluateHeaderMappings(mappings: HeaderMapping[]): HeaderMappingPreview {
  const mapped = new Set(mappings.flatMap((item) => item.standard ? [item.standard] : []))
  const missingRequired = STANDARD_REQUIRED.filter((field) => !mapped.has(field))
  const duplicateStandards = [...new Set(mappings.flatMap((item) => item.standard ? [item.standard] : []))].filter((standard) => mappings.filter((item) => item.standard === standard).length > 1)
  const canGenerate = missingRequired.length === 0 && duplicateStandards.length === 0
  const operationsReason = missingRequired.length > 0
    ? `缺少：${missingRequired.join('、')}`
    : duplicateStandards.length > 0 ? `重复映射：${duplicateStandards.join('、')}` : '必需字段齐全，待数据校验'
  const optionalReason = (fields: string[]) => {
    if (!canGenerate) return '先补齐必需字段并解决重复映射'
    const missing = fields.filter((field) => !mapped.has(field))
    return missing.length > 0 ? `缺少：${missing.join('、')}` : '字段齐全'
  }
  return {
    mappings,
    missingRequired,
    duplicateStandards,
    canGenerate,
    modules: [
      { id: 'operations', label: '经营与投放', available: canGenerate, reason: operationsReason },
      { id: 'traffic', label: '流量转化', available: canGenerate && ['曝光', '进店'].every((field) => mapped.has(field)), reason: optionalReason(['曝光', '进店']) },
      { id: 'users', label: '用户经营', available: canGenerate && ['复购率', '会员占比'].every((field) => mapped.has(field)), reason: optionalReason(['复购率', '会员占比']) },
    ],
  }
}

export function buildHeaderMapping(headers: string[]): HeaderMappingPreview {
  const mappings = headers.filter((header) => header.trim()).map((source) => ({ source: source.trim(), ...standardFor(source) }))
  return evaluateHeaderMappings(mappings)
}
