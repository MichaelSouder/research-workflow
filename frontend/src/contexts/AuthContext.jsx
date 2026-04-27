import { createContext, useContext, useEffect, useState, useCallback, useRef } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { getAuthMe } from '../api'

const AuthContext = createContext(null)

const AUTH_ME_TIMEOUT_MS = 15000

function isAbortError(e) {
  return (
    e != null &&
    (e.name === 'AbortError' ||
      (typeof DOMException !== 'undefined' && e instanceof DOMException && e.name === 'AbortError'))
  )
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()
  const location = useLocation()
  const skipNextPathRefresh = useRef(true)

  const refresh = useCallback(async () => {
    try {
      const u = await getAuthMe()
      setUser(u)
      return u
    } catch (e) {
      // Do not clear the session on network / proxy failures (e.g. backend stopped while UI stays open).
      // Only explicit 401 is handled inside getAuthMe (returns null); other HTTP errors are rare for /auth/me.
      if (isAbortError(e)) return null
      console.warn('[auth] refresh skipped (backend unreachable or error):', e)
      return null
    }
  }, [])

  useEffect(() => {
    const ac = new AbortController()
    const timeout = setTimeout(() => ac.abort(), AUTH_ME_TIMEOUT_MS)
    /** Strict Mode runs mount → cleanup → mount; without this, the aborted first fetch still runs `finally` and sets loading false while user is still null → instant redirect to /login. */
    let active = true

    ;(async () => {
      try {
        const u = await getAuthMe(ac.signal)
        if (active) setUser(u)
      } catch (e) {
        if (active && !isAbortError(e)) setUser(null)
      } finally {
        clearTimeout(timeout)
        if (active) setLoading(false)
      }
    })()

    return () => {
      active = false
      clearTimeout(timeout)
      ac.abort()
    }
  }, [])

  // After login redirect or server role changes, /auth/me can be stale — refresh when navigating (not duplicate initial fetch).
  useEffect(() => {
    if (loading) return
    if (skipNextPathRefresh.current) {
      skipNextPathRefresh.current = false
      return
    }
    refresh()
  }, [location.pathname, loading, refresh])

  const logout = useCallback(() => {
    setUser(null)
    navigate('/login', { replace: true })
  }, [navigate])

  const value = {
    user,
    loading,
    isSuperuser: Boolean(user?.isSuperuser),
    refresh,
    logout,
    setUser,
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
