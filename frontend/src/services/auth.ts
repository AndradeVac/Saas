import { api, tokenStorage } from './api'

export type LoginPayload = { username: string; password: string }

export async function login(payload: LoginPayload) {
  const form = new URLSearchParams()
  form.set('username', payload.username)
  form.set('password', payload.password)
  const { data } = await api.post<{ access_token: string }>('/auth/login', form, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  })
  tokenStorage.set(data.access_token)
}

export const logout = () => tokenStorage.clear()

export async function changePassword(current_password: string, new_password: string) {
  await api.post('/auth/password', { current_password, new_password })
}
