import React, { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { login } from '../services/api';

export default function Login() {
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [step, setStep] = useState('email'); // 'email' or 'password'

  // Apply theme class for auth pages (they render outside ChatApp)
  useEffect(() => {
    const stored = localStorage.getItem('mediskye_theme');
    const systemDark = typeof window !== 'undefined' && window.matchMedia ? window.matchMedia('(prefers-color-scheme: dark)').matches : false;
    const isDark = stored ? stored === 'dark' : systemDark;
    if (isDark) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }, []);

  const handleEmailContinue = (e) => {
    e.preventDefault();
    const trimmed = email.trim();
    if (!trimmed) return;
    setError('');
    setEmail(trimmed);
    setStep('password');
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    const trimmed = email.trim();
    if (!trimmed) {
      setError('Please enter your email address.');
      setStep('email');
      return;
    }
    setLoading(true);
    try {
      const data = await login(trimmed, password);
      if (data.access_token) {
        const lastEmail = localStorage.getItem('mediskye_user_email');
        if (lastEmail && lastEmail.toLowerCase() !== trimmed.toLowerCase()) {
          localStorage.removeItem('mediskye_conversations');
          localStorage.removeItem('mediskye_session_id');
          localStorage.removeItem('mediskye_patient_id');
        }
        localStorage.setItem('mediskye_user_email', trimmed);
        localStorage.setItem('token', data.access_token);
        navigate('/');
      }

    } catch (err) {
      setError(err.message || 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-page">
      {/* Subtle background glow */}
      <div className="login-bg-glow" />

      <div className="login-card">
        {/* Logo */}
        <div className="login-logo">
          <div className="login-logo-icon">
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
            </svg>
          </div>
        </div>

        {/* Heading */}
        <h1 className="login-title">Welcome back</h1>
        <p className="login-subtitle">
          Sign in to MediSkye to continue analyzing your medical reports.
        </p>

        {/* Error */}
        {error && (
          <div className="login-error">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10" />
              <line x1="15" y1="9" x2="9" y2="15" />
              <line x1="9" y1="9" x2="15" y2="15" />
            </svg>
            {error}
          </div>
        )}

        {/* Step 1: Email */}
        {step === 'email' && (
          <form onSubmit={handleEmailContinue} className="login-form">
            <div className="login-field">
              <input
                id="login-email"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="Email address"
                autoFocus
                autoComplete="email"
              />
            </div>

            <button type="submit" className="login-btn-primary">
              Continue
            </button>
          </form>
        )}

        {/* Step 2: Password */}
        {step === 'password' && (
          <form onSubmit={handleSubmit} className="login-form">
            <div className="login-email-display" onClick={() => { setStep('email'); setError(''); }}>
              <span>{email}</span>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
                <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
              </svg>
            </div>

            <div className="login-field">
              <input
                id="login-password"
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Password"
                autoFocus
                autoComplete="current-password"
              />
            </div>

            <button type="submit" className="login-btn-primary" disabled={loading}>
              {loading ? (
                <span className="login-spinner" />
              ) : (
                'Sign in'
              )}
            </button>
          </form>
        )}

        {/* Divider */}
        <div className="login-divider">
          <span>OR</span>
        </div>

        {/* Switch to Register */}
        <Link to="/register" className="login-btn-secondary">
          Create a new account
        </Link>

        {/* Footer */}
        <p className="login-footer">
          MediSkye AI — Making medical reports understandable for everyone.
        </p>
      </div>
    </div>
  );
}
