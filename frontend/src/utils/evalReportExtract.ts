import type { ContentEvalJob } from '@/api/contentEvalController'
import type { ListenEvalJob } from '@/api/listenEvalController'
import type { OralCombinedJob } from '@/api/oralCombinedEvalController'
import type { UnifiedEvalJob } from '@/api/unifiedEvalController'
import type { EvalReportJobKind } from '@/constants/evalReportDimensions'
import {
  listenDimColumnKey,
  listenDimensionKeys,
  parseListenDimKey,
} from '@/constants/evalReportDimensions'

export type ReportJobRef = {
  kind: EvalReportJobKind
  jobId: string
  displayName?: string
  model?: string
}

export type ReportCellValue = {
  value: number | null
  kind: EvalReportJobKind
  jobId: string
}

export type ReportTableRow = {
  modelName: string
  cells: Record<string, ReportCellValue[]>
}

type MetricRecord = Record<string, number | undefined | null>

function num(v: unknown): number | null {
  if (v == null || v === '') return null
  const n = Number(v)
  return Number.isFinite(n) ? n : null
}

function speechMetricsFromSummary(summary?: UnifiedEvalJob['summary']): MetricRecord {
  const mp = summary?.multipa
  return {
    accuracy: num(mp?.accuracy),
    fluency: num(mp?.fluency),
    naturalness: num(mp?.naturalness),
    apgMosBvcc: num(summary?.apgMosBvccMean),
    apgMosSomos: num(summary?.apgMosSomosMean),
  }
}

function speechMetricsFromComparison(row: MetricRecord): MetricRecord {
  return {
    accuracy: num(row.accuracyMean),
    fluency: num(row.fluencyMean),
    naturalness: num(row.naturalnessMean),
    apgMosBvcc: num(row.apgMosBvccMean),
    apgMosSomos: num(row.apgMosSomosMean),
  }
}

function contentMetrics(summary?: MetricRecord): MetricRecord {
  return {
    grammarScore: num(summary?.grammarMean),
    themeFocusScore: num(summary?.themeFocusMean),
    answerClarityScore: num(summary?.answerClarityMean),
    compositeScore: num(summary?.compositeMean),
  }
}

function combinedMetrics(summary?: OralCombinedJob['summary']): MetricRecord {
  return {
    accuracy: num(summary?.accuracyMean),
    fluency: num(summary?.fluencyMean),
    naturalness: num(summary?.naturalnessMean),
    apgMosBvcc: num(summary?.apgMosBvccMean),
    apgMosSomos: num(summary?.apgMosSomosMean),
    grammarScore: num(summary?.grammarMean),
    themeFocusScore: num(summary?.themeFocusMean),
    answerClarityScore: num(summary?.answerClarityMean),
    compositeScore: num(summary?.compositeMean),
  }
}

function listenMetrics(job: ListenEvalJob): MetricRecord {
  const out: MetricRecord = {
    overallAccuracy: num(job.summary?.overall?.accuracy),
  }
  const dims = job.summary?.byDimension
  if (dims) {
    for (const [name, v] of Object.entries(dims)) {
      out[listenDimColumnKey(name)] = num(v.accuracy)
    }
  }
  return out
}

export function extractListenDynamicColumns(jobs: ListenEvalJob[]): string[] {
  const keys = new Set<string>()
  for (const job of jobs) {
    for (const k of listenDimensionKeys(job.summary)) {
      keys.add(listenDimColumnKey(k))
    }
  }
  return [...keys].sort()
}

export function modelEntriesFromSpeechJob(
  job: UnifiedEvalJob,
): Array<{ modelName: string; metrics: MetricRecord }> {
  if (job.jobType === 'multi_model' && job.comparison?.byModel?.length) {
    return job.comparison.byModel.map((row) => ({
      modelName: row.modelName,
      metrics: speechMetricsFromComparison(row as unknown as MetricRecord),
    }))
  }
  const modelName = job.model || 'default'
  return [{ modelName, metrics: speechMetricsFromSummary(job.summary) }]
}

