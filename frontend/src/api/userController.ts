import request from '@/request'

type BaseResponse<T = unknown> = {
  code: number
  data: T
  message?: string
}

export type UserVO = {
  id?: string | number
  userAccount?: string
  userName?: string
  userAvatar?: string
  userProfile?: string
  userRole?: string
  createTime?: string
}

export type UserQueryRequest = {
  current?: number
  pageSize?: number
  userAccount?: string
  userName?: string
  userRole?: string
}

export type DeleteRequest = {
  id: string | number
}

export type UserLoginRequest = {
  userAccount: string
  userPassword: string
}

export type UserRegisterRequest = {
  userAccount: string
  userPassword: string
  checkPassword: string
}

export type PageResponse<T> = {
  records: T[]
  total: number
  current: number
  pageSize: number
}

export function userLogout() {
  return request.post<BaseResponse<boolean>>('/user/logout')
}

export function getLoginUser() {
  return request.get<BaseResponse<UserVO>>('/user/get/login')
}

export function userLogin(data: UserLoginRequest) {
  return request.post<BaseResponse<UserVO>>('/user/login', data)
}

export function userRegister(data: UserRegisterRequest) {
  return request.post<BaseResponse<number>>('/user/register', data)
}

export function listUserVoByPage(data: UserQueryRequest) {
  return request.post<BaseResponse<PageResponse<UserVO>>>('/user/list/page/vo', data)
}

export function deleteUser(data: DeleteRequest) {
  return request.post<BaseResponse<boolean>>('/user/delete', data)
}
