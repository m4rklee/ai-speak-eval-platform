import request from '@/request'

type BaseResponse<T = unknown> = {
  code: number
  data: T
  message?: string
}

export type RatingRequest = {
  conversationId: string
  messageIndex: number
  ratingType: 'model_better' | 'tie' | 'both_bad'
  winnerModel?: string
  loserModel?: string
}

export function addRating(data: RatingRequest) {
  return request.post<BaseResponse<boolean>>('/rating/add', data)
}
