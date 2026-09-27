import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { api, tokenStore } from './api'
import type { StaffProfile } from './types'

interface AuthContextValue {
  staff: StaffProfile | null
  loading: boolean
  signIn: (email: string, password: string) => Promise<void>
  signOut: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [staff, setStaff] = useState<StaffProfile | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let mounted = true
    const token = tokenStore.get()
    const expireSession = () => {
      tokenStore.clear()
      if (mounted) {
        setStaff(null)
        setLoading(false)
      }
    }
    window.addEventListener('admitcrew:session-expired', expireSession)

    if (!token) {
      setLoading(false)
    } else {
      api.auth.me()
        .then(({ staff: profile }) => {
          if (mounted) setStaff(profile)
        })
        .catch(() => {
          if (mounted) setStaff(null)
        })
        .finally(() => {
          if (mounted) setLoading(false)
        })
    }

    return () => {
      mounted = false
      window.removeEventListener('admitcrew:session-expired', expireSession)
    }
  }, [])

  const value = useMemo<AuthContextValue>(() => ({
    staff,
    loading,
    async signIn(email, password) {
      const response = await api.auth.login(email, password)
      tokenStore.set(response.access_token)
      setStaff(response.staff)
    },
    signOut() {
      tokenStore.clear()
      setStaff(null)
    },
  }), [staff, loading])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const value = useContext(AuthContext)
  if (!value) throw new Error('useAuth must be used within AuthProvider.')
  return value
}
