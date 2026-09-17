import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { api, login as apiLogin, tokens } from './lib/api'
import type { Vendor } from './types'

type AuthValue = { vendor: Vendor | null; ready: boolean; login: (u: string, p: string) => Promise<void>; logout: () => Promise<void> }
const AuthContext = createContext<AuthValue | null>(null)
export function AuthProvider({ children }: { children: ReactNode }) {
  const [vendor, setVendor] = useState<Vendor | null>(null); const [ready, setReady] = useState(false)
  useEffect(() => { tokens.restore().then(({ access, refresh }) => access || refresh ? api<Vendor>('/me').then(setVendor).catch(() => tokens.clear()) : undefined).finally(() => setReady(true)) }, [])
  const value = useMemo(() => ({ vendor, ready, login: async (u: string, p: string) => setVendor(await apiLogin(u, p)), logout: async () => { await tokens.clear(); setVendor(null) } }), [vendor, ready])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
export const useAuth = () => { const value = useContext(AuthContext); if (!value) throw new Error('AuthProvider missing'); return value }
