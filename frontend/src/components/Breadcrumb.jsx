import { Link } from 'react-router-dom'
import { cn } from '@/lib/utils'

/**
 * Items: array of { label, to? }. Last item is current (no link) if to is omitted.
 */
export default function Breadcrumb({ items, className }) {
  return (
    <nav aria-label="Breadcrumb" className={cn('text-sm text-muted-foreground', className)}>
      <ol className="flex flex-wrap items-center gap-1.5">
        {items.map((item, i) => (
          <li key={i} className="flex items-center gap-1.5">
            {i > 0 && <span aria-hidden className="text-muted-foreground/60">/</span>}
            {item.to != null ? (
              <Link
                to={item.to}
                className="hover:text-foreground transition-colors focus:outline-none focus:ring-2 focus:ring-ring rounded"
              >
                {item.label}
              </Link>
            ) : (
              <span className="text-foreground font-medium">{item.label}</span>
            )}
          </li>
        ))}
      </ol>
    </nav>
  )
}
