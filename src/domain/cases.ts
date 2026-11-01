import type { ProductUsage, StoreProfile, WeeklyReport } from './types'

export const demoStore: StoreProfile = {
  alias: '合成餐饮品牌 A',
  platform: '示例平台',
  city: '杭州',
  district: '城西科创商圈',
  category: '中式快餐',
  priceBand: '25—35 元',
  stage: '成熟店',
  rating: 4.4,
  menuNote: '一人食套餐 3 款，招牌饭为主要成交商品',
}

export const mainCase: WeeklyReport = {
  synthetic: true,
  store: demoStore,
  weekStart: '2026-10-12',
  exportedAt: '2026-10-26T00:00:00+08:00',
  orders: 1200,
  netGmv: 60000,
  merchantSubsidy: 4000,
  platformSubsidy: 1500,
  exposure: 120000,
  visits: 12000,
  repeatCustomerRate: 0.28,
  memberShare: 0.24,
  tools: [
    { toolName: '点金推广', spend: 1000, attributedGmv: 10000, roi: 10, attributionWindowDays: 7, attributionDefinition: '点击归因' },
    { toolName: '搜索推广', spend: 800, attributedGmv: 14400, roi: 18, attributionWindowDays: 7, attributionDefinition: '点击归因' },
    { toolName: '品牌展示', spend: 600, attributedGmv: 7200, roi: 12, attributionWindowDays: 7, attributionDefinition: '点击归因' },
  ],
}

export const mainProductUsage: ProductUsage = {
  synthetic: true,
  activeOperators: 2,
  reportImports: 1,
  followUpCompletionRate: 0.33,
  lastActiveAt: '2026-10-18',
  renewalReviewDate: '2026-12-31',
}

export const controlCase: WeeklyReport = {
  ...mainCase,
  store: { ...demoStore, alias: '合成对照品牌 B' },
  tools: [
    { toolName: '点金推广', spend: 1000, attributedGmv: 10000, roi: 10, attributionWindowDays: 7, attributionDefinition: '点击归因' },
    { toolName: '搜索推广', spend: 800, attributedGmv: 14400, roi: 18, attributionWindowDays: 1, attributionDefinition: '点击归因' },
  ],
}
