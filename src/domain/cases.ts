import type { StoreProfile, WeeklyReport } from './types'

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

export const fineDiningCase: WeeklyReport = {
  ...mainCase,
  store: {
    ...demoStore,
    alias: '合成粤菜餐厅 C',
    category: '粤式正餐',
    priceBand: '80—120 元',
    rating: 4.2,
    menuNote: '双人套餐 2 款，单人工作日餐选择较少',
  },
  orders: 420,
  netGmv: 56000,
  merchantSubsidy: 9000,
  platformSubsidy: 2000,
  exposure: 50000,
  visits: 4000,
  repeatCustomerRate: 0.38,
  memberShare: 0.41,
  tools: [
    { toolName: '斗金推广', spend: 1000, attributedGmv: 6000, roi: 6, attributionWindowDays: 7, attributionDefinition: '点击归因' },
    { toolName: '品牌展位', spend: 500, attributedGmv: 5000, roi: 10, attributionWindowDays: 7, attributionDefinition: '点击归因' },
  ],
}

export const controlCase: WeeklyReport = {
  ...mainCase,
  store: { ...demoStore, alias: '合成对照品牌 B' },
  tools: [
    { toolName: '点金推广', spend: 1000, attributedGmv: 10000, roi: 10, attributionWindowDays: 7, attributionDefinition: '点击归因' },
    { toolName: '搜索推广', spend: 800, attributedGmv: 14400, roi: 18, attributionWindowDays: 1, attributionDefinition: '点击归因' },
  ],
}
