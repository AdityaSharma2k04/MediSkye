import React, { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import {
  auth,
  googleProvider,
  signInWithPopup,
  createUserWithEmailAndPassword,
  updateProfile,
  getFirebaseErrorMessage,
} from '../services/firebase';

export default function Register() {
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [fullName, setFullName] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [loading, setLoading] = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);
  const [phiConsent, setPhiConsent] = useState(false);
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

  const handleGoogleSignIn = async () => {
    setError('');
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
        navigate('/');
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
    const trimmedEmail = email.trim().toLowerCase();
    if (!trimmedEmail) return;
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(trimmedEmail)) {
      setError('Please enter a valid email address.');
      return;
    }
    setError('');
    setEmail(trimmedEmail);
    setStep('password');
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');

    const trimmedEmail = email.trim().toLowerCase();
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!trimmedEmail || !emailRegex.test(trimmedEmail)) {
      setError('Please enter a valid email address.');
      setStep('email');
      return;
    }

    if (!password || password.length < 8) {
      setError('Password must be at least 8 characters.');
      return;
    }

    if (password.length > 72) {
      setError('Password cannot exceed 72 characters.');
      return;
    }

    if (!phiConsent) {
      setError('You must consent to PHI processing to register.');
      return;
    }

    setLoading(true);
    try {
      const userCredential = await createUserWithEmailAndPassword(auth, trimmedEmail, password);
      
      let token;
      if (fullName && fullName.trim()) {
        try {
          await updateProfile(userCredential.user, { displayName: fullName.trim() });
        } catch (e) {
          // Non-critical if display name update fails
        }
        token = await userCredential.user.getIdToken(true);
      } else {
        token = await userCredential.user.getIdToken();
      }

      const userEmail = userCredential.user?.email || trimmedEmail;
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

      setSuccess('Account created! Redirecting to MediSkye…');
      setTimeout(() => {
        navigate('/');
      }, 600);
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

        {/* Google Sign In as primary action */}
        <button
          type="button"
          id="register-google-btn"
          onClick={handleGoogleSignIn}
          disabled={googleLoading || loading}
          className="login-btn-google"
          aria-label="Sign up with Google"
        >
          {googleLoading ? (
            <>
              <span className="login-google-spinner" />
              <span>Signing up with Google...</span>
            </>
          ) : (
            <>
              <svg width="20" height="20" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
                <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
                <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
                <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/>
                <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
              </svg>
              <span>Sign up with Google</span>
            </>
          )}
        </button>

        {/* Divider */}
        <div className="login-divider login-divider-subtle">
          <span>or continue with email</span>
        </div>

        {/* Step 1: Email */}
        {step === 'email' && (
          <form onSubmit={handleEmailContinue} className="login-form">
            <div className="login-field">
              <input
                id="register-email"
                type="email"
                required
                value={email}
                onChange={(e) => {
                  setEmail(e.target.value);
                  if (error) setError('');
                }}
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
                id="register-fullname"
                type="text"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder="Full name (optional)"
                autoComplete="name"
              />
            </div>

            <div className="login-field">
              <input
                id="register-password"
                type="password"
                required
                minLength={8}
                maxLength={72}
                value={password}
                onChange={(e) => {
                  setPassword(e.target.value);
                  if (error) setError('');
                }}
                placeholder="Create a password"
                autoFocus
                autoComplete="new-password"
              />
            </div>
            <p className="login-password-hint">Must be 8 to 72 characters</p>

            <label className="flex items-start gap-3 mt-4 mb-2 cursor-pointer group select-none">
              <div className="relative flex items-center justify-center mt-0.5 flex-shrink-0">
                <input
                  id="register-phi-consent"
                  type="checkbox"
                  checked={phiConsent}
                  onChange={(e) => {
                    setPhiConsent(e.target.checked);
                    if (error && error.includes('consent')) setError('');
                  }}
                  className="sr-only"
                />
                <div
                  className={`w-5 h-5 rounded border transition-colors flex items-center justify-center ${
                    phiConsent
                      ? 'bg-zinc-900 border-zinc-900 dark:bg-white dark:border-white text-white dark:text-zinc-900'
                      : 'bg-transparent border-zinc-400 dark:border-zinc-600 hover:border-zinc-500'
                  }`}
                >
                  <svg
                    className={`w-3.5 h-3.5 transform transition-transform ${phiConsent ? 'scale-100' : 'scale-0'}`}
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
              <span className="text-xs text-zinc-600 dark:text-zinc-400 leading-relaxed group-hover:text-zinc-900 dark:group-hover:text-zinc-200 transition-colors">
                I acknowledge and consent that my Protected Health Information (PHI) will be processed by Google Gemini for AI-driven insights.
              </span>
            </label>

            <button type="submit" className="login-btn-primary" disabled={loading || !!success}>
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
