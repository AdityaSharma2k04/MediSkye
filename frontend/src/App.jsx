import React, { useEffect, lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route, Navigate, useNavigate } from 'react-router-dom';

const Login = lazy(() => import('./components/Login'));
const Register = lazy(() => import('./components/Register'));
const ChatApp = lazy(() => import('./components/ChatApp'));
const LandingPage = lazy(() => import('./components/LandingPage'));

const PageLoader = () => (
  <div className="min-h-screen bg-zinc-950 flex items-center justify-center">
    <div className="w-8 h-8 border-2 border-cyan-500 border-t-transparent rounded-full animate-spin" />
  </div>
);

const ProtectedRoute = ({ children }) => {
  const token = localStorage.getItem('token');
  if (!token) {
    return <Navigate to="/login" replace />;
  }

  try {
    const parts = token.split('.');
    if (parts.length < 2) {
      localStorage.removeItem('token');
      return <Navigate to="/login" replace />;
    }
    const base64Url = parts[1];
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
    const payload = JSON.parse(atob(base64));
    if (payload.exp && payload.exp * 1000 < Date.now()) {
      localStorage.removeItem('token');
      return <Navigate to="/login" replace />;
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
      <Suspense fallback={<PageLoader />}>
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
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
