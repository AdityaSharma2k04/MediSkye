import React, { useRef, useEffect, useState } from 'react';
import {
  Stethoscope, ArrowDown, Upload, FileText, Sparkles, Shield,
  Printer, Table, MessageSquare, AlertCircle, Sun, Moon, X,
  ChevronLeft, ChevronRight
} from 'lucide-react';
import ChatMessage from './ChatMessage';
import LabMetrics from './LabMetrics';
import PrintableSummary from './PrintableSummary';
import { fetchLabMetrics, getProfile, sendQueryStream } from '../services/api';
import PatientContextSelector from './PatientContextSelector';

export default function ChatWindow({
  messages,
  isGenerating,
  onRegenerate,
  onSelectSource,
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
}) {

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
    const metrics = await fetchLabMetrics(documentId);
    setLabMetrics(metrics);
    setLoadingMetrics(false);
  };

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
      const promptText =
        'Generate a comprehensive, structured clinical summary of this entire report suitable for printing. Use clean markdown. Do not use emojis. Include an overview, abnormal findings grouped by system, and next steps.';

      let generatedText = '';
      const assistantMsgs = (messages || []).filter((m) => m.sender === 'assistant');
      const fallbackText = assistantMsgs.length > 0 ? assistantMsgs[assistantMsgs.length - 1].text : '';

      if (documentId) {
        try {
          await sendQueryStream(
            promptText,
            documentId,
            'English',
            (chunk) => {
              if (chunk.chunk || chunk.token) {
                generatedText += (chunk.chunk || chunk.token);
              }
            },
            selectedPatientId
          );
        } catch (_) {}
      }

      summaryTextToUse = (generatedText && generatedText.trim()) ? generatedText : fallbackText;
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
  const headerBg = darkMode ? 'bg-[#09090B]' : 'bg-white';
  const textPrimary = darkMode ? 'text-white' : 'text-zinc-900';
  const textSecondary = darkMode ? 'text-zinc-400' : 'text-zinc-500';
  const textMuted = darkMode ? 'text-zinc-500' : 'text-zinc-400';

  const isSelf = !selectedPatientId || selectedPatientId === 'self' || (currentUser && selectedPatientId === currentUser.id);
  const activeDependent = !isSelf ? dependents?.find(d => d.id === selectedPatientId) : null;

  // A7: Welcome message
  const firstName = currentUser?.full_name?.split(' ')[0] || null;

  return (
    <div className={`flex-1 flex flex-col h-full overflow-hidden relative transition-colors duration-200 ${
      darkMode ? 'bg-black text-slate-100' : 'bg-zinc-50 text-zinc-900'
    }`}>
      {/* Header */}
      <header className={`flex items-center justify-between p-3.5 px-4 sm:px-6 border-b z-10 transition-colors duration-200 ${headerBg} ${cardBorder}`}>
        <div className="flex items-center gap-3">
          {toggleSidebar && (
            <button
              onClick={toggleSidebar}
              aria-label="Toggle sidebar"
              className={`p-1.5 rounded-lg border transition-colors ${
                darkMode
                  ? 'border-zinc-800 text-zinc-400 hover:text-white hover:bg-zinc-800'
                  : 'border-zinc-200 text-zinc-600 hover:text-zinc-900 hover:bg-zinc-100'
              }`}
            >
              {sidebarOpen ? <ChevronLeft className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
            </button>
          )}

          <div className={`w-7 h-7 rounded-lg flex items-center justify-center font-bold text-xs ${
            darkMode ? 'bg-white text-black' : 'bg-zinc-900 text-white'
          }`}>
            <Stethoscope className="w-4 h-4" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className={`font-semibold text-sm ${textPrimary}`}>MediSkye AI Medical Assistant</h2>
              {activeDependent && (
                <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium border ${
                  darkMode
                    ? 'bg-rose-950/60 text-rose-300 border-rose-800/60'
                    : 'bg-rose-50 text-rose-700 border-rose-200'
                }`}>
                  Lens: {activeDependent.full_name} ({activeDependent.relationship})
                </span>
              )}
            </div>
            <p className={`text-[10px] ${textSecondary}`}>AI Medical Assistant</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* A4: Theme toggle in header (sun/moon icon) */}
          {setDarkMode && (
            <button
              onClick={() => setDarkMode(!darkMode)}
              aria-label={darkMode ? 'Switch to light theme' : 'Switch to dark theme'}
              className={`p-1.5 rounded-lg transition-colors ${
                darkMode
                  ? 'text-zinc-400 hover:text-white hover:bg-zinc-800'
                  : 'text-zinc-500 hover:text-zinc-900 hover:bg-zinc-100'
              }`}
            >
              {darkMode ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
            </button>
          )}

          {/* A4: Lab Metrics + Export Summary only when a document is loaded */}
          {activePdf && (
            <>
              <div className={`flex items-center rounded-xl p-0.5 text-xs border ${
                darkMode ? 'bg-zinc-900 border-zinc-800' : 'bg-zinc-100 border-zinc-200'
              }`}>
                <button
                  onClick={() => setViewMode('chat')}
                  aria-label="Switch to chat view"
                  className={`px-3 py-1 rounded-lg transition-colors flex items-center gap-1.5 ${
                    viewMode === 'chat'
                      ? darkMode
                        ? 'bg-zinc-800 text-white font-medium'
                        : 'bg-white text-zinc-900 font-medium shadow-sm'
                      : darkMode
                        ? 'text-zinc-400 hover:text-white'
                        : 'text-zinc-500 hover:text-zinc-900'
                  }`}
                >
                  <MessageSquare className="w-3.5 h-3.5" />
                  <span>Chat</span>
                </button>
                <button
                  onClick={loadMetrics}
                  aria-label="View extracted lab metrics table"
                  className={`px-3 py-1 rounded-lg transition-colors flex items-center gap-1.5 ${
                    viewMode === 'metrics'
                      ? darkMode
                        ? 'bg-zinc-800 text-white font-medium'
                        : 'bg-white text-zinc-900 font-medium shadow-sm'
                      : darkMode
                        ? 'text-zinc-400 hover:text-white'
                        : 'text-zinc-500 hover:text-zinc-900'
                  }`}
                >
                  <Table className="w-3.5 h-3.5" />
                  <span>Lab Metrics</span>
                </button>
              </div>

              <button
                onClick={handlePrintDoctorSummary}
                disabled={isExporting}
                aria-label="Export printable doctor consultation summary"
                className={`px-3 py-1.5 rounded-xl text-xs flex items-center gap-1.5 transition-colors border ${
                  isExporting ? 'opacity-70 cursor-not-allowed ' : ''
                }${
                  darkMode
                    ? 'bg-zinc-900 hover:bg-zinc-800 text-zinc-200 border-zinc-800'
                    : 'bg-white hover:bg-zinc-50 text-zinc-700 border-zinc-200'
                }`}
                title="Export 1-Click Printable Doctor Consultation Summary"
              >
                <Printer className="w-3.5 h-3.5" />
                <span className="hidden sm:inline">
                  {isExporting ? 'Generating Summary...' : 'Export Summary'}
                </span>
              </button>
            </>
          )}
        </div>
      </header>

      {/* TASK F3: Multi-Document Header Chip Row */}
      {attachedDocuments && attachedDocuments.length > 0 && (
        <div className={`flex items-center gap-2 px-4 sm:px-6 py-2 border-b overflow-x-auto text-xs shrink-0 ${
          darkMode ? 'bg-zinc-950/80 border-zinc-800' : 'bg-zinc-100/70 border-zinc-200'
        }`}>
          <span className={`text-[11px] font-medium shrink-0 ${textMuted}`}>Attached Reports:</span>
          <div className="flex items-center gap-2 flex-wrap sm:flex-nowrap">
            {attachedDocuments.map((doc) => (
              <div
                key={doc.id || doc.name || doc.filename}
                className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg border text-xs shrink-0 transition-colors ${
                  darkMode ? 'bg-zinc-900 border-zinc-800 text-zinc-200' : 'bg-white border-zinc-200 text-zinc-800 shadow-sm'
                }`}
              >
                <span>📄</span>
                <span className="font-medium max-w-[160px] truncate" title={doc.name || doc.filename}>
                  {doc.name || doc.filename}
                </span>
                {onDetachDocument && (
                  <button
                    type="button"
                    onClick={() => onDetachDocument(doc.id)}
                    aria-label={`Detach ${doc.name || doc.filename}`}
                    className={`p-0.5 rounded hover:text-red-400 transition-colors ${
                      darkMode ? 'text-zinc-500 hover:bg-zinc-800' : 'text-zinc-400 hover:bg-zinc-100'
                    }`}
                    title="Detach report from chat"
                  >
                    <X className="w-3 h-3" />
                  </button>
                )}
              </div>
            ))}

            <button
              type="button"
              onClick={onOpenUpload}
              aria-label="Add report"
              className={`flex items-center gap-1 px-2.5 py-1 rounded-lg border border-dashed text-xs shrink-0 transition-colors ${
                darkMode
                  ? 'border-zinc-700 text-zinc-400 hover:border-zinc-500 hover:text-zinc-200'
                  : 'border-zinc-300 text-zinc-600 hover:border-zinc-400 hover:text-zinc-900'
              }`}
            >
              <span>+ Add Report</span>
            </button>
          </div>
        </div>
      )}

      <div
        ref={scrollRef}
        onScroll={handleScroll}
        className="chat-messages-container flex-1 overflow-y-auto p-4 sm:p-6 lg:p-8 max-w-4xl w-full mx-auto"
      >
        {viewMode === 'metrics' ? (
          loadingMetrics ? (
            <div className={`p-8 text-center rounded-2xl animate-pulse border mt-4 ${cardBg} ${cardBorder}`}>
              <Sparkles className={`w-6 h-6 mx-auto mb-2 animate-spin ${textSecondary}`} />
              <div className={`text-sm font-medium ${darkMode ? 'text-zinc-300' : 'text-zinc-700'}`}>Extracting Lab Value Metrics...</div>
              <div className={`text-xs mt-1 ${textMuted}`}>Analyzing numerical bounds &amp; reference ranges</div>
            </div>
          ) : labMetrics.length === 0 ? (
            <div className={`p-8 text-center rounded-2xl border mt-4 ${cardBg} ${cardBorder}`}>
              <AlertCircle className={`w-8 h-8 mx-auto mb-3 ${textMuted}`} />
              <div className={`text-sm font-semibold mb-1 ${textPrimary}`}>No Lab Values Found</div>
              <div className={`text-xs max-w-md mx-auto ${textSecondary}`}>
                Upload a text-based diagnostic PDF report (e.g. CBC Blood Test or Lipid Panel) to extract structured lab metrics.
              </div>
            </div>
          ) : (
            <LabMetrics
              metrics={labMetrics}
              darkMode={darkMode}
              onBack={() => setViewMode('chat')}
            />
          )
        ) : messages.length === 0 ? (
          /* ── A1: EMPTY STATE ── */
          <div className="min-h-[72vh] flex flex-col items-center justify-center text-center max-w-2xl mx-auto py-8 animate-fade-in">
            <div className={`w-12 h-12 rounded-2xl flex items-center justify-center mb-5 ${
              darkMode ? 'bg-white text-black' : 'bg-zinc-900 text-white'
            }`}>
              <Stethoscope className="w-6 h-6" />
            </div>

            <h1 className={`text-2xl sm:text-3xl font-bold tracking-tight mb-2 ${textPrimary}`}>
              MediSkye AI Medical Assistant
            </h1>

            {/* A7: Personal welcome message */}
            <p className={`text-sm mb-6 max-w-lg leading-relaxed ${textSecondary}`}>
              {firstName
                ? `Welcome back, ${firstName}. Upload a report to get started, or ask a general health question.`
                : 'Upload a medical report to get started, or ask a general health question below.'}
            </p>

            {/* Active Patient Lens Selector */}
            <div className="mb-6 flex justify-center">
              <PatientContextSelector
                currentUser={currentUser}
                dependents={dependents}
                selectedPatientId={selectedPatientId}
                onSelectPatient={onSelectPatient}
                onOpenDependents={onOpenDependents}
                darkMode={darkMode}
              />
            </div>

            {/* A1 & A3: Dropzone when no document, compact chip when loaded */}
            {!activePdf ? (
              <div
                onClick={onOpenUpload}
                className={`w-full p-6 border border-dashed rounded-2xl cursor-pointer transition-all duration-150 shadow-sm mb-6 group ${
                  darkMode
                    ? 'border-zinc-800 bg-[#121212] hover:border-zinc-700 hover:bg-zinc-900/50'
                    : 'border-zinc-300 bg-white hover:border-zinc-400 hover:bg-zinc-50'
                }`}
              >
                <div className={`w-9 h-9 rounded-full flex items-center justify-center mx-auto mb-3 group-hover:scale-105 transition-transform ${
                  darkMode ? 'bg-zinc-800 text-zinc-300' : 'bg-zinc-100 text-zinc-600'
                }`}>
                  <Upload className="w-4 h-4" />
                </div>
                <div className={`font-semibold text-sm mb-1 ${textPrimary}`}>
                  Upload Medical Report (PDF)
                </div>
                <div className={`text-xs ${textSecondary}`}>
                  Drag &amp; drop or click to select file • Supports files up to <strong>50MB</strong>
                </div>
              </div>
            ) : null}

            {/* A1b: Context-aware suggestion cards (work with AND without document) */}
            <div className="w-full grid grid-cols-1 sm:grid-cols-2 gap-3 text-left">
              {sampleQueries.map((item, idx) => (
                <button
                  key={idx}
                  onClick={() => onSelectSampleQuery(item.query)}
                  className={`p-4 rounded-2xl text-xs transition-all duration-150 shadow-sm group flex flex-col justify-between min-h-[90px] border ${
                    darkMode
                      ? 'bg-[#121212] border-zinc-800/80 hover:border-zinc-700'
                      : 'bg-white border-zinc-200 hover:border-zinc-400'
                  }`}
                >
                  <div className={`font-medium flex items-center justify-between w-full ${textPrimary}`}>
                    <span>{item.title}</span>
                    <Sparkles className={`w-3.5 h-3.5 opacity-0 group-hover:opacity-100 transition-opacity ${textSecondary}`} />
                  </div>
                  <div className={`text-[11px] line-clamp-2 mt-2 ${textSecondary}`}>
                    "{item.query}"
                  </div>
                </button>
              ))}
            </div>

            <div className={`mt-8 flex items-center gap-2 text-xs ${textMuted}`}>
              <Shield className="w-3.5 h-3.5" />
              {/* A6: No HIPAA claim */}
              <span>End-to-end encrypted session • Discarded on close</span>
            </div>
          </div>
        ) : (
          /* ── A1: LOADED STATE — show conversation ── */
          <div className="py-4">
            {/* A1: Compact document chip above conversation */}
            {activePdf && (
              <div className={`mb-4 flex items-center gap-2 px-3 py-2 rounded-xl text-xs border w-fit ${
                darkMode ? 'bg-zinc-900 border-zinc-800 text-zinc-300' : 'bg-zinc-50 border-zinc-200 text-zinc-600'
              }`}>
                <FileText className="w-3.5 h-3.5 shrink-0" />
                <span className="font-medium truncate max-w-xs">{activePdf.name}</span>
                {activePdf.pages && <span className="text-zinc-500">• {activePdf.pages} pages</span>}
              </div>
            )}

            {messages.map((msg, index) => (
              <ChatMessage
                key={msg.id || index}
                message={msg}
                onRegenerate={index === messages.length - 1 && msg.sender === 'assistant' ? onRegenerate : null}
                onSelectSource={onSelectSource}
                showToast={showToast}
                darkMode={darkMode}
              />
            ))}
          </div>
        )}
      </div>

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
          className={`absolute bottom-20 right-6 z-20 p-2.5 rounded-full shadow-lg transition-all duration-150 ${
            darkMode
              ? 'bg-zinc-100 text-black hover:bg-zinc-200'
              : 'bg-zinc-900 text-white hover:bg-zinc-800'
          }`}
          title="Scroll to latest message"
        >
          <ArrowDown className="w-4 h-4" />
        </button>
      )}
    </div>
  );
}
