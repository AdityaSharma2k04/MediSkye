import React, { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { register } from '../services/api';

export default function Register() {
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [loading, setLoading] = useState(false);
  const [phiConsent, setPhiConsent] = useState(false);
  const [step, setStep] = useState('email'); // 'email' or 'password'

  // Apply theme class for auth pages (they render outside ChatApp)
  useEffect(() => {
    const stored = localStorage.getItem('mediskye_theme');
    const systemDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    const isDark = stored ? stored === 'dark' : systemDark;
    if (isDark) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }, []);

  const handleEmailContinue = (e) => {
    e.preventDefault();
    if (!email) return;
    setError('');
    setStep('password');
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');
    if (!phiConsent) {
      setError('You must consent to PHI processing to register.');
      return;
    }
    setLoading(true);
    try {
      await register(email, password, phiConsent);
      setSuccess('Account created! Redirecting to sign in…');
      setTimeout(() => {
        navigate('/login');
      }, 1800);
    } catch (err) {
      setError(err.message || 'Registration failed');
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
        <h1 className="login-title">Create your account</h1>
        <p className="login-subtitle">
          Join MediSkye to start understanding your medical reports in plain language.
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

        {/* Success */}
        {success && (
          <div className="login-success">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
              <polyline points="22 4 12 14.01 9 11.01" />
            </svg>
            {success}
          </div>
        )}

        {/* Step 1: Email */}
        {step === 'email' && (
          <form onSubmit={handleEmailContinue} className="login-form">
            <div className="login-field">
              <input
                id="register-email"
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
            <div className="login-email-display" onClick={() => { setStep('email'); setError(''); setSuccess(''); }}>
              <span>{email}</span>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
                <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
              </svg>
            </div>

            <div className="login-field">
              <input
                id="register-password"
                type="password"
                required
                minLength={6}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Create a password"
                autoFocus
                autoComplete="new-password"
              />
            </div>
            <p className="login-password-hint">Must be at least 6 characters</p>

            <label className="flex items-start gap-3 mt-4 mb-2 cursor-pointer group">
              <div className="relative flex items-center justify-center mt-0.5">
                <input
                  type="checkbox"
                  checked={phiConsent}
                  onChange={(e) => setPhiConsent(e.target.checked)}
                  className="peer sr-only"
                />
                <div className="w-5 h-5 rounded bg-zinc-900 border border-zinc-700 peer-checked:bg-white peer-checked:border-white transition-colors flex items-center justify-center dark:bg-zinc-900 dark:border-zinc-700 dark:peer-checked:bg-white dark:peer-checked:border-white">
                  <svg
                    className={`w-3.5 h-3.5 text-black transform transition-transform ${phiConsent ? 'scale-100' : 'scale-0'}`}
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="3"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                </div>
              </div>
              <span className="text-xs text-zinc-400 leading-relaxed group-hover:text-zinc-300 transition-colors">
                I acknowledge and consent that my Protected Health Information (PHI) will be processed by Google Gemini for AI-driven insights.
              </span>
            </label>

            <button type="submit" className="login-btn-primary" disabled={loading || !!success || !phiConsent}>
              {loading ? (
                <span className="login-spinner" />
              ) : success ? (
                'Redirecting…'
              ) : (
                'Create account'
              )}
            </button>
          </form>
        )}

        {/* Divider */}
        <div className="login-divider">
          <span>OR</span>
        </div>

        {/* Switch to Login */}
        <Link to="/login" className="login-btn-secondary">
          Already have an account? Sign in
        </Link>

        {/* Footer */}
        <p className="login-footer">
          MediSkye AI — Making medical reports understandable for everyone.
        </p>
      </div>
    </div>
  );
}
