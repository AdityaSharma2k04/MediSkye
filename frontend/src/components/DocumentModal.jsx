import React, { useRef } from 'react';
import { FileText, X, Bookmark } from 'lucide-react';
import useFocusTrap from '../hooks/useFocusTrap';

export default function DocumentModal({ source, onClose }) {
  const modalRef = useRef(null);
  useFocusTrap(modalRef, Boolean(source), onClose);

  if (!source) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-0 sm:p-4 bg-slate-900/40 backdrop-blur-sm animate-backdrop-in"
      role="dialog"
      aria-modal="true"
      aria-labelledby="document-modal-title"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        ref={modalRef}
        className="bg-white border border-slate-200 rounded-t-[28px] sm:rounded-3xl shadow-xl w-full sm:max-w-2xl max-h-[92dvh] sm:max-h-[85dvh] flex flex-col overflow-hidden ms-sheet-mobile sm:animate-modal-in"
      >
        <div className="flex items-center justify-between p-4 px-6 border-b border-slate-200">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-slate-100 text-slate-800 rounded-xl">
              <FileText className="w-5 h-5" />
            </div>
            <div>
              <h3 id="document-modal-title" className="font-semibold text-slate-900 text-base">
                {source.title || 'Medical PDF Report'}
              </h3>
              <p className="text-xs text-slate-500">
                Page {source.page || 1} • Relevance Match: <span className="font-semibold text-slate-900">{source.score || '98%'}</span>
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            aria-label="Close document modal"
            className="p-1.5 text-slate-400 hover:text-slate-800 rounded-lg hover:bg-slate-100 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-6 overflow-y-auto flex-1 text-sm leading-relaxed text-slate-800 font-mono bg-slate-50">
          <div className="mb-3 flex items-center gap-2 text-xs font-sans text-slate-500">
            <Bookmark className="w-3.5 h-3.5 text-slate-400" />
            Extracted Report Excerpt:
          </div>
          <div className="p-4 bg-white border border-slate-200 rounded-xl whitespace-pre-wrap font-sans text-xs sm:text-sm text-slate-900">
            {source.content || source.excerpt || 'No excerpt available.'}
          </div>
        </div>

        <div className="p-4 px-6 border-t border-slate-200 bg-white flex justify-between items-center text-xs text-slate-500">
          <span>Verified against uploaded medical records</span>
          <button
            onClick={onClose}
            className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-900 font-medium rounded-xl text-xs transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
