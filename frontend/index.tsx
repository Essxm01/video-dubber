import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './index.css';
import { ErrorBoundary } from './components/ErrorBoundary';
import { ToastProvider } from './components/ToastContext';
import { AuthProvider } from './contexts/AuthContext';

/**
 * Root Application Entry Point
 * Wrapped with:
 * - ErrorBoundary: لالتقاط الأخطاء
 * - AuthProvider: للمصادقة
 * - ToastProvider: للإشعارات
 */
ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ErrorBoundary>
      <AuthProvider>
        <ToastProvider>
          <App />
        </ToastProvider>
      </AuthProvider>
    </ErrorBoundary>
  </React.StrictMode>
);