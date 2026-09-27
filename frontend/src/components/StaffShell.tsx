import { useEffect, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import {
  Activity, BriefcaseBusiness, CheckSquare2, ChevronDown, ClipboardList,
  FileCheck2, GraduationCap, LayoutDashboard, LogOut, Menu, MessageSquareMore,
  PanelLeftClose, Users, X,
} from 'lucide-react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../auth'

const mainNavigation = [
  { label: 'Overview', path: '/staff', icon: LayoutDashboard, exact: true },
  { label: 'Leads', path: '/staff/leads', icon: Users },
  { label: 'Applications', path: '/staff/applications', icon: BriefcaseBusiness },
  { label: 'Documents', path: '/staff/documents', icon: FileCheck2 },
  { label: 'Tasks', path: '/staff/tasks', icon: CheckSquare2 },
  { label: 'Follow-ups', path: '/staff/follow-ups', icon: MessageSquareMore },
  { label: 'Escalations', path: '/staff/escalations', icon: ClipboardList },
  { label: 'Programs', path: '/staff/programs', icon: GraduationCap },
  { label: 'Agent Activity', path: '/staff/activity', icon: Activity },
]

const pageNames: Record<string, string> = {
  '/staff': 'Overview',
  '/staff/leads': 'Leads',
  '/staff/applications': 'Applications',
  '/staff/documents': 'Documents',
  '/staff/tasks': 'Tasks',
  '/staff/follow-ups': 'Follow-ups',
  '/staff/escalations': 'Escalations',
  '/staff/programs': 'Programs',
  '/staff/activity': 'Agent Activity',
  '/staff/team': 'Staff Management',
}

export function StaffShell() {
  const { staff, signOut } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [mobileOpen, setMobileOpen] = useState(false)
  const [backendState, setBackendState] = useState<'checking' | 'online' | 'offline'>('checking')
  const title = location.pathname.startsWith('/staff/students/') ? 'Student case' : pageNames[location.pathname] ?? 'Control center'

  useEffect(() => {
    let active = true
    const checkHealth = () => api.health().then(() => { if (active) setBackendState('online') }).catch(() => { if (active) setBackendState('offline') })
    void checkHealth()
    const interval = window.setInterval(checkHealth, 30_000)
    return () => { active = false; window.clearInterval(interval) }
  }, [])

  function logout() {
    signOut()
    navigate('/staff/login', { replace: true })
  }

  const links = [...mainNavigation]
  if (staff?.role === 'admin') links.push({ label: 'Staff Management', path: '/staff/team', icon: Users })

  return (
    <div className="staff-frame">
      <AnimatePresence>
        {mobileOpen && <motion.button className="sidebar-scrim" type="button" aria-label="Close navigation" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={() => setMobileOpen(false)} />}
      </AnimatePresence>
      <aside className={`staff-sidebar${mobileOpen ? ' sidebar-open' : ''}`} aria-label="Staff navigation">
        <div className="brand-lockup">
          <span className="brand-mark"><GraduationCap size={21} strokeWidth={1.8} /></span>
          <span className="brand-name">Admit<span>Crew</span></span>
          <span className="brand-edition">OPS</span>
          <button className="icon-button sidebar-close" type="button" aria-label="Close navigation" onClick={() => setMobileOpen(false)}><X size={18} /></button>
        </div>
        <div className="workspace-label"><span className="workspace-pulse" /> Admissions workspace</div>
        <nav className="sidebar-nav">
          <p className="nav-caption">WORKSPACE</p>
          {links.slice(0, 5).map(({ label, path, icon: Icon, exact }) => (
            <NavLink key={path} to={path} end={exact} className={({ isActive }) => `nav-link${isActive ? ' nav-link-active' : ''}`} onClick={() => setMobileOpen(false)}>
              <Icon size={17} strokeWidth={1.8} /><span>{label}</span>
              {label === 'Overview' && <span className="nav-key">⌘ 1</span>}
            </NavLink>
          ))}
          <p className="nav-caption nav-caption-spaced">STUDENT SUPPORT</p>
          {links.slice(5, 9).map(({ label, path, icon: Icon }) => (
            <NavLink key={path} to={path} className={({ isActive }) => `nav-link${isActive ? ' nav-link-active' : ''}`} onClick={() => setMobileOpen(false)}>
              <Icon size={17} strokeWidth={1.8} /><span>{label}</span>
            </NavLink>
          ))}
          {staff?.role === 'admin' && <>
            <p className="nav-caption nav-caption-spaced">ADMINISTRATION</p>
            <NavLink to="/staff/team" className={({ isActive }) => `nav-link${isActive ? ' nav-link-active' : ''}`} onClick={() => setMobileOpen(false)}>
              <Users size={17} strokeWidth={1.8} /><span>Staff Management</span>
            </NavLink>
          </>}
        </nav>
        <div className="sidebar-bottom">
          <div className="sidebar-note"><span className="note-orbit" /><div><strong>Admissions, in motion.</strong><small>Your team workspace</small></div></div>
          <div className="sidebar-account">
            <span className="account-avatar">{staff?.name.split(/\s+/).map((part) => part[0]).slice(0, 2).join('').toUpperCase()}</span>
            <div className="account-copy"><strong>{staff?.name}</strong><small>{staff?.role}</small></div>
            <button className="icon-button logout-button" type="button" onClick={logout} aria-label="Sign out" title="Sign out"><LogOut size={16} /></button>
          </div>
        </div>
      </aside>

      <div className="staff-main">
        <header className="staff-topbar">
          <div className="topbar-leading">
            <button className="icon-button mobile-menu-button" type="button" onClick={() => setMobileOpen(true)} aria-label="Open navigation"><Menu size={19} /></button>
            <div className="breadcrumbs"><span>AdmitCrew</span><span className="breadcrumb-slash">/</span><strong>{title}</strong></div>
          </div>
          <div className="topbar-right">
            <span className={`live-indicator live-${backendState}`}><span /> {backendState === 'online' ? 'Backend connected' : backendState === 'offline' ? 'Backend unavailable' : 'Checking backend'}</span>
            <div className="topbar-user"><span className="topbar-avatar">{staff?.name.split(/\s+/).map((part) => part[0]).slice(0, 2).join('').toUpperCase()}</span><div><strong>{staff?.name}</strong><small>{staff?.role}</small></div><ChevronDown size={14} className="topbar-chevron" /></div>
          </div>
        </header>
        <main className="staff-content">
          <AnimatePresence mode="wait">
            <motion.div key={location.pathname} className="route-surface" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -5 }} transition={{ duration: 0.2, ease: 'easeOut' }}>
              <Outlet />
            </motion.div>
          </AnimatePresence>
          <footer className="staff-footer"><span>ADMITCREW OPERATIONS</span><span>Verified data. Human judgment.</span><PanelLeftClose size={14} /></footer>
        </main>
      </div>
    </div>
  )
}
