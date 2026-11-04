import type { WeeklyReport } from './types'

export interface DemoWeek {
  weekStart: string
  netGmv: number
  spend: number
  roi: number
}

const GMV_FACTORS = [0.88, 0.9, 0.91, 0.93, 0.95, 0.96, 0.98, 1]
const SPEND_FACTORS = [0.72, 0.76, 0.79, 0.82, 0.86, 0.9, 0.95, 1]
const ROI_FACTORS = [1.12, 1.1, 1.08, 1.07, 1.05, 1.03, 1.01, 1]

function round(value: number): number {
  return Math.round(value * 100) / 100
}

function shiftWeek(date: string, weeks: number): string {
  const value = new Date(`${date}T00:00:00Z`)
  value.setUTCDate(value.getUTCDate() + weeks * 7)
  return value.toISOString().slice(0, 10)
}

export function buildDemoSeries(report: WeeklyReport): DemoWeek[] {
  if (!report.synthetic) return []
  const spend = report.tools.reduce((sum, tool) => sum + tool.spend, 0)
  const attributedGmv = report.tools.reduce((sum, tool) => sum + tool.attributedGmv, 0)
  const currentRoi = spend > 0 ? attributedGmv / spend : 0
  return GMV_FACTORS.map((gmvFactor, index) => ({
    weekStart: shiftWeek(report.weekStart, index - 7),
    netGmv: Math.round(report.netGmv * gmvFactor),
    spend: Math.round(spend * SPEND_FACTORS[index]),
    roi: round(currentRoi * ROI_FACTORS[index]),
  }))
}
