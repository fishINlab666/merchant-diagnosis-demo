import { describe, expect, it } from 'vitest'
import { mainCase } from '../src/domain/cases'
import { buildDiagnosis, type Assumptions } from '../src/domain/diagnosis'
import { BOSS_QUESTIONS, buildOfflineBossAnswers, requestBossAnswer, validateBossAnswer } from '../src/domain/bossQuestions'

const assumptions: Assumptions = {
  mode: 'reallocate',
  amount: 400,
  grossMargin: 0.45,
  marginalFactor: 0.8,
  merchantSubsidyDelta: -1000,
  subsidyOrderLossRate: 0.4,
}
const result = buildDiagnosis(mainCase, assumptions)

describe('boss follow-up questions', () => {
  it('answers all four questions from current evidence and assumptions', () => {
    const answers = buildOfflineBossAnswers(mainCase, result, assumptions)

    expect(BOSS_QUESTIONS).toHaveLength(4)
    expect(answers['为什么不直接加预算？']).toContain('点金推广')
    expect(answers['挪了效果变差怎么办？']).toContain('400')
    expect(answers['补贴降了订单会不会掉？']).toContain('40%')
    expect(answers['这个测算靠谱吗？']).toContain('45%')
  })

  it('rejects guarantee language and numbers absent from the evidence', () => {
    expect(validateBossAnswer('保证每月多赚 99999 元', '周报金额 400 元')).toBe(false)
    expect(validateBossAnswer('建议再增加 88 元', '周报金额 400 元')).toBe(false)
    expect(validateBossAnswer('先保留基本盘，小步执行一周后复核。', '周报金额 400 元')).toBe(true)
  })

  it('falls back to the offline answer when AI fails', async () => {
    const response = await requestBossAnswer('为什么不直接加预算？', mainCase, result, assumptions, async () => {
      throw new Error('offline')
    })

    expect(response.source).toBe('offline')
    expect(response.answer).toBe(buildOfflineBossAnswers(mainCase, result, assumptions)['为什么不直接加预算？'])
  })

  it('falls back when AI adds an unsupported promise', async () => {
    const response = await requestBossAnswer('这个测算靠谱吗？', mainCase, result, assumptions, async () => new Response('保证每月多赚 99999 元'))

    expect(response.source).toBe('offline')
  })

  it('never sends real merchant data to the AI route', async () => {
    let called = false
    const response = await requestBossAnswer('这个测算靠谱吗？', { ...mainCase, synthetic: false }, result, assumptions, async () => {
      called = true
      return new Response('这是一句不会使用的回答。')
    })

    expect(called).toBe(false)
    expect(response.source).toBe('offline')
  })
})
