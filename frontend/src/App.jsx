import React, { useEffect, useState, lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route, Navigate, useNavigate } from 'react-router-dom';
import {
  auth,
  GoogleAuthProvider,
  signInWithCredential,
  saveAuthSession,
  saveAuthSnapshot,
  getSavedAuthSession,
  clearSavedAuthSession,
  touchAuthActivity,
  isSessionExpiredByInactivity,
  performExplicitLogout,
  onAuthStateChanged,
  FIFTEEN_DAYS_MS,
} from './services/firebase';
import { warmBackendConnection } from './services/api';

const Login = lazy(() => import('./components/Login'));
const Register = lazy(() => import('./components/Register'));
const AuthAction = lazy(() => import('./components/AuthAction'));
const ChatApp = lazy(() => import('./components/ChatApp'));
const LandingPage = lazy(() => import('./components/LandingPage'));
const PrivacyPolicy = lazy(() => import('./components/PrivacyPolicy'));
const ExternalAuthLanding = lazy(() => import('./components/ExternalAuthLanding'));

const LandingSkeleton = () => (
  <div className="min-h-screen bg-obsidian text-ink font-sans flex flex-col justify-between overflow-hidden animate-pulse" aria-label="Loading MediSkye">
    {/* Navbar Skeleton */}
    <nav className="sticky top-0 z-50 bg-obsidian/90 backdrop-blur-md border-b border-white/[0.07] px-6 py-3.5 flex items-center justify-between">
      <div className="flex items-center gap-2.5">
        <div className="w-8 h-8 rounded-[8px] bg-gradient-to-b from-cyan-400 via-cyan-600 to-sky-600 border border-cyan-300/80 shadow-[0_0_12px_rgba(6,182,212,0.5)] flex items-center justify-center">
          <svg className="w-5 h-5" viewBox="0 0 512 512" fill="none">
            <path d="M 148 264 L 210 264 L 238 176 L 282 344 L 312 264 L 364 264" stroke="#060A12" strokeWidth="44" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </div>
        <span className="font-semibold text-base tracking-tight text-ink">MediSkye</span>
      </div>
      <div className="hidden sm:flex items-center gap-6">
        <div className="h-4 w-16 bg-slate2/60 rounded" />
        <div className="h-4 w-24 bg-slate2/60 rounded" />
        <div className="h-4 w-16 bg-slate2/60 rounded" />
      </div>
      <div className="flex items-center gap-3">
        <div className="h-9 w-20 bg-slate2/60 rounded-xl" />
        <div className="h-9 w-28 bg-cyan-500/20 rounded-xl border border-cyan-500/30" />
      </div>
    </nav>

    {/* Hero Section Skeleton */}
    <div className="flex-1 max-w-6xl w-full mx-auto px-6 py-16 grid grid-cols-1 lg:grid-cols-2 gap-12 items-center">
      <div className="space-y-6">
        {/* Pulsing MediSkye Badge */}
        <div className="inline-flex items-center gap-2.5 px-3.5 py-1.5 rounded-full border border-cyan-500/30 bg-cyan-950/30 shadow-sm">
          <div className="w-5 h-5 rounded-md bg-cyan-400/20 flex items-center justify-center">
            <svg
              className="w-3.5 h-3.5 text-cyan-400 animate-bounce"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
            </svg>
          </div>
          <span className="text-xs font-semibold text-cyan-300 tracking-wide uppercase">MediSkye AI</span>
        </div>

        {/* Hero Title */}
        <div className="space-y-3">
          <div className="h-10 sm:h-12 w-11/12 bg-slate2/90 rounded-xl" />
          <div className="h-10 sm:h-12 w-4/5 bg-slate2/70 rounded-xl" />
        </div>

        {/* Subtitle */}
        <div className="space-y-2 pt-2 max-w-lg">
          <div className="h-4 w-full bg-slate2/50 rounded" />
          <div className="h-4 w-5/6 bg-slate2/50 rounded" />
          <div className="h-4 w-2/3 bg-slate2/40 rounded" />
        </div>

        {/* Action Buttons */}
        <div className="flex flex-wrap gap-3 pt-4">
          <div className="h-12 w-36 bg-cyan-500/30 rounded-xl border border-cyan-400/30" />
          <div className="h-12 w-36 bg-slate2/60 rounded-xl border border-white/[0.12]" />
        </div>
      </div>

      {/* Mockup Card Skeleton with Pulsing Glow */}
      <div className="rounded-2xl border border-white/[0.07] bg-graphite/40 p-6 space-y-4 shadow-2xl backdrop-blur-sm">
        <div className="flex items-center justify-between pb-3 border-b border-white/[0.07]">
          <div className="flex gap-2">
            <div className="w-2.5 h-2.5 rounded-full bg-red-500/40" />
            <div className="w-2.5 h-2.5 rounded-full bg-amber-500/40" />
            <div className="w-2.5 h-2.5 rounded-full bg-green-500/40" />
          </div>
          <div className="h-3 w-28 bg-slate2/50 rounded" />
          <div className="w-4" />
        </div>
        <div className="space-y-3 pt-2">
          <div className="flex justify-end">
            <div className="h-10 w-2/3 bg-cyan-950/40 border border-cyan-800/30 rounded-2xl rounded-br-sm" />
          </div>
          <div className="flex items-start gap-3">
            <div className="w-7 h-7 rounded-lg bg-slate2/80 shrink-0 flex items-center justify-center text-cyan-400">
              <svg className="w-3.5 h-3.5 animate-pulse" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
              </svg>
            </div>
            <div className="flex-1 space-y-2">
              <div className="h-4 w-1/4 bg-slate2/70 rounded" />
              <div className="h-14 w-full bg-slate2/40 rounded-xl" />
            </div>
          </div>
        </div>
      </div>
    </div>

    {/* Footer Skeleton */}
    <div className="border-t border-white/[0.07] px-6 py-4 flex items-center justify-between">
      <div className="h-3 w-32 bg-slate2/40 rounded" />
      <div className="h-3 w-40 bg-slate2/40 rounded" />
    </div>
  </div>
);

