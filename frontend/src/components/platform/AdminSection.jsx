import { cn } from '@/lib/utils'

/**
 * Consistent heading block for platform admin pages (plan: DashboardSection / hierarchy).
 */
function AdminSection({ title, description, className, children }) {
  return (
    <div className={cn('space-y-2', className)}>
      {title ? <h2 className="text-lg font-semibold tracking-tight">{title}</h2> : null}
      {description ? <p className="text-sm text-muted-foreground">{description}</p> : null}
      {children}
    </div>
  )
}

export default AdminSection
export const AdminPageFrame = AdminSection
