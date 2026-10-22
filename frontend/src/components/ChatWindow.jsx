import React, { useRef, useEffect, useState } from 'react';
import {
  Stethoscope, ArrowDown, Upload, FileText, Sparkles, Shield,
  Printer, Table, MessageSquare, AlertCircle, Sun, Moon, X, Download,
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
  onAttachFile,
  activePdf,
  documentId,
  showToast,
  darkMode,
  setDarkMode,
  currentUser,
  dependents,
  selectedPatientId,
  onSelectPatient,
  onOpenDependents,
  attachedDocuments = [],
  onDetachDocument,
  onOpenUpload,
  sidebarOpen = true,
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
      if (showToast) showToast('info', 'No PDF Report', 'Please upload a PDF report to extract lab metrics.');
      return;
    }
    setViewMode('metrics');
    setLoadingMetrics(true);
    if (!documentId) {
      showToast('error', 'Metrics Error', 'No document found for this session.');
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
    console.info(
      `[METRICS_TIMING] fetch: ${timing.fetchMs.toFixed(1)}ms | render+commit: ${commitMs.toFixed(1)}ms | rows: ${labMetrics.length}`
    );
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
  const cardBg = darkMode ? 'bg-[#121212]' : 'bg-white';
  const cardBorder = darkMode ? 'border-zinc-800' : 'border-zinc-200';
  const headerBg = darkMode ? 'bg-zinc-950' : 'bg-white';
  const textPrimary = darkMode ? 'text-white' : 'text-zinc-900';
  const textSecondary = darkMode ? 'text-zinc-400' : 'text-zinc-500';
  const textMuted = darkMode ? 'text-zinc-500' : 'text-zinc-400';

  const isSelf = !selectedPatientId || selectedPatientId === 'self' || (currentUser && selectedPatientId === currentUser.id);
  const activeDependent = !isSelf ? dependents?.find(d => d.id === selectedPatientId) : null;

  // A7: Welcome message
  const firstName = currentUser?.full_name?.split(' ')[0] || null;

  return (
    <div className={`flex-1 flex flex-col h-full overflow-hidden relative transition-colors duration-200 ${
      darkMode ? 'bg-zinc-950 text-zinc-50' : 'bg-zinc-50 text-zinc-900'
    }`}>
      {/* Header */}
      <header className={`h-14 px-4 flex items-center justify-between border-b z-10 transition-colors duration-200 ${
        darkMode ? 'bg-[#0e0e11] border-white/5' : 'bg-white border-zinc-200'
      }`}>
        <div className="flex items-center gap-2.5 sm:gap-3 min-w-0">
          {toggleSidebar && (
            <button
              onClick={toggleSidebar}
              aria-label="Toggle sidebar"
              className={`p-2 rounded-lg transition-colors ${
                darkMode
                  ? 'text-zinc-400 hover:text-white hover:bg-zinc-800/80'
                  : 'text-zinc-600 hover:text-zinc-900 hover:bg-zinc-100'
              }`}
            >
              {sidebarOpen ? <ChevronLeft className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
            </button>
          )}

          {/* Brand title on single line */}
          <span className={`text-base font-semibold tracking-tight whitespace-nowrap ${
            darkMode ? 'text-white' : 'text-zinc-900'
          }`}>
            MediSkye
          </span>

          {/* Subtle Patient Context Selector right next to MediSkye */}
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

        <div className="flex items-center gap-1.5 sm:gap-2">
          {/* Export Printable Doctor Summary when active report is present */}
          {activePdf && (
            <button
              onClick={handlePrintDoctorSummary}
              disabled={isExporting}
              aria-label="Export Summary"
              className={`p-2 rounded-lg text-xs flex items-center gap-1.5 transition-colors border ${
                isExporting ? 'opacity-70 cursor-not-allowed ' : ''
              }${
                darkMode
                  ? 'bg-zinc-900 hover:bg-zinc-800 text-zinc-300 border-zinc-800 hover:text-white'
                  : 'bg-white hover:bg-zinc-50 text-zinc-700 border-zinc-200'
              }`}
              title="Export 1-Click Printable Doctor Consultation Summary"
            >
              <Printer className="w-4 h-4" />
              <span className="hidden lg:inline">
                {isExporting ? t('chat.preparing_summary', 'Preparing Summary...') : t('chat.export_summary', 'Export Summary')}
              </span>
            </button>
          )}

          {/* Export Chat Data */}
          {onOpenExport && (
            <button
              onClick={onOpenExport}
              aria-label="Export chat data"
              className={`p-2 rounded-lg transition-colors border ${
                darkMode
                  ? 'bg-zinc-900 hover:bg-zinc-800 text-zinc-300 border-zinc-800 hover:text-white'
                  : 'bg-white hover:bg-zinc-50 text-zinc-700 border-zinc-200'
              }`}
              title="Export full chat transcript and lab metrics (PDF or JSON)"
            >
              <Download className="w-4 h-4" />
            </button>
          )}

          {/* Theme toggle */}
          {setDarkMode && (
            <button
              onClick={() => setDarkMode(!darkMode)}
              aria-label={darkMode ? 'Switch to light theme' : 'Switch to dark theme'}
              className={`p-2 rounded-lg transition-colors ${
                darkMode
                  ? 'text-zinc-400 hover:text-white hover:bg-zinc-800'
                  : 'text-zinc-500 hover:text-zinc-900 hover:bg-zinc-100'
              }`}
            >
              {darkMode ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
            </button>
          )}

          {/* User Avatar Circle */}
          {currentUser && (
            <div
              className={`w-8 h-8 rounded-full flex items-center justify-center font-medium text-xs border ${
                darkMode
                  ? 'bg-zinc-800 text-zinc-200 border-white/10'
                  : 'bg-zinc-200 text-zinc-800 border-zinc-300'
              }`}
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
                    ? 'bg-white text-black border-zinc-700 hover:bg-zinc-200'
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
          <div className="w-full flex flex-col items-center justify-center text-center max-w-xl mx-auto py-8 my-auto animate-fade-in px-4">
            <div className={`w-12 h-12 rounded-2xl flex items-center justify-center mb-3 shadow-lg ${
              darkMode
                ? 'bg-gradient-to-tr from-cyan-500/20 to-blue-500/20 text-cyan-400 border border-cyan-500/30 shadow-cyan-950/40'
                : 'bg-gradient-to-tr from-blue-50 to-cyan-50 text-blue-600 border border-blue-200'
            }`}>
              <Sparkles className="w-6 h-6 animate-pulse" />
            </div>

            {/* Subtle brand badge ensuring test compatibility */}
            <span className={`text-[11px] font-semibold uppercase tracking-wider mb-2 ${
              darkMode ? 'text-zinc-500' : 'text-zinc-400'
            }`}>
              MediSkye AI Medical Assistant
            </span>

            <h1 className={`text-2xl sm:text-3xl font-medium tracking-tight mb-6 ${textPrimary}`}>
              Where should we start?
            </h1>

            {/* Starter prompts as clean stack on mobile, sm:grid-cols-2 grid on desktop */}
            <div className="w-full grid grid-cols-1 sm:grid-cols-2 gap-2.5 text-left mb-6">
              {sampleQueries.map((item, idx) => (
                <button
                  key={idx}
                  onClick={() => onSelectSampleQuery(item.query)}
                  className={`w-full flex items-center gap-3 py-3 px-3.5 text-sm rounded-xl transition-all duration-150 border ${
                    darkMode
                      ? 'text-zinc-300 hover:text-white bg-white/[0.02] hover:bg-white/5 border-white/5 hover:border-white/10 active:bg-white/10'
                      : 'text-zinc-700 hover:text-zinc-900 bg-zinc-50/80 hover:bg-zinc-100 border-zinc-200/60 active:bg-zinc-200'
                  }`}
                >
                  <div className={`p-1.5 rounded-lg shrink-0 ${
                    darkMode ? 'bg-zinc-900 text-zinc-400' : 'bg-zinc-200 text-zinc-600'
                  }`}>
                    {idx === 0 ? <Activity className="w-4 h-4" /> :
                     idx === 1 ? <FileText className="w-4 h-4" /> :
                     idx === 2 ? <HelpCircle className="w-4 h-4" /> :
                     <Sparkles className="w-4 h-4" />}
                  </div>
                  <span className="truncate">{item.title}</span>
                </button>
              ))}

              {/* "Try with a Sample Blood Test Report" item - spanning across 2 columns on desktop */}
              <button
                onClick={() => onSelectSampleQuery('Please show and explain a sample blood test report with common metrics like Hemoglobin, WBC, and Platelets.')}
                className={`w-full sm:col-span-2 flex items-center gap-3 py-3 px-3.5 text-sm rounded-xl transition-all duration-150 border ${
                  darkMode
                    ? 'text-cyan-300 hover:text-cyan-200 bg-cyan-950/20 hover:bg-cyan-950/30 border-cyan-800/30 hover:border-cyan-700/50'
                    : 'text-blue-700 hover:text-blue-900 bg-blue-50/50 hover:bg-blue-50 border-blue-200 hover:border-blue-300'
                }`}
              >
                <div className={`p-1.5 rounded-lg shrink-0 ${
                  darkMode ? 'bg-cyan-950/60 text-cyan-400' : 'bg-blue-100 text-blue-600'
                }`}>
                  <FileText className="w-4 h-4" />
                </div>
                <span className="font-medium truncate">Try with a Sample Blood Test Report</span>
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
                showToast={showToast}
                darkMode={darkMode}
              />
            ))}
          </div>
        )}
      </div>

      {/* Floating Mode Switcher Pill (Above Input Box) */}
      {activePdf && (
        <div className="w-full max-w-3xl mx-auto px-4 md:px-6 flex justify-center pb-2 shrink-0 z-10 pointer-events-none">
          <div className={`pointer-events-auto mx-auto mb-2.5 flex items-center rounded-full p-1 border shadow-md w-fit backdrop-blur-md transition-colors ${
            darkMode
              ? 'bg-zinc-900/90 border-white/10'
              : 'bg-white/95 border-zinc-200 shadow-sm'
          }`}>
            <button
              onClick={() => setViewMode('chat')}
              aria-label="Switch to chat view"
              className={`px-4 py-1 rounded-full text-xs font-medium transition-all flex items-center gap-1.5 ${
                viewMode === 'chat'
                  ? darkMode
                    ? 'bg-zinc-700/80 text-white shadow-xs'
                    : 'bg-zinc-900 text-white shadow-xs'
                  : darkMode
                    ? 'text-zinc-400 hover:text-zinc-200'
                    : 'text-zinc-600 hover:text-zinc-900'
              }`}
            >
              <MessageSquare className="w-3.5 h-3.5" />
              <span>{t('chat.view_chat', 'Chat')}</span>
            </button>
            <button
              onClick={loadMetrics}
              aria-label="View extracted lab metrics table"
              className={`px-4 py-1 rounded-full text-xs font-medium transition-all flex items-center gap-1.5 ${
                viewMode === 'metrics'
                  ? darkMode
                    ? 'bg-zinc-700/80 text-white shadow-xs'
                    : 'bg-zinc-900 text-white shadow-xs'
                  : darkMode
                    ? 'text-zinc-400 hover:text-zinc-200'
                    : 'text-zinc-600 hover:text-zinc-900'
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
          className={`absolute bottom-20 right-6 z-20 p-2.5 rounded-full shadow-lg transition-all duration-150 ${
            darkMode
              ? 'bg-zinc-100 text-black hover:bg-zinc-200'
              : 'bg-zinc-900 text-white hover:bg-zinc-800'
          }`}
        >
          <ArrowDown className="w-4 h-4" />
        </button>
      )}
    </div>
  );
}
