import { Link, useLocation } from 'react-router-dom'
import { BookOpen, FlaskConical, Moon, PanelLeft, PanelLeftClose, Shield, Sun } from 'lucide-react'
import { APP_NAME } from '../branding'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { useAuth } from '../contexts/AuthContext'
import { useAppUi } from '../contexts/AppUiContext'

function NavItem({ to, icon: Icon, children, active, collapsed }) {
  return (
    <Button
      variant={active ? 'secondary' : 'ghost'}
      className={cn(
        'w-full justify-start gap-2',
        active && 'bg-muted',
        collapsed && 'justify-center px-0'
      )}
      asChild
      title={collapsed ? String(children) : undefined}
    >
      <Link to={to}>
        <Icon className="size-4 shrink-0" />
        <span className={cn('truncate', collapsed && 'sr-only')}>{children}</span>
      </Link>
    </Button>
  )
}

export default function AppSidebar() {
  const location = useLocation()
  const { isSuperuser } = useAuth()
  const { sidebarCollapsed: collapsed, toggleSidebar, theme, toggleTheme } = useAppUi()
  const path = location.pathname

  return (
    <aside
      className={cn(
        'flex shrink-0 flex-col border-r border-border bg-card transition-[width] duration-200 ease-out',
        collapsed ? 'w-[4.5rem]' : 'w-64'
      )}
    >
      <div className="flex h-14 items-center border-b border-border px-3">
        <Link
          to="/studies"
          className={cn(
            'flex min-w-0 items-center font-semibold tracking-tight text-foreground',
            collapsed ? 'mx-auto text-lg' : 'text-lg'
          )}
          title={APP_NAME}
        >
          {collapsed ? (
            <span className="flex size-9 items-center justify-center rounded-md bg-primary/10 text-[10px] font-bold leading-tight text-primary">
              RW
            </span>
          ) : (
            <span className="truncate pl-1">{APP_NAME}</span>
          )}
        </Link>
      </div>
      <nav className="flex flex-1 flex-col gap-1 p-2" aria-label="Main">
        <NavItem
          to="/studies"
          icon={FlaskConical}
          active={path === '/studies' || path === '/'}
          collapsed={collapsed}
        >
          Studies
        </NavItem>
        {isSuperuser && (
          <NavItem
            to="/platform"
            icon={Shield}
            active={path.startsWith('/platform')}
            collapsed={collapsed}
          >
            Platform
          </NavItem>
        )}
        <NavItem to="/help" icon={BookOpen} active={path.startsWith('/help')} collapsed={collapsed}>
          Help
        </NavItem>
      </nav>

      <div
        className={cn('border-t border-border p-2', collapsed && 'flex flex-col items-stretch gap-1')}
        aria-label="Appearance and layout"
      >
        <Button
          type="button"
          variant="ghost"
          className={cn('w-full justify-start gap-2', collapsed && 'justify-center px-0')}
          onClick={toggleSidebar}
          title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {collapsed ? (
            <PanelLeft className="size-4 shrink-0" aria-hidden />
          ) : (
            <PanelLeftClose className="size-4 shrink-0" aria-hidden />
          )}
          <span className={cn('truncate', collapsed && 'sr-only')}>
            {collapsed ? 'Expand menu' : 'Collapse menu'}
          </span>
        </Button>
        <Button
          type="button"
          variant="ghost"
          className={cn('w-full justify-start gap-2', collapsed && 'justify-center px-0')}
          onClick={toggleTheme}
          aria-label={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
          title={theme === 'dark' ? 'Light mode' : 'Dark mode'}
        >
          {theme === 'dark' ? (
            <Sun className="size-4 shrink-0" aria-hidden />
          ) : (
            <Moon className="size-4 shrink-0" aria-hidden />
          )}
          <span className={cn('truncate', collapsed && 'sr-only')}>
            {theme === 'dark' ? 'Light mode' : 'Dark mode'}
          </span>
        </Button>
      </div>
    </aside>
  )
}
