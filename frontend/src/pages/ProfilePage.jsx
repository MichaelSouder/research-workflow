import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { getStudies } from '../api'
import { useAuth } from '../contexts/AuthContext'
import { formatStudyRoleLabel } from '../lib/roles'
import Breadcrumb from '../components/Breadcrumb'
import PageHeader from '../components/PageHeader'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'

export default function ProfilePage() {
  const { user, loading, isSuperuser } = useAuth()
  const [studies, setStudies] = useState([])

  useEffect(() => {
    if (!user) return
    let cancelled = false
    getStudies()
      .then((data) => {
        if (!cancelled) setStudies(data.studies || [])
      })
      .catch(() => {
        if (!cancelled) setStudies([])
      })
    return () => { cancelled = true }
  }, [user])

  if (loading || !user) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <p className="text-muted-foreground">{loading ? 'Loading…' : 'Redirecting…'}</p>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-background text-foreground">
      <main className="mx-auto max-w-6xl space-y-6 p-4 md:p-6">
        <Breadcrumb
          items={[
            { label: 'Dashboard', to: '/studies' },
            { label: 'Profile Settings' },
          ]}
          className="mb-2"
        />
        <PageHeader
          title="Profile Settings"
          description="Your account is managed by your sign-in provider. Below is what we store for this app."
        />
        <section aria-labelledby="account-heading" className="max-w-2xl space-y-6">
          <Card>
            <CardHeader>
              <CardTitle id="account-heading">Account</CardTitle>
              <CardDescription>
                Name and email are updated when you sign in with Google (or your configured provider).
              </CardDescription>
            </CardHeader>
            <CardContent>
              <dl className="grid gap-4 sm:grid-cols-1">
                <div>
                  <dt className="text-sm font-medium text-muted-foreground">Name</dt>
                  <dd className="mt-1 text-sm text-foreground">{user.name || '—'}</dd>
                </div>
                <div>
                  <dt className="text-sm font-medium text-muted-foreground">Email</dt>
                  <dd className="mt-1 text-sm text-foreground">{user.email || '—'}</dd>
                </div>
                {isSuperuser ? (
                  <div>
                    <dt className="text-sm font-medium text-muted-foreground">Platform Access</dt>
                    <dd className="mt-1">
                      <Badge>Superuser</Badge>
                    </dd>
                  </div>
                ) : null}
                {user.id ? (
                  <div>
                    <dt className="text-sm font-medium text-muted-foreground">User ID</dt>
                    <dd className="mt-1 font-mono text-xs text-muted-foreground break-all">{user.id}</dd>
                  </div>
                ) : null}
              </dl>
              <div className="mt-6">
                <Button asChild variant="outline" size="sm">
                  <Link to="/studies">Back to Dashboard</Link>
                </Button>
              </div>
            </CardContent>
          </Card>

          {studies.length > 0 ? (
            <Card>
              <CardHeader>
                <CardTitle>Your Studies</CardTitle>
                <CardDescription>Studies you can access and your role in each.</CardDescription>
              </CardHeader>
              <CardContent>
                <Table>
                  <TableHeader>
                    <TableRow className="bg-muted/30 hover:bg-muted/30">
                      <TableHead scope="col">Study</TableHead>
                      <TableHead scope="col" className="w-[120px]">Role</TableHead>
                      <TableHead scope="col" className="w-[100px] text-right">Open</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {studies.map((s) => (
                      <TableRow key={s.id}>
                        <TableCell className="font-medium">{s.name}</TableCell>
                        <TableCell>
                          <Badge variant="secondary" className="capitalize">{formatStudyRoleLabel(s)}</Badge>
                        </TableCell>
                        <TableCell className="text-right">
                          <Button variant="link" size="sm" className="h-auto p-0" asChild>
                            <Link to={`/studies/${s.id}`}>Open</Link>
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          ) : null}
        </section>
      </main>
    </div>
  )
}
