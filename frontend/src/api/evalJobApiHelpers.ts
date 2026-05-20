import request from '@/request'
import type { EvalJobCreateMeta, EvalJobRuntimeOptions } from '@/types/evalJobCommon'

type BaseResponse<T = unknown> = {
  code: number
  data: T
  message?: string
}

function unwrap<T>(res: { data: BaseResponse<T> }): T {
  const body = res.data
  if (body.code !== 0) {
    throw new Error(body.message || '请求失败')
  }
  return body.data as T
}

function appendCreateMeta(form: FormData, meta?: EvalJobCreateMeta) {
  if (!meta) return
  if (meta.displayName?.trim()) form.append('display_name', meta.displayName.trim())
  if (meta.evalRounds != null) form.append('eval_rounds', String(meta.evalRounds))
  if (meta.judgeModel?.trim()) form.append('judge_model', meta.judgeModel.trim())
}

export async function updateEvalJobDisplayName(
  modulePrefix: string,
  jobId: string,
  displayName: string,
) {
  const res = await request.patch<BaseResponse<null>>(
    `/${modulePrefix}/jobs/${encodeURIComponent(jobId)}/display-name`,
    { displayName },
  )
  return unwrap(res)
}

export async function pauseEvalJob(modulePrefix: string, jobId: string) {
  const res = await request.post<BaseResponse<null>>(
    `/${modulePrefix}/jobs/${encodeURIComponent(jobId)}/pause`,
  )
  return unwrap(res)
}

export async function rerunEvalJob(
  modulePrefix: string,
  jobId: string,
  options?: EvalJobRuntimeOptions,
) {
  const res = await request.post<BaseResponse<null>>(
    `/${modulePrefix}/jobs/${encodeURIComponent(jobId)}/rerun`,
    options ?? {},
  )
  return unwrap(res)
}

export type { EvalJobRuntimeOptions }

export { appendCreateMeta, unwrap }
