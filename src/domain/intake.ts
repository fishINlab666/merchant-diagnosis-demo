import type { StoreProfile } from './types'

export interface DataRequest {
  files: string[]
  fields: string[]
  optionalFields: string[]
  exportSteps: string[]
}

export function buildInitialObservations(store: StoreProfile): string[] {
  const observations: string[] = []
  if (Number.isFinite(store.rating)) {
    observations.push(`公开事实：当前评分 ${store.rating}；近期评价是否集中反映份量、配送或价格问题仍待验证。`)
  } else {
    observations.push('公开信息不足：缺少可确认评分，请人工补充平台、评分和采集日期。')
  }
  if (store.menuNote.trim()) {
    observations.push(`公开事实：${store.menuNote}；一人食场景的曝光和下单承接需要周报验证。`)
  } else {
    observations.push('公开信息不足：请人工补充菜单、套餐和典型评价，不用店名推测菜品结构。')
  }
  if (store.priceBand.trim()) {
    observations.push(`待验证：门店处于${store.priceBand}价格带，补贴和投放是否侵蚀毛利需要平台周报。`)
  } else {
    observations.push('公开信息不足：请人工补充价格带；上传周报后再判断经营、转化和利润。')
  }
  return observations
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
