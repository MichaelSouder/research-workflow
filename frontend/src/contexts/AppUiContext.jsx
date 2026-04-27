import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'

const STORAGE_THEME = 'qa-theme'
const STORAGE_SIDEBAR = 'qa-sidebar-collapsed'

const AppUiContext = createContext(null)

export function AppUiProvider({ children }) {
  const [theme, setThemeState] = useState(() => {
    if (typeof window === 'undefined') return 'dark'
    return window.localStorage.getItem(STORAGE_THEME) || 'dark'
  })
  const [sidebarCollapsed, setSidebarCollapsedState] = useState(() => {
    if (typeof window === 'undefined') return false
    return window.localStorage.getItem(STORAGE_SIDEBAR) === '1'
  })

  useEffect(() => {
    const root = document.documentElement
    root.classList.toggle('dark', theme === 'dark')
    window.localStorage.setItem(STORAGE_THEME, theme)
  }, [theme])

  useEffect(() => {
    window.localStorage.setItem(STORAGE_SIDEBAR, sidebarCollapsed ? '1' : '0')
  }, [sidebarCollapsed])

  const setTheme = useCallback((t) => {
    setThemeState(t === 'light' ? 'light' : 'dark')
  }, [])

  const toggleTheme = useCallback(() => {
    setThemeState((prev) => (prev === 'dark' ? 'light' : 'dark'))
  }, [])

  const toggleSidebar = useCallback(() => {
    setSidebarCollapsedState((c) => !c)
  }, [])

  const setSidebarCollapsed = useCallback((collapsed) => {
    setSidebarCollapsedState(Boolean(collapsed))
  }, [])

  const value = useMemo(
    () => ({
      theme,
      setTheme,
      toggleTheme,
      sidebarCollapsed,
      setSidebarCollapsed,
      toggleSidebar,
    }),
    [theme, setTheme, toggleTheme, sidebarCollapsed, setSidebarCollapsed, toggleSidebar]
  )

  return <AppUiContext.Provider value={value}>{children}</AppUiContext.Provider>
}

export function useAppUi() {
  const ctx = useContext(AppUiContext)
  if (!ctx) throw new Error('useAppUi must be used within AppUiProvider')
  return ctx
}
