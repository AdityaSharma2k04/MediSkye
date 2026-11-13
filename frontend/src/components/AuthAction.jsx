import React, { useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import {
  applyActionCode,
  auth,
  confirmPasswordReset,
  getFirebaseErrorMessage,
  verifyPasswordResetCode,
} from '../services/firebase';
import { logger } from '../services/logger';

const getActionErrorMessage = (error) => {
  if (['auth/invalid-action-code', 'auth/expired-action-code'].includes(error?.code)) {
    return 'This link is invalid or has expired. Please request a new one and try again.';
  }
  return getFirebaseErrorMessage(error);
};

const getPasswordStrength = (password) => {
  if (!password) return { level: 0, label: '', color: 'bg-slate-800' };
  if (password.length < 8) return { level: 1, label: 'Too short (min 8 characters)', color: 'bg-red-500' };
  if (password.length < 12) return { level: 2, label: 'Good password', color: 'bg-amber-400' };
  return { level: 3, label: 'Strong clinical-grade passphrase', color: 'bg-emerald-400' };
};

export default function AuthAction() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const mode = searchParams.get('mode');
  const oobCode = searchParams.get('oobCode');
  const [status, setStatus] = useState('checking');
  const [error, setError] = useState('');
  const [accountEmail, setAccountEmail] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const verificationRequest = useRef(null);
  const strength = getPasswordStrength(newPassword);

  useEffect(() => {
    let cancelled = false;
    setError('');

    if (!oobCode) {
      setError('This link is missing its verification code. Please request a new one.');
      setStatus('error');
      return () => {
        cancelled = true;
      };
    }

    if (mode === 'resetPassword') {
      setStatus('checking');
      verifyPasswordResetCode(auth, oobCode)
        .then((resolvedEmail) => {
          if (!cancelled) {
            if (typeof resolvedEmail === 'string' && resolvedEmail.trim()) {
              setAccountEmail(resolvedEmail.trim());
            }
            setStatus('ready');
          }
        })
        .catch((actionError) => {
          if (!cancelled) {
            setError(getActionErrorMessage(actionError));
            setStatus('error');
          }
        });
    } else if (mode === 'verifyEmail') {
      setStatus('processing');
      if (!verificationRequest.current || verificationRequest.current.code !== oobCode) {
        verificationRequest.current = {
          code: oobCode,
          promise: Promise.resolve().then(() => applyActionCode(auth, oobCode)),
        };
      }
      verificationRequest.current.promise
        .then(async () => {
          const currentUser = auth?.currentUser;
          if (currentUser?.reload && currentUser?.getIdToken) {
            try {
              await currentUser.reload();
              if (currentUser.emailVerified) {
                const freshToken = await currentUser.getIdToken(true);
                if (freshToken) {
                  localStorage.setItem('token', freshToken);
                  if (currentUser.email) {
                    localStorage.setItem('mediskye_user_email', currentUser.email);
                  }
                }
              }
            } catch (refreshError) {
              logger.warn('Unable to refresh the signed-in session after email verification.', refreshError);
            }
          }
          if (!cancelled) setStatus('success');
        })
        .catch((actionError) => {
          if (!cancelled) {
            setError(getActionErrorMessage(actionError));
            setStatus('error');
          }
        });
    } else {
      setError('This action link is not supported.');
      setStatus('error');
    }

    return () => {
      cancelled = true;
    };
  }, [mode, oobCode]);

  useEffect(() => {
    if (status !== 'success') return undefined;
    const redirectTimer = window.setTimeout(() => navigate('/login', { replace: true }), 3000);
    return () => window.clearTimeout(redirectTimer);
  }, [navigate, status]);

  const handlePasswordReset = async (event) => {
    event.preventDefault();
    setError('');
    if (newPassword !== confirmPassword) {
      setError('Passwords do not match.');
      return;
    }

    setSubmitting(true);
    try {
      await confirmPasswordReset(auth, oobCode, newPassword);
      setStatus('success');
    } catch (actionError) {
      setError(getActionErrorMessage(actionError));
    } finally {
      setSubmitting(false);
    }
  };

  const isPasswordReset = mode === 'resetPassword';
  const isSuccess = status === 'success';
  const isVerifyingEmail = mode === 'verifyEmail';

  return (
    <main className="login-page min-h-screen bg-obsidian text-slate-100 flex flex-col items-center justify-center px-4 py-10 relative overflow-hidden">
      <div
        className="login-bg-glow pointer-events-none absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[480px] h-[480px] rounded-full bg-cyan-500/10 blur-[130px]"
        aria-hidden="true"
      />

      <section className="login-card w-full max-w-md bg-[#0d121a] border border-white/[0.08] rounded-2xl shadow-2xl relative z-10 overflow-hidden">
        <div className="h-1 w-full bg-gradient-to-r from-cyan-500 via-cyan-400 to-sky-400" aria-hidden="true" />
        <div className="p-6 sm:p-8">
          <div className="flex items-center justify-between gap-3 pb-5 mb-6 border-b border-white/[0.06]">
            <Link to="/" className="inline-flex items-center gap-2.5 text-left group focus:outline-none">
              <div className="login-logo-icon w-9 h-9 rounded-xl bg-white text-[#07090e] flex items-center justify-center shadow-sm group-hover:scale-105 transition" aria-hidden="true">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
                </svg>
              </div>
              <div>
                <span className="block text-base font-bold tracking-tight text-white leading-none">MediSkye</span>
                <span className="block text-xs font-medium uppercase tracking-wider text-slate-400 mt-1">Clinical AI Platform</span>
              </div>
            </Link>
            <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold uppercase tracking-wider bg-cyan-500/10 text-cyan-300 border border-cyan-500/25">
              {isPasswordReset ? 'Password Reset' : 'Verify Account'}
            </span>
          </div>

          <h1 className="login-title text-2xl font-bold tracking-tight text-white mb-2">
            {isPasswordReset ? 'Reset your password' : 'Email verification'}
          </h1>
          <p className="login-subtitle text-sm text-slate-400 leading-relaxed mb-6">
            {isPasswordReset
              ? 'Choose a new password for your MediSkye account.'
              : 'Confirming your email helps keep your account secure.'}
          </p>

          {accountEmail && status === 'ready' && (
            <div className="mb-5 px-3.5 py-2.5 rounded-xl bg-[#111824] border border-white/[0.07] text-xs text-slate-400 flex items-center justify-between gap-2">
              <span>Account</span>
              <strong className="text-slate-100 font-semibold truncate">{accountEmail}</strong>
            </div>
          )}

          {error && (
            <div role="alert" className="login-error bg-red-500/10 border border-red-500/30 text-red-300 rounded-xl px-4 py-3 text-sm mb-5 flex items-start gap-2.5">
              <svg className="w-5 h-5 text-red-400 shrink-0 mt-0.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                <circle cx="12" cy="12" r="10" />
                <line x1="12" y1="8" x2="12" y2="12" />
                <line x1="12" y1="16" x2="12.01" y2="16" />
              </svg>
              <span className="leading-snug">{error}</span>
            </div>
          )}

          {status === 'checking' && (
            <div className="py-8 flex flex-col items-center justify-center text-center">
              <div className="w-10 h-10 rounded-full border-2 border-cyan-500/20 border-t-cyan-400 animate-spin mb-4" aria-hidden="true" />
              <p role="status" className="text-sm font-medium text-slate-300">Checking your secure link...</p>
              <p className="text-xs text-slate-500 mt-1">Validating your single-use security token</p>
            </div>
          )}

          {status === 'processing' && (
            <div className="py-8 flex flex-col items-center justify-center text-center">
              <div className="w-10 h-10 rounded-full border-2 border-cyan-500/20 border-t-cyan-400 animate-spin mb-4" aria-hidden="true" />
              <p role="status" className="text-sm font-medium text-slate-300">Verifying your email...</p>
              <p className="text-xs text-slate-500 mt-1">Activating your encrypted MediSkye workspace</p>
            </div>
          )}

          {status === 'ready' && isPasswordReset && (
            <form onSubmit={handlePasswordReset} className="login-form space-y-4">
              <div className="login-field">
                <label htmlFor="new-password" className="block text-xs font-medium text-slate-300 mb-1.5">New password</label>
                <div className="relative">
                  <input
                    id="new-password"
                    type={showPassword ? 'text' : 'password'}
                    value={newPassword}
                    onChange={(event) => setNewPassword(event.target.value)}
                    placeholder="New Password"
                    aria-label="New Password"
                    autoComplete="new-password"
                    minLength={8}
                    required
                    className="w-full rounded-xl bg-[#111824] border border-white/10 focus:border-cyan-500/50 focus:outline-none px-3.5 py-2.5 pr-16 text-sm text-white placeholder-slate-500 transition"
                  />
                  <button type="button" onClick={() => setShowPassword((previous) => !previous)} className="absolute right-3 top-1/2 -translate-y-1/2 text-xs font-medium text-slate-400 hover:text-slate-200 transition">
                    {showPassword ? 'Hide' : 'Show'}
                  </button>
                </div>
                {newPassword.length > 0 && (
                  <div className="mt-2">
                    <div className="grid grid-cols-3 gap-1.5 h-1" aria-hidden="true">
                      {[1, 2, 3].map((bar) => (
                        <div key={bar} className={`rounded-full transition-colors ${strength.level >= bar ? strength.color : 'bg-slate-800'}`} />
                      ))}
                    </div>
                    <p className="text-xs text-slate-400 mt-1">{strength.label}</p>
                  </div>
                )}
              </div>

              <div className="login-field">
                <label htmlFor="confirm-password" className="block text-xs font-medium text-slate-300 mb-1.5">Confirm new password</label>
                <input
                  id="confirm-password"
                  type={showPassword ? 'text' : 'password'}
                  value={confirmPassword}
                  onChange={(event) => setConfirmPassword(event.target.value)}
                  placeholder="Confirm Password"
                  aria-label="Confirm Password"
                  autoComplete="new-password"
                  minLength={8}
                  required
                  className="w-full rounded-xl bg-[#111824] border border-white/10 focus:border-cyan-500/50 focus:outline-none px-3.5 py-2.5 text-sm text-white placeholder-slate-500 transition"
                />
              </div>

              <p className="text-xs text-slate-500 leading-relaxed">
                Tip: A 12+ character phrase like <span className="text-slate-300">blue coffee morning</span> is strong and easy to remember.
              </p>
              <button type="submit" className="login-btn-primary w-full rounded-xl py-3 px-4 bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-semibold text-sm shadow-sm shadow-cyan-500/20 transition disabled:opacity-50" disabled={submitting}>
                {submitting ? 'Resetting...' : 'Reset Password'}
              </button>
            </form>
          )}

          {isSuccess && (
            <div className="text-center py-2">
              <div className="w-12 h-12 rounded-2xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 flex items-center justify-center mx-auto mb-4" aria-hidden="true">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="20 6 9 17 4 12" />
                </svg>
              </div>
              <div role="status" className="login-success bg-emerald-500/10 border border-emerald-500/25 text-emerald-300 rounded-xl px-4 py-3 text-sm font-medium mb-4">
                {isVerifyingEmail
                  ? 'Email Verified! You can now log in.'
                  : 'Your password has been reset successfully. You can now log in.'}
              </div>
              <p className="text-xs text-slate-400 mb-5">Redirecting to login in 3 seconds...</p>
              <Link to="/login" className="login-btn-primary w-full inline-flex items-center justify-center rounded-xl py-3 px-4 bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-semibold text-sm shadow-sm shadow-cyan-500/20 transition">
                Go to Login
              </Link>
            </div>
          )}

          {status === 'error' && (
            <div className="pt-2 text-center">
              <Link to="/login" className="w-full inline-flex items-center justify-center rounded-xl py-2.5 px-4 bg-white/[0.05] hover:bg-white/[0.09] border border-white/10 text-sm font-medium text-cyan-400 hover:text-cyan-300 transition">
                Return to login
              </Link>
            </div>
          )}
        </div>
      </section>
    </main>
  );
}
