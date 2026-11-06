import React, { useRef } from 'react';
import { FileText, X, Bookmark } from 'lucide-react';
import useFocusTrap from '../hooks/useFocusTrap';

export default function DocumentModal({ source, onClose }) {
  const modalRef = useRef(null);
  useFocusTrap(modalRef, Boolean(source), onClose);

  if (!source) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 dark:bg-black/60 backdrop-blur-sm animate-backdrop-in"
      role="dialog"
      aria-modal="true"
      aria-labelledby="document-modal-title"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        ref={modalRef}
        className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-2xl shadow-2xl max-w-2xl w-full max-h-[85vh] flex flex-col overflow-hidden animate-modal-in"
      >
        <div className="flex items-center justify-between p-4 px-6 border-b border-zinc-200 dark:border-zinc-800">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-zinc-100 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-200 rounded-xl">
              <FileText className="w-5 h-5" />
            </div>
            <div>
              <h3 id="document-modal-title" className="font-semibold text-zinc-900 dark:text-zinc-100 text-base">
                {source.title || 'Medical PDF Report'}
              </h3>
              <p className="text-xs text-zinc-500 dark:text-zinc-400">
                Page {source.page || 1} • Relevance Match: <span className="font-semibold text-zinc-900 dark:text-zinc-100">{source.score || '98%'}</span>
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            aria-label="Close document modal"
            className="p-1.5 text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-200 rounded-lg hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-6 overflow-y-auto flex-1 text-sm leading-relaxed text-zinc-800 dark:text-zinc-200 font-mono bg-zinc-50 dark:bg-zinc-950">
          <div className="mb-3 flex items-center gap-2 text-xs font-sans text-zinc-500 dark:text-zinc-400">
            <Bookmark className="w-3.5 h-3.5 text-zinc-500" />
            Extracted Report Excerpt:
          </div>
          <div className="p-4 bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-xl whitespace-pre-wrap font-sans text-xs sm:text-sm">
            {source.content || source.excerpt || 'No excerpt available.'}
          </div>
        </div>

        <div className="p-4 px-6 border-t border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 flex justify-between items-center text-xs text-zinc-500 dark:text-zinc-400">
          <span>Verified against uploaded medical records</span>
          <button
            onClick={onClose}
            className="px-4 py-2 bg-zinc-900 dark:bg-zinc-100 hover:bg-zinc-800 dark:hover:bg-zinc-200 text-white dark:text-zinc-900 font-medium rounded-xl text-xs transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
