import { useState } from 'react'
import { BOSS_QUESTIONS, buildOfflineBossAnswers, requestBossAnswer, type BossQuestion } from '../domain/bossQuestions'
import type { Assumptions } from '../domain/diagnosis'
import type { DiagnosisResult, WeeklyReport } from '../domain/types'

interface BossQuestionsProps {
  report: WeeklyReport
  result: DiagnosisResult
  assumptions: Assumptions
}

export function BossQuestions({ report, result, assumptions }: BossQuestionsProps) {
  const [selected, setSelected] = useState<BossQuestion | null>(null)
  const [answer, setAnswer] = useState('')
  const [source, setSource] = useState<'offline' | 'ai' | null>(null)
  const [loading, setLoading] = useState(false)

  async function ask(question: BossQuestion) {
    if (loading) return
    setSelected(question)
    if (!report.synthetic) {
      setAnswer(buildOfflineBossAnswers(report, result, assumptions)[question])
      setSource('offline')
      return
    }
    setLoading(true)
    setAnswer('')
    const response = await requestBossAnswer(question, report, result, assumptions, fetch)
    setAnswer(response.answer)
    setSource(response.source)
    setLoading(false)
  }

  return (
    <section className="boss-questions" aria-labelledby="boss-questions-title">
      <div className="section-heading">
        <div><h2 id="boss-questions-title">老板会追问</h2><p>点一个问题，用当前证据接住；真实周报只在本机生成回答。</p></div>
        {source && <span className={`status-badge ${source === 'ai' ? 'info' : 'neutral'} boss-answer-source`}>{source === 'ai' ? 'AI 实时回答' : '离线预置回答'}</span>}
      </div>
      <div className="boss-question-buttons">
        {BOSS_QUESTIONS.map((question) => <button type="button" key={question} aria-pressed={selected === question} disabled={loading} onClick={() => void ask(question)}>{question}</button>)}
      </div>
      <div className="boss-answer" aria-live="polite">
        {loading ? '正在核对当前证据…' : answer || '选择一个追问，查看回答。'}
      </div>
    </section>
  )
}
