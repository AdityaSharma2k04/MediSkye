import React, { useRef } from 'react';
import { Brain, ShieldCheck } from 'lucide-react';
import useFocusTrap from '../hooks/useFocusTrap';

export default function MemoryConsentModal({ isOpen, onAllow, onSkip, darkMode = false }) {
  const modalRef = useRef(null);
  useFocusTrap(modalRef, isOpen, onSkip);

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-[75] flex items-end sm:items-center justify-center p-0 sm:p-4 bg-black/60 backdrop-blur-sm animate-backdrop-in"
      role="dialog"
      aria-modal="true"
      aria-labelledby="memory-consent-title"
    >
      <div
        ref={modalRef}
        className={`w-full sm:max-w-md rounded-t-[28px] sm:rounded-3xl p-6 pb-[max(1.5rem,env(safe-area-inset-bottom))] shadow-float border ms-sheet-mobile sm:animate-modal-in ${
          darkMode ? 'bg-graphite border-white/[0.07] text-white' : 'bg-white border-zinc-200 text-zinc-900'
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
            <p className={`text-xs ${darkMode ? 'text-ink-mute' : 'text-ink-faint'}`}>
              Personalized cross-session assistance
            </p>
          </div>
        </div>

        <p className={`text-xs leading-relaxed mb-6 ${darkMode ? 'text-ink-soft' : 'text-zinc-600'}`}>
          MediSkye can remember important health information from our conversations to personalize future answers. You can see and edit what's remembered anytime in Settings.
        </p>

        <div className={`p-3 rounded-xl mb-6 text-[11px] flex items-center gap-2 border ${
          darkMode ? 'bg-obsidian border-white/[0.07] text-ink-mute' : 'bg-zinc-50 border-zinc-200 text-zinc-600'
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
                ? 'bg-slate2 text-ink-soft hover:bg-zinc-700'
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
