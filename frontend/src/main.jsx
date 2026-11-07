import "./instrument";
import React from 'react';
import ReactDOM from 'react-dom/client';
import * as Sentry from "@sentry/react";
import '@fontsource-variable/inter';
import '@fontsource-variable/fraunces';
import '@fontsource-variable/jetbrains-mono';
import App from './App';
import './i18n';
import './index.css';
import './styles/print.css';

function CrashFallback() {
  return (
    <div className="min-h-app flex items-center justify-center bg-obsidian px-6 text-center">
      <div className="max-w-sm">
        <p className="ms-display text-2xl text-white mb-2">MediSkye hit an unexpected error.</p>
        <p className="text-sm text-ink-mute mb-5">Your reports and conversations are safe on the server. Reload to continue where you left off.</p>
        <button
          type="button"
          onClick={() => window.location.reload()}
          className="h-11 px-5 rounded-xl bg-clinical-cyan text-slate-950 text-sm font-semibold"
        >
          Reload MediSkye
        </button>
      </div>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <Sentry.ErrorBoundary fallback={<CrashFallback />}>
    <App />
  </Sentry.ErrorBoundary>
);
