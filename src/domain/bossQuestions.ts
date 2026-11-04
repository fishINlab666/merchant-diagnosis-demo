import type { Assumptions } from './diagnosis'
import type { PublicFetch } from './publicSearch'
import type { DiagnosisResult, WeeklyReport } from './types'

export const BOSS_QUESTIONS = [
  '为什么不直接加预算？',
  '挪了效果变差怎么办？',
  '补贴降了订单会不会掉？',
  '这个测算靠谱吗？',
] as const

export type BossQuestion = typeof BOSS_QUESTIONS[number]
export type BossAnswer = { answer: string; source: 'offline' | 'ai' }

export function buildOfflineBossAnswers(
  report: WeeklyReport,
  result: DiagnosisResult,
  assumptions: Assumptions,
): Record<BossQuestion, string> {
  const sorted = [...report.tools].sort((a, b) => a.roi - b.roi)
  const source = sorted[0]
  const target = sorted.at(-1)
  const recommendation = result.recommendation
  const calculation = result.calculation
  const subsidyLossRate = Math.round((assumptions.subsidyOrderLossRate ?? 0.4) * 100)
  return {
    '为什么不直接加预算？': source && target
      ? `${source.toolName}当前 ROI ${source.roi}，同口径${target.toolName} ROI ${target.roi}。先修正预算结构，再用实际结果决定是否追加，避免新增钱继续进入低效环节。`
      : '当前投放口径或数据完整度还不足以比较效率。先统一周报口径，再决定是否追加。',
    '挪了效果变差怎么办？': recommendation
      ? `本次只调整 ${recommendation.amount} 元并先试一周，保留原方案作对照。目标工具 ROI 或毛利低于基线就回退，不做全量切换。`
      : '当前不建议直接挪移。先补齐同口径数据；后续也只能小步测试并保留原方案作对照。',
    '补贴降了订单会不会掉？': assumptions.merchantSubsidyDelta < 0
      ? `当前假设商家补贴减少 ${Math.abs(assumptions.merchantSubsidyDelta)} 元，已按 ${subsidyLossRate}% 折算 GMV 流失并扣除毛利影响。下周要同时看订单和毛利，超出停止条件就暂停。`
      : '当前方案的商家补贴变化为 0，因此没有额外扣除补贴收紧造成的订单流失。如果现场降低补贴，工具会按设定的流失折算同步重算。',
    '这个测算靠谱吗？': calculation
      ? `计算使用当前周报、毛利率 ${(assumptions.grossMargin * 100).toFixed(0)}% 和边际 ROI 折算 ${(assumptions.marginalFactor * 100).toFixed(0)}%，净 GMV 变化 ${calculation.deltaGmv} 元、毛利变化 ${calculation.deltaGrossProfit} 元都能复算。它用于选择一周测试方案，不是收益承诺。`
      : '当前没有收益测算，因为归因口径或风险门槛尚未通过。先补数据，不输出看似精确的预测。',
  }
}

export function validateBossAnswer(answer: string, evidence: string): boolean {
  const normalized = answer.trim()
  if (normalized.length < 10 || normalized.length > 260) return false
  if (/保证|必然|稳赚|确定增加|承诺收益/.test(normalized)) return false
  const numbers = normalized.match(/\d+(?:\.\d+)?/g) ?? []
  return numbers.every((number) => evidence.includes(number))
}

function responseText(raw: string): string {
  try {
    const payload = JSON.parse(raw) as { answer?: string; choices?: Array<{ message?: { content?: string } }> }
    return (payload.answer ?? payload.choices?.[0]?.message?.content ?? raw).trim()
  } catch {
    return raw.trim()
  }
}

export async function requestBossAnswer(
  question: BossQuestion,
  report: WeeklyReport,
  result: DiagnosisResult,
  assumptions: Assumptions,
  fetcher: PublicFetch,
): Promise<BossAnswer> {
  const offline = buildOfflineBossAnswers(report, result, assumptions)[question]
  if (!report.synthetic) return { answer: offline, source: 'offline' }
  const evidence = JSON.stringify({ report, result, assumptions })
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), 6000)
  try {
    const response = await fetcher('https://text.pollinations.ai/', {
      method: 'POST',
      signal: controller.signal,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model: 'openai',
        messages: [
          { role: 'system', content: '你是外卖经营复盘助手。只能用给定事实回答，三句大白话，120字内；不得新增数字，不得承诺或保证收益。' },
          { role: 'user', content: `问题：${question}\n离线参考答案：${offline}\n合成演示证据：${evidence.slice(0, 5000)}` },
        ],
      }),
    })
    if (!response.ok) throw new Error(`AI HTTP ${response.status}`)
    const answer = responseText(await response.text())
    if (!validateBossAnswer(answer, evidence)) return { answer: offline, source: 'offline' }
    return { answer, source: 'ai' }
  } catch {
    return { answer: offline, source: 'offline' }
  } finally {
    clearTimeout(timeout)
  }
}