const ProtectedRoute = ({ children }) => {
  if (isSessionExpiredByInactivity()) {
    clearSavedAuthSession();
    return <Navigate to="/login" replace />;
  }

  const session = getSavedAuthSession();
  const token = localStorage.getItem('token') || localStorage.getItem('mediskye_auth_id_token');

  if (!session && !token) {
    return <Navigate to="/login" replace />;
  }

  touchAuthActivity();
  return children;
};

const GlobalAuthListener = ({ user, setUser }) => {
  const navigate = useNavigate();

  useEffect(() => {
    // 1. Guard onAuthStateChanged: never let transient null log out an active 15-day session
    let unsubscribe = () => {};
    if (auth && typeof onAuthStateChanged === 'function') {
      try {
        unsubscribe = onAuthStateChanged(auth, async (firebaseUser) => {
          if (firebaseUser) {
            touchAuthActivity();
            const idToken = await firebaseUser.getIdToken(false).catch(() => null);
            saveAuthSession(firebaseUser, idToken);
            if (typeof setUser === 'function') {
              setUser(firebaseUser);
            }
          } else {
            const savedSession = getSavedAuthSession();
            if (savedSession) {
              // DO NOT call setUser(null) and DO NOT clear localStorage!
              // Keep user set to savedSession across sleep/wake, offline boots, and WebView reloads.
              if (typeof setUser === 'function') {
                setUser(savedSession);
              }
            } else {
              if (typeof setUser === 'function') {
                setUser(null);
              }
            }
          }
        });
      } catch (err) {
        console.error('onAuthStateChanged setup error:', err);
      }
    }

    // 2. Rolling Activity Heartbeat Listener (pointerdown, keydown, touchstart, focus) throttled to 60s
    let lastThrottledTouch = 0;
    const handleUserActivity = () => {
      const now = Date.now();
      if (now - lastThrottledTouch > 60000) {
        lastThrottledTouch = now;
        touchAuthActivity();
      }
    };
    const activityEvents = ['pointerdown', 'keydown', 'touchstart', 'focus'];
    activityEvents.forEach((evt) => {
      window.addEventListener(evt, handleUserActivity, { passive: true });
    });

    // 3. Proactive 45-Minute Token Refresh & Wake-From-Sleep Refresh
    const refreshAuthTokenIfActive = async () => {
      if (isSessionExpiredByInactivity()) {
        await performExplicitLogout();
        if (typeof setUser === 'function') {
          setUser(null);
        }
        navigate('/login', { replace: true });
        return;
      }
      touchAuthActivity();
      if (auth && auth.currentUser) {
        try {
          const freshToken = await auth.currentUser.getIdToken(true);
          if (freshToken) {
            localStorage.setItem('mediskye_auth_id_token', freshToken);
            localStorage.setItem('token', freshToken);
          }
        } catch (_) {}
      }
    };

    const interval45m = setInterval(() => {
      if (getSavedAuthSession() || (auth && auth.currentUser)) {
        refreshAuthTokenIfActive();
      }
    }, 45 * 60 * 1000);

    // Warm up Cloud Run container on initial mount & check refresh on visibilitychange / online
    warmBackendConnection();
    let lastActive = Date.now();
    const handleVisibility = () => {
      if (document.visibilityState === 'visible') {
        const inactiveMs = Date.now() - lastActive;
        if (inactiveMs > 2 * 60 * 1000) {
          warmBackendConnection();
        }
        lastActive = Date.now();
        if (getSavedAuthSession() || (auth && auth.currentUser)) {
          refreshAuthTokenIfActive();
        }
      } else {
        lastActive = Date.now();
      }
    };
    const handleOnline = () => {
      if (getSavedAuthSession() || (auth && auth.currentUser)) {
        refreshAuthTokenIfActive();
      }
    };
    document.addEventListener('visibilitychange', handleVisibility);
    window.addEventListener('online', handleOnline);

    const handleAuthExpired = () => {
      if (isSessionExpiredByInactivity()) {
        performExplicitLogout();
        navigate('/login', { replace: true });
      }
    };
    window.addEventListener('auth:expired', handleAuthExpired);

    const handleNativeGoogleAuth = async (e) => {
      try {
        const { idToken, accessToken } = e?.detail || {};
        if (idToken || accessToken) {
          const credential = GoogleAuthProvider.credential(idToken || null, accessToken || null);
          const result = await signInWithCredential(auth, credential);
          if (result?.user) {
            const token = await result.user.getIdToken();
            saveAuthSession(result.user, token);
            if (typeof setUser === 'function') {
              setUser(result.user);
            }
            navigate('/chat', { replace: true });
          }
        }
      } catch (err) {
        console.error('Failed to sign in with native Google credential:', err);
      }
    };
    window.addEventListener('mediskye-native-google-auth', handleNativeGoogleAuth);

    return () => {
      unsubscribe();
      clearInterval(interval45m);
      activityEvents.forEach((evt) => {
        window.removeEventListener(evt, handleUserActivity);
      });
      document.removeEventListener('visibilitychange', handleVisibility);
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('auth:expired', handleAuthExpired);
      window.removeEventListener('mediskye-native-google-auth', handleNativeGoogleAuth);
    };
  }, [navigate, setUser]);

  return null;
};

