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

export interface PublicCompetitor {
  name: string
  rating: number | null
  monthlySales: number | null
  averagePrice: number | null
  deliveryMinutes: number | null
}

export interface PublicIntakeAnalysis {
  facts: {
    name: string
    rating: number | null
    monthlySales: number | null
    averagePrice: number | null
    minimumOrder: number | null
    deliveryFee: number | null
    deliveryMinutes: number | null
    menuItems: string[]
  }
  themes: Array<{ id: string; label: string; count: number; quotes: string[] }>
  competitors: PublicCompetitor[]
  peerSummary: { ratingMedian: number | null; deliveryMinutesMedian: number | null } | null
  candidates: Array<{ title: string; evidence: string; hypothesis: string; action: string; quote?: string }>
}

export const PUBLIC_INTAKE_SAMPLE = `张记煲仔饭（城西店）
评分 4.4 · 月售 2600+ · 人均 ¥29 · 起送 ¥20 · 配送费 ¥4 · 配送约 42 分钟
招牌腊味煲仔饭 ¥32｜香菇滑鸡煲仔饭 ¥28｜一人食套餐（饭+例汤）¥35｜双人套餐 ¥66
评价：
“等了快一个小时，送到饭都凉了，锅巴也软了”
“分量比堂食少一圈”
“锅巴糊了，有点苦”
“配送太慢，下次不点了”
“腊味很足，锅巴香”
“凉了就不好吃了，建议包装改一下”
竞店：老广记煲仔饭｜评分 4.7｜月售 4100｜人均 ¥31｜配送约 31 分钟
竞店：陈家煲仔饭｜评分 4.6｜月售 3300｜人均 ¥27｜配送约 35 分钟`

function numberFrom(text: string, pattern: RegExp): number | null {
  const match = text.match(pattern)
  if (!match) return null
  const value = Number(match[1])
  return Number.isFinite(value) ? value : null
}

function median(values: Array<number | null>): number | null {
  const sorted = values.filter((value): value is number => value !== null).sort((a, b) => a - b)
  if (!sorted.length) return null
  const middle = Math.floor(sorted.length / 2)
  return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2
}

function parseCompetitor(line: string): PublicCompetitor {
  const [rawName] = line.replace(/^竞店\s*[：:]?\s*/, '').split(/[｜|]/)
  return {
    name: rawName.trim(),
    rating: numberFrom(line, /评分\s*[：:]?\s*([0-5](?:\.\d+)?)/),
    monthlySales: numberFrom(line, /月售\s*[：:]?\s*(\d+(?:\.\d+)?)/),
    averagePrice: numberFrom(line, /人均\s*[¥￥]?\s*(\d+(?:\.\d+)?)/),
    deliveryMinutes: numberFrom(line, /配送(?:约|时长)?\s*[：:]?\s*(\d+(?:\.\d+)?)\s*分钟/),
  }
}

