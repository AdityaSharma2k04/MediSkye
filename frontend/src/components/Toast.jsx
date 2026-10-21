import React from 'react';
import { CheckCircle2, AlertCircle, Info, X } from 'lucide-react';

export default function Toast({ toasts, onDismiss }) {
  if (!toasts || toasts.length === 0) return null;

  return (
    <div className="fixed bottom-5 right-5 z-50 flex flex-col gap-2 pointer-events-none max-w-sm w-full">
      {toasts.map((toast) => {
        let borderClass = 'border-blue-500 text-blue-900 dark:text-blue-200';
        let icon = <Info className="w-5 h-5 text-blue-600 dark:text-blue-400 shrink-0" />;

        if (toast.type === 'success') {
          borderClass = 'border-emerald-500 text-emerald-900 dark:text-emerald-200';
          icon = <CheckCircle2 className="w-5 h-5 text-emerald-600 dark:text-emerald-400 shrink-0" />;
        } else if (toast.type === 'error') {
          borderClass = 'border-rose-500 text-rose-900 dark:text-rose-200';
          icon = <AlertCircle className="w-5 h-5 text-rose-600 dark:text-rose-400 shrink-0" />;
        }

        return (
          <div
            key={toast.id}
            className={`pointer-events-auto flex items-start gap-3 p-4 bg-white dark:bg-zinc-900 border-l-4 ${borderClass} rounded-xl shadow-lg border border-zinc-200/80 dark:border-zinc-800 transition-all duration-200 animate-toast-in`}
          >
            {icon}
            <div className="flex-1 text-sm">
              <h4 className="font-semibold text-zinc-900 dark:text-zinc-100">{toast.title}</h4>
              {toast.message && <p className="text-zinc-600 dark:text-zinc-400 mt-0.5 text-xs">{toast.message}</p>}
            </div>
            <button
              onClick={() => onDismiss(toast.id)}
              aria-label="Dismiss notification"
              className="text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-200 p-0.5"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        );
      })}
    </div>
  );
}
