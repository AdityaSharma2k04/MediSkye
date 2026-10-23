import React, { useRef, useEffect, useState } from 'react';
import {
  Stethoscope, ArrowDown, Upload, FileText, Sparkles, Shield,
  Printer, Table, MessageSquare, AlertCircle, X, Download,
  ChevronLeft, ChevronRight, Activity, HelpCircle
} from 'lucide-react';
import { useTranslation } from 'react-i18next';
import ChatMessage from './ChatMessage';
import LabMetrics from './LabMetrics';
import PrintableSummary from './PrintableSummary';
import PatientContextSelector from './PatientContextSelector';
import { fetchLabMetrics, getProfile, sendQueryStream, getDocumentSummary } from '../services/api';

export default function ChatWindow({
  messages,
  isGenerating,
  loadingHistory = false,
  onRegenerate,
  onSelectSampleQuery,
  onTrySampleReport,
  activePdf,
  documentId,
  darkMode,
  currentUser,
  dependents,
  selectedPatientId,
  onSelectPatient,
  onOpenDependents,
  onOpenUpload,
  toggleSidebar,
  isExportingSummary: propIsExportingSummary,
  printSummaryText: propPrintSummaryText,
  onExportSummary,
  onOpenExport,
}) {
  const { t } = useTranslation();
  const scrollRef = useRef(null);
  const [showScrollBtn, setShowScrollBtn] = useState(false);
  const [viewMode, setViewMode] = useState('chat');
  const [labMetrics, setLabMetrics] = useState([]);
  const [loadingMetrics, setLoadingMetrics] = useState(false);
  const [showPrintSummary, setShowPrintSummary] = useState(false);
  const [localIsExporting, setLocalIsExporting] = useState(false);
  const [localPrintSummaryText, setLocalPrintSummaryText] = useState('');
  // Resolved user for the print summary — falls back to a fresh fetch if currentUser is null
  const [printUser, setPrintUser] = useState(null);
  const metricsTimingRef = useRef(null);

  const isExporting = propIsExportingSummary !== undefined ? propIsExportingSummary : localIsExporting;
  const currentSummaryText = propPrintSummaryText !== undefined ? propPrintSummaryText : localPrintSummaryText;

  // When activePdf is removed, reset to chat view
  useEffect(() => {
    if (!activePdf && viewMode === 'metrics') setViewMode('chat');
  }, [activePdf]);

  const scrollToBottom = () => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isGenerating]);

  const handleScroll = () => {
    if (!scrollRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = scrollRef.current;
    if (scrollHeight - scrollTop - clientHeight > 150) {
      setShowScrollBtn(true);
    } else {
      setShowScrollBtn(false);
    }
  };

  const loadMetrics = async () => {
    if (!activePdf) {
      console.warn('No PDF report attached to extract lab metrics.');
      return;
    }
    setViewMode('metrics');
    setLoadingMetrics(true);
    if (!documentId) {
      console.error('Metrics Error: No document found for this session.');
      setLoadingMetrics(false);
      return;
    }
    const tFetch = typeof performance !== 'undefined' ? performance.now() : 0;
    const metrics = await fetchLabMetrics(documentId);
    if (typeof performance !== 'undefined') {
      metricsTimingRef.current = { fetchMs: performance.now() - tFetch, resolvedAt: performance.now() };
    }
    setLabMetrics(metrics);
    setLoadingMetrics(false);
  };

  // [METRICS_TIMING] network vs. React commit time for the metrics view.
  // Logged once per load so slow "browser metrics" can be attributed to the
  // request or to rendering without attaching a profiler.
  useEffect(() => {
    const timing = metricsTimingRef.current;
    if (!timing || loadingMetrics || viewMode !== 'metrics') return;
    metricsTimingRef.current = null;
    const commitMs = performance.now() - timing.resolvedAt;
    if (import.meta.env.DEV) {
      console.info(
        `[METRICS_TIMING] fetch: ${timing.fetchMs.toFixed(1)}ms | render+commit: ${commitMs.toFixed(1)}ms | rows: ${labMetrics.length}`
      );
    }
  }, [loadingMetrics, labMetrics, viewMode]);

  const handlePrintDoctorSummary = async () => {
    if (isExporting) return;

    // Resolve user — prefer prop, fall back to fresh GET /users/me
    let resolvedUser = currentUser;
    if (!resolvedUser) {
      try { resolvedUser = await getProfile(); } catch (_) {}
    }
    setPrintUser(resolvedUser);

    // Auto-fetch metrics if user hasn't opened Lab Metrics tab yet
    if (documentId && labMetrics.length === 0) {
      try {
        const m = await fetchLabMetrics(documentId);
        setLabMetrics(m);
      } catch (_) {}
    }

    let summaryTextToUse = '';
    if (onExportSummary) {
      summaryTextToUse = await onExportSummary();
    } else {
      setLocalIsExporting(true);
      const assistantMsgs = (messages || []).filter((m) => m.sender === 'assistant');
      const fallbackText = assistantMsgs.length > 0 ? assistantMsgs[assistantMsgs.length - 1].text : '';

      if (documentId) {
        try {
          const res = await getDocumentSummary(documentId);
          if (res && res.summary) {
            summaryTextToUse = res.summary.trim();
          }
        } catch (_) {
          summaryTextToUse = fallbackText;
        }
      } else {
        summaryTextToUse = fallbackText;
      }

      summaryTextToUse = (summaryTextToUse && summaryTextToUse.trim()) ? summaryTextToUse : fallbackText;
      setLocalPrintSummaryText(summaryTextToUse);
      setLocalIsExporting(false);
    }

    setShowPrintSummary(true);
    // Give React time to commit PrintableSummary to the DOM before printing
    setTimeout(() => {
      window.print();
      const cleanup = () => {
        setShowPrintSummary(false);
        window.removeEventListener('afterprint', cleanup);
      };
      window.addEventListener('afterprint', cleanup);
    }, 150);
  };

  // A1b: Context-aware suggestion cards
  const emptyStateSuggestions = [
    { title: 'Explain Hemoglobin levels', query: 'Explain Hemoglobin levels and what they indicate about health.' },
    { title: 'Cholesterol & LDL — what do they mean?', query: 'What do Cholesterol and LDL levels mean, and what are healthy ranges?' },
    { title: 'Common lab tests explained', query: 'What are the most common blood lab tests and what do they measure?' },
    { title: 'When should I see a doctor?', query: 'When should I see a doctor about my lab results?' },
  ];

  const loadedStateSuggestions = [
    { title: 'What are my abnormal values?', query: 'What are my abnormal values in this report?' },
    { title: 'Explain my first abnormal biomarker', query: 'Explain my first abnormal biomarker and what it means.' },
    { title: 'Summarize for my doctor', query: 'Summarize this report for my doctor in plain language.' },
    { title: 'What should I ask my doctor?', query: 'What should I ask my doctor based on this report?' },
  ];

  const sampleQueries = activePdf ? loadedStateSuggestions : emptyStateSuggestions;

  // Shared color helpers
  const cardBg = darkMode ? 'bg-[#0e131b]' : 'bg-white';
  const cardBorder = darkMode ? 'border-white/[0.08]' : 'border-zinc-200';
  const textPrimary = darkMode ? 'text-white' : 'text-zinc-900';
  const textSecondary = darkMode ? 'text-zinc-400' : 'text-zinc-500';
  const textMuted = darkMode ? 'text-zinc-500' : 'text-zinc-400';

  return (
    <div className={`flex-1 flex flex-col h-full overflow-hidden relative transition-colors duration-200 ${
      darkMode ? 'bg-[#07090e] text-slate-100' : 'bg-zinc-50 text-zinc-900'
    }`}>
      {/* Header — Gemini-style minimal top navbar, non-overlapping flex bar */}
      <header className="h-14 px-3 sm:px-5 flex items-center justify-between gap-2 bg-[#07090e] border-b border-white/[0.06] shrink-0 z-20">
        <div className="flex items-center gap-2 min-w-0 flex-1">
          {toggleSidebar && (
            <button
              onClick={toggleSidebar}
              aria-label="Toggle sidebar"
              className="w-9 h-9 rounded-full flex items-center justify-center text-slate-300 hover:bg-white/5 shrink-0 transition"
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                <line x1="4" y1="8" x2="20" y2="8" />
                <line x1="4" y1="16" x2="15" y2="16" />
              </svg>
            </button>
          )}

          {/* Brand title + Inline Patient Selector (Gemini Style) */}
          <span className="font-semibold text-white text-sm sm:text-base tracking-tight whitespace-nowrap shrink-0">
            MediSkye
          </span>

          {currentUser && (
            <PatientContextSelector
              currentUser={currentUser}
              dependents={dependents}
              selectedPatientId={selectedPatientId}
              onSelectPatient={onSelectPatient}
              onOpenDependents={onOpenDependents}
              darkMode={darkMode}
              hideLabel={true}
            />
          )}
        </div>

        <div className="flex items-center gap-1.5 sm:gap-2 shrink-0 ml-auto">
          {/* Print Doctor Summary when an active report is present */}
          {activePdf && (
            <button
              onClick={handlePrintDoctorSummary}
              disabled={isExporting}
              aria-label="Export Summary"
              className={`w-9 h-9 rounded-xl bg-white/[0.04] hover:bg-cyan-500/15 border border-white/[0.08] hover:border-cyan-500/30 text-slate-300 hover:text-cyan-300 flex items-center justify-center transition shrink-0 ${
                isExporting ? 'opacity-70 cursor-not-allowed' : ''
              }`}
              title={isExporting ? t('chat.preparing_summary', 'Preparing Summary...') : 'Export 1-Click Printable Doctor Consultation Summary'}
            >
              <Printer className={`w-4 h-4 ${isExporting ? 'animate-pulse' : ''}`} />
            </button>
          )}

          {/* Download / Share Chat */}
          {onOpenExport && (
            <button
              onClick={onOpenExport}
              aria-label="Export chat data"
              className="w-9 h-9 rounded-xl bg-white/[0.04] hover:bg-cyan-500/15 border border-white/[0.08] hover:border-cyan-500/30 text-slate-300 hover:text-cyan-300 flex items-center justify-center transition shrink-0"
              title="Export full chat transcript and lab metrics (PDF or JSON)"
            >
              <Download className="w-4 h-4" />
            </button>
          )}

          {/* User Avatar Circle */}
          {currentUser && (
            <div
              className="w-8 h-8 rounded-full bg-cyan-500/15 ring-2 ring-cyan-500/40 text-cyan-300 font-semibold text-xs flex items-center justify-center shrink-0"
              title={currentUser.email || currentUser.full_name}
            >
              {currentUser.full_name
                ? currentUser.full_name.charAt(0).toUpperCase()
                : (currentUser.email ? currentUser.email.charAt(0).toUpperCase() : 'U')}
            </div>
          )}
        </div>
      </header>

      <div
        ref={scrollRef}
        onScroll={handleScroll}
        className={`chat-messages-container flex-1 overflow-y-auto py-4 sm:py-6 w-full mx-auto flex flex-col px-4 md:px-6 transition-all duration-200 ${
          viewMode === 'metrics' ? 'max-w-4xl' : 'max-w-3xl'
        }`}
      >
        {viewMode === 'metrics' ? (
          loadingMetrics ? (
            <div className="py-4 animate-fade-in" data-testid="metrics-skeleton">
              <div className="flex items-center gap-3 mb-4">
                <Sparkles className={`w-5 h-5 animate-spin ${textSecondary}`} />
                <div>
                  <div className={`text-sm font-medium ${darkMode ? 'text-zinc-300' : 'text-zinc-700'}`}>{t('chat.extracting_metrics', 'Extracting Lab Value Metrics...')}</div>
                  <div className={`text-xs mt-0.5 ${textMuted}`}>{t('chat.analyzing_ranges', 'Analyzing numerical bounds & reference ranges')}</div>
                </div>
              </div>
              <div className={`rounded-xl border overflow-hidden ${cardBg} ${cardBorder}`} role="status" aria-label="Loading lab metrics">
                <div className="grid grid-cols-5 gap-4 px-4 py-3 border-b border-zinc-800/70">
                  {[0, 1, 2, 3, 4].map((i) => (
                    <div key={`h${i}`} className="skeleton-shimmer h-3 rounded-md" style={{ width: i === 0 ? '60%' : '45%' }} />
                  ))}
                </div>
                {[0, 1, 2, 3, 4].map((row) => (
                  <div key={`r${row}`} className="grid grid-cols-5 gap-4 px-4 py-3 border-b border-zinc-800/60 last:border-b-0">
                    <div className="skeleton-shimmer h-3 rounded-md" />
                    <div className="skeleton-shimmer h-3 rounded-md w-2/3" />
                    <div className="skeleton-shimmer h-3 rounded-md w-1/3" />
                    <div className="skeleton-shimmer h-3 rounded-md w-3/4" />
                    <div className="skeleton-shimmer h-3 rounded-md w-1/2" />
                  </div>
                ))}
              </div>
            </div>
          ) : labMetrics.length === 0 ? (
            <div className={`p-8 sm:p-10 text-center rounded-2xl border mt-4 ${cardBg} ${cardBorder} animate-fade-in`}>
              <div className={`w-14 h-14 rounded-2xl flex items-center justify-center mx-auto mb-4 ${
                darkMode ? 'bg-zinc-800 text-zinc-400' : 'bg-zinc-100 text-zinc-500'
              }`}>
                <AlertCircle className="w-6 h-6" />
              </div>
              <div className={`text-sm font-semibold mb-1.5 ${textPrimary}`}>{t('chat.no_metrics_found', 'No Lab Values Found')}</div>
              <div className={`text-xs max-w-md mx-auto leading-relaxed mb-5 ${textSecondary}`}>
                {t('chat.no_metrics_desc', 'Upload a text-based diagnostic PDF report (e.g. CBC Blood Test or Lipid Panel) to extract structured lab metrics.')}
              </div>
              <button
                onClick={onOpenUpload}
                className={`inline-flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-medium border transition-all active:scale-[0.97] ${
                  darkMode
                    ? 'bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-semibold border-cyan-400/40 transition'
                    : 'bg-zinc-900 text-white border-zinc-800 hover:bg-zinc-700'
                }`}
              >
                <Upload className="w-3.5 h-3.5" />
                <span>{t('chat.upload_report', 'Upload a Report')}</span>
              </button>
            </div>
          ) : (
            <LabMetrics
              metrics={labMetrics}
              darkMode={darkMode}
              onBack={() => setViewMode('chat')}
            />
          )
        ) : loadingHistory ? (
          <div className="min-h-[72vh] flex flex-col items-center justify-center text-center max-w-2xl mx-auto py-8 animate-fade-in">
            <Sparkles className={`w-8 h-8 animate-spin ${textSecondary} mb-3`} />
            <div className={`text-sm font-medium ${darkMode ? 'text-zinc-300' : 'text-zinc-700'}`}>{t('chat.loading_conversation', 'Loading Conversation...')}</div>
            <div className={`text-xs mt-1 ${textMuted}`}>{t('chat.fetching_messages', 'Fetching latest messages from Neon DB')}</div>
          </div>
        ) : messages.length === 0 ? (
          /* ── GEMINI MINIMALIST EMPTY STATE ── */
          <div className="w-full flex-1 flex flex-col items-center justify-center text-center max-w-xl mx-auto pt-12 pb-6 my-auto animate-fade-in px-2 sm:px-4">
            <div className="w-12 h-12 rounded-2xl flex items-center justify-center mb-4 bg-gradient-to-tr from-cyan-500/20 to-blue-500/20 text-cyan-400 border border-cyan-500/30 shadow-lg shadow-cyan-950/40">
              <Sparkles className="w-6 h-6 animate-pulse" />
            </div>

            <span className="sr-only">MediSkye AI Medical Assistant</span>

            <h1 className="text-2xl sm:text-3xl font-medium text-white tracking-tight text-center mb-7">
              Where should we start?
            </h1>

            {/* Borderless Gemini-style starter prompt rows */}
            <div className="w-full flex flex-col gap-1 text-left mb-6">
              {sampleQueries.map((item, idx) => (
                <button
                  key={idx}
                  onClick={() => onSelectSampleQuery(item.query)}
                  className="w-full flex items-center gap-3.5 py-3 px-3.5 rounded-2xl text-left text-[15px] text-slate-300 hover:text-white hover:bg-white/[0.05] active:bg-white/[0.08] transition"
                >
                  {idx === 0 ? <Activity className="w-4 h-4 text-slate-500 shrink-0" /> :
                   idx === 1 ? <FileText className="w-4 h-4 text-slate-500 shrink-0" /> :
                   idx === 2 ? <HelpCircle className="w-4 h-4 text-slate-500 shrink-0" /> :
                   <Sparkles className="w-4 h-4 text-slate-500 shrink-0" />}
                  <span className="truncate">{item.title}</span>
                </button>
              ))}

              {/* 5th item: subtle cyan-accented borderless row */}
              <button
                onClick={() => {
                  if (onTrySampleReport) {
                    onTrySampleReport();
                  } else if (onSelectSampleQuery) {
                    onSelectSampleQuery('Can you summarize the abnormal findings in this report?');
                  }
                }}
                className="w-full flex items-center gap-3.5 py-3 px-3.5 rounded-2xl text-left text-[15px] text-cyan-400 hover:bg-cyan-500/10 font-medium transition"
              >
                <FileText className="w-4 h-4 text-cyan-400 shrink-0" />
                <span className="truncate">Try with a Sample Blood Test Report</span>
              </button>
            </div>

            <div className={`flex items-center gap-2 text-xs ${textMuted}`}>
              <Shield className="w-3.5 h-3.5" />
              <span>{t('chat.encrypted_session', 'End-to-end encrypted session • Discarded on close')}</span>
            </div>
          </div>
        ) : (
          /* ── LOADED STATE — show conversation (no duplicate chip) ── */
          <div className="py-4">
            {messages.map((msg, index) => (
              <ChatMessage
                key={msg.id || index}
                message={msg}
                onRegenerate={index === messages.length - 1 && msg.sender === 'assistant' ? onRegenerate : null}
                darkMode={darkMode}
              />
            ))}
          </div>
        )}
      </div>

      {/* Non-scrolling bottom Mode Switcher Pill (Directly above composer so chat text is never covered) */}
      {activePdf && (
        <div className="w-full max-w-3xl mx-auto px-4 md:px-6 flex justify-center pt-1.5 pb-2.5 shrink-0 bg-[#07090e] z-10">
          <div className="mx-auto flex items-center rounded-full p-1 border border-white/[0.08] bg-[#151a23] w-fit">
            <button
              onClick={() => setViewMode('chat')}
              aria-label="Switch to chat view"
              className={`flex items-center gap-1.5 transition ${
                viewMode === 'chat'
                  ? 'rounded-full bg-[#282d37] text-white font-medium px-4 py-1.5 text-xs shadow-xs'
                  : 'rounded-full text-slate-400 hover:text-slate-200 px-4 py-1.5 text-xs font-medium'
              }`}
            >
              <MessageSquare className="w-3.5 h-3.5" />
              <span>{t('chat.view_chat', 'Chat')}</span>
            </button>
            <button
              onClick={loadMetrics}
              aria-label="View extracted lab metrics table"
              className={`flex items-center gap-1.5 transition ${
                viewMode === 'metrics'
                  ? 'rounded-full bg-[#282d37] text-white font-medium px-4 py-1.5 text-xs shadow-xs'
                  : 'rounded-full text-slate-400 hover:text-slate-200 px-4 py-1.5 text-xs font-medium'
              }`}
            >
              <Table className="w-3.5 h-3.5" />
              <span>{t('chat.lab_metrics', 'Lab Metrics')}</span>
            </button>
          </div>
        </div>
      )}

      {/* PrintableSummary — mounted only when printing */}
      {showPrintSummary && (() => {
        const activePatient =
          selectedPatientId && selectedPatientId !== 'self' && (!currentUser || String(selectedPatientId) !== String(currentUser.id))
            ? dependents?.find((d) => String(d.id) === String(selectedPatientId)) || (printUser || currentUser)
            : (printUser || currentUser);

        const summaryToPrint =
          currentSummaryText ||
          messages.filter((m) => m.sender === 'assistant').map((m) => m.text).join('\n\n');

        return (
          <PrintableSummary
            user={activePatient}
            document={activePdf}
            summary={summaryToPrint}
            metrics={labMetrics}
            specialists={messages.flatMap((m) => m.specialists || [])}
          />
        );
      })()}

      {showScrollBtn && (
        <button
          onClick={scrollToBottom}
          aria-label="Scroll to latest message"
          title="Scroll to latest message"
          className="absolute bottom-14 right-6 z-20 w-8 h-8 rounded-full bg-[#1a1f29] border border-white/15 text-slate-300 hover:text-white shadow-lg flex items-center justify-center transition-all duration-150"
        >
          <ArrowDown className="w-4 h-4" />
        </button>
      )}
    </div>
  );
}
