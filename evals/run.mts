import { writeFile } from 'node:fs/promises'
import { resolve } from 'node:path'
import { evalCases } from './cases.mts'

const results = []
for (const testCase of evalCases) {
  try {
    const result = await testCase.check()
    results.push({ id: testCase.id, group: testCase.group, description: testCase.description, ...result })
  } catch (error) {
    results.push({
      id: testCase.id,
      group: testCase.group,
      description: testCase.description,
      pass: false,
      evidence: error instanceof Error ? error.message : String(error),
    })
  }
}
const passed = results.filter((result) => result.pass).length
const failed = results.length - passed
const report = {
  suite: 'merchant-diagnosis-business-evals',
  total: results.length,
  passed,
  failed,
  passRate: Number((passed / results.length * 100).toFixed(1)),
  results,
}
const target = resolve(import.meta.dirname, 'results.json')
await writeFile(target, `${JSON.stringify(report, null, 2)}\n`)
for (const result of results) {
  console.log(`${result.pass ? 'PASS' : 'FAIL'} ${result.id} ${result.description}`)
  if (!result.pass) console.log(`  ${result.evidence}`)
}
console.log(`\nEval result: ${passed}/${results.length} passed (${report.passRate}%)`)
console.log(`Results: ${target}`)
if (failed > 0) process.exitCode = 1
