import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  createPlatformUser,
  getPlatformUsers,
  patchPlatformUser,
  patchPlatformUserSuperuser,
} from '../api'
import AdminSection from '../components/platform/AdminSection'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { useAuth } from '../contexts/AuthContext'
import { Loader2, Pencil, Search, UserPlus } from 'lucide-react'
import { Skeleton } from '@/components/ui/skeleton'

export default function PlatformUsersPage() {
  const { isSuperuser, user: me } = useAuth()
  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [pendingId, setPendingId] = useState(null)
  const [query, setQuery] = useState('')
  const [sortBy, setSortBy] = useState('name')

  const [addOpen, setAddOpen] = useState(false)
  const [addEmail, setAddEmail] = useState('')
  const [addName, setAddName] = useState('')
  const [addPassword, setAddPassword] = useState('')
  const [addBusy, setAddBusy] = useState(false)

  const [editOpen, setEditOpen] = useState(false)
  const [editUser, setEditUser] = useState(null)
  const [editName, setEditName] = useState('')
  const [editEmail, setEditEmail] = useState('')
  const [editNewPassword, setEditNewPassword] = useState('')
  const [editClearPassword, setEditClearPassword] = useState(false)
  const [editBusy, setEditBusy] = useState(false)

  useEffect(() => {
    if (!isSuperuser) {
      setLoading(false)
      return
    }
    let cancelled = false
    setLoading(true)
    ;(async () => {
      try {
        const data = await getPlatformUsers()
        if (!cancelled) setUsers(data.users || [])
      } catch (e) {
        if (!cancelled) setError(e.message)
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [isSuperuser])

  const filteredUsers = useMemo(() => {
    let list = users
    const q = query.trim().toLowerCase()
    if (q) {
      list = list.filter(
        (u) =>
          (u.name || '').toLowerCase().includes(q) || (u.email || '').toLowerCase().includes(q)
      )
    }
    const sorted = [...list].sort((a, b) => {
      if (sortBy === 'email') {
        return (a.email || '').localeCompare(b.email || '', undefined, { sensitivity: 'base' })
      }
      return (a.name || '').localeCompare(b.name || '', undefined, { sensitivity: 'base' })
    })
    return sorted
  }, [users, query, sortBy])

  const toggleSuperuser = async (target) => {
    setPendingId(target.id)
    setError(null)
    try {
      const next = !target.isSuperuser
      const res = await patchPlatformUserSuperuser(target.id, next)
      const updated = res.user
      if (updated) {
        setUsers((prev) => prev.map((u) => (u.id === target.id ? { ...u, ...updated } : u)))
      } else {
        setUsers((prev) =>
          prev.map((u) => (u.id === target.id ? { ...u, isSuperuser: next } : u))
        )
      }
    } catch (e) {
      setError(e.message)
    } finally {
      setPendingId(null)
    }
  }

  const openEdit = (u) => {
    setEditUser(u)
    setEditName(u.name || '')
    setEditEmail(u.email || '')
    setEditNewPassword('')
    setEditClearPassword(false)
    setEditOpen(true)
  }

  const submitAdd = async (e) => {
    e.preventDefault()
    setError(null)
    setAddBusy(true)
    try {
      const res = await createPlatformUser({
        email: addEmail,
        name: addName,
        password: addPassword.trim() || undefined,
      })
      if (res.user) setUsers((prev) => [...prev, res.user])
      setAddOpen(false)
      setAddEmail('')
      setAddName('')
      setAddPassword('')
    } catch (err) {
      setError(err.message)
    } finally {
      setAddBusy(false)
    }
  }

  const submitEdit = async (e) => {
    e.preventDefault()
    if (!editUser) return
    setError(null)
    const patch = {}
    if (editName.trim() !== (editUser.name || '')) patch.name = editName.trim()
    if (editEmail.trim() !== (editUser.email || '')) patch.email = editEmail.trim()
    if (editClearPassword) patch.clear_password = true
    else if (editNewPassword.trim()) patch.password = editNewPassword.trim()
    if (Object.keys(patch).length === 0) {
      setEditOpen(false)
      return
    }
    setEditBusy(true)
    try {
      const res = await patchPlatformUser(editUser.id, patch)
      if (res.user) {
        setUsers((prev) => prev.map((u) => (u.id === editUser.id ? { ...u, ...res.user } : u)))
      }
      setEditOpen(false)
    } catch (err) {
      setError(err.message)
    } finally {
      setEditBusy(false)
    }
  }

  if (!isSuperuser) return null

  return (
    <div className="space-y-4">
      <AdminSection title="Users">
        <p className="text-sm text-muted-foreground">
          Search and sort the directory. Add users before they sign in with Google, set an optional password for
          email login, and edit names or passwords. Superusers can grant or revoke platform superuser for others.
          Set{' '}
          <code className="rounded-md border border-border bg-muted px-1.5 py-0.5 font-mono text-xs">
            SUPERUSER_EMAILS
          </code>{' '}
          in the server environment for initial access.
        </p>
      </AdminSection>

      <Card className="overflow-hidden border-border shadow-sm">
        <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-4 border-b border-border bg-card">
          <div>
            <CardTitle className="text-lg">Directory</CardTitle>
            <CardDescription>Click a name to view study memberships.</CardDescription>
          </div>
          <Button type="button" onClick={() => setAddOpen(true)}>
            <UserPlus className="mr-2 size-4" aria-hidden />
            Add User
          </Button>
        </CardHeader>
        <CardContent className="space-y-4 pt-6">
          <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-end">
            <div className="grid max-w-md flex-1 gap-2">
              <Label htmlFor="user-search">Search</Label>
              <div className="relative">
                <Search className="text-muted-foreground absolute left-2.5 top-1/2 size-4 -translate-y-1/2" aria-hidden />
                <Input
                  id="user-search"
                  className="pl-9"
                  placeholder="Name or Email"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  autoComplete="off"
                />
              </div>
            </div>
            <div className="grid w-full gap-2 sm:w-44">
              <Label htmlFor="user-sort">Sort By</Label>
              <Select value={sortBy} onValueChange={setSortBy}>
                <SelectTrigger id="user-sort">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="name">Name</SelectItem>
                  <SelectItem value="email">Email</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          {loading ? (
            <div className="space-y-3 rounded-md border border-border p-4">
              {[1, 2, 3, 4, 5].map((i) => (
                <div key={i} className="flex gap-4">
                  <Skeleton className="h-5 flex-1" />
                  <Skeleton className="h-5 flex-1" />
                  <Skeleton className="h-9 w-24" />
                </div>
              ))}
            </div>
          ) : error ? (
            <p className="text-destructive">{error}</p>
          ) : users.length === 0 ? (
            <p className="text-muted-foreground text-sm">No users in the directory.</p>
          ) : filteredUsers.length === 0 ? (
            <p className="text-muted-foreground text-sm">No users match your search.</p>
          ) : (
            <div className="rounded-md border border-border">
              <Table>
                <TableHeader>
                  <TableRow className="bg-muted/30 hover:bg-muted/30">
                    <TableHead scope="col">Name</TableHead>
                    <TableHead scope="col">Email</TableHead>
                    <TableHead scope="col" className="w-[120px]">
                      Password
                    </TableHead>
                    <TableHead scope="col" className="w-[200px]">
                      Superuser
                    </TableHead>
                    <TableHead scope="col" className="w-[100px] text-right">
                      Edit
                    </TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredUsers.map((u) => (
                    <TableRow key={u.id}>
                      <TableCell className="font-medium text-foreground">
                        <Link
                          to={`/platform/users/${encodeURIComponent(u.id)}`}
                          className="text-primary underline-offset-4 hover:underline"
                        >
                          {u.name}
                        </Link>
                      </TableCell>
                      <TableCell className="text-muted-foreground">{u.email}</TableCell>
                      <TableCell>
                        {u.hasPassword ? (
                          <Badge variant="outline">Set</Badge>
                        ) : (
                          <Badge variant="secondary">Not Set</Badge>
                        )}
                      </TableCell>
                      <TableCell>
                        <div className="flex flex-wrap items-center gap-2">
                          {u.isSuperuser ? (
                            <Badge>Yes</Badge>
                          ) : (
                            <Badge variant="secondary">No</Badge>
                          )}
                          <Button
                            type="button"
                            variant="outline"
                            size="sm"
                            disabled={pendingId === u.id || u.id === me?.id}
                            title={
                              u.id === me?.id
                                ? 'Use another superuser to change your own flag'
                                : ''
                            }
                            onClick={() => toggleSuperuser(u)}
                          >
                            {pendingId === u.id ? (
                              <Loader2 className="size-4 animate-spin" />
                            ) : u.isSuperuser ? (
                              'Revoke'
                            ) : (
                              'Grant'
                            )}
                          </Button>
                        </div>
                      </TableCell>
                      <TableCell className="text-right">
                        <Button type="button" variant="ghost" size="sm" onClick={() => openEdit(u)}>
                          <Pencil className="size-4" aria-hidden />
                          <span className="sr-only">Edit {u.name}</span>
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>

      <Dialog open={addOpen} onOpenChange={setAddOpen}>
        <DialogContent className="sm:max-w-md">
          <form onSubmit={submitAdd}>
            <DialogHeader>
              <DialogTitle>Add User</DialogTitle>
              <DialogDescription>
                Creates a directory entry. They can sign in with Google (matching this email) or with the password
                below if set (minimum 8 characters).
              </DialogDescription>
            </DialogHeader>
            <div className="grid gap-4 py-4">
              <div className="grid gap-2">
                <Label htmlFor="add-email">Email</Label>
                <Input
                  id="add-email"
                  type="email"
                  required
                  autoComplete="off"
                  value={addEmail}
                  onChange={(e) => setAddEmail(e.target.value)}
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="add-name">Display Name</Label>
                <Input
                  id="add-name"
                  value={addName}
                  onChange={(e) => setAddName(e.target.value)}
                  placeholder="User"
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="add-password">Password (Optional)</Label>
                <Input
                  id="add-password"
                  type="password"
                  autoComplete="new-password"
                  value={addPassword}
                  onChange={(e) => setAddPassword(e.target.value)}
                  placeholder="Leave empty for Google only"
                />
              </div>
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setAddOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={addBusy}>
                {addBusy ? <Loader2 className="size-4 animate-spin" /> : 'Create'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <Dialog open={editOpen} onOpenChange={setEditOpen}>
        <DialogContent className="sm:max-w-md">
          <form onSubmit={submitEdit}>
            <DialogHeader>
              <DialogTitle>Edit User</DialogTitle>
              <DialogDescription>Update profile or password. Use a strong password (at least 8 characters).</DialogDescription>
            </DialogHeader>
            <div className="grid gap-4 py-4">
              <div className="grid gap-2">
                <Label htmlFor="edit-name">Display Name</Label>
                <Input
                  id="edit-name"
                  value={editName}
                  onChange={(e) => setEditName(e.target.value)}
                  autoComplete="off"
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="edit-email">Email</Label>
                <Input
                  id="edit-email"
                  type="email"
                  required
                  value={editEmail}
                  onChange={(e) => setEditEmail(e.target.value)}
                  autoComplete="off"
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="edit-new-password">New Password</Label>
                <Input
                  id="edit-new-password"
                  type="password"
                  autoComplete="new-password"
                  value={editNewPassword}
                  onChange={(e) => {
                    setEditNewPassword(e.target.value)
                    if (e.target.value) setEditClearPassword(false)
                  }}
                  placeholder="Leave blank to keep current"
                  disabled={editClearPassword}
                />
              </div>
              <label className="flex cursor-pointer items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={editClearPassword}
                  onChange={(e) => {
                    setEditClearPassword(e.target.checked)
                    if (e.target.checked) setEditNewPassword('')
                  }}
                  className="border-input rounded border"
                />
                Remove Password (Google Sign-In Only)
              </label>
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setEditOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={editBusy}>
                {editBusy ? <Loader2 className="size-4 animate-spin" /> : 'Save'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  )
}
