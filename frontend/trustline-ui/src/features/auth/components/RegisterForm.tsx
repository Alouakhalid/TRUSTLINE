import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { UserPlus } from 'lucide-react';
import { Button } from '@/shared/components/Button';
import { Input } from '@/shared/components/Input';
import { useAuth } from '../hooks/useAuth';

export function RegisterForm() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [role, setRole] = useState('ASTRONAUT');
  const [astronautId, setAstronautId] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const { register, login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (password !== confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    if (password.length < 12) {
      setError('Password must be at least 12 characters');
      return;
    }

    setIsLoading(true);
    try {
      await register(username, password, role, astronautId || null);
      await login(username, password);
      navigate('/portal');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Registration failed');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="auth-form deck-card" noValidate>
      <div className="auth-form-header">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px', marginBottom: '8px' }}>
          <span className="dot-indicator dot-teal" />
          <span className="dark-label">[ CREW ENROLLMENT // EXP-72 ]</span>
        </div>
        <h1 className="auth-form-title">Create Account</h1>
        <p className="auth-form-subtitle">Enroll in the TRUSTLINE mission team</p>
      </div>

      {error && (
        <div className="auth-error" role="alert">
          {error}
        </div>
      )}

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
        autoComplete="new-password"
        required
        minLength={12}
        hint="Minimum 12 characters"
      />

      <Input
        label="Confirm Password"
        type="password"
        value={confirmPassword}
        onChange={(e) => setConfirmPassword(e.target.value)}
        autoComplete="new-password"
        required
      />

      <div className="input-group">
        <label htmlFor="role-select" className="input-label">Role</label>
        <select
          id="role-select"
          className="input-field"
          value={role}
          onChange={(e) => setRole(e.target.value)}
        >
          <option value="ASTRONAUT">Astronaut</option>
          <option value="MEDICAL_OFFICER">Medical Officer</option>
          <option value="ADMINISTRATOR">Administrator</option>
        </select>
      </div>

      {role === 'ASTRONAUT' && (
        <Input
          label="Astronaut ID"
          type="text"
          value={astronautId}
          onChange={(e) => setAstronautId(e.target.value)}
          placeholder="e.g. AST-001"
          hint="Your mission crew identifier"
        />
      )}

      <Button
        type="submit"
        variant="primary"
        size="lg"
        isLoading={isLoading}
        icon={<UserPlus size={18} />}
        className="auth-submit"
      >
        Create Account
      </Button>

      <p className="auth-form-footer">
        Already have an account?{' '}
        <Link to="/login" className="auth-link">
          Sign in
        </Link>
      </p>
    </form>
  );
}
