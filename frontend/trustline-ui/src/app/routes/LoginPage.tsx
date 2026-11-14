import { LoginForm } from '@/features/auth';

export default function LoginPage() {
  return (
    <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '40px 16px' }}>
      <LoginForm />
    </div>
  );
}
