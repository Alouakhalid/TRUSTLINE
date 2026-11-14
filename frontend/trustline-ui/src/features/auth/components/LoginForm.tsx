import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { LogIn } from 'lucide-react';
import { Button } from '@/shared/components/Button';
import { Input } from '@/shared/components/Input';
import { useAuth } from '../hooks/useAuth';

export function LoginForm() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);

    try {
      await login(username, password);
      navigate('/portal');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed');
    } finally {
      setIsLoading(false);
    }
  };

  const setQuickCreds = (u: string, p: string) => {
    setUsername(u);
    setPassword(p);
  };

  return (
    <form onSubmit={handleSubmit} className="auth-form deck-card" noValidate>
      <div className="auth-form-header">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px', marginBottom: '8px' }}>
          <span className="dot-indicator dot-teal" />
          <span className="dark-label">[ MISSION ACCESS // SECURE RBAC ]</span>
        </div>
        <h1 className="auth-form-title">Sign In</h1>
        <p className="auth-form-subtitle">Access your TRUSTLINE aerospace health portal</p>
      </div>

      {error && (
        <div className="auth-error" role="alert">
          {error}
        </div>
      )}

      {/* Quick Test Credential Pills */}
      <div style={{ marginBottom: '14px', display: 'flex', flexDirection: 'column', gap: '6px' }}>
        <span className="dark-label" style={{ fontSize: '9.5px', color: 'var(--color-muted)' }}>
          QUICK SELECT TEST PROFILE:
        </span>
        <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
          <button
            type="button"
            onClick={() => setQuickCreds('testastro', 'securepass12345')}
            className="badge badge--sm badge--outline"
            style={{ cursor: 'pointer', fontSize: '10.5px' }}
          >
            <span className="dot-indicator dot-bone" style={{ marginRight: '4px' }} />
            Astronaut (testastro)
          </button>
          <button
            type="button"
            onClick={() => setQuickCreds('doc_elena', 'securepass12345')}
            className="badge badge--sm badge--outline"
            style={{ cursor: 'pointer', fontSize: '10.5px' }}
          >
            <span className="dot-indicator dot-teal" style={{ marginRight: '4px' }} />
            Flight Surgeon (doc_elena)
          </button>
          <button
            type="button"
            onClick={() => setQuickCreds('admin_chief', 'securepass12345')}
            className="badge badge--sm badge--outline"
            style={{ cursor: 'pointer', fontSize: '10.5px' }}
          >
            <span className="dot-indicator dot-amber" style={{ marginRight: '4px' }} />
            Administrator (admin_chief)
          </button>
        </div>
      </div>

      <Input
        label="Username"
        type="text"
        value={username}
        onChange={(e) => setUsername(e.target.value)}
        autoComplete="username"
        required
        minLength={3}
      />

      <Input
        label="Password"
        type="password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        autoComplete="current-password"
        required
        minLength={12}
      />

      <Button
        type="submit"
        variant="primary"
        size="lg"
        isLoading={isLoading}
        icon={<LogIn size={18} />}
        className="auth-submit"
      >
        Sign In
      </Button>

      <p className="auth-form-footer">
        No account?{' '}
        <Link to="/register" className="auth-link">
          Create one
        </Link>
      </p>
    </form>
  );
}
