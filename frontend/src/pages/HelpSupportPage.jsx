import { useAuth } from '../contexts/AuthContext'
import Breadcrumb from '../components/Breadcrumb'
import PageHeader from '../components/PageHeader'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { HELP_TABS } from '../constants'
import { guides, troubleshooting } from '../content/helpContent'

const defaultTab = HELP_TABS[0]?.id ?? 'guides'

export default function HelpSupportPage() {
  const { user, loading } = useAuth()

  if (loading || !user) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <p className="text-muted-foreground">{loading ? 'Loading…' : 'Redirecting…'}</p>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-background text-foreground">
      <main className="mx-auto max-w-6xl space-y-6 p-4 md:p-6">
        <Breadcrumb
          items={[
            { label: 'Dashboard', to: '/studies' },
            { label: 'Help & Support' },
          ]}
          className="mb-2"
        />
        <PageHeader
          title="Help & Support"
          description="Guides for using the pipeline and fixes for common issues."
        />
        <Card>
          <CardHeader>
            <CardTitle id="help-heading">Guides and Troubleshooting</CardTitle>
          </CardHeader>
          <CardContent>
            <Tabs defaultValue={defaultTab} className="w-full">
              <TabsList variant="line" className="mb-4 w-full justify-start">
                {HELP_TABS.map((t) => (
                  <TabsTrigger key={t.id} value={t.id}>
                    {t.label}
                  </TabsTrigger>
                ))}
              </TabsList>
              <TabsContent value="guides" className="min-h-[120px] outline-none">
                <div className="space-y-6">
                  {guides.map((g) => (
                    <div key={g.id} className="space-y-3">
                      <h3 className="mb-2 text-sm font-medium text-muted-foreground">{g.title}</h3>
                      {g.body && <p className="text-sm text-foreground/90">{g.body}</p>}
                      {g.sections?.map((sec, idx) => (
                        <div key={idx}>
                          {sec.label && (
                            <p className="mb-1 text-sm font-medium text-foreground">{sec.label}</p>
                          )}
                          <ul className="list-disc space-y-0.5 pl-4 text-sm text-foreground/90">
                            {sec.items.map((item, i) => (
                              <li key={i}>{item}</li>
                            ))}
                          </ul>
                        </div>
                      ))}
                    </div>
                  ))}
                </div>
              </TabsContent>
              <TabsContent value="troubleshooting" className="min-h-[120px] outline-none">
                <div className="space-y-6">
                  {troubleshooting.map((t) => (
                    <div key={t.id} className="space-y-2">
                      <h3 className="mb-2 text-sm font-medium text-muted-foreground">{t.title}</h3>
                      <div className="text-sm text-foreground/90">
                        <p className="font-medium text-foreground">What It Means:</p>
                        {Array.isArray(t.problem) ? (
                          <ul className="mt-1 list-disc space-y-0.5 pl-4">
                            {t.problem.map((p, i) => (
                              <li key={i}>{p}</li>
                            ))}
                          </ul>
                        ) : (
                          <p className="mt-1">{t.problem}</p>
                        )}
                      </div>
                      <div className="text-sm text-foreground/90">
                        <p className="font-medium text-foreground">What to Try:</p>
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
                            <p className="mt-3 font-medium text-foreground">Things to verify in Settings:</p>
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
              </TabsContent>
            </Tabs>
          </CardContent>
        </Card>
      </main>
    </div>
  )
}
