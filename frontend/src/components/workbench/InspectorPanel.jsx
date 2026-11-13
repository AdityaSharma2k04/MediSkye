import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Activity,
  FlaskConical,
  LineChart,
  FileText,
  X,
  RefreshCw,
  Printer,
  Download,
  Calendar,
  History,
  AlertTriangle,
  Upload,
  Sparkles,
} from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { cn } from '../../lib/cn';
import LabMetrics from '../LabMetrics';
import OrganSystemsOverview from '../clinical/OrganSystemsOverview';
import TrendsView from '../clinical/TrendsView';
import { reportLabel, reportDateLabel } from '../../lib/clinical';

export const INSPECTOR_TABS = [
  { value: 'overview', label: 'Overview', icon: Activity },
  { value: 'metrics', label: 'Metrics', icon: FlaskConical },
  { value: 'trends', label: 'Trends', icon: LineChart },
  { value: 'report', label: 'Report', icon: FileText },
];

/**
 * Right-hand clinical inspector (desktop) / full-screen analytics view (mobile).
 * Shows the active report through four lenses: triage overview, the full
 * metrics table, longitudinal trends, and report/source details.
 */
export default function InspectorPanel({
  tab,
  onTabChange,
  tabs = INSPECTOR_TABS,
  metrics,
  metricsLoading,
  metricsError,
  onReloadMetrics,
  trends,
  activePdf,
  attachedDocuments = [],
  metricsFilter,
  onMetricsFilterChange,
  metricsSearch,
  onMetricsSearchChange,
  highlightKey,
  onFocusMetric,
  onAskAbout,
  onPrintSummary,
  isExporting,
  onExportChat,
  onUpload,
  onClose,
  layout = 'list',
  variant = 'pane',
  compactTabs = false,
}) {
  const { t } = useTranslation();
  const hasMetrics = Array.isArray(metrics) && metrics.length > 0;
  const isPane = variant === 'pane';

  return (
    <div className={cn('h-full min-h-0 flex flex-col', isPane ? 'bg-carbon/60' : 'bg-transparent')}>
      <div className={cn('shrink-0 flex items-center gap-2 border-b border-white/[0.06]', isPane ? 'h-12 px-3' : 'h-12 px-4')}>
        <div role="tablist" aria-label="Inspector views" data-testid="inspector-tabs" className="flex items-center gap-0.5 min-w-0 overflow-x-auto no-scrollbar">
          {tabs.map((tabDef) => {
            const active = tab === tabDef.value;
            const Icon = tabDef.icon;
            return (
              <button
                key={tabDef.value}
                type="button"
                role="tab"
                aria-selected={active}
                onClick={() => onTabChange(tabDef.value)}
                className={cn(
                  'relative ms-tap shrink-0 inline-flex items-center gap-1.5 h-8 px-2.5 rounded-lg text-xs font-medium transition-colors',
                  active ? 'text-white' : 'text-ink-mute hover:text-ink'
                )}
              >
                {active && (
                  <motion.span
                    layoutId={`inspector-tab-${variant}`}
                    className="absolute inset-0 rounded-lg bg-white/[0.07] border border-white/[0.08]"
                    transition={{ type: 'spring', stiffness: 520, damping: 40 }}
                  />
                )}
                <Icon className="relative w-3.5 h-3.5" />
                <span className={cn('relative', compactTabs && !active && 'sr-only')}>{t(`workbench.${tabDef.value}`, tabDef.label)}</span>
              </button>
            );
          })}
        </div>
        <div className="ml-auto flex items-center gap-1 shrink-0">
          {onReloadMetrics && activePdf && (
            <button
              type="button"
              onClick={onReloadMetrics}
              aria-label="Re-run biomarker extraction"
              title="Re-run biomarker extraction"
              className="ms-tap w-8 h-8 rounded-lg flex items-center justify-center text-ink-mute hover:text-white hover:bg-white/[0.06] transition"
            >
              <RefreshCw className={cn('w-3.5 h-3.5', metricsLoading && 'animate-spin')} />
            </button>
          )}
          {onClose && (
            <button
              type="button"
              onClick={onClose}
              aria-label="Close clinical inspector"
              title={t('workbench.close_inspector', 'Close inspector')}
              className="ms-tap w-8 h-8 rounded-lg flex items-center justify-center text-ink-mute hover:text-white hover:bg-white/[0.06] transition"
            >
              <X className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>

      <div className={cn('flex-1 min-h-0 overflow-y-auto overscroll-contain', isPane ? 'px-4 py-4' : 'px-4 py-4 pb-10')}>
        {!activePdf ? (
          <NoReport onUpload={onUpload} t={t} />
        ) : metricsError && !hasMetrics && tab !== 'report' ? (
          <div data-testid="inspector-metrics-error" className="py-12 px-4 flex flex-col items-center justify-center text-center">
            <AlertTriangle className="w-8 h-8 text-amber-400/80 mb-3" />
            <div className="text-sm text-white font-medium mb-1">
              {t('inspector.metrics_error', 'Unable to load biomarker metrics')}
            </div>
            <div className="text-xs text-ink-mute max-w-xs mb-4">
              {typeof metricsError === 'string' ? metricsError : t('inspector.metrics_error_hint', 'A network error occurred while retrieving lab metrics.')}
            </div>
            {onReloadMetrics && (
              <button
                type="button"
                onClick={onReloadMetrics}
                className="ms-tap px-3 py-1.5 rounded-lg text-xs font-medium text-white bg-white/[0.08] hover:bg-white/[0.14] border border-white/[0.10] flex items-center gap-1.5 transition"
              >
                <RefreshCw className="w-3.5 h-3.5" />
                {t('common.retry', 'Retry')}
              </button>
            )}
          </div>
        ) : metricsLoading && !hasMetrics && tab !== 'report' ? (
          <MetricsSkeleton />
        ) : (
          <AnimatePresence mode="wait" initial={false}>
            <motion.div
              key={tab}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -4 }}
              transition={{ duration: 0.16, ease: [0.22, 1, 0.36, 1] }}
            >
              {tab === 'overview' &&
                (hasMetrics ? (
                  <OrganSystemsOverview
                    metrics={metrics}
                    compact={layout === 'list'}
                    onSelectMetric={(row) => onFocusMetric?.(row)}
                    onApplyFilter={(f) => {
                      onMetricsFilterChange?.(f);
                      onTabChange('metrics');
                    }}
                  />
                ) : (
                  <NoMetrics onUpload={onUpload} onReload={onReloadMetrics} />
                ))}

              {tab === 'metrics' && (
                <LabMetrics
                  metrics={metrics}
                  layout={layout}
                  filter={metricsFilter}
                  onFilterChange={onMetricsFilterChange}
                  search={metricsSearch}
                  onSearchChange={onMetricsSearchChange}
                  highlightKey={highlightKey}
                  onAskAbout={onAskAbout}
                />
              )}

              {tab === 'trends' && (
                <TrendsView
                  series={trends?.series}
                  loading={trends?.loading}
                  source={trends?.source}
                  reportCount={trends?.reportCount}
                  latestMetrics={metrics}
                  focusKey={highlightKey}
                  onUpload={onUpload}
                />
              )}

              {tab === 'report' && (
                <ReportDetails
                  activePdf={activePdf}
                  metrics={metrics}
                  attachedDocuments={attachedDocuments}
                  onPrintSummary={onPrintSummary}
                  isExporting={isExporting}
                  onExportChat={onExportChat}
                />
              )}
            </motion.div>
          </AnimatePresence>
        )}
      </div>
    </div>
  );
}

