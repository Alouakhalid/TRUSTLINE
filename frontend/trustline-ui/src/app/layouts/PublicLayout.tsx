import { Outlet, Link } from 'react-router-dom';
import { Satellite } from 'lucide-react';
import { Button } from '@/shared/components/Button';

export default function PublicLayout() {
  return (
    <div className="public-layout">
      <nav className="public-nav">
        <Link to="/" className="public-nav-logo">
          <Satellite size={18} />
          TRUSTLINE
          <span className="dot-indicator dot-teal" style={{ marginLeft: '4px' }} />
          <span className="dark-label" style={{ fontSize: '10px', marginLeft: '12px', color: 'var(--color-muted)' }}>
            [ EXP-72 // DEEP SPACE MEDICAL ]
          </span>
        </Link>
        <div className="public-nav-links">
          <Link to="/login">
            <Button variant="ghost" size="sm">Sign In</Button>
          </Link>
          <Link to="/register">
            <Button variant="primary" size="sm">Get Started</Button>
          </Link>
        </div>
      </nav>
      <Outlet />
    </div>
  );
}
