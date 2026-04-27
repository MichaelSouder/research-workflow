import { Toaster } from 'sonner'
import { Routes, Route, Navigate } from 'react-router-dom'
import { AppUiProvider, useAppUi } from './contexts/AppUiContext'
import AppLayout from './components/AppLayout'
import PlatformLayout from './components/PlatformLayout'
import LoginPage from './pages/LoginPage'
import StudiesList from './pages/StudiesList'
import StudyDashboard from './pages/StudyDashboard'
import StudyAdminPage from './pages/StudyAdminPage'
import DistributionPage from './pages/DistributionPage'
import PipelineGraphPage from './pages/PipelineGraphPage'
import ProfilePage from './pages/ProfilePage'
import HelpSupportPage from './pages/HelpSupportPage'
import IntegrationsPage from './pages/IntegrationsPage'
import PlatformDashboardPage from './pages/PlatformDashboardPage'
import PlatformUsersPage from './pages/PlatformUsersPage'
import PlatformUserDetailPage from './pages/PlatformUserDetailPage'
import PlatformApiKeysPage from './pages/PlatformApiKeysPage'
import PlatformApiLogsPage from './pages/PlatformApiLogsPage'

function ThemedToaster() {
  const { theme } = useAppUi()
  return <Toaster position="top-right" richColors closeButton theme={theme} />
}

export default function App() {
  return (
    <AppUiProvider>
      <ThemedToaster />
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route element={<AppLayout />}>
          <Route path="/studies" element={<StudiesList />} />
          <Route path="/studies/:studyId" element={<StudyDashboard />} />
          <Route path="/studies/:studyId/admin" element={<StudyAdminPage />} />
          <Route path="/studies/:studyId/distribution" element={<DistributionPage />} />
          <Route path="/studies/:studyId/pipeline-graph" element={<PipelineGraphPage />} />
          <Route path="/platform/*" element={<PlatformLayout />}>
            <Route index element={<PlatformDashboardPage />} />
            <Route path="overview" element={<Navigate to="/platform" replace />} />
            <Route path="users" element={<PlatformUsersPage />} />
            <Route path="users/:userId" element={<PlatformUserDetailPage />} />
            <Route path="api-keys" element={<PlatformApiKeysPage />} />
            <Route path="api-logs" element={<PlatformApiLogsPage />} />
          </Route>
          <Route path="/profile" element={<ProfilePage />} />
          <Route path="/integrations" element={<IntegrationsPage />} />
          <Route path="/help" element={<HelpSupportPage />} />
          <Route path="/" element={<Navigate to="/studies" replace />} />
          <Route path="*" element={<Navigate to="/studies" replace />} />
        </Route>
      </Routes>
    </AppUiProvider>
  )
}