function ReportDetails({ activePdf, metrics, attachedDocuments, onPrintSummary, isExporting, onExportChat }) {
  const collected = metrics?.collected_at || activePdf?.collected_at;
  const priorDate = metrics?.prior_document_date;
  const isFuture = metrics?.is_future_collection_date || activePdf?.is_future_collection_date;
  const docs = attachedDocuments.length ? attachedDocuments : activePdf ? [activePdf] : [];

  return (
    <div className="space-y-4">
      <section className="rounded-2xl ms-surface p-4">
        <div className="flex items-start gap-3">
          <div className="w-10 h-12 rounded-lg bg-gradient-to-b from-white/[0.08] to-white/[0.02] border border-white/[0.1] flex items-center justify-center shrink-0">
            <FileText className="w-4 h-4 text-cyan-300" />
          </div>
          <div className="min-w-0">
            <div className="text-[13px] font-semibold text-white break-words">{activePdf?.filename || activePdf?.name || 'Lab report'}</div>
            <div className="text-xs text-ink-mute mt-0.5">{`Indexed for hybrid FAISS + BM25 retrieval`}</div>
          </div>
        </div>
        <dl className="mt-4 grid grid-cols-2 gap-3 text-xs">
          <Fact icon={Calendar} label="Specimen collected" value={collected || 'Not stated in report'} mono={Boolean(collected)} />
          <Fact icon={History} label="Compared against" value={priorDate ? `Report from ${priorDate}` : 'No earlier report'} />
          <Fact icon={FlaskConical} label="Biomarkers extracted" value={Array.isArray(metrics) ? String(metrics.length) : '—'} mono />
          <Fact icon={Sparkles} label="Answer grounding" value="Cited from this report" />
        </dl>
        {isFuture && (
          <div className="mt-3 flex items-start gap-2 text-xs text-amber-200 bg-amber-500/10 border border-amber-500/20 rounded-xl px-3 py-2">
            <AlertTriangle className="w-3.5 h-3.5 mt-px shrink-0" />
            The collection date on this report is in the future. It may be a synthetic or sample report.
          </div>
        )}
      </section>

      {docs.length > 1 && (
        <section className="rounded-2xl ms-surface p-4">
          <h4 className="text-xs font-semibold text-ink-mute mb-2">Sources in this conversation</h4>
          <ul className="space-y-1.5">
            {docs.map((d, i) => (
              <li key={d.id || i} className="flex items-center gap-2 text-xs text-ink-soft">
                <FileText className="w-3.5 h-3.5 text-ink-faint shrink-0" />
                <span className="truncate">{d.filename || d.name}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="grid grid-cols-1 gap-2">
        {onPrintSummary && (
          <button
            type="button"
            onClick={onPrintSummary}
            disabled={isExporting}
            className="ms-tap w-full flex items-center gap-3 px-4 h-12 rounded-2xl text-left bg-cyan-500/10 border border-cyan-500/25 hover:bg-cyan-500/15 text-cyan-100 transition disabled:opacity-60"
          >
            <Printer className={cn('w-4 h-4', isExporting && 'animate-pulse')} />
            <span className="text-[13px] font-medium">{isExporting ? 'Preparing physician report…' : 'Print physician report (A4)'}</span>
          </button>
        )}
        {onExportChat && (
          <button
            type="button"
            onClick={onExportChat}
            className="ms-tap w-full flex items-center gap-3 px-4 h-12 rounded-2xl text-left bg-white/[0.03] border border-white/[0.08] hover:bg-white/[0.06] text-ink-soft transition"
          >
            <Download className="w-4 h-4" />
            <span className="text-[13px] font-medium">Download transcript and metrics</span>
          </button>
        )}
      </section>
    </div>
  );
}

function Fact({ icon: Icon, label, value, mono }) {
  return (
    <div className="min-w-0">
      <dt className="flex items-center gap-1.5 text-xs text-ink-faint">
        <Icon className="w-3 h-3" /> {label}
      </dt>
      <dd className={cn('mt-1 text-ink-soft truncate', mono && 'ms-num')}>{value}</dd>
    </div>
  );
}

function NoReport({ onUpload, t }) {
  return (
    <div className="py-12 px-6 text-center">
      <div className="w-12 h-12 rounded-2xl mx-auto mb-3 flex items-center justify-center bg-white/[0.04] border border-white/[0.07] text-ink-mute">
        <FlaskConical className="w-5 h-5" />
      </div>
      <div className="ms-display text-lg text-white mb-1">{t('workbench.no_report_title', 'No report open')}</div>
      <p className="text-xs text-ink-mute max-w-[260px] mx-auto mb-5">{t('workbench.no_report_desc', 'Open a lab report from history or upload one to see biomarkers, ranges and trends here.')}</p>
      {onUpload && (
        <button type="button" onClick={onUpload} className="ms-tap inline-flex items-center gap-2 h-10 px-4 rounded-xl text-xs font-semibold bg-clinical-cyan text-slate-950 hover:bg-cyan-300 transition">
          <Upload className="w-3.5 h-3.5" /> Upload a report
        </button>
      )}
    </div>
  );
}

function NoMetrics({ onUpload, onReload }) {
  return (
    <div className="py-10 px-6 text-center rounded-2xl border border-dashed border-white/[0.1]">
      <div className="w-11 h-11 rounded-2xl mx-auto mb-3 flex items-center justify-center bg-white/[0.04] text-ink-mute">
        <AlertTriangle className="w-5 h-5" />
      </div>
      <div className="text-sm font-semibold text-white mb-1">No lab values found yet</div>
      <p className="text-xs text-ink-mute max-w-xs mx-auto mb-4">
        Extraction works on text-based reports such as a CBC or lipid panel. If this report was just uploaded, values may still be warming up.
      </p>
      <div className="flex items-center justify-center gap-2">
        {onReload && (
          <button type="button" onClick={onReload} className="ms-tap h-9 px-3.5 rounded-xl text-xs font-medium text-ink-soft border border-white/[0.1] hover:bg-white/[0.05]">
            Try extraction again
          </button>
        )}
        {onUpload && (
          <button type="button" onClick={onUpload} className="ms-tap h-9 px-3.5 rounded-xl text-xs font-semibold bg-clinical-cyan text-slate-950 hover:bg-cyan-300">
            Upload a Report
          </button>
        )}
      </div>
    </div>
  );
}

function MetricsSkeleton() {
  return (
    <div className="space-y-3 animate-fade-in" data-testid="metrics-skeleton" role="status" aria-label="Loading lab metrics">
      <div className="flex items-center gap-2.5 text-xs text-ink-mute">
        <Sparkles className="w-4 h-4 animate-pulse text-cyan-300" />
        Analyzing clinical biomarkers and reference ranges…
      </div>
      {[0, 1, 2, 3].map((i) => (
        <div key={i} className="rounded-2xl ms-surface p-3.5 space-y-2.5">
          <div className="flex justify-between">
            <div className="skeleton-shimmer h-3 w-1/3 rounded-md" />
            <div className="skeleton-shimmer h-3 w-14 rounded-full" />
          </div>
          <div className="skeleton-shimmer h-5 w-1/4 rounded-md" />
          <div className="skeleton-shimmer h-2 w-full rounded-full" />
        </div>
      ))}
    </div>
  );
}
