import React, { useEffect, lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route, Navigate, useNavigate } from 'react-router-dom';

const Login = lazy(() => import('./components/Login'));
const Register = lazy(() => import('./components/Register'));
const AuthAction = lazy(() => import('./components/AuthAction'));
const ChatApp = lazy(() => import('./components/ChatApp'));
const LandingPage = lazy(() => import('./components/LandingPage'));
const PrivacyPolicy = lazy(() => import('./components/PrivacyPolicy'));

const LandingSkeleton = () => (
  <div className="min-h-screen bg-obsidian text-ink font-sans flex flex-col justify-between overflow-hidden animate-pulse" aria-label="Loading MediSkye">
    {/* Navbar Skeleton */}
    <nav className="sticky top-0 z-50 bg-obsidian/90 backdrop-blur-md border-b border-white/[0.07] px-6 py-3.5 flex items-center justify-between">
      <div className="flex items-center gap-2.5">
        <div className="w-8 h-8 rounded-lg bg-clinical-cyan flex items-center justify-center shadow-lg shadow-cyan-500/10">
          <svg
            className="w-4 h-4 text-zinc-900 animate-pulse"
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

const FIFTEEN_DAYS_MS = 15 * 24 * 60 * 60 * 1000;

const ProtectedRoute = ({ children }) => {
  const token = localStorage.getItem('token') || localStorage.getItem('mediskye_auth_id_token');
  const lastActive = localStorage.getItem('mediskye_auth_last_active');

  // If user was inactive for > 15 days, purge auth and force login
  if (lastActive && Date.now() - Number(lastActive) > FIFTEEN_DAYS_MS) {
    for (let i = localStorage.length - 1; i >= 0; i--) {
      const k = localStorage.key(i);
      if (k && (k.startsWith('mediskye_auth_') || k.startsWith('mediskye_cached_') || k === 'token')) {
        localStorage.removeItem(k);
      }
    }
    return <Navigate to="/login" replace />;
  }

  if (!token) {
    return <Navigate to="/login" replace />;
  }

  // Touch last active on route access
  localStorage.setItem('mediskye_auth_last_active', String(Date.now()));

  try {
    const parts = token.split('.');
    if (parts.length < 2) {
      localStorage.removeItem('token');
      localStorage.removeItem('mediskye_auth_id_token');
      return <Navigate to="/login" replace />;
    }
    const base64Url = parts[1];
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
    const payload = JSON.parse(atob(base64));
    // If JWT expired but within 15-day inactivity window, don't boot user — let Firebase refresh in background
    if (payload.exp && payload.exp * 1000 < Date.now()) {
      if (!lastActive || Date.now() - Number(lastActive) > FIFTEEN_DAYS_MS) {
        localStorage.removeItem('token');
        return <Navigate to="/login" replace />;
      }
      // Within 15 days: allow component to render immediately
    }
  } catch (e) {
    localStorage.removeItem('token');
    return <Navigate to="/login" replace />;
  }

  return children;
};

const GlobalAuthListener = () => {
  const navigate = useNavigate();
  useEffect(() => {
    const handleAuthExpired = () => {
      navigate('/login', { replace: true });
    };
    window.addEventListener('auth:expired', handleAuthExpired);
    return () => window.removeEventListener('auth:expired', handleAuthExpired);
  }, [navigate]);
  return null;
};

export default function App() {
  return (
    <BrowserRouter>
      <GlobalAuthListener />
      <Suspense fallback={<LandingSkeleton />}>
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
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
          {/* Catch-all: redirect unknown paths to landing */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Suspense>
    </BrowserRouter>
  );
}
