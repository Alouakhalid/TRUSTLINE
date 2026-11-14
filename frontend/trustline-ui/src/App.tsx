import { useEffect, useState } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { useAuthStore } from '@/features/auth/stores/auth-store';

import PublicLayout from '@/app/layouts/PublicLayout';
import DashboardLayout from '@/app/layouts/DashboardLayout';
import LandingPage from '@/app/routes/LandingPage';

import AstronautPortal from '@/app/routes/AstronautPortal';
import MedicalPortal from '@/app/routes/MedicalPortal';
import AdminPortal from '@/app/routes/AdminPortal';

import ChatPage from '@/app/routes/ChatPage';
import VitalsPage from '@/app/routes/VitalsPage';
import TwinPage from '@/app/routes/TwinPage';
import SimulatorPage from '@/app/routes/SimulatorPage';
import DocumentsPage from '@/app/routes/DocumentsPage';
import AssessmentsPage from '@/app/routes/AssessmentsPage';
import MemoryPage from '@/app/routes/MemoryPage';
import UsersPage from '@/app/routes/UsersPage';
import ConnectivityPage from '@/app/routes/ConnectivityPage';
import SyncPage from '@/app/routes/SyncPage';
import AuditPage from '@/app/routes/AuditPage';

function ProtectedRoute({ children, allowedRoles }: { children: React.ReactNode; allowedRoles?: string[] }) {
  const { token, role, initDirectEntry } = useAuthStore();
  const [initializing, setInitializing] = useState(!token);

  useEffect(() => {
    if (!token) {
      initDirectEntry().finally(() => setInitializing(false));
    } else {
      setInitializing(false);
    }
  }, [token, initDirectEntry]);

  if (initializing) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh', background: 'var(--color-bg)' }}>
        <div className="dark-label" style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <span className="dot-indicator dot-teal animate-pulse" />
          ESTABLISHING SECURE MISSION CONTROL TELEMETRY SESSION...
        </div>
      </div>
    );
  }

  if (allowedRoles && !allowedRoles.includes(role)) return <Navigate to="/portal" replace />;
  return <>{children}</>;
}

export default function App() {
  const { role } = useAuthStore();

  const getDefaultPortal = () => {
    switch (role) {
      case 'MEDICAL_OFFICER': return '/medical';
      case 'ADMINISTRATOR': return '/admin';
      default: return '/astronaut';
    }
  };

  return (
    <Routes>
      <Route element={<PublicLayout />}>
        <Route path="/" element={<LandingPage />} />
        {/* Legacy login & registration routes redirect directly into Mission Control */}
        <Route path="/login" element={<Navigate to="/portal" replace />} />
        <Route path="/register" element={<Navigate to="/portal" replace />} />
      </Route>

      <Route element={<ProtectedRoute><DashboardLayout /></ProtectedRoute>}>
        <Route path="/portal" element={<Navigate to={getDefaultPortal()} replace />} />
        
        {/* Core Mission Routes */}
        <Route path="/astronaut" element={<AstronautPortal />} />
        <Route path="/chat" element={<ChatPage />} />
        <Route path="/vitals" element={<VitalsPage />} />
        <Route path="/twin" element={<TwinPage />} />
        <Route path="/simulator" element={<SimulatorPage />} />

        {/* Clinical & Medical Routes */}
        <Route path="/medical" element={<ProtectedRoute allowedRoles={['MEDICAL_OFFICER', 'ADMINISTRATOR']}><MedicalPortal /></ProtectedRoute>} />
        <Route path="/documents" element={<ProtectedRoute allowedRoles={['MEDICAL_OFFICER', 'ADMINISTRATOR']}><DocumentsPage /></ProtectedRoute>} />
        <Route path="/assessments" element={<AssessmentsPage />} />
        <Route path="/memory" element={<ProtectedRoute allowedRoles={['MEDICAL_OFFICER', 'ADMINISTRATOR']}><MemoryPage /></ProtectedRoute>} />

        {/* Administration Routes */}
        <Route path="/admin" element={<ProtectedRoute allowedRoles={['ADMINISTRATOR']}><AdminPortal /></ProtectedRoute>} />
        <Route path="/users" element={<ProtectedRoute allowedRoles={['ADMINISTRATOR']}><UsersPage /></ProtectedRoute>} />
        <Route path="/connectivity" element={<ProtectedRoute allowedRoles={['ADMINISTRATOR']}><ConnectivityPage /></ProtectedRoute>} />
        <Route path="/sync" element={<ProtectedRoute allowedRoles={['ADMINISTRATOR']}><SyncPage /></ProtectedRoute>} />
        <Route path="/audit" element={<ProtectedRoute allowedRoles={['ADMINISTRATOR']}><AuditPage /></ProtectedRoute>} />
      </Route>

      {/* Catch-all redirect */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
