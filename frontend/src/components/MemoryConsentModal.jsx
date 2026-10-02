import React from 'react';
import { Brain, ShieldCheck } from 'lucide-react';

export default function MemoryConsentModal({ isOpen, onAllow, onSkip, darkMode = false }) {
  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fade-in"
      role="dialog"
      aria-modal="true"
      aria-labelledby="memory-consent-title"
    >
      <div
        className={`max-w-md w-full rounded-2xl p-6 shadow-2xl border transition-all ${
          darkMode ? 'bg-zinc-900 border-zinc-800 text-white' : 'bg-white border-zinc-200 text-zinc-900'
        }`}
      >
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400 shrink-0">
            <Brain className="w-5 h-5" />
          </div>
          <div>
            <h3 id="memory-consent-title" className="text-base font-semibold">
              Enable Health Memory?
            </h3>
            <p className={`text-xs ${darkMode ? 'text-zinc-400' : 'text-zinc-500'}`}>
              Personalized cross-session assistance
            </p>
          </div>
        </div>

        <p className={`text-xs leading-relaxed mb-6 ${darkMode ? 'text-zinc-300' : 'text-zinc-600'}`}>
          MediSkye can remember important health information from our conversations to personalize future answers. You can see and edit what's remembered anytime in Settings.
        </p>

        <div className={`p-3 rounded-xl mb-6 text-[11px] flex items-center gap-2 border ${
          darkMode ? 'bg-zinc-950 border-zinc-800 text-zinc-400' : 'bg-zinc-50 border-zinc-200 text-zinc-600'
        }`}>
          <ShieldCheck className="w-4 h-4 text-emerald-500 shrink-0" />
          <span>Encrypted with AES-256 Fernet. You retain full control to edit or forget facts anytime.</span>
        </div>

        <div className="flex items-center justify-end gap-2.5">
          <button
            type="button"
            onClick={onSkip}
            className={`px-4 py-2 text-xs font-medium rounded-xl transition-colors ${
              darkMode
                ? 'bg-zinc-800 text-zinc-300 hover:bg-zinc-700'
                : 'bg-zinc-100 text-zinc-700 hover:bg-zinc-200'
            }`}
          >
            Skip
          </button>
          <button
            type="button"
            onClick={onAllow}
            className="px-4 py-2 text-xs font-medium rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white transition-colors shadow-sm"
          >
            Allow
          </button>
        </div>
      </div>
    </div>
  );
}
