import React, { useState } from 'react';
import {
  auth,
  googleProvider,
  GoogleAuthProvider,
  signInWithPopup,
  getFirebaseErrorMessage,
  saveAuthSession,
} from '../services/firebase';
import { BrandMark } from './workbench/Brand';

export default function ExternalAuthLanding() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [signedInEmail, setSignedInEmail] = useState('');
  const [redirectTargetUrl, setRedirectTargetUrl] = useState('');

  const handleSelectAccount = async () => {
    setError('');
    setLoading(true);

    try {
      // Direct call preserves browser user gesture
      const result = await signInWithPopup(auth, googleProvider);
      const cred = GoogleAuthProvider.credentialFromResult(result);
      const idToken = cred?.idToken || (await result.user.getIdToken());
      const accessToken = cred?.accessToken || '';
      saveAuthSession(result.user, idToken);

      if (!idToken && !accessToken) {
        throw new Error('Google authentication succeeded but no valid token was returned. Please try again.');
      }

      const callbackUrl = `/__native_auth_done?id_token=${encodeURIComponent(idToken)}&access_token=${encodeURIComponent(accessToken)}`;
      try {
        await fetch(callbackUrl, { method: 'GET', cache: 'no-store' });
      } catch (_) {}

      const isAndroid = typeof navigator !== 'undefined' && /Android/i.test(navigator.userAgent || '');
      const urlParams = typeof window !== 'undefined' ? new URLSearchParams(window.location.search) : null;
      const port = urlParams?.get('port');

      let targetUrl = '';
      if (isAndroid) {
        targetUrl =
          'intent://auth-callback?id_token=' +
          encodeURIComponent(idToken) +
          '&access_token=' +
          encodeURIComponent(accessToken) +
          '#Intent;scheme=mediskye;package=com.mediskye.app;end';
      } else if (port) {
        targetUrl = `http://127.0.0.1:${port}/auth-callback?id_token=${encodeURIComponent(idToken)}&access_token=${encodeURIComponent(accessToken)}`;
      } else {
        targetUrl = callbackUrl;
      }

      setRedirectTargetUrl(targetUrl);
      setSignedInEmail(result.user?.email || 'User');

      try {
        window.location.replace(targetUrl);
      } catch (_) {
        try {
          window.location.href = targetUrl;
        } catch (__) {}
      }

      if (!isAndroid) {
        setTimeout(() => {
          try {
            window.close();
          } catch (_) {}
        }, 1200);
      }
    } catch (err) {
      setError(getFirebaseErrorMessage(err) || err.message || 'Authentication failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#F8FAFC] text-slate-900 flex items-center justify-center p-6 selection:bg-cyan-500/30">
      <div className="w-full max-w-md bg-white border border-slate-200 rounded-2xl p-8 shadow-xl text-center space-y-6">
        {/* Brand Header */}
        <div className="flex items-center justify-center gap-3">
          <BrandMark size={38} />
          <span className="text-xl font-bold tracking-tight text-slate-900">MediSkye</span>
        </div>

        {signedInEmail ? (
          <div className="space-y-4 animate-fade-in" data-testid="auth-success-container">
            <div className="w-12 h-12 rounded-full bg-emerald-50 border border-emerald-200 text-emerald-700 flex items-center justify-center mx-auto shadow-sm">
              <svg className="w-6 h-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M20 6L9 17l-5-5" />
              </svg>
            </div>
            <div className="space-y-1">
              <h2 className="text-lg font-semibold text-slate-900">Signed in as {signedInEmail}</h2>
              <p className="text-sm text-cyan-800 font-medium">Sign-in verified! Redirecting you back to MediSkye...</p>
            </div>

            {redirectTargetUrl && (
              <div className="pt-2">
                <a
                  href={redirectTargetUrl}
                  onClick={() => {
                    try {
                      window.location.href = redirectTargetUrl;
                    } catch (_) {}
                  }}
                  className="inline-block py-3 px-5 rounded-xl bg-cyan-600 text-white font-semibold text-sm hover:bg-cyan-700 active:scale-[0.98] transition shadow-md cursor-pointer"
                >
                  Open MediSkye App — Click here if not redirected automatically
                </a>
              </div>
            )}
          </div>
        ) : (
          <>
            <div className="space-y-2">
              <h2 className="text-lg font-semibold text-cyan-800">Google Account Sign-In</h2>
              <p className="text-sm text-slate-600">
                Sign in securely with Google to continue to your MediSkye health records.
              </p>
            </div>

            {error && (
              <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl text-rose-700 text-xs text-left">
                {error}
              </div>
            )}

            <button
              type="button"
              onClick={handleSelectAccount}
              disabled={loading}
              className="w-full py-3.5 px-5 rounded-xl font-medium text-sm flex items-center justify-center gap-3 bg-white border border-slate-200 text-slate-900 hover:bg-slate-50 active:scale-[0.98] transition shadow-sm disabled:opacity-50 cursor-pointer"
            >
              <svg className="w-4 h-4 shrink-0" viewBox="0 0 24 24">
                <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
                <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
                <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z" />
                <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z" />
              </svg>
              <span>{loading ? 'Opening Google Account Chooser...' : 'Continue with Google Account'}</span>
            </button>

            <p className="text-xs text-slate-500">
              A popup will prompt you to select your Google Account.
            </p>
          </>
        )}
      </div>
    </div>
  );
}
