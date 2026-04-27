import { useId } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { cn } from '@/lib/utils'

/**
 * Consistent section with optional Card wrapper.
 */
export default function PageSection({
  title,
  description,
  children,
  className,
  contentClassName,
  asCard = true,
}) {
  const headingId = useId()
  if (!asCard) {
    return (
      <section className={cn('space-y-3', className)} aria-labelledby={title ? headingId : undefined}>
        {title ? (
          <div>
            <h2 id={headingId} className="text-base font-semibold text-foreground">
              {title}
            </h2>
            {description ? (
              <p className="mt-1 text-sm text-muted-foreground">{description}</p>
            ) : null}
          </div>
        ) : null}
        <div className={contentClassName}>{children}</div>
      </section>
    )
  }

  return (
    <Card className={className}>
      {(title || description) && (
        <CardHeader>
          {title ? <CardTitle>{title}</CardTitle> : null}
          {description ? <CardDescription>{description}</CardDescription> : null}
        </CardHeader>
      )}
      <CardContent className={cn(!title && !description && 'pt-6', contentClassName)}>{children}</CardContent>
    </Card>
  )
}
