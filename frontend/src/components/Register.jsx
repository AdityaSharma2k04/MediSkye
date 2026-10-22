import React, { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import {
  auth,
  googleProvider,
  signInWithPopup,
  createUserWithEmailAndPassword,
  updateProfile,
  signOut,
  getFirebaseErrorMessage,
} from '../services/firebase';
import api from '../services/api';
import { useTranslation } from 'react-i18next';
import { Eye, EyeOff } from 'lucide-react';

export const validatePassword = (pass) => {
  if (!pass || pass.length < 8) return "Password must be at least 8 characters.";
  if (pass.length > 64) return "Password cannot exceed 64 characters.";

  const weakPasswords = new Set([
    "password",
    "12345678",
    "123456789",
    "11111111",
    "qwerty123",
    "qwertyui",
    "mediskye",
  ]);

  const lower = pass.toLowerCase();
  const isRepeatedChar =
    pass.length > 1 &&
    pass.split('').every((c) => c.toLowerCase() === pass[0].toLowerCase());

  if (weakPasswords.has(lower) || isRepeatedChar) {
    return "This password is too common. Please choose a stronger one.";
  }

  return null; // Valid
};

export const getPasswordStrength = (pass) => {
  if (!pass || pass.length < 8 || validatePassword(pass) !== null) {
    return {
      level: 'weak',
      label: 'Weak',
      color: '#ef4444', // Red
      score: 1,
      allowsSubmit: false,
    };
  }
  if (pass.length < 12) {
    return {
      level: 'fair',
      label: 'Fair',
      color: '#f59e0b', // Amber
      score: 2,
      allowsSubmit: true,
    };
  }
  return {
    level: 'strong',
    label: 'Strong',
    color: '#10b981', // Emerald/Green
    score: 3,
    allowsSubmit: true,
  };
};

export default function Register() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [fullName, setFullName] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [isRegistered, setIsRegistered] = useState(false);
  const [loading, setLoading] = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);
  const [phiConsent, setPhiConsent] = useState(false);
  const [step, setStep] = useState('email'); // 'email' or 'password'

  const passwordStrength = getPasswordStrength(password);
  const isPasswordMismatch = confirmPassword.length > 0 && password !== confirmPassword;

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
    const trimmedEmail = email.trim().toLowerCase();
    if (!trimmedEmail) return;
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(trimmedEmail)) {
      setError("Please enter a valid email address (e.g., name@example.com).");
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
      setError("Please enter a valid email address (e.g., name@example.com).");
      setStep('email');
      return;
    }

    const passwordError = validatePassword(password);
    if (passwordError) {
      setError(passwordError);
      return;
    }

    if (password !== confirmPassword) {
      setError('Passwords do not match.');
      return;
    }

    if (!phiConsent) {
      setError('You must consent to PHI processing to register.');
      return;
    }

    setLoading(true);
    try {
      const userCredential = await createUserWithEmailAndPassword(auth, trimmedEmail, password);
      
      if (fullName && fullName.trim()) {
        try {
          await updateProfile(userCredential.user, { displayName: fullName.trim() });
        } catch (e) {
          // Non-critical if display name update fails
        }
      }

      await api.post('/auth/send-custom-verification', { email: trimmedEmail });
      await signOut(auth);

      const successMsg = `Account created! We've sent a verification link to ${trimmedEmail}. Please check your inbox.`;
      setSuccess(successMsg);
      setIsRegistered(true);

      setTimeout(() => {
        navigate('/login');
      }, 4000);
    } catch (err) {
      if (err.code === 'auth/email-already-in-use') {
        setError("An account with this email already exists. Please log in or reset your password.");
      } else {
        setError(getFirebaseErrorMessage(err));
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-page">
      {/* Subtle background glow */}
      <div className="login-bg-glow" />

      <div className="login-card bg-[#0e131b] border border-white/[0.08]">
        {/* Logo */}
        <div className="login-logo">
          <div className="login-logo-icon">
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
            </svg>
          </div>
        </div>

        {/* Heading */}
        <h1 className="login-title">{t('auth.register_title', 'Create your account')}</h1>
        <p className="login-subtitle">
          {t('auth.register_subtitle', 'Join MediSkye to start understanding your medical reports in plain language.')}
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

        {/* Success Screen / Modal after Email Registration */}
        {isRegistered ? (
          <div className="text-center py-4 space-y-4">
            <div className="w-14 h-14 rounded-full bg-emerald-500/10 text-emerald-400 mx-auto flex items-center justify-center">
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
                <polyline points="22 4 12 14.01 9 11.01" />
              </svg>
            </div>
            <h2 className="login-title text-xl font-semibold">{t('auth.verify_email_title', 'Verify your email')}</h2>
            <p className="login-subtitle text-sm" style={{ marginBottom: 24 }}>
              Account created! We've sent a verification link to <strong className="text-zinc-900 dark:text-zinc-100">{email}</strong>. Please verify your email before logging in.
            </p>
            <button
              type="button"
              id="register-go-to-login-btn"
              onClick={() => navigate('/login')}
              className="login-btn-primary bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-semibold transition"
            >
              {t('auth.go_to_login', 'Go to Login')}
            </button>
          </div>
        ) : (
          <>
            {/* Google Sign In as primary action */}
            <button
              type="button"
              id="register-google-btn"
              onClick={handleGoogleSignIn}
              disabled={googleLoading || loading}
              className="login-btn-google"
              aria-label={t('auth.google_signup', 'Sign up with Google')}
            >
              {googleLoading ? (
                <>
                  <span className="login-google-spinner" />
                  <span>{t('auth.google_signing_up', 'Signing up with Google...')}</span>
                </>
              ) : (
                <>
                  <svg width="20" height="20" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
                    <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
                    <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
                    <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/>
                    <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
                  </svg>
                  <span>{t('auth.google_signup', 'Sign up with Google')}</span>
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
                    id="register-email"
                    type="email"
                    required
                    value={email}
                    onChange={(e) => {
                      setEmail(e.target.value);
                      if (error) setError('');
                    }}
                    placeholder={t('auth.email_placeholder', 'Email address')}
                    autoFocus
                    autoComplete="email"
                  />
                </div>

                <button type="submit" className="login-btn-primary bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-semibold transition">
                  {t('auth.continue', 'Continue')}
                </button>
              </form>
            )}

            {/* Step 2: Password */}
            {step === 'password' && (
              <form onSubmit={handleSubmit} className="login-form">
                <div className="login-email-display" onClick={() => { setStep('email'); setError(''); setSuccess(''); setConfirmPassword(''); }}>
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
                    placeholder={t('auth.fullname_placeholder', 'Full name (optional)')}
                    autoComplete="name"
                  />
                </div>

                <div className="login-field">
                  <input
                    id="register-password"
                    type={showPassword ? 'text' : 'password'}
                    required
                    minLength={8}
                    maxLength={64}
                    value={password}
                    onChange={(e) => {
                      setPassword(e.target.value);
                      if (error) setError('');
                    }}
                    placeholder={t('auth.create_password_placeholder', 'Create a password')}
                    autoFocus
                    autoComplete="new-password"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="login-field-toggle"
                    aria-label="Toggle password visibility"
                  >
                    {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>

                {/* Password Strength Indicator & Friendly Hint */}
                <div className="login-password-strength-container" style={{ marginTop: '0.375rem', marginBottom: '0.625rem' }}>
                  {password.length > 0 && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.375rem' }}>
                      <div
                        style={{
                          flex: 1,
                          height: '4px',
                          backgroundColor: 'rgba(161, 161, 170, 0.2)',
                          borderRadius: '2px',
                          display: 'flex',
                          gap: '4px',
                        }}
                      >
                        <div
                          style={{
                            flex: 1,
                            backgroundColor: passwordStrength.color,
                            borderRadius: '2px',
                            transition: 'background-color 0.2s',
                          }}
                        />
                        <div
                          style={{
                            flex: 1,
                            backgroundColor:
                              passwordStrength.score >= 2
                                ? passwordStrength.color
                                : 'rgba(161, 161, 170, 0.2)',
                            borderRadius: '2px',
                            transition: 'background-color 0.2s',
                          }}
                        />
                        <div
                          style={{
                            flex: 1,
                            backgroundColor:
                              passwordStrength.score >= 3
                                ? passwordStrength.color
                                : 'rgba(161, 161, 170, 0.2)',
                            borderRadius: '2px',
                            transition: 'background-color 0.2s',
                          }}
                        />
                      </div>
                      <span
                        style={{
                          fontSize: '0.75rem',
                          fontWeight: 600,
                          color: passwordStrength.color,
                          minWidth: '42px',
                          textAlign: 'right',
                        }}
                      >
                        {passwordStrength.label}
                      </span>
                    </div>
                  )}
                  <p className="login-password-hint" style={{ fontSize: '0.75rem', color: '#71717a', margin: 0, lineHeight: 1.4 }}>
                    {t(
                      'auth.password_hint',
                      "Minimum 8 characters. Tip: A 12+ character phrase like 'blue coffee morning' is easiest to remember."
                    )}
                  </p>
                </div>

                <div className="login-field">
                  <input
                    id="register-confirm-password"
                    type={showConfirmPassword ? 'text' : 'password'}
                    required
                    minLength={8}
                    maxLength={64}
                    value={confirmPassword}
                    onChange={(e) => {
                      setConfirmPassword(e.target.value);
                      if (error) setError('');
                    }}
                    placeholder={t('auth.confirm_password_placeholder', 'Confirm password')}
                    autoComplete="new-password"
                    className={isPasswordMismatch ? 'border-red-500' : ''}
                    style={isPasswordMismatch ? { borderColor: '#ef4444' } : undefined}
                  />
                  <button
                    type="button"
                    onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                    className="login-field-toggle"
                    aria-label="Toggle confirm password visibility"
                  >
                    {showConfirmPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>

                {isPasswordMismatch && (
                  <p
                    id="register-confirm-password-error"
                    className="text-red-500 text-xs mt-1 font-medium"
                    style={{ color: '#ef4444', fontSize: '0.75rem', marginTop: '0.25rem', marginBottom: '0.25rem' }}
                  >
                    {t('auth.passwords_do_not_match', 'Passwords do not match.')}
                  </p>
                )}

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
                    {t('auth.phi_consent', 'I acknowledge and consent that my Protected Health Information (PHI) will be processed by Google Gemini for AI-driven insights.')}
                  </span>
                </label>

                <button type="submit" className="login-btn-primary bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-semibold transition" disabled={loading || !!success || isPasswordMismatch}>
                  {loading ? (
                    <span className="login-spinner" />
                  ) : success ? (
                    t('auth.redirecting', 'Redirecting…')
                  ) : (
                    t('auth.create_account', 'Create account')
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
              {t('auth.switch_to_login', 'Already have an account? Sign in')}
            </Link>
          </>
        )}

        {/* Footer */}
        <p className="login-footer">
          {t('auth.tagline', 'MediSkye AI — Making medical reports understandable for everyone.')}
        </p>
      </div>
    </div>
  );
}
