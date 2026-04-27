import { useState } from 'react'
import { HELP_TABS } from '../constants'
import { guides, troubleshooting } from '../content/helpContent'

export default function HelpSupport() {
  const [open, setOpen] = useState(false)
  const [activeTab, setActiveTab] = useState(HELP_TABS[0]?.id ?? 'guides')

  return (
    <section className="rounded-xl border border-border bg-card" aria-labelledby="help-heading">
      <h2 id="help-heading" className="sr-only">Help & support</h2>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="flex w-full items-center justify-between px-4 py-3 text-left text-sm font-medium text-foreground hover:bg-muted/50 rounded-t-xl transition-colors"
        aria-expanded={open}
      >
        Help & support
        <span className="text-muted-foreground" aria-hidden>{open ? '▼' : '▶'}</span>
      </button>
      {open && (
        <div className="border-t border-border p-4">
          <div
            role="tablist"
            className="mb-4 flex flex-wrap gap-1 border-b border-border"
            aria-label="Help sections"
          >
            {HELP_TABS.map((t) => (
              <button
                key={t.id}
                type="button"
                role="tab"
                aria-selected={activeTab === t.id}
                tabIndex={activeTab === t.id ? 0 : -1}
                onClick={() => setActiveTab(t.id)}
                className={`rounded-t px-3 py-2 text-sm font-medium transition-colors ${
                  activeTab === t.id
                    ? 'border-b-2 border-primary bg-muted/50 text-foreground'
                    : 'text-muted-foreground hover:bg-muted/30 hover:text-foreground'
                }`}
              >
                {t.label}
              </button>
            ))}
          </div>
          <div role="tabpanel" className="min-h-[120px]">
            {activeTab === 'guides' && (
              <div className="space-y-6">
                {guides.map((g) => (
                  <div key={g.id}>
                    <h3 className="mb-2 text-sm font-medium text-slate-200">{g.title}</h3>
                    <p className="text-sm text-slate-400">{g.body}</p>
                  </div>
                ))}
              </div>
            )}
            {activeTab === 'troubleshooting' && (
              <div className="space-y-6">
                {troubleshooting.map((t) => (
                  <div key={t.id}>
                    <h3 className="mb-2 text-sm font-medium text-slate-200">{t.title}</h3>
                    <p className="mb-2 text-sm text-slate-400">
                      <span className="font-medium text-slate-300">What it means: </span>
                      {t.problem}
                    </p>
                    <div className="text-sm text-slate-400">
                      <span className="font-medium text-slate-300">What to try: </span>
                      {t.steps ? (
                        <ol className="mt-1 list-decimal space-y-1 pl-4">
                          {t.steps.map((step, i) => (
                            <li key={i}>{step}</li>
                          ))}
                        </ol>
                      ) : (
                        <p className="mt-1">{t.solution}</p>
                      )}
                      {t.bullets && (
                        <>
                          <p className="mt-3 font-medium text-slate-300">Things to verify in Settings:</p>
                          <ul className="mt-1 list-disc space-y-0.5 pl-4">
                            {t.bullets.map((b, i) => (
                              <li key={i}>{b}</li>
                            ))}
                          </ul>
                        </>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </section>
  )
}
