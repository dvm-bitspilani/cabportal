import { SecureStorage } from '@aparajita/capacitor-secure-storage'
import type { Vendor } from '../types'

const base = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/vendor/v1').replace(/\/$/, '')
const ACCESS = 'ridezy_access'
const REFRESH = 'ridezy_refresh'
let accessToken: string | null = null
let refreshPromise: Promise<string> | null = null

const getStored = async (key: string) => (await SecureStorage.get(key)) as string | null
export const tokens = {
  async restore() { accessToken = await getStored(ACCESS); return { access: accessToken, refresh: await getStored(REFRESH) } },
  async set(access: string, refresh?: string) { accessToken = access; await SecureStorage.set(ACCESS, access); if (refresh) await SecureStorage.set(REFRESH, refresh) },
  async clear() { accessToken = null; await Promise.all([SecureStorage.remove(ACCESS), SecureStorage.remove(REFRESH)]) }
}

export class ApiError extends Error {
  constructor(public status: number, public fields: Record<string, string[]>, message = 'Request failed') { super(message) }
}
const normalize = async (res: Response) => {
  const body = await res.json().catch(() => ({}))
  const fields: Record<string, string[]> = {}
  Object.entries(body).forEach(([key, value]) => { fields[key] = Array.isArray(value) ? value.map(String) : [String(value)] })
  return new ApiError(res.status, fields, fields.detail?.[0] || fields.non_field_errors?.[0] || 'Request failed')
}
const refreshAccess = async () => {
  if (!refreshPromise) refreshPromise = (async () => {
    const refresh = await getStored(REFRESH)
    if (!refresh) throw new ApiError(401, {}, 'Session expired')
    const res = await fetch(`${base}/auth/refresh`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ refresh }) })
    if (!res.ok) { await tokens.clear(); throw await normalize(res) }
    const data = await res.json(); await tokens.set(data.access, data.refresh); return data.access as string
  })().finally(() => { refreshPromise = null })
  return refreshPromise
}

export async function api<T>(path: string, init: RequestInit = {}, retry = true): Promise<T> {
  const headers = new Headers(init.headers)
  headers.set('Accept', 'application/json')
  if (init.body) headers.set('Content-Type', 'application/json')
  if (accessToken) headers.set('Authorization', `Bearer ${accessToken}`)
  let res: Response
  try { res = await fetch(`${base}${path}`, { ...init, headers }) }
  catch { throw new ApiError(0, {}, 'You appear to be offline. Check your connection and retry.') }
  if (res.status === 401 && retry && !path.startsWith('/auth/')) { await refreshAccess(); return api<T>(path, init, false) }
  if (!res.ok) throw await normalize(res)
  return res.status === 204 ? undefined as T : res.json()
}
export async function login(username: string, password: string) {
  const data = await api<{ access: string; refresh: string; vendor: Vendor }>('/auth/login', { method: 'POST', body: JSON.stringify({ username, password }) }, false)
  await tokens.set(data.access, data.refresh); return data.vendor
}
