export default function ProgressBar({ status, currentStep, progressPercent, message }) {
  return (
    <section className="rounded-xl border border-border bg-card p-4" aria-label="Run progress">
      <h2 className="mb-2 text-sm font-medium text-foreground">Progress</h2>
      <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
        <div
          className="h-full rounded-full bg-primary transition-all duration-300"
          style={{ width: `${progressPercent}%` }}
          role="progressbar"
          aria-valuenow={progressPercent}
          aria-valuemin={0}
          aria-valuemax={100}
        />
      </div>
      <p className="mt-2 text-sm text-muted-foreground">{currentStep || message || '—'}</p>
    </section>
  )
}
