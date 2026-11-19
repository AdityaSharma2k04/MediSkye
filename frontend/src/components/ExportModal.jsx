import React, { useEffect, useRef, useState } from 'react';
import { X, FileJson, FileText, Download } from 'lucide-react';
import { exportDocumentData } from '../services/api';
import { logger } from '../services/logger';
import useFocusTrap from '../hooks/useFocusTrap';
import PrintableTranscript from './PrintableTranscript';

function safeFilename(name) {
  const base = String(name || 'consultation')
    .replace(/[^\w\- ]+/g, '')
    .replace(/\s+/g, '-')
    .slice(0, 40);
  return base || 'consultation';
}

/**
 * ExportModal — offers two download paths for the current conversation:
 *   1. JSON  — raw data (document metadata + full transcript + lab metrics)
 *              from GET /users/me/documents/{id}/export, falling back to the
 *              in-memory conversation for general (document-less) chats.
 *   2. PDF   — a formal, print-styled transcript with metrics table and the
 *              medical disclaimer, using the same print pipeline as the
 *              doctor summary.
 */
export default function ExportModal({
  isOpen,
  onClose,
  darkMode,
  documentId,
  documentTitle,
  messages = [],
  user,
}) {
  const modalRef = useRef(null);
  const fallbackTimerRef = useRef(null);
  const [busy, setBusy] = useState(null); // null | 'json' | 'pdf'

  useEffect(() => {
    return () => {
      if (fallbackTimerRef.current) {
        clearTimeout(fallbackTimerRef.current);
        fallbackTimerRef.current = null;
      }
    };
  }, []);
  const [printData, setPrintData] = useState(null);
  const [exportError, setExportError] = useState(null);

  useFocusTrap(modalRef, isOpen, onClose);

  if (!isOpen) return null;

  const buildPayload = async () => {
    if (documentId) {
      try {
        return await exportDocumentData(documentId);
      } catch (err) {
        logger.warn('Export endpoint failed; falling back to in-memory chat data:', err);
      }
    }
    return {
      document: {
        id: documentId || null,
        filename: documentTitle || null,
        title: documentTitle || null,
        created_at: null,
      },
      messages: (messages || []).map((m) => ({
        role: (m.sender === 'user' || m.role === 'user' || m.isUser) ? 'user' : 'ai',
        message: m.content || m.text || m.message || '',
        created_at: m.created_at || null,
      })),
      lab_metrics: [],
    };
  };

  const downloadJson = async () => {
    if (busy) return;
    setBusy('json');
    try {
      const payload = await buildPayload();
      const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      const dateStamp = new Date().toISOString().slice(0, 10);
      anchor.download = `MediSkye-${safeFilename(payload.document?.title || documentTitle)}-${dateStamp}.json`;
      document.body.appendChild(anchor);
      anchor.click();
      document.body.removeChild(anchor);
      // Defer URL revocation so WebView download streams are not prematurely aborted
      setTimeout(() => {
        try {
          URL.revokeObjectURL(url);
        } catch (_) { }
      }, 2000);
      setExportError(null);
    } catch (err) {
      console.error('JSON Export Failed:', err);
      setExportError(err.message || 'Could not prepare the JSON export.');
    } finally {
      setBusy(null);
    }
  };

  const downloadPdf = () => {
    if (busy) return;
    setBusy('pdf');
    buildPayload()
      .then((payload) => {
        const transcriptMessages = (payload.messages || []).map((m) => ({
          sender: m.role === 'ai' ? 'assistant' : 'user',
          text: m.message || '',
          timestamp: m.created_at
            ? new Date(m.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
            : '',
        }));
        setPrintData({
          document: payload.document,
          messages: transcriptMessages,
          metrics: payload.lab_metrics || [],
        });
        // Let the hidden print document commit to the DOM before printing.
        setTimeout(() => {
          const origTitle = document.title;
          const patientName = user?.full_name || user?.name || (user?.email ? user.email.split('@')[0] : 'Patient');
          const docTitle = payload?.document?.title || payload?.document?.filename || 'Lab Report';
          document.title = `${patientName} - ${docTitle} - Clinical Summary`;

          const cleanup = () => {
            if (fallbackTimerRef.current) {
              clearTimeout(fallbackTimerRef.current);
              fallbackTimerRef.current = null;
            }
            document.title = origTitle;
            setPrintData(null);
            setBusy(null);
            window.removeEventListener('afterprint', cleanup);
          };
          window.addEventListener('afterprint', cleanup);
          try {
            if (typeof window.print === 'function') {
              window.print();
            }
          } catch (printErr) {
            console.warn('Native WebView window.print not supported:', printErr);
          }
          // Fallback for browsers that never fire afterprint.
          fallbackTimerRef.current = setTimeout(cleanup, 60000);
        }, 150);
      })
      .catch((err) => {
        console.error('PDF Export Failed:', err);
        setExportError(err.message || 'Could not prepare the PDF export.');
        setBusy(null);
      });
  };

  return (
    <>
      <div
        className="fixed inset-0 z-[65] flex items-end sm:items-center justify-center p-0 sm:p-4 bg-black/60 backdrop-blur-sm animate-backdrop-in"
        onMouseDown={(e) => {
          if (e.target === e.currentTarget) onClose();
        }}
        role="dialog"
        aria-modal="true"
        aria-label="Export chat data"
      >
        <div
          ref={modalRef}
          className={`relative rounded-t-[28px] sm:rounded-3xl shadow-float w-full sm:max-w-md border ms-sheet-mobile sm:animate-modal-in overflow-hidden pb-[env(safe-area-inset-bottom)] sm:pb-0 ${
            darkMode ? 'bg-graphite border-white/[0.07]' : 'bg-white border-zinc-200'
          }`}
          onMouseDown={(e) => e.stopPropagation()}
        >
          {/* Header */}
          <div className={`flex items-center justify-between px-5 py-4 border-b ${darkMode ? 'border-white/[0.07]' : 'border-zinc-100'}`}>
            <div className="flex items-center gap-2.5">
              <Download className={`w-4 h-4 ${darkMode ? 'text-ink-soft' : 'text-zinc-600'}`} />
              <h3 className={`font-semibold text-sm ${darkMode ? 'text-ink' : 'text-zinc-900'}`}>
                Export Chat Data
              </h3>
            </div>
            <button
              onClick={onClose}
              aria-label="Close export dialog"
              className={`p-1 rounded-lg transition-colors ${darkMode ? 'text-ink-faint hover:text-ink hover:bg-slate2' : 'text-ink-mute hover:text-zinc-700 hover:bg-zinc-100'}`}
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          <div className="p-5 space-y-3">
            {exportError && (
              <div role="alert" className="text-xs text-red-300 bg-red-500/10 border border-red-500/30 rounded-xl px-3 py-2">
                {exportError}
              </div>
            )}
            <p className={`text-xs leading-relaxed ${darkMode ? 'text-ink-mute' : 'text-ink-faint'}`}>
              Export this conversation{documentTitle ? ` for “${documentTitle}”` : ''} — including every message and the extracted lab metrics.
            </p>

            {/* JSON option */}
            <button
              type="button"
              onClick={(e) => {
                if (e) {
                  e.preventDefault();
                  e.stopPropagation();
                }
                downloadJson();
              }}
              disabled={!!busy}
              className={`w-full flex items-center gap-3.5 p-4 rounded-xl border text-left transition-all active:scale-[0.99] ${
                busy ? 'opacity-60 cursor-not-allowed' : ''
              } ${
                darkMode
                  ? 'bg-obsidian border-white/[0.07] hover:border-white/[0.12]'
                  : 'bg-zinc-50 border-zinc-200 hover:border-zinc-300'
              }`}
            >
              <div className={`w-9 h-9 rounded-xl flex items-center justify-center shrink-0 ${
                darkMode ? 'bg-slate2 text-amber-300' : 'bg-amber-100 text-amber-700'
              }`}>
                <FileJson className="w-5 h-5" />
              </div>
              <div className="min-w-0">
                <div className={`text-xs font-semibold ${darkMode ? 'text-ink' : 'text-zinc-900'}`}>Download JSON</div>
                <div className={`text-xs leading-relaxed mt-0.5 ${darkMode ? 'text-ink-faint' : 'text-ink-mute'}`}>
                  Raw data — full transcript, document metadata and lab metrics in machine-readable JSON.
                </div>
              </div>
            </button>

            {/* PDF option */}
            <button
              type="button"
              onClick={(e) => {
                if (e) {
                  e.preventDefault();
                  e.stopPropagation();
                }
                downloadPdf();
              }}
              disabled={!!busy}
              className={`w-full flex items-center gap-3.5 p-4 rounded-xl border text-left transition-all active:scale-[0.99] ${
                busy ? 'opacity-60 cursor-not-allowed' : ''
              } ${
                darkMode
                  ? 'bg-obsidian border-white/[0.07] hover:border-white/[0.12]'
                  : 'bg-zinc-50 border-zinc-200 hover:border-zinc-300'
              }`}
            >
              <div className={`w-9 h-9 rounded-xl flex items-center justify-center shrink-0 ${
                darkMode ? 'bg-slate2 text-rose-300' : 'bg-rose-100 text-rose-700'
              }`}>
                <FileText className="w-5 h-5" />
              </div>
              <div className="min-w-0">
                <div className={`text-xs font-semibold ${darkMode ? 'text-ink' : 'text-zinc-900'}`}>Download PDF</div>
                <div className={`text-xs leading-relaxed mt-0.5 ${darkMode ? 'text-ink-faint' : 'text-ink-mute'}`}>
                  Formal document — formatted transcript, metrics table and medical disclaimer, ready to print or save.
                </div>
              </div>
            </button>
          </div>
        </div>
      </div>

      {/* Hidden print-only transcript (revealed during window.print) */}
      {printData && (
        <PrintableTranscript
          document={printData.document}
          messages={printData.messages}
          metrics={printData.metrics}
          user={user}
        />
      )}
    </>
  );
}