export default function App() {
  const [user, setUser] = useState(() => getSavedAuthSession());
  const isExternalGoogleAuth = typeof window !== 'undefined' &&
    new URLSearchParams(window.location.search).get('native_google_auth') === '1';

  if (isExternalGoogleAuth) {
    return (
      <Suspense fallback={<div className="fixed inset-0 bg-[#070B14]" />}>
        <ExternalAuthLanding />
      </Suspense>
    );
  }

  const isNativeApp = typeof window !== 'undefined' && Boolean(
    window.__TAURI_INTERNALS__ ||
    window.__TAURI__ ||
    window.MediskyeNativeAuth ||
    window.Capacitor?.isNativePlatform?.()
  );

  const isAuthenticated = Boolean(user || getSavedAuthSession());

  return (
    <BrowserRouter>
      <GlobalAuthListener user={user} setUser={setUser} />
      <Suspense fallback={<div className="fixed inset-0 bg-[#070B14]" />}>
        <Routes>
          <Route
            path="/"
            element={
              isAuthenticated ? (
                <Navigate to="/chat" replace />
              ) : isNativeApp ? (
                <Navigate to="/login" replace />
              ) : (
                <LandingPage />
              )
            }
          />
          <Route
            path="/login"
            element={
              isAuthenticated ? <Navigate to="/chat" replace /> : <Login />
            }
          />
          <Route
            path="/register"
            element={
              isAuthenticated ? <Navigate to="/chat" replace /> : <Register />
            }
          />
          <Route path="/privacy" element={<PrivacyPolicy />} />
          <Route path="/auth/action" element={<AuthAction />} />
          <Route
            path="/chat/*"
            element={
              <ProtectedRoute>
                <ChatApp />
              </ProtectedRoute>
            }
          />
          <Route
            path="*"
            element={
              <Navigate
                to={isAuthenticated ? "/chat" : isNativeApp ? "/login" : "/"}
                replace
              />
            }
          />
        </Routes>
      </Suspense>
    </BrowserRouter>
  );
}
