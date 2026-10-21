import React, { useEffect, useRef, useState } from 'react';
import { X, AlertTriangle } from 'lucide-react';
import useFocusTrap from '../hooks/useFocusTrap';

/**
 * ConfirmModal — reusable destructive-action confirmation dialog.
 *
 * Props:
 *   isOpen          {bool}
 *   onClose         {fn}   — called on Cancel / Esc / backdrop
 *   onConfirm       {fn}   — called when user confirms
 *   title           {string}
 *   body            {string}
 *   confirmLabel    {string}  default "Delete"
 *   requireTyping   {string|null} — if set, user must type this exact string to enable the confirm btn
 *   closeable       {bool}  default true — if false, backdrop click does not close (for hard destructive)
 *   darkMode        {bool}
 */
export default function ConfirmModal({
  isOpen,
  onClose,
  onConfirm,
  title,
  body,
  message,
  confirmLabel = 'Delete',
  cancelLabel = 'Cancel',
  requireTyping = null,
  closeable = true,
  darkMode = true,
}) {
  const [typed, setTyped] = useState('');
  const inputRef = useRef(null);
  const firstBtnRef = useRef(null);
  const modalRef = useRef(null);

  useFocusTrap(modalRef, isOpen, onClose);

  // Reset typed value each time modal opens
  useEffect(() => {
    if (isOpen) {
      setTyped('');
      setTimeout(() => {
        if (requireTyping && inputRef.current) inputRef.current.focus();
        else if (firstBtnRef.current) firstBtnRef.current.focus();
      }, 50);
    }
  }, [isOpen, requireTyping]);

  if (!isOpen) return null;

  const canConfirm = !requireTyping || typed === requireTyping;

  const handleBackdrop = () => { if (closeable) onClose(); };

  return (
    <div
      className="fixed inset-0 z-[60] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-backdrop-in"
      onMouseDown={handleBackdrop}
    >
      <div
        ref={modalRef}
        className={`relative rounded-2xl shadow-2xl max-w-sm w-full border overflow-hidden animate-modal-in ${
          darkMode
            ? 'bg-zinc-900 border-zinc-800'
            : 'bg-white border-zinc-200'
        }`}
        onMouseDown={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="confirm-modal-title"
      >
        {/* Header */}
        <div className={`flex items-center justify-between px-5 py-4 border-b ${darkMode ? 'border-zinc-800' : 'border-zinc-100'}`}>
          <div className="flex items-center gap-2.5">
            <AlertTriangle className="w-4 h-4 text-red-500 shrink-0" />
            <h3 id="confirm-modal-title" className={`font-semibold text-sm ${darkMode ? 'text-zinc-100' : 'text-zinc-900'}`}>
              {title}
            </h3>
          </div>
          {closeable && (
            <button
              onClick={onClose}
              aria-label="Close dialog"
              className={`p-1 rounded-lg transition-colors ${darkMode ? 'text-zinc-500 hover:text-zinc-200 hover:bg-zinc-800' : 'text-zinc-400 hover:text-zinc-700 hover:bg-zinc-100'}`}
            >
              <X className="w-4 h-4" />
            </button>
          )}
        </div>

        {/* Body */}
        <div className="px-5 py-4">
          <p className={`text-sm leading-relaxed ${darkMode ? 'text-zinc-300' : 'text-zinc-600'}`}>
            {body || message}
          </p>

          {requireTyping && (
            <div className="mt-4">
              <label className={`block text-xs font-medium mb-1.5 ${darkMode ? 'text-zinc-400' : 'text-zinc-500'}`}>
                Type <span className={`font-mono font-bold ${darkMode ? 'text-zinc-100' : 'text-zinc-900'}`}>{requireTyping}</span> to confirm
              </label>
              <input
                ref={inputRef}
                type="text"
                value={typed}
                onChange={(e) => setTyped(e.target.value)}
                placeholder={requireTyping}
                className={`w-full px-3 py-2 text-sm rounded-xl border focus:outline-none transition-colors ${
                  darkMode
                    ? 'bg-zinc-950 border-zinc-700 text-white placeholder-zinc-600 focus:border-zinc-500'
                    : 'bg-zinc-50 border-zinc-300 text-zinc-900 placeholder-zinc-400 focus:border-zinc-500'
                }`}
              />
            </div>
          )}
        </div>

        {/* Footer */}
        <div className={`px-5 py-4 flex items-center justify-end gap-2 border-t ${darkMode ? 'border-zinc-800 bg-zinc-950' : 'border-zinc-100 bg-zinc-50'}`}>
          <button
            ref={firstBtnRef}
            onClick={onClose}
            className={`px-4 py-2 text-xs font-medium rounded-xl transition-colors border ${
              darkMode
                ? 'border-zinc-700 text-zinc-300 hover:bg-zinc-800 hover:text-white'
                : 'border-zinc-200 text-zinc-600 hover:bg-zinc-100 hover:text-zinc-900'
            }`}
          >
            {cancelLabel}
          </button>
          <button
            onClick={() => { if (canConfirm) { onConfirm(); onClose(); } }}
            disabled={!canConfirm}
            className={`px-4 py-2 text-xs font-medium rounded-xl transition-colors text-white ${
              canConfirm
                ? 'bg-red-500 hover:bg-red-600 cursor-pointer'
                : 'bg-red-500/40 cursor-not-allowed opacity-50'
            }`}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
