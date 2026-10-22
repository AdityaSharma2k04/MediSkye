import "./instrument";
import React from 'react';
import ReactDOM from 'react-dom/client';
import * as Sentry from "@sentry/react";
import App from './App';
import './i18n';
import './index.css';
import './styles/print.css';

ReactDOM.createRoot(document.getElementById('root')).render(
  <Sentry.ErrorBoundary fallback={<div>Oops, something went wrong. Please refresh.</div>}>
    <App />
  </Sentry.ErrorBoundary>
);
