export type EvalReportJobKind = 'speech' | 'content' | 'listen' | 'combined'

export type EvalReportDimensionDef = {
  key: string
  label: string
  kinds: EvalReportJobKind[]
}

export const EVAL_REPORT_DIMENSIONS: EvalReportDimensionDef[] = [
  { key: 'accuracy', label: '发音准确度', kinds: ['speech', 'combined'] },
  { key: 'fluency', label: '流利度', kinds: ['speech', 'combined'] },
  { key: 'naturalness', label: '自然度', kinds: ['speech', 'combined'] },
  { key: 'apgMosBvcc', label: 'APG MOS BVCC', kinds: ['speech', 'combined'] },
  { key: 'apgMosSomos', label: 'APG MOS SOMOS', kinds: ['speech', 'combined'] },
  { key: 'grammarScore', label: '语法准确表达', kinds: ['content', 'combined'] },
  { key: 'themeFocusScore', label: '主题聚焦拓展', kinds: ['content', 'combined'] },
  { key: 'answerClarityScore', label: '回复简洁清晰', kinds: ['content', 'combined'] },
  { key: 'compositeScore', label: '内容综合分', kinds: ['content', 'combined'] },
  { key: 'overallAccuracy', label: '听力总准确率', kinds: ['listen'] },
]

export const LISTEN_DIMENSION_PREFIX = 'listen:'

export function dimensionsForKinds(kinds: Set<EvalReportJobKind>): EvalReportDimensionDef[] {
  return EVAL_REPORT_DIMENSIONS.filter((d) => d.kinds.some((k) => kinds.has(k)))
}

export function kindLabel(kind: EvalReportJobKind | 'oral_gen' | 'listening') {
  const map: Record<string, string> = {
    speech: '语音',
    content: '内容',
    listen: '听力',
    listening: '听力',
    combined: '综合',
    oral_gen: '回复生成',
  }
  return map[kind] || kind
}

export function kindTagColor(kind: EvalReportJobKind | 'oral_gen' | 'listening') {
  if (kind === 'oral_gen') return 'geekblue'
  if (kind === 'speech') return 'blue'
  if (kind === 'content' || kind === 'listening' || kind === 'listen') return 'purple'
  return 'cyan'
}

/** Extract listen dynamic dimension keys from job summary.byDimension */
export function listenDimensionKeys(summary?: {
  byDimension?: Record<string, { accuracy?: number }>
}): string[] {
  if (!summary?.byDimension) return []
  return Object.keys(summary.byDimension).sort()
}

export function listenDimensionLabel(name: string) {
  return `听力·${name}`
}

export function dimensionColumnKey(key: string) {
  return key.startsWith(LISTEN_DIMENSION_PREFIX) ? key : key
}

export function listenDimColumnKey(name: string) {
  return `${LISTEN_DIMENSION_PREFIX}${name}`
}

export function parseListenDimKey(colKey: string): string | null {
  if (!colKey.startsWith(LISTEN_DIMENSION_PREFIX)) return null
  return colKey.slice(LISTEN_DIMENSION_PREFIX.length)
}