export function modelEntriesFromContentJob(
  job: ContentEvalJob,
): Array<{ modelName: string; metrics: MetricRecord }> {
  if (job.jobType === 'multi_model' && job.comparison?.byModel?.length) {
    return job.comparison.byModel.map((row) => ({
      modelName: row.modelName,
      metrics: contentMetrics(row as unknown as MetricRecord),
    }))
  }
  const modelName = (job as { model?: string }).model || 'default'
  return [{ modelName, metrics: contentMetrics(job.summary as unknown as MetricRecord) }]
}

export function modelEntriesFromCombinedJob(
  job: OralCombinedJob,
): Array<{ modelName: string; metrics: MetricRecord }> {
  const modelName = job.model || 'default'
  return [{ modelName, metrics: combinedMetrics(job.summary) }]
}

export function modelEntriesFromListenJob(
  job: ListenEvalJob,
): Array<{ modelName: string; metrics: MetricRecord }> {
  const modelName = job.model || 'default'
  return [{ modelName, metrics: listenMetrics(job) }]
}

export function buildReportRows(
  selected: Array<{
    kind: EvalReportJobKind
    jobId: string
    job: UnifiedEvalJob | ContentEvalJob | ListenEvalJob | OralCombinedJob
  }>,
  modelFilter?: string,
): ReportTableRow[] {
  const rowMap = new Map<string, ReportTableRow>()

  for (const item of selected) {
    let entries: Array<{ modelName: string; metrics: MetricRecord }> = []
    if (item.kind === 'speech') {
      entries = modelEntriesFromSpeechJob(item.job as UnifiedEvalJob)
    } else if (item.kind === 'content') {
      entries = modelEntriesFromContentJob(item.job as ContentEvalJob)
    } else if (item.kind === 'listen') {
      entries = modelEntriesFromListenJob(item.job as ListenEvalJob)
    } else if (item.kind === 'combined') {
      entries = modelEntriesFromCombinedJob(item.job as OralCombinedJob)
    }

    for (const { modelName, metrics } of entries) {
      if (modelFilter && modelName !== modelFilter) continue
      let row = rowMap.get(modelName)
      if (!row) {
        row = { modelName, cells: {} }
        rowMap.set(modelName, row)
      }
      for (const [key, value] of Object.entries(metrics)) {
        if (value == null) continue
        if (!row.cells[key]) row.cells[key] = []
        row.cells[key].push({ value, kind: item.kind, jobId: item.jobId })
      }
    }
  }

  return [...rowMap.values()].sort((a, b) => a.modelName.localeCompare(b.modelName))
}

export function formatCellValues(cells?: ReportCellValue[]): string {
  if (!cells?.length) return '—'
  if (cells.length === 1) return formatScore(cells[0]?.value ?? null)
  return cells.map((c) => `${formatScore(c.value)}`).join(' / ')
}

export function sortValueForRow(row: ReportTableRow, colKey: string): number | null {
  const cells = row.cells[colKey]
  if (!cells?.length) return null
  const vals = cells.map((c) => c.value).filter((v): v is number => v != null)
  if (!vals.length) return null
  return vals.reduce((a, b) => a + b, 0) / vals.length
}

export function formatScore(v: number | null | undefined) {
  if (v == null) return '—'
  if (Math.abs(v) <= 1 && v !== 0 && !Number.isInteger(v)) {
    return `${(v * 100).toFixed(1)}%`
  }
  return Number(v).toFixed(2)
}

export function columnLabel(key: string, staticLabels: Record<string, string>) {
  if (staticLabels[key]) return staticLabels[key]
  const listenName = parseListenDimKey(key)
  if (listenName) return `听力·${listenName}`
  return key
}

export function staticDimensionLabels(): Record<string, string> {
  return {
    accuracy: '发音准确度',
    fluency: '流利度',
    naturalness: '自然度',
    apgMosBvcc: 'APG MOS BVCC',
    apgMosSomos: 'APG MOS SOMOS',
    grammarScore: '语法准确表达',
    themeFocusScore: '主题聚焦拓展',
    answerClarityScore: '回复简洁清晰',
    compositeScore: '内容综合分',
    overallAccuracy: '听力总准确率',
  }
}
