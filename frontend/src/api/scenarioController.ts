import request from '@/request'

type BaseResponse<T = unknown> = {
  code: number
  data: T
  message?: string
}

export type ScenarioVO = {
  id: string
  userId?: number
  name: string
  description?: string
  sourceType: 'system' | 'custom'
  category?: string
  itemCount: number
  createTime?: string
}

export type ScenarioItemVO = {
  id: string
  scenarioId: string
  prompt: string
  expectedAnswer: string
  category?: string
  sortOrder: number
}

export function listScenarios() {
  return request.get<BaseResponse<ScenarioVO[]>>('/scenario/list')
}

export function getScenario(id: string, current = 1, pageSize = 50) {
  return request.get<BaseResponse<ScenarioVO & { items: ScenarioItemVO[]; total: number }>>(
    `/scenario/${id}`,
    { params: { current, pageSize } },
  )
}

export function addScenario(data: { name: string; description?: string; category?: string }) {
  return request.post<BaseResponse<string>>('/scenario/add', data)
}

export function updateScenario(
  id: string,
  data: { name?: string; description?: string; category?: string },
) {
  return request.put<BaseResponse<boolean>>(`/scenario/${id}`, data)
}

export function deleteScenario(id: string) {
  return request.delete<BaseResponse<boolean>>(`/scenario/${id}`)
}

export function importScenarioItems(
  id: string,
  items: {
    prompt: string
    expectedAnswer: string
    modelOutput?: string
    category?: string
    audioFileName?: string
    audioData?: string
    audioFormat?: string
    inputType?: string
  }[],
) {
  return request.post<BaseResponse<number>>(`/scenario/${id}/import`, { items })
}

export function listScenarioItems(id: string, current = 1, pageSize = 20) {
  return request.get<BaseResponse<{ records: ScenarioItemVO[]; total: number }>>(
    `/scenario/${id}/items`,
    { params: { current, pageSize } },
  )
}

export function updateScenarioItem(
  itemId: string,
  data: Partial<{ prompt: string; expectedAnswer: string; category: string; sortOrder: number }>,
) {
  return request.put<BaseResponse<boolean>>(`/scenario/item/${itemId}`, data)
}

export function deleteScenarioItem(itemId: string) {
  return request.delete<BaseResponse<boolean>>(`/scenario/item/${itemId}`)
}
