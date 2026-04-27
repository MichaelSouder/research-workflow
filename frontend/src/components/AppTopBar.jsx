import { Link } from 'react-router-dom'
import { LogOut, UserCircle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { getLogoutUrl } from '../api'
import { useAuth } from '../contexts/AuthContext'
import { cn } from '@/lib/utils'

function initials(name, email) {
  const s = (name || email || '?').trim()
  const parts = s.split(/\s+/).filter(Boolean)
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase()
  return s.slice(0, 2).toUpperCase()
}

export default function AppTopBar({ className }) {
  const { user, isSuperuser } = useAuth()

  return (
    <header
      className={cn(
        'sticky top-0 z-40 flex h-14 shrink-0 items-center justify-end gap-3 border-b border-border bg-card/95 px-3 backdrop-blur supports-[backdrop-filter]:bg-card/80 md:px-4',
        className
      )}
    >
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" className="gap-2 px-2 sm:px-3">
            <Avatar className="size-8">
              <AvatarFallback className="text-xs">{initials(user?.name, user?.email)}</AvatarFallback>
            </Avatar>
            <span className="hidden max-w-[160px] truncate text-left text-sm font-medium md:inline">
              {user?.name || user?.email || 'Account'}
            </span>
            {isSuperuser ? (
              <span className="hidden rounded-md bg-primary/15 px-2 py-0.5 text-xs font-medium text-primary md:inline">
                Superuser
              </span>
            ) : null}
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-56">
          <DropdownMenuLabel className="font-normal">
            <div className="flex flex-col space-y-1">
              <p className="text-sm font-medium leading-none">{user?.name || 'User'}</p>
              <p className="text-xs leading-none text-muted-foreground">{user?.email}</p>
              {isSuperuser ? (
                <p className="pt-1 text-xs font-medium text-primary">Superuser</p>
              ) : null}
            </div>
          </DropdownMenuLabel>
          <DropdownMenuSeparator />
          <DropdownMenuItem asChild>
            <Link to="/profile" className="cursor-pointer">
              <UserCircle className="mr-2 size-4" />
              Profile
            </Link>
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem asChild>
            <a href={getLogoutUrl()} className="cursor-pointer">
              <LogOut className="mr-2 size-4" />
              Log out
            </a>
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </header>
  )
}
