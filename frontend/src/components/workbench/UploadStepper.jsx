import React, { useEffect, useState } from 'react';
import { Check, FileSearch, Loader2, X, Flame, AlertTriangle, ScanText, DatabaseZap, MessageSquareText } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { cn } from '../../lib/cn';

/**
 * Visualizes MediSkye's real two-phase ingestion pipeline:
 *   Step A (blocking):   validate → extract text → build FAISS + BM25 index → ready
 *   Step B (background): summary + metrics cache warming
 *
 * `upload` shape (owned by ChatApp):
 *   { phase: 'validating'|'uploading'|'extracting'|'indexing'|'ready'|'error',
 *     fileName, startedAt, warming, error }
 */
export const UPLOAD_STEPS = [
  { key: 'validate', i18n: 'workbench.upload_validating', label: 'Validating PDF', icon: FileSearch, phases: ['validating', 'uploading'] },
  { key: 'extract', i18n: 'workbench.upload_extracting', label: 'Extracting clinical text', icon: ScanText, phases: ['extracting'] },
  { key: 'index', i18n: 'workbench.upload_indexing', i18nShort: 'workbench.upload_indexing_short', label: 'Building hybrid FAISS + BM25 index', short: 'Building search index', icon: DatabaseZap, phases: ['indexing'] },
  { key: 'ready', i18n: 'workbench.upload_ready', label: 'Ready for Q&A', icon: MessageSquareText, phases: ['ready'] },
];

function stepIndex(phase) {
  const i = UPLOAD_STEPS.findIndex((s) => s.phases.includes(phase));
  return i === -1 ? 0 : i;
}

export default function UploadStepper({ upload, onDismiss, className }) {
  const { t } = useTranslation();
  const [now, setNow] = useState(Date.now());
  const active = upload && upload.phase !== 'ready' && upload.phase !== 'error';

  useEffect(() => {
    if (!active) return undefined;
    const id = setInterval(() => setNow(Date.now()), 500);
    return () => clearInterval(id);
  }, [active]);

  if (!upload) return null;
  const current = stepIndex(upload.phase);
  const isError = upload.phase === 'error';
  const isReady = upload.phase === 'ready';
  const elapsed = upload.startedAt ? Math.max(0, Math.round(((upload.finishedAt || now) - upload.startedAt) / 100) / 10) : null;

  return (
    <div
      data-testid="upload-progress-banner"
      role="status"
      aria-live="polite"
      className={cn('rounded-2xl ms-raised px-3.5 py-3 animate-fade-in', isError && 'border-rose-200 bg-rose-50', className)}
    >
      <div className="flex items-center gap-2.5 mb-2.5">
        <span className="relative flex h-2 w-2 shrink-0">
          {active && <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-cyan-600 opacity-70" />}
          <span className={cn('relative inline-flex rounded-full h-2 w-2', isError ? 'bg-rose-600' : isReady ? 'bg-emerald-600' : 'bg-cyan-600')} />
        </span>
        <span className="text-xs font-semibold text-slate-900 truncate min-w-0 flex-1">
          {isError ? t('workbench.upload_failed', 'Upload failed') : isReady ? t('workbench.upload_report_ready', 'Report ready') : t('workbench.upload_processing', 'Processing report...')}
          {upload.fileName ? <span className="text-slate-600 font-normal"> {upload.fileName}</span> : null}
        </span>
        {elapsed !== null && <span className="ms-num text-xs text-ink-faint shrink-0">{elapsed.toFixed(1)}s</span>}
        {upload.warming && isReady && (
          <span className="inline-flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-full bg-amber-50 text-amber-700 border border-amber-200 shrink-0">
            <Flame className="w-3 h-3" /> {t('workbench.warming_cache', 'Warming summary cache')}
          </span>
        )}
        {(isReady || isError) && onDismiss && (
          <button type="button" onClick={onDismiss} aria-label="Dismiss upload status" className="w-7 h-7 -mr-1 rounded-lg flex items-center justify-center text-slate-400 hover:text-slate-800 hover:bg-slate-100">
            <X className="w-3.5 h-3.5" />
          </button>
        )}
      </div>

      {isError ? (
        <div className="flex items-start gap-2 text-xs text-rose-700">
          <AlertTriangle className="w-3.5 h-3.5 mt-0.5 shrink-0" />
          <span>{upload.error || 'The report could not be processed. Check that it is a text-based PDF under 50 MB and try again.'}</span>
        </div>
      ) : (
        <ol className="grid grid-cols-4 gap-1.5">
          {UPLOAD_STEPS.map((step, i) => {
            const done = i < current || isReady;
            const running = i === current && !isReady;
            const Icon = step.icon;
            return (
              <li key={step.key} className="min-w-0">
                <div className="relative h-1 rounded-full bg-slate-200 overflow-hidden">
                  {done && <div className="absolute inset-0 bg-emerald-600" />}
                  {running && <div className="absolute inset-0 bg-cyan-600 animate-stage-sweep" />}
                </div>
                <div className={cn('mt-1.5 flex items-center gap-1 text-xs leading-tight', done ? 'text-emerald-700 font-medium' : running ? 'text-slate-900 font-medium' : 'text-slate-400')}>
                  {done ? <Check className="w-3.5 h-3.5 shrink-0 text-emerald-600" /> : running ? <Loader2 className="w-3 h-3 shrink-0 animate-spin text-cyan-600" /> : <Icon className="w-3 h-3 shrink-0" />}
                  <span className="truncate hidden sm:inline" title={t(step.i18n, step.label)}>{t(step.i18n, step.label)}</span>
                  <span className="truncate sm:hidden">{step.i18nShort ? t(step.i18nShort, step.short) : t(step.i18n, step.label)}</span>
                </div>
              </li>
            );
          })}
        </ol>
      )}
    </div>
  );
}
