import { Navigate, Outlet, Route, Routes, useLocation } from 'react-router-dom'
import { useAuth } from './auth'
import { StaffShell } from './components/StaffShell'
import { LoadingState } from './components/ui'
import { ActivityPage, ApplicationsPage, DocumentsPage, EscalationsPage, FollowupsPage, LeadsPage, ProgramsPage, StaffPage, StudentCasePage, TasksPage } from './pages/CaseworkPages'
import { ChatPage } from './pages/ChatPage'
import { LoginPage } from './pages/LoginPage'
import { OverviewPage } from './pages/OverviewPage'

function RequireStaff() {
  const { staff, loading } = useAuth()
  const location = useLocation()
  if (loading) return <div className="auth-loading"><LoadingState label="Restoring staff session" /></div>
  if (!staff) return <Navigate to="/staff/login" replace state={{ from: location.pathname }} />
  return <Outlet />
}

function RequireAdmin() {
  const { staff } = useAuth()
  if (staff?.role !== 'admin') return <Navigate to="/staff" replace />
  return <StaffPage />
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/chat" replace />} />
      <Route path="/chat" element={<ChatPage />} />
      <Route path="/staff/login" element={<LoginPage />} />
      <Route path="/staff" element={<RequireStaff />}>
        <Route element={<StaffShell />}>
          <Route index element={<OverviewPage />} />
          <Route path="leads" element={<LeadsPage />} />
          <Route path="students/:leadId" element={<StudentCasePage />} />
          <Route path="applications" element={<ApplicationsPage />} />
          <Route path="documents" element={<DocumentsPage />} />
          <Route path="tasks" element={<TasksPage />} />
          <Route path="follow-ups" element={<FollowupsPage />} />
          <Route path="escalations" element={<EscalationsPage />} />
          <Route path="programs" element={<ProgramsPage />} />
          <Route path="activity" element={<ActivityPage />} />
          <Route path="team" element={<RequireAdmin />} />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/chat" replace />} />
    </Routes>
  )
}
