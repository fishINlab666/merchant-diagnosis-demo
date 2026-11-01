import type { StoreProfile } from './types'

export interface PublicSource {
  title: string
  url: string
  capturedAt: string
  snippet: string
}

export interface PublicSearchResult {
  status: 'review' | 'manual'
  sources: PublicSource[]
  observations: string[]
  error?: string
}

export type PublicFetch = (url: string, init?: RequestInit) => Promise<Response>

function excerpt(text: string): string {
  return text.replace(/\s+/g, ' ').trim().slice(0, 700)
}

function usable(text: string): boolean {
  const normalized = excerpt(text)
  if (normalized.length < 40) return false
  return !/access denied|request has been blocked|no results|not found|captcha|verify you are human/i.test(normalized)
}

export async function searchPublicMerchant(
  profile: StoreProfile,
  fetcher: PublicFetch,
): Promise<PublicSearchResult> {
  const query = [profile.alias, profile.city, profile.district, profile.category, '门店 评分 人均'].filter(Boolean).join(' ')
  const searchUrl = `https://www.google.com/search?q=${encodeURIComponent(query)}`
  const readerUrl = `https://r.jina.ai/http://www.google.com/search?q=${encodeURIComponent(query)}`
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), 12000)
  try {
    const response = await fetcher(readerUrl, { signal: controller.signal })
    if (!response.ok) throw new Error(`公共读取失败（HTTP ${response.status}）`)
    const text = await response.text()
    if (!usable(text)) {
      return {
        status: 'manual',
        sources: [],
        observations: ['未找到足够的公开门店信息，请人工补充评分、菜单、价格和典型评价；周报诊断仍可继续。'],
      }
    }
    const rating = text.match(/评分\s*[：:]?\s*([0-5](?:\.\d)?)/)?.[1] ?? text.match(/([0-5]\.\d)\s*分/)?.[1]
    const price = text.match(/人均\s*[¥￥]?\s*(\d+(?:\.\d+)?)/)?.[1]
    return {
      status: 'review',
      sources: [{
        title: `公开搜索：${profile.alias}`,
        url: searchUrl,
        capturedAt: new Date().toISOString(),
        snippet: excerpt(text),
      }],
      observations: [
        `检索到与“${profile.alias}”相关的公开网页摘要，以下内容均为待确认信息，不作为已核实门店事实。`,
        rating ? `摘要出现评分 ${rating}，请确认是否属于该门店。` : '摘要中没有可确认的评分，请人工补充。',
        price ? `摘要出现人均 ${price} 元，请确认采集日期和平台口径。` : '摘要中没有可确认的人均价，请人工补充价格带。',
        '公开信息只用于门店基建初诊；曝光、转化、投放和利润需要商家授权周报。',
      ],
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    return {
      status: 'manual',
      sources: [],
      observations: ['公开检索暂不可用，请人工补充公开信息；不会用店名生成虚构诊断，周报诊断仍可继续。'],
      error: message,
    }
  } finally {
    clearTimeout(timeout)
  }
}