export function parsePublicIntake(text: string): PublicIntakeAnalysis {
  const normalized = text.replace(/\r/g, '').trim()
  const lines = normalized.split('\n').map((line) => line.trim()).filter(Boolean)
  const shopLines = lines.filter((line) => !/^竞店\s*[：:]?/.test(line))
  const shopText = shopLines.join('\n')
  const competitors = lines.filter((line) => /^竞店\s*[：:]?/.test(line)).map(parseCompetitor)
  const ratingMedian = median(competitors.map((item) => item.rating))
  const deliveryMinutesMedian = median(competitors.map((item) => item.deliveryMinutes))
  const reviewSection = normalized.split(/评价\s*[：:]/)[1] ?? ''
  const quoted = Array.from(reviewSection.matchAll(/["“]([^"”\n]+)["”]/g), (match) => match[1].trim())
  const reviews = quoted.length ? quoted : reviewSection.split('\n')
    .map((line) => line.trim())
    .filter((line) => line && !/^竞店\s*[：:]?/.test(line))
  const themeRules = [
    { id: 'delivery', label: '配送慢', pattern: /慢|一个小时|等了|太久/ },
    { id: 'temperature', label: '送到变凉', pattern: /凉|冷|软了/ },
    { id: 'portion', label: '分量不足', pattern: /分量|量少|少一圈/ },
    { id: 'taste', label: '口味不稳', pattern: /糊|苦|咸|口味不稳/ },
  ]
  const themes = themeRules.map((theme) => {
    const quotes = reviews.filter((review) => theme.pattern.test(review))
    return { id: theme.id, label: theme.label, count: quotes.length, quotes: quotes.slice(0, 3) }
  }).filter((theme) => theme.count > 0).sort((a, b) => b.count - a.count)
  const menuItems = lines.filter((line) => /[¥￥]/.test(line) && !/评分|月售|人均|起送|配送费|^竞店/.test(line))
    .flatMap((line) => line.split(/[｜|]/).map((item) => item.trim()).filter(Boolean))
  const facts = {
    name: shopLines[0]?.replace(/^店名\s*[：:]\s*/, '') ?? '',
    rating: numberFrom(shopText, /评分\s*[：:]?\s*([0-5](?:\.\d+)?)/),
    monthlySales: numberFrom(shopText, /月售\s*[：:]?\s*(\d+(?:\.\d+)?)/),
    averagePrice: numberFrom(shopText, /人均\s*[¥￥]?\s*(\d+(?:\.\d+)?)/),
    minimumOrder: numberFrom(shopText, /起送\s*[¥￥]?\s*(\d+(?:\.\d+)?)/),
    deliveryFee: numberFrom(shopText, /配送费\s*[¥￥]?\s*(\d+(?:\.\d+)?)/),
    deliveryMinutes: numberFrom(shopText, /配送约\s*[：:]?\s*(\d+(?:\.\d+)?)\s*分钟/),
    menuItems,
  }
  const candidates: PublicIntakeAnalysis['candidates'] = []
  const deliveryTheme = themes.find((theme) => theme.id === 'delivery' || theme.id === 'temperature')
  if (deliveryTheme || facts.deliveryMinutes !== null) {
    const comparison = deliveryMinutesMedian !== null && facts.deliveryMinutes !== null
      ? `；粘贴竞店的配送中位数为 ${deliveryMinutesMedian} 分钟` : ''
    candidates.push({
      title: '先核查配送与到手品质',
      evidence: `公开配送约 ${facts.deliveryMinutes ?? '未提供'} 分钟${comparison}；评价主题“${deliveryTheme?.label ?? '配送'}”出现 ${deliveryTheme?.count ?? 0} 条`,
      hypothesis: '待验证：出餐排序、配送时长或保温包装是否影响到手品质。',
      action: '先复核高峰出餐与保温流程，再用周报观察转化和复购，不先加推广。',
      quote: deliveryTheme?.quotes[0],
    })
  }
  if (facts.rating !== null && ratingMedian !== null && facts.rating < ratingMedian) {
    candidates.push({
      title: '评分低于已粘贴竞店',
      evidence: `本店评分 ${facts.rating}，竞店评分中位数 ${ratingMedian}`,
      hypothesis: '待验证：差评是否集中在可修复的门店承接环节；不推断搜索排序因果。',
      action: '按评价原文逐项确认责任环节，下周复查新增评价与复购。',
    })
  }
  if (facts.menuItems.length || facts.averagePrice !== null) {
    const solo = facts.menuItems.find((item) => /一人食|单人/.test(item))
    candidates.push({
      title: '检查单人餐与价格承接',
      evidence: `人均 ${facts.averagePrice ?? '未提供'} 元；${solo ? `已有一人食：${solo}` : '粘贴菜单中未识别到明确一人食套餐'}`,
      hypothesis: '待验证：套餐位置、起送门槛和配送费是否影响单人下单。',
      action: '优化一人食套餐表达，并用周报核对订单、客单与补贴，不直接承诺提客单。',
    })
  }
  return {
    facts,
    themes,
    competitors,
    peerSummary: competitors.length ? { ratingMedian, deliveryMinutesMedian } : null,
    candidates: candidates.slice(0, 3),
  }
}
