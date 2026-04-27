import { useState, useEffect, useCallback, useRef } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { toast } from 'sonner'
import {
  getStudies,
  getStudy,
  patchStudy,
  getStudyUsers,
  setStudyUsers,
  addStudyUserByEmail,
  deleteStudy,
} from '../api'
import { useAuth } from '../contexts/AuthContext'
import Header from '../components/Header'
import Breadcrumb from '../components/Breadcrumb'
import PageHeader from '../components/PageHeader'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'

const ROLES = ['staff', 'admin']
const ROLE_DESCRIPTIONS = {
  staff: 'Can edit config, run the pipeline, and use distribution tools',
  admin: 'Can manage study users, settings, and all staff capabilities',
}

export default function StudyAdminPage() {
  const { studyId } = useParams()
  const navigate = useNavigate()
  const { user, isSuperuser } = useAuth()
  const [studies, setStudies] = useState([])
  const [study, setStudy] = useState(null)
  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(true)
  const [studyRoleCanonical, setStudyRoleCanonical] = useState(null)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const savedNameRef = useRef('')
  const savedDescriptionRef = useRef('')
  const [savingDetails, setSavingDetails] = useState(false)
  const [savingUsers, setSavingUsers] = useState(false)
  const [addEmail, setAddEmail] = useState('')
  const [addRole, setAddRole] = useState('staff')
  const [adding, setAdding] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [deleteConfirmValue, setDeleteConfirmValue] = useState('')
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [removeUserDialog, setRemoveUserDialog] = useState(null) // { userId, email }
  const usersSnapshotRef = useRef([]) // last saved/fetched list for dirty check

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

  const fetchStudy = useCallback(async () => {
    if (!studyId) return
    try {
      const s = await getStudy(studyId)
      setStudy(s)
      setStudyRoleCanonical(s.roleCanonical)
      const n = s.name ?? ''
      const d = s.description ?? ''
      setName(n)
      setDescription(d)
      savedNameRef.current = n
      savedDescriptionRef.current = d
    } catch (e) {
      if (e?.message?.includes('403') || e?.message?.includes('404')) {
        navigate('/studies', { replace: true })
      } else {
        toast.error(e.message)
      }
    }
  }, [studyId, navigate])

  const fetchUsers = useCallback(async () => {
    if (!studyId) return
    try {
      const data = await getStudyUsers(studyId)
      const list = data.users || []
      setUsers(list)
      usersSnapshotRef.current = list.map((u) => ({ id: u.id, role: u.role }))
    } catch (_) {}
  }, [studyId])

  useEffect(() => {
    if (!user || !studyId) return
    let cancelled = false
    setLoading(true)
    Promise.all([fetchStudy(), fetchUsers()])
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => { cancelled = true }
  }, [user, studyId, fetchStudy, fetchUsers])

  const isAdmin = studyRoleCanonical === 'admin' || isSuperuser
  const detailsDirty = name !== savedNameRef.current || description !== savedDescriptionRef.current
  const usersDirty = (() => {
    if (users.length !== usersSnapshotRef.current.length) return true
    const snap = new Map(usersSnapshotRef.current.map((u) => [u.id, u.role]))
    for (const u of users) {
      if (snap.get(u.id) !== u.role) return true
    }
    return false
  })()

  const handleSaveDetails = async () => {
    if (!studyId || !isAdmin) return
    setSavingDetails(true)
    try {
      await patchStudy(studyId, { name: name.trim() || undefined, description: description.trim() || undefined })
      savedNameRef.current = name.trim()
      savedDescriptionRef.current = description.trim()
      toast.success('Study updated.')
      fetchStudy()
    } catch (e) {
      toast.error(e.message)
    } finally {
      setSavingDetails(false)
    }
  }

  const handleCancelDetails = () => {
    setName(savedNameRef.current)
    setDescription(savedDescriptionRef.current)
  }

  const handleRoleChange = (userId, newRole) => {
    setUsers(users.map((u) => (u.id === userId ? { ...u, role: newRole } : u)))
  }

  const openRemoveUserDialog = (u) => setRemoveUserDialog({ userId: u.id, email: u.email || u.name || u.id })
  const closeRemoveUserDialog = () => setRemoveUserDialog(null)

  const confirmRemoveUser = () => {
    if (!removeUserDialog) return
    setUsers(users.filter((u) => u.id !== removeUserDialog.userId))
    closeRemoveUserDialog()
  }

  const handleSaveUsers = async () => {
    if (!studyId || !isAdmin) return
    setSavingUsers(true)
    try {
      await setStudyUsers(studyId, users.map((u) => ({ user_id: u.id, role: u.role })))
      usersSnapshotRef.current = users.map((u) => ({ id: u.id, role: u.role }))
      toast.success('Users saved.')
      fetchUsers()
    } catch (e) {
      toast.error(e.message)
    } finally {
      setSavingUsers(false)
    }
  }

  const handleAddUser = async () => {
    if (!studyId || !isAdmin || !addEmail.trim()) return
    setAdding(true)
    try {
      await addStudyUserByEmail(studyId, { email: addEmail.trim(), role: addRole })
      setAddEmail('')
      toast.success('User added.')
      fetchUsers()
    } catch (e) {
      toast.error(e.message)
    } finally {
      setAdding(false)
    }
  }

  const handleDeleteStudy = async () => {
    if (!studyId || !isAdmin) return
    const studyName = study?.name || studyId
    if (deleteConfirmValue.trim() !== studyName) {
      toast.error('Type the study name exactly to confirm.')
      return
    }
    setDeleting(true)
    try {
      await deleteStudy(studyId)
      toast.success('Study deleted.')
      closeDeleteDialog()
      navigate('/studies', { replace: true })
    } catch (e) {
      toast.error(e.message)
    } finally {
      setDeleting(false)
    }
  }

  const openDeleteDialog = () => setDeleteDialogOpen(true)
  const closeDeleteDialog = () => {
    setDeleteDialogOpen(false)
    setDeleteConfirmValue('')
  }

  if (!user) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <p className="text-muted-foreground">Checking auth…</p>
      </div>
    )
  }

  if (!studyId || loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <p className="text-muted-foreground">Loading…</p>
      </div>
    )
  }

  if (!study) {
    return null
  }

  if (!isAdmin) {
    return (
      <div className="min-h-screen bg-background text-foreground">
        <Header status="idle" onStart={() => {}} onStop={() => {}} starting={false} stopping={false} canEdit={false} showRunControls={false} />
        <main className="mx-auto max-w-6xl space-y-6 p-4 md:p-6">
          <Breadcrumb
            items={[
              { label: 'Studies', to: '/studies' },
              { label: study?.name || 'Study', to: `/studies/${studyId}` },
              { label: 'Admin' },
            ]}
            className="mb-2"
          />
          <Alert variant="destructive">
            <AlertTitle>Access denied</AlertTitle>
            <AlertDescription>You must be an admin of this study to manage it.</AlertDescription>
          </Alert>
          <Button asChild variant="outline">
            <Link to={`/studies/${studyId}`}>Back to pipelines</Link>
          </Button>
        </main>
      </div>
    )
  }

  const studyName = study?.name || studyId

  return (
    <div className="min-h-screen bg-background text-foreground">
      <Header
        status="idle"
        onStart={() => {}}
        onStop={() => {}}
        starting={false}
        stopping={false}
        canEdit={false}
        showRunControls={false}
      />
      <main className="mx-auto max-w-6xl space-y-6 p-4 md:p-6">
        <Breadcrumb
          items={[
            { label: 'Studies', to: '/studies' },
            { label: study?.name || 'Study', to: `/studies/${studyId}` },
            { label: 'Admin' },
          ]}
          className="mb-2"
        />
        <PageHeader
          title="Manage Study"
          description="Edit study details, manage who has access, and use the danger zone to delete the study."
          actions={
            <Button asChild variant="outline" size="sm">
              <Link to={`/studies/${studyId}`}>Back to Pipelines</Link>
            </Button>
          }
        />

        <Tabs defaultValue="details" className="space-y-4">
          <TabsList>
            <TabsTrigger value="details">Details</TabsTrigger>
            <TabsTrigger value="users">Users</TabsTrigger>
            <TabsTrigger value="danger">Danger Zone</TabsTrigger>
          </TabsList>

          <TabsContent value="details" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>Study Details</CardTitle>
                <CardDescription>Name and description for this study.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <dl className="grid gap-4 sm:grid-cols-2">
                  {studyId && (
                    <div>
                      <dt className="text-sm font-medium text-muted-foreground">Study ID</dt>
                      <dd className="mt-1 font-mono text-sm text-foreground break-all">{studyId}</dd>
                    </div>
                  )}
                  {study?.created_at && (
                    <div>
                      <dt className="text-sm font-medium text-muted-foreground">Created</dt>
                      <dd className="mt-1 text-sm text-foreground">{new Date(study.created_at).toLocaleString()}</dd>
                    </div>
                  )}
                </dl>
                <div className="space-y-2">
                  <Label htmlFor="study-name">Name</Label>
                  <Input
                    id="study-name"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="Study name"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="study-desc">Description</Label>
                  <textarea
                    id="study-desc"
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    placeholder="Optional description"
                    rows={3}
                    className={cn(
                      'flex w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-xs transition-[color,box-shadow] outline-none placeholder:text-muted-foreground disabled:cursor-not-allowed disabled:opacity-50',
                      'focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-[3px]'
                    )}
                  />
                </div>
                <div className="flex gap-2">
                  <Button onClick={handleSaveDetails} disabled={savingDetails || !detailsDirty}>
                    {savingDetails ? 'Saving…' : 'Save'}
                  </Button>
                  {detailsDirty && (
                    <Button type="button" variant="outline" onClick={handleCancelDetails}>
                      Cancel
                    </Button>
                  )}
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="users" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>Study Users</CardTitle>
                <CardDescription>Who has access. Staff can run pipelines and edit study config; study admins can also manage users and study settings.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex flex-wrap items-end gap-2">
                  <div className="min-w-[200px] space-y-1">
                    <Label htmlFor="add-email">Email</Label>
                    <Input
                      id="add-email"
                      type="email"
                      value={addEmail}
                      onChange={(e) => setAddEmail(e.target.value)}
                      placeholder="user@example.com"
                    />
                  </div>
                  <div className="w-[120px] space-y-1">
                    <Label>Role</Label>
                    <Select value={addRole} onValueChange={setAddRole}>
                      <SelectTrigger id="add-role">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {ROLES.map((r) => (
                          <SelectItem key={r} value={r} title={ROLE_DESCRIPTIONS[r]}>
                            {r === 'staff' ? 'Staff' : 'Admin'}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <Button onClick={handleAddUser} disabled={adding || !addEmail.trim()}>
                    {adding ? 'Adding…' : 'Add User'}
                  </Button>
                </div>
                {usersDirty && (
                  <Alert>
                    <AlertTitle>Unsaved User Changes</AlertTitle>
                    <AlertDescription>Click &quot;Save User Changes&quot; below to apply role changes and removals.</AlertDescription>
                  </Alert>
                )}
                {users.length === 0 ? (
                  <p className="text-muted-foreground text-sm">No users with access yet. Add someone by email above.</p>
                ) : (
                  <div className="rounded-md border border-border">
                    <Table>
                      <TableHeader>
                        <TableRow className="bg-muted/30 hover:bg-muted/30">
                          <TableHead scope="col">User</TableHead>
                          <TableHead scope="col" className="w-[140px]">Role</TableHead>
                          <TableHead scope="col" className="w-[100px] text-right">Actions</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {users.map((u) => (
                          <TableRow key={u.id}>
                            <TableCell>
                              <span className="flex flex-wrap items-center gap-2 text-sm">
                                <span className="font-medium text-foreground">{u.email || u.name || u.id}</span>
                                {user?.id && u.id === user.id ? (
                                  <Badge variant="secondary" className="text-xs">You</Badge>
                                ) : null}
                              </span>
                            </TableCell>
                            <TableCell>
                              <Select value={u.role} onValueChange={(v) => handleRoleChange(u.id, v)}>
                                <SelectTrigger className="h-8 w-[120px]" aria-label={`Role for ${u.email || u.name || u.id}`}>
                                  <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                  {ROLES.map((r) => (
                                    <SelectItem key={r} value={r} title={ROLE_DESCRIPTIONS[r]}>
                                      {r === 'staff' ? 'Staff' : 'Admin'}
                                    </SelectItem>
                                  ))}
                                </SelectContent>
                              </Select>
                            </TableCell>
                            <TableCell className="text-right">
                              <Button
                                type="button"
                                variant="ghost"
                                size="sm"
                                className="text-destructive hover:text-destructive"
                                onClick={() => openRemoveUserDialog(u)}
                              >
                                Remove
                              </Button>
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                )}
                {users.length > 0 && (
                  <Button onClick={handleSaveUsers} disabled={savingUsers || !usersDirty}>
                    {savingUsers ? 'Saving…' : 'Save User Changes'}
                  </Button>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="danger" className="space-y-4">
            <Card className="border-destructive/50">
              <CardHeader>
                <CardTitle className="text-destructive">Danger Zone</CardTitle>
                <CardDescription>Permanently delete this study and its config. Stop any run first.</CardDescription>
              </CardHeader>
              <CardContent>
                <Button variant="destructive" onClick={openDeleteDialog} disabled={deleting}>
                  Delete Study
                </Button>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </main>

      {/* Delete study dialog */}
      <AlertDialog open={deleteDialogOpen} onOpenChange={(open) => !open && closeDeleteDialog()}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete this study?</AlertDialogTitle>
            <AlertDialogDescription>
              This cannot be undone. Type the study name below to confirm: <strong>{studyName}</strong>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <div className="py-2">
            <Label htmlFor="delete-confirm">Study name</Label>
            <Input
              id="delete-confirm"
              value={deleteConfirmValue}
              onChange={(e) => setDeleteConfirmValue(e.target.value)}
              placeholder={studyName}
              className="mt-1"
            />
          </div>
          <AlertDialogFooter>
            <AlertDialogCancel onClick={closeDeleteDialog}>Cancel</AlertDialogCancel>
            <Button
              variant="destructive"
              disabled={deleting || deleteConfirmValue.trim() !== studyName}
              onClick={handleDeleteStudy}
            >
              {deleting ? 'Deleting…' : 'Delete Study'}
            </Button>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Remove user dialog */}
      <AlertDialog open={!!removeUserDialog} onOpenChange={(open) => !open && closeRemoveUserDialog()}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Remove user from study?</AlertDialogTitle>
            <AlertDialogDescription>
              {removeUserDialog ? `Remove ${removeUserDialog.email} from this study? They will lose access.` : ''}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel onClick={closeRemoveUserDialog}>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={confirmRemoveUser}>Remove</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
