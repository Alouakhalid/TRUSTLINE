import { RegisterForm } from '@/features/auth';

export default function RegisterPage() {
  return (
    <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '40px 16px' }}>
      <RegisterForm />
    </div>
  );
}
