import { useState, useEffect } from 'react';
import { Outlet, NavLink, useNavigate } from 'react-router-dom';
import {
  Satellite, LayoutDashboard, MessageSquare, HeartPulse, User,
  FileText, Shield, Brain, Users, Wifi, RefreshCw, ScrollText,
  LogOut, Menu, X,
} from 'lucide-react';
import { useAuth } from '@/features/auth';
import { StatusDot } from '@/shared/components/StatusDot';
import { Badge } from '@/shared/components/Badge';
import { Button } from '@/shared/components/Button';

const NAV_ITEMS = [
  { section: 'Mission', items: [
    { to: '/astronaut', icon: LayoutDashboard, label: 'Dashboard', roles: ['ASTRONAUT', 'MEDICAL_OFFICER', 'ADMINISTRATOR'] },
    { to: '/chat', icon: MessageSquare, label: 'AI Chat', roles: ['ASTRONAUT', 'MEDICAL_OFFICER', 'ADMINISTRATOR'] },
    { to: '/vitals', icon: HeartPulse, label: 'Vitals & Waves', roles: ['ASTRONAUT', 'MEDICAL_OFFICER', 'ADMINISTRATOR'] },
    { to: '/twin', icon: User, label: '3D Digital Twin', roles: ['ASTRONAUT', 'MEDICAL_OFFICER', 'ADMINISTRATOR'] },
    { to: '/simulator', icon: RefreshCw, label: 'Simulator', roles: ['ASTRONAUT', 'MEDICAL_OFFICER', 'ADMINISTRATOR'] },
  ]},
  { section: 'Medical', items: [
    { to: '/documents', icon: FileText, label: 'Documents', roles: ['MEDICAL_OFFICER', 'ADMINISTRATOR'] },
    { to: '/assessments', icon: Shield, label: 'Assessments', roles: ['MEDICAL_OFFICER', 'ADMINISTRATOR'] },
    { to: '/memory', icon: Brain, label: 'Agent Memory', roles: ['MEDICAL_OFFICER', 'ADMINISTRATOR'] },
  ]},
  { section: 'Administration', items: [
    { to: '/users', icon: Users, label: 'Users', roles: ['ADMINISTRATOR'] },
    { to: '/connectivity', icon: Wifi, label: 'Connectivity', roles: ['ADMINISTRATOR'] },
    { to: '/sync', icon: RefreshCw, label: 'Sync Queue', roles: ['ADMINISTRATOR'] },
    { to: '/audit', icon: ScrollText, label: 'Audit Log', roles: ['ADMINISTRATOR'] },
  ]},
];

export default function DashboardLayout() {
  const { username, role, isDemo, logout, setDemo } = useAuth();
  const navigate = useNavigate();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [clock, setClock] = useState('');

  useEffect(() => {
    const update = () => setClock(new Date().toISOString().slice(11, 19) + ' UTC');
    update();
    const id = setInterval(update, 1000);
    return () => clearInterval(id);
  }, []);

  const handleLogout = () => { logout(); navigate('/login'); };

  return (
    <div className="dashboard-layout">
      <aside className={`sidebar ${sidebarOpen ? 'sidebar--open' : ''}`}>
        <div className="sidebar-brand">
          <Satellite size={20} />
          TRUSTLINE
        </div>
        <nav className="sidebar-nav">
          {NAV_ITEMS.map((section) => {
            const visible = section.items.filter((i) => i.roles.includes(role));
            if (visible.length === 0) return null;
            return (
              <div key={section.section}>
                <div className="sidebar-section">{section.section}</div>
                {visible.map((item) => (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    className={({ isActive }) => `sidebar-link ${isActive ? 'sidebar-link--active' : ''}`}
                    onClick={() => setSidebarOpen(false)}
                  >
                    <item.icon size={16} />
                    {item.label}
                  </NavLink>
                ))}
              </div>
            );
          })}
        </nav>
        <div className="sidebar-footer">
          <button className="sidebar-link" onClick={handleLogout} type="button">
            <LogOut size={16} />
            Sign Out
          </button>
        </div>
      </aside>

      <div className="content-area">
        <header className="topbar">
          <div className="topbar-left">
            <button className="hamburger" onClick={() => setSidebarOpen(!sidebarOpen)} aria-label="Toggle menu" type="button">
              {sidebarOpen ? <X size={20} /> : <Menu size={20} />}
            </button>
            <span className="topbar-clock">{clock}</span>
            <StatusDot status="nominal" label="CONNECTED" pulse />
          </div>
          <div className="topbar-right">
            <Button
              variant={isDemo ? 'danger' : 'ghost'}
              size="sm"
              onClick={() => setDemo(!isDemo)}
            >
              {isDemo ? 'DEMO MODE' : 'OPERATIONAL'}
            </Button>
            <span className="topbar-user">{username}</span>
            <Badge variant={role === 'ADMINISTRATOR' ? 'info' : role === 'MEDICAL_OFFICER' ? 'success' : 'outline'} size="sm">
              {role.replace('_', ' ')}
            </Badge>
          </div>
        </header>
        <main className="content-main">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
