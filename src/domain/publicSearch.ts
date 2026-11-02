import type { StoreProfile } from './types'

export interface PublicSource {
  title: string
  url: string
  capturedAt: string
  snippet: string
}

export type HypothesisId = 'rating_reviews' | 'menu_structure' | 'price_sensitivity' | 'insufficient_data'

export interface PublicAiResult {
  status: 'used' | 'fallback'
  hypothesisId: HypothesisId
  reason: string
}

export interface PublicSearchResult {
  status: 'review' | 'manual'
  sources: PublicSource[]
  observations: string[]
  ai?: PublicAiResult
  error?: string
}

export type PublicFetch = (url: string, init?: RequestInit) => Promise<Response>

const hypothesisLabels: Record<HypothesisId, string> = {
  rating_reviews: '评分与评价问题',
  menu_structure: '菜单与套餐承接',
  price_sensitivity: '价格带与权益敏感性',
  insufficient_data: '公开信息不足',
}

function excerpt(text: string): string {
  return text.replace(/\s+/g, ' ').trim().slice(0, 700)
}

function usable(text: string): boolean {
  const normalized = excerpt(text)
  if (normalized.length < 40) return false
  return !/access denied|request has been blocked|no results|not found|captcha|verify you are human|百度安全验证/i.test(normalized)
}

function ruleHypothesis(text: string): HypothesisId {
  if (/评分|评价/.test(text)) return 'rating_reviews'
  if (/人均|价格|优惠|补贴/.test(text)) return 'price_sensitivity'
  if (/菜单|套餐|菜品/.test(text)) return 'menu_structure'
  return 'insufficient_data'
}

async function chooseAiHypothesis(text: string, fetcher: PublicFetch): Promise<PublicAiResult> {
  const fallback = { status: 'fallback' as const, hypothesisId: ruleHypothesis(text), reason: 'AI 不可用或输出未通过白名单校验，已按本地规则选择。' }
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), 12000)
  try {
    const response = await fetcher('https://text.pollinations.ai/', {
      method: 'POST',
      signal: controller.signal,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model: 'openai',
        messages: [
          { role: 'system', content: '你是公开信息分类器。只能从 rating_reviews、menu_structure、price_sensitivity、insufficient_data 中选择一个待验证方向。只输出 JSON：{"hypothesisId":"其中一个ID"}。不得输出其他字段、数字、原因或经营建议。' },
          { role: 'user', content: `根据以下公开摘要选择方向：\n${text.slice(0, 1800)}` },
        ],
        response_format: { type: 'json_object' },
      }),
    })
    if (!response.ok) throw new Error(`AI HTTP ${response.status}`)
    const payload = JSON.parse(await response.text()) as { hypothesisId?: string; choices?: { message?: { content?: string } }[] }
    const candidate = payload.hypothesisId ?? payload.choices?.[0]?.message?.content ?? ''
    const hypothesisId = typeof candidate === 'string' ? candidate.replace(/["\s]/g, '') : ''
    if (!Object.keys(hypothesisLabels).includes(hypothesisId)) return fallback
    return { status: 'used', hypothesisId: hypothesisId as HypothesisId, reason: 'AI 仅选择待验证方向，解释与计算由本地规则完成。' }
  } catch {
    return fallback
  } finally {
    clearTimeout(timeout)
  }
}

function providers(query: string) {
  const encoded = encodeURIComponent(query)
  return [
    { name: 'Bing', searchUrl: `https://www.bing.com/search?q=${encoded}`, readerUrl: `https://r.jina.ai/http://www.bing.com/search?q=${encoded}` },
    { name: 'DuckDuckGo', searchUrl: `https://duckduckgo.com/html/?q=${encoded}`, readerUrl: `https://r.jina.ai/http://duckduckgo.com/html/?q=${encoded}` },
  ]
}

export async function searchPublicMerchant(
  profile: StoreProfile,
  fetcher: PublicFetch,
): Promise<PublicSearchResult> {
  const query = [profile.alias, profile.city, profile.district, profile.category, '门店 评分 人均'].filter(Boolean).join(' ')
  const errors: string[] = []
  for (const provider of providers(query)) {
    const controller = new AbortController()
    const timeout = setTimeout(() => controller.abort(), 12000)
    try {
      const response = await fetcher(provider.readerUrl, { signal: controller.signal })
      if (!response.ok) throw new Error(`${provider.name} HTTP ${response.status}`)
      const text = await response.text()
      if (!usable(text)) throw new Error(`${provider.name} 无有效公开文本`)
      const rating = text.match(/评分\s*[：:]?\s*([0-5](?:\.\d)?)/)?.[1] ?? text.match(/([0-5]\.\d)\s*分/)?.[1]
      const price = text.match(/人均\s*[¥￥]?\s*(\d+(?:\.\d+)?)/)?.[1]
      const ai = await chooseAiHypothesis(text, fetcher)
      return {
        status: 'review',
        sources: [{
          title: `公开搜索：${profile.alias}`,
          url: provider.searchUrl,
          capturedAt: new Date().toISOString(),
          snippet: excerpt(text),
        }],
        observations: [
          `检索到与“${profile.alias}”相关的公开网页摘要，以下内容均为待确认信息，不作为已核实门店事实。`,
          rating ? `摘要出现评分 ${rating}，请确认是否属于该门店。` : '摘要中没有可确认的评分，请人工补充。',
          price ? `摘要出现人均 ${price} 元，请确认采集日期和平台口径。` : '摘要中没有可确认的人均价，请人工补充价格带。',
          `${ai.status === 'used' ? 'AI 辅助选择' : '本地规则选择'}的待验证方向：${hypothesisLabels[ai.hypothesisId]}。${ai.reason}`,
          '公开信息只用于门店基建初诊；曝光、转化、投放和利润需要商家授权周报。',
        ],
        ai,
      }
    } catch (error) {
      errors.push(error instanceof Error ? error.message : String(error))
    } finally {
      clearTimeout(timeout)
    }
  }
  return {
    status: 'manual',
    sources: [],
    observations: ['公开检索暂不可用，请人工补充公开信息；不会用店名生成虚构诊断，周报诊断仍可继续。'],
    error: errors.join('；') || '公共检索不可用',
  }
}
