import React, { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import {
  auth,
  googleProvider,
  signInWithPopup,
  signInWithEmailAndPassword,
  sendPasswordResetEmail,
  getFirebaseErrorMessage,
} from '../services/firebase';
import { useTranslation } from 'react-i18next';

export default function Login() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);
  const [resetLoading, setResetLoading] = useState(false);
  const [resetSuccessMessage, setResetSuccessMessage] = useState('');
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

  const handleForgotPassword = async (e) => {
    e.preventDefault();
    setError('');
    setResetSuccessMessage('');

    const trimmedEmail = email.trim();
    if (!trimmedEmail) {
      setError("Please enter your email address in the field above first, then click 'Forgot password?'.");
      return;
    }

    setResetLoading(true);
    try {
      await sendPasswordResetEmail(auth, trimmedEmail);
      setResetSuccessMessage(
        `Password reset link sent to ${trimmedEmail}. Please check your inbox (and Spam folder).`
      );
    } catch (err) {
      setError(getFirebaseErrorMessage(err));
    } finally {
      setResetLoading(false);
    }
  };

  const handleGoogleSignIn = async () => {
    setError('');
    setResetSuccessMessage('');
    setGoogleLoading(true);
    try {
      const result = await signInWithPopup(auth, googleProvider);
      if (result && result.user) {
        const token = await result.user.getIdToken();
        const userEmail = result.user.email || '';
        const lastEmail = localStorage.getItem('mediskye_user_email');
        if (lastEmail && userEmail && lastEmail.toLowerCase() !== userEmail.toLowerCase()) {
          localStorage.removeItem('mediskye_conversations');
          localStorage.removeItem('mediskye_session_id');
          localStorage.removeItem('mediskye_patient_id');
        }
        if (userEmail) {
          localStorage.setItem('mediskye_user_email', userEmail);
        }
        localStorage.setItem('token', token);
        navigate('/chat');
      }
    } catch (err) {
      if (err.code === 'auth/popup-closed-by-user' || err.code === 'auth/cancelled-popup-request') {
        return;
      }
      setError(getFirebaseErrorMessage(err));
    } finally {
      setGoogleLoading(false);
    }
  };

  const handleEmailContinue = (e) => {
    e.preventDefault();
    const trimmed = email.trim().toLowerCase();
    if (!trimmed) return;
    setError('');
    setResetSuccessMessage('');
    setEmail(trimmed);
    setStep('password');
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setResetSuccessMessage('');
    const trimmed = email.trim().toLowerCase();
    if (!trimmed) {
      setError('Please enter your email address.');
      setStep('email');
      return;
    }
    setLoading(true);
    try {
      const userCredential = await signInWithEmailAndPassword(auth, trimmed, password);
      const token = await userCredential.user.getIdToken();
      const userEmail = userCredential.user.email || trimmed;
      const lastEmail = localStorage.getItem('mediskye_user_email');
      if (lastEmail && userEmail && lastEmail.toLowerCase() !== userEmail.toLowerCase()) {
        localStorage.removeItem('mediskye_conversations');
        localStorage.removeItem('mediskye_session_id');
        localStorage.removeItem('mediskye_patient_id');
      }
      if (userEmail) {
        localStorage.setItem('mediskye_user_email', userEmail);
      }
      localStorage.setItem('token', token);
      navigate('/chat');
    } catch (err) {
      setError(getFirebaseErrorMessage(err));
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
        <h1 className="login-title">{t('auth.login_title', 'Welcome back')}</h1>
        <p className="login-subtitle">
          {t('auth.login_subtitle', 'Sign in to MediSkye to continue analyzing your medical reports.')}
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

        {/* Google Sign In as primary action */}
        <button
          type="button"
          id="login-google-btn"
          onClick={handleGoogleSignIn}
          disabled={googleLoading || loading}
          className="login-btn-google"
          aria-label={t('auth.google_continue', 'Continue with Google')}
        >
          {googleLoading ? (
            <>
              <span className="login-google-spinner" />
              <span>{t('auth.google_signing_in', 'Signing in with Google...')}</span>
            </>
          ) : (
            <>
              <svg width="20" height="20" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
                <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
                <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
                <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/>
                <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
              </svg>
              <span>{t('auth.google_continue', 'Continue with Google')}</span>
            </>
          )}
        </button>

        {/* Divider */}
        <div className="login-divider login-divider-subtle">
          <span>{t('auth.or_email', 'or continue with email')}</span>
        </div>

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
                placeholder={t('auth.email_placeholder', 'Email address')}
                autoFocus
                autoComplete="email"
              />
            </div>

            <div className="login-forgot-wrapper">
              <button
                type="button"
                onClick={handleForgotPassword}
                disabled={resetLoading || loading}
                className="login-forgot-btn"
              >
                {resetLoading ? t('auth.sending_reset', 'Sending reset link...') : t('auth.forgot_password', 'Forgot password?')}
              </button>
            </div>

            {resetSuccessMessage && (
              <div className="login-success">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
                  <polyline points="22 4 12 14.01 9 11.01" />
                </svg>
                {resetSuccessMessage}
              </div>
            )}

            <button type="submit" className="login-btn-primary">
              {t('auth.continue', 'Continue')}
            </button>
          </form>
        )}

        {/* Step 2: Password */}
        {step === 'password' && (
          <form onSubmit={handleSubmit} className="login-form">
            <div className="login-email-display" onClick={() => { setStep('email'); setError(''); setResetSuccessMessage(''); }}>
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
                placeholder={t('auth.password_placeholder', 'Password')}
                autoFocus
                autoComplete="current-password"
              />
            </div>

            <div className="login-forgot-wrapper">
              <button
                type="button"
                onClick={handleForgotPassword}
                disabled={resetLoading || loading}
                className="login-forgot-btn"
              >
                {resetLoading ? t('auth.sending_reset', 'Sending reset link...') : t('auth.forgot_password', 'Forgot password?')}
              </button>
            </div>

            {resetSuccessMessage && (
              <div className="login-success">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
                  <polyline points="22 4 12 14.01 9 11.01" />
                </svg>
                {resetSuccessMessage}
              </div>
            )}

            <button type="submit" className="login-btn-primary" disabled={loading}>
              {loading ? (
                <span className="login-spinner" />
              ) : (
                t('auth.sign_in', 'Sign in')
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
          {t('auth.switch_to_register', 'Create a new account')}
        </Link>

        {/* Footer */}
        <p className="login-footer">
          {t('auth.tagline', 'MediSkye AI — Making medical reports understandable for everyone.')}
        </p>
      </div>
    </div>
  );
}
