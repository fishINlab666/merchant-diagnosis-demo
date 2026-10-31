import type { StoreProfile } from './types'

export interface DataRequest {
  files: string[]
  fields: string[]
  optionalFields: string[]
  exportSteps: string[]
}

export function buildInitialObservations(store: StoreProfile): string[] {
  return [
    `当前公开评分 ${store.rating}，需要先确认近期评价是否集中反映份量、配送或价格问题。`,
    `公开菜单显示${store.menuNote}，可以继续聊一人食场景的曝光和下单承接。`,
    `门店处于${store.priceBand}价格带，下一步需要用周报判断补贴和投放是否正在侵蚀毛利。`,
  ]
}

export function buildDataRequest(): DataRequest {
  return {
    files: ['平台后台周报表（CSV／XLSX）'],
    fields: ['门店ID', '周开始', '订单', '净GMV', '投放工具', '消耗', '归因净GMV', 'ROI', '商家补贴', '平台补贴', '归因窗口', '归因定义', '导出时间'],
    optionalFields: ['曝光', '进店', '复购率（0—1）', '会员占比（0—1）'],
    exportSteps: [
      '进入平台后台的经营或推广数据页面，选择最近一个完整自然周。',
      '保留门店汇总，以及各投放工具的花费、归因 GMV、ROI 和补贴字段。',
      '导出 CSV 或 XLSX；商户名、门店名可替换为别名，不需要提供用户明细。',
    ],
  }
}
