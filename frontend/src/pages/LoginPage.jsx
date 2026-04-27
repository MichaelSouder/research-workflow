import { useEffect, useState } from 'react'
import { APP_NAME } from '../branding'
import { getAuthBase, getDevBypassStatus } from '../api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'

function isDevEnvironment() {
  const authBase = getAuthBase()
  if (typeof import.meta !== 'undefined' && import.meta.env?.DEV === true) return true
  if (typeof window === 'undefined') return false
  const host = window.location.hostname
  if (host === 'localhost' || host === '127.0.0.1') return true
  return !!(authBase && (authBase.includes('localhost') || authBase.includes('127.0.0.1')))
}

export default function LoginPage() {
  const isDev = isDevEnvironment()
  /** 'idle' until first check; then 'on' | 'off' | 'unreachable' */
  const [bypassState, setBypassState] = useState('idle')
  const [pwEmail, setPwEmail] = useState('')
  const [pwPassword, setPwPassword] = useState('')
  const [pwError, setPwError] = useState('')
  const [pwLoading, setPwLoading] = useState(false)
  const authBase = getAuthBase()
  const loginUrl = `${authBase}/auth/login`
  const devLoginUrl = `${authBase}/auth/dev-login`

  const submitPasswordLogin = async (e) => {
    e.preventDefault()
    setPwError('')
    setPwLoading(true)
    try {
      const r = await fetch(`${authBase}/auth/password-login`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: pwEmail.trim(), password: pwPassword }),
      })
      const data = await r.json().catch(() => ({}))
      if (!r.ok) {
        const d = data?.detail
        throw new Error(typeof d === 'string' ? d : r.statusText || 'Sign-in failed')
      }
      window.location.href = data.redirect || '/'
    } catch (err) {
      setPwError(err.message || 'Sign-in failed')
    } finally {
      setPwLoading(false)
    }
  }

  useEffect(() => {
    if (!isDev) return
    let cancelled = false
    setBypassState('idle')
    getDevBypassStatus().then((s) => {
      if (cancelled) return
      if (!s.fetchOk) {
        setBypassState('unreachable')
        return
      }
      setBypassState(s.available ? 'on' : 'off')
    })
    return () => {
      cancelled = true
    }
  }, [isDev])

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <Card className="w-full max-w-sm border-border">
        <CardHeader>
          <CardTitle className="text-center">{APP_NAME}</CardTitle>
          <CardDescription className="text-center">
            Sign in to run the pipeline and manage settings.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          <Button asChild className="w-full" size="lg">
            <a href={loginUrl} className="inline-flex items-center justify-center gap-2">
              <svg className="size-5" viewBox="0 0 24 24">
                <path
                  fill="#4285F4"
                  d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                />
                <path
                  fill="#34A853"
                  d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                />
                <path
                  fill="#FBBC05"
                  d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
                />
                <path
                  fill="#EA4335"
                  d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
                />
              </svg>
              Sign in with Google
            </a>
          </Button>
          {isDev ? (
            <div className="bg-muted/40 space-y-2 rounded-lg border border-border p-3">
              <p className="text-muted-foreground text-center text-xs font-medium uppercase tracking-wide">
                Development
              </p>
              {bypassState === 'idle' ? (
                <p className="text-muted-foreground text-center text-xs">Checking dev bypass…</p>
              ) : bypassState === 'on' ? (
                <Button asChild variant="outline" className="w-full" size="lg">
                  <a href={devLoginUrl} className="text-foreground">
                    Bypass Login (Dev Session)
                  </a>
                </Button>
              ) : bypassState === 'unreachable' ? (
                <p className="text-muted-foreground text-center text-xs leading-snug">
                  Could not reach the API at{' '}
                  <code className="rounded bg-muted px-1 py-0.5 font-mono text-[0.65rem]">
                    {authBase || '(same origin → Vite proxies to port 48721)'}
                  </code>
                  . Start the backend from the project root on{' '}
                  <code className="rounded bg-muted px-1 font-mono text-[0.65rem]">BACKEND_PORT</code> (default{' '}
                  <code className="font-mono text-[0.65rem]">48721</code>), e.g.{' '}
                  <code className="rounded bg-muted px-1 font-mono text-[0.65rem]">uv run python run_backend.py</code>
                  , keep <code className="font-mono text-[0.65rem]">npm run dev</code> running for the UI, then reload
                  this page.
                </p>
              ) : (
                <p className="text-muted-foreground text-center text-xs leading-snug">
                  Bypass is off on the server. Add{' '}
                  <code className="rounded bg-muted px-1 py-0.5 font-mono text-[0.7rem]">BYPASS_AUTH_DEV=1</code> to
                  the project <code className="rounded bg-muted px-1 py-0.5 font-mono text-[0.7rem]">.env</code>, then
                  restart the backend (required when <code className="font-mono text-[0.65rem]">GOOGLE_CLIENT_ID</code>{' '}
                  is set).
                </p>
              )}
            </div>
          ) : null}
          <div className="relative py-2">
            <div className="absolute inset-0 flex items-center">
              <span className="w-full border-t border-border" />
            </div>
            <div className="relative flex justify-center text-xs uppercase">
              <span className="bg-card text-muted-foreground px-2">Or email</span>
            </div>
          </div>
          <form className="flex flex-col gap-3" onSubmit={submitPasswordLogin}>
            <div className="grid gap-2">
              <Label htmlFor="login-email">Email</Label>
              <Input
                id="login-email"
                type="email"
                autoComplete="username"
                value={pwEmail}
                onChange={(e) => setPwEmail(e.target.value)}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="login-password">Password</Label>
              <Input
                id="login-password"
                type="password"
                autoComplete="current-password"
                value={pwPassword}
                onChange={(e) => setPwPassword(e.target.value)}
              />
            </div>
            {pwError ? <p className="text-destructive text-sm">{pwError}</p> : null}
            <Button type="submit" variant="secondary" className="w-full" disabled={pwLoading}>
              {pwLoading ? 'Signing in…' : 'Sign in with password'}
            </Button>
          </form>
        </CardContent>
        <CardFooter className="flex justify-center text-muted-foreground text-xs">
          {isDev
            ? 'Bypass login uses a local session only — never enable in production.'
            : 'You will be redirected to Google to sign in securely.'}
        </CardFooter>
      </Card>
    </div>
  )
}
