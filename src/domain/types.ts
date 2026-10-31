export type Role = 'ka' | 'agency' | 'cs'
export type BudgetMode = 'reallocate' | 'add'

export interface StoreProfile {
  alias: string
  platform: string
  city: string
  district: string
  category: string
  priceBand: string
  stage: string
  rating: number
  menuNote: string
}

export interface ToolMetric {
  toolName: string
  spend: number
  attributedGmv: number
  roi: number
  attributionWindowDays: number
  attributionDefinition: string
}

export interface WeeklyReport {
  synthetic: boolean
  store: StoreProfile
  weekStart: string
  exportedAt: string
  orders: number
  netGmv: number
  merchantSubsidy: number
  platformSubsidy: number
  exposure?: number
  visits?: number
  repeatCustomerRate?: number
  memberShare?: number
  tools: ToolMetric[]
}

export interface Recommendation {
  mode: BudgetMode
  sourceTool: string | null
  targetTool: string
  amount: number
}

export interface Calculation {
  currentGmv: number
  projectedGmv: number
  deltaGmv: number
  currentGrossProfit: number
  projectedGrossProfit: number
  deltaGrossProfit: number
  spendDelta: number
}

export interface DiagnosisIssue {
  code: 'LOW_ROI' | 'SUBSIDY' | 'ATTRIBUTION_MISMATCH' | 'ATTRIBUTION_IMMATURE' | 'BASIC_POOL' | 'PROFIT_RISK'
  title: string
  value: number
  detail: string
}

export interface FollowUp {
  action: string
  owner: string
  metric: string
  target: string
  reviewDate: string
  stopCondition: string
}

export interface DiagnosisResult {
  issues: DiagnosisIssue[]
  recommendation: Recommendation | null
  calculation: Calculation | null
  talkTracks: string[]
  followUps: FollowUp[]
}
