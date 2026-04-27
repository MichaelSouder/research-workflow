import { useState, useEffect } from 'react'
import { getStudyUsers, setStudyUsers } from '../api'
import { Button } from '@/components/ui/button'

const ROLES = ['staff', 'admin']

export default function StudyUsers({ studyId, canManage }) {
  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (!studyId || !canManage) return
    let cancelled = false
    getStudyUsers(studyId)
      .then((data) => {
        if (!cancelled) setUsers(data.users || [])
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => { cancelled = true }
  }, [studyId, canManage])

  const handleRoleChange = (userId, newRole) => {
    const next = users.map((u) =>
      u.id === userId ? { ...u, role: newRole } : u
    )
    setUsers(next)
  }

  const handleRemove = (userId) => {
    setUsers(users.filter((u) => u.id !== userId))
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      await setStudyUsers(studyId, users.map((u) => ({ user_id: u.id, role: u.role })))
    } finally {
      setSaving(false)
    }
  }

  if (!canManage) return null
  if (!studyId) return null

  return (
    <section className="overflow-hidden rounded-xl border border-border bg-card text-card-foreground shadow-sm">
      <div className="flex items-center justify-between border-b border-border bg-muted/30 px-4 py-3">
        <h2 className="text-sm font-medium text-foreground">Study users</h2>
        <Button size="sm" onClick={handleSave} disabled={saving || loading}>
          {saving ? 'Saving…' : 'Save'}
        </Button>
      </div>
      <div className="p-4">
        {loading ? (
          <p className="text-sm text-muted-foreground">Loading…</p>
        ) : users.length === 0 ? (
          <p className="text-sm text-muted-foreground">No users with access.</p>
        ) : (
          <ul className="space-y-2">
            {users.map((u) => (
              <li
                key={u.id}
                className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border bg-muted/20 px-3 py-2 text-sm"
              >
                <span className="text-foreground">{u.email || u.name || u.id}</span>
                <div className="flex items-center gap-2">
                  <select
                    value={u.role}
                    onChange={(e) => handleRoleChange(u.id, e.target.value)}
                    className="rounded-md border border-input bg-background px-2 py-1.5 text-sm text-foreground shadow-xs"
                  >
                    {ROLES.map((r) => (
                      <option key={r} value={r}>
                        {r}
                      </option>
                    ))}
                  </select>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="text-destructive hover:text-destructive"
                    onClick={() => handleRemove(u.id)}
                  >
                    Remove
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  )
}
