/** Shared fields returned on eval job VOs (API error, meta, token/cost). */

export type EvalJobApiErrorFields = {
  apiErrorCount?: number
  lastApiError?: string
  lastApiErrorAt?: string
}

export type EvalJobMetaFields = {
  displayName?: string
  evalRounds?: number
  judgeModel?: string
}

export type EvalJobTokenFields = {
  totalInputTokens?: number
  totalOutputTokens?: number
  estimatedCostUsd?: number | null
}

export type EvalJobControlFields = {
  pausedAt?: string
  canPause?: boolean
  canRerun?: boolean
  canResume?: boolean
}

export type EvalJobCommonFields = EvalJobApiErrorFields &
  EvalJobMetaFields &
  EvalJobTokenFields &
  EvalJobControlFields

export type EvalJobCreateMeta = {
  displayName?: string
  evalRounds?: number
  judgeModel?: string
}

export type EvalJobRuntimeOptions = {
  workers?: number
  requestInterval?: number
  skipCompleted?: boolean
}
