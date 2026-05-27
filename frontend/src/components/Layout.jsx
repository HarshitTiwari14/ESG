import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { LayoutDashboard, ClipboardCheck, Upload, Layers, LogOut, Leaf } from 'lucide-react'
import './Layout.css'

const NAV = [
  { to: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/review', icon: ClipboardCheck, label: 'Review Queue' },
  { to: '/upload', icon: Upload, label: 'Upload Data' },
  { to: '/batches', icon: Layers, label: 'Batches' },
]

export default function Layout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <div className="layout">
      <aside className="sidebar">
        <div className="sidebar-logo">
          <Leaf size={20} strokeWidth={1.5} />
          <span>Breathe ESG</span>
        </div>

        <nav className="sidebar-nav">
          {NAV.map(({ to, icon: Icon, label }) => (
            <NavLink key={to} to={to} className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
              <Icon size={16} strokeWidth={1.5} />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="sidebar-footer">
          <div className="user-info">
            <div className="user-avatar">{user?.first_name?.[0] || user?.username?.[0] || 'U'}</div>
            <div className="user-details">
              <div className="user-name">{user?.first_name || user?.username}</div>
              <div className="user-role">{user?.role}</div>
            </div>
          </div>
          <button className="logout-btn" onClick={handleLogout} title="Sign out">
            <LogOut size={14} strokeWidth={1.5} />
          </button>
        </div>
      </aside>

      <main className="main-content">
        <Outlet />
      </main>
    </div>
  )
}
