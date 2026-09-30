import React, { useRef, useEffect, useState } from 'react';
import { Stethoscope, ArrowDown, Upload, FileText, Sparkles, Shield, Printer, Table, MessageSquare, AlertCircle, HeartPulse, User } from 'lucide-react';
import ChatMessage from './ChatMessage';
import { fetchLabMetrics } from '../services/api';
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
  currentUser,
  dependents,
  selectedPatientId,
  onSelectPatient,
  onOpenDependents,
}) {

  const scrollRef = useRef(null);
  const [showScrollBtn, setShowScrollBtn] = useState(false);
  const [viewMode, setViewMode] = useState('chat');
  const [labMetrics, setLabMetrics] = useState([]);
  const [loadingMetrics, setLoadingMetrics] = useState(false);

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

  const handlePrintDoctorSummary = () => {
    window.print();
  };

  const sampleQueries = [
    { title: 'Explain Hemoglobin levels', query: 'Explain my Hemoglobin levels and what they indicate.' },
    { title: 'Cholesterol & LDL Check', query: 'Are my cholesterol or LDL numbers within normal range?' },
    { title: 'Summarize Abnormal Values', query: 'Summarize key findings and any abnormal values in this report.' },
    { title: 'Follow-up Questions', query: 'What follow-up questions should I ask my doctor about this report?' },
  ];

  // Shared color helpers
  const cardBg = darkMode ? 'bg-[#121212]' : 'bg-white';
  const cardBorder = darkMode ? 'border-zinc-800' : 'border-zinc-200';
  const headerBg = darkMode ? 'bg-[#09090B]' : 'bg-white';
  const textPrimary = darkMode ? 'text-white' : 'text-zinc-900';
  const textSecondary = darkMode ? 'text-zinc-400' : 'text-zinc-500';
  const textMuted = darkMode ? 'text-zinc-500' : 'text-zinc-400';

  const isSelf = !selectedPatientId || selectedPatientId === 'self' || (currentUser && selectedPatientId === currentUser.id);
  const activeDependent = !isSelf ? dependents?.find(d => d.id === selectedPatientId) : null;

  return (
    <div className={`flex-1 flex flex-col h-full overflow-hidden relative transition-colors duration-200 ${
      darkMode ? 'bg-black text-slate-100' : 'bg-zinc-50 text-zinc-900'
    }`}>
      <header className={`flex items-center justify-between p-3.5 px-4 sm:px-6 border-b z-10 transition-colors duration-200 ${headerBg} ${cardBorder}`}>
        <div className="flex items-center gap-3">
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
            <p className={`text-[10px] ${textSecondary}`}>
              {darkMode ? 'Obsidian' : 'Light'} Theme • 50MB PDF Supported
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <div className={`flex items-center rounded-xl p-0.5 text-xs border ${
            darkMode ? 'bg-zinc-900 border-zinc-800' : 'bg-zinc-100 border-zinc-200'
          }`}>
            <button
              onClick={() => setViewMode('chat')}
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
            className={`px-3 py-1.5 rounded-xl text-xs flex items-center gap-1.5 transition-colors border ${
              darkMode
                ? 'bg-zinc-900 hover:bg-zinc-800 text-zinc-200 border-zinc-800'
                : 'bg-white hover:bg-zinc-50 text-zinc-700 border-zinc-200'
            }`}
            title="Export 1-Click Printable Doctor Consultation Summary"
          >
            <Printer className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Export Summary</span>
          </button>
        </div>
      </header>

      <div
        ref={scrollRef}
        onScroll={handleScroll}
        className="flex-1 overflow-y-auto p-4 sm:p-6 lg:p-8 max-w-4xl w-full mx-auto"
      >
        {viewMode === 'metrics' ? (
          <div className="animate-fade-in py-4">
            <div className="flex items-center justify-between mb-6">
              <div>
                <h2 className={`text-xl font-bold tracking-tight ${textPrimary}`}>Structured Lab Metrics</h2>
                <p className={`text-xs mt-0.5 ${textSecondary}`}>Extracted lab values and reference range evaluation</p>
              </div>
              <button
                onClick={() => setViewMode('chat')}
                className={`text-xs underline ${darkMode ? 'text-zinc-400 hover:text-white' : 'text-zinc-500 hover:text-zinc-900'}`}
              >
                Back to Chat →
              </button>
            </div>

            {loadingMetrics ? (
              <div className={`p-8 text-center rounded-2xl animate-pulse border ${cardBg} ${cardBorder}`}>
                <Sparkles className={`w-6 h-6 mx-auto mb-2 animate-spin ${textSecondary}`} />
                <div className={`text-sm font-medium ${darkMode ? 'text-zinc-300' : 'text-zinc-700'}`}>Extracting Lab Value Metrics...</div>
                <div className={`text-xs mt-1 ${textMuted}`}>Analyzing numerical bounds & reference ranges</div>
              </div>
            ) : labMetrics.length === 0 ? (
              <div className={`p-8 text-center rounded-2xl border ${cardBg} ${cardBorder}`}>
                <AlertCircle className={`w-8 h-8 mx-auto mb-3 ${textMuted}`} />
                <div className={`text-sm font-semibold mb-1 ${textPrimary}`}>No Lab Values Found</div>
                <div className={`text-xs max-w-md mx-auto ${textSecondary}`}>
                  Upload a text-based diagnostic PDF report (e.g. CBC Blood Test or Lipid Panel) to extract structured lab metrics.
                </div>
              </div>
            ) : (
              <div className={`rounded-2xl overflow-hidden shadow-xl border ${cardBg} ${cardBorder}`}>
                <table className="w-full text-left text-xs">
                  <thead className={`border-b ${
                    darkMode ? 'bg-zinc-900 border-zinc-800 text-zinc-400' : 'bg-zinc-50 border-zinc-200 text-zinc-500'
                  }`}>
                    <tr>
                      <th className="p-3.5 px-4 font-semibold">Test Name</th>
                      <th className="p-3.5 px-4 font-semibold">Observed Value</th>
                      <th className="p-3.5 px-4 font-semibold">Reference Range</th>
                      <th className="p-3.5 px-4 font-semibold">Status</th>
                    </tr>
                  </thead>
                  <tbody className={`divide-y ${darkMode ? 'divide-zinc-800/80' : 'divide-zinc-100'}`}>
                    {labMetrics.map((row, idx) => {
                      let badge = darkMode ? 'bg-zinc-800 text-zinc-300' : 'bg-zinc-100 text-zinc-600';
                      if (row.status === 'High') badge = darkMode ? 'bg-rose-950/80 text-rose-300 border border-rose-900' : 'bg-rose-50 text-rose-700 border border-rose-200';
                      else if (row.status === 'Low') badge = darkMode ? 'bg-amber-950/80 text-amber-300 border border-amber-900' : 'bg-amber-50 text-amber-700 border border-amber-200';
                      else if (row.status === 'Normal') badge = darkMode ? 'bg-emerald-950/80 text-emerald-300 border border-emerald-900' : 'bg-emerald-50 text-emerald-700 border border-emerald-200';

                      return (
                        <tr key={idx} className={`transition-colors ${darkMode ? 'hover:bg-zinc-900/50' : 'hover:bg-zinc-50'}`}>
                          <td className={`p-3.5 px-4 font-medium ${textPrimary}`}>{row.test}</td>
                          <td className={`p-3.5 px-4 font-semibold ${textPrimary}`}>
                            {row.value} <span className={`text-[11px] font-normal ${textSecondary}`}>{row.unit}</span>
                          </td>
                          <td className={`p-3.5 px-4 ${textSecondary}`}>{row.range || 'N/A'}</td>
                          <td className="p-3.5 px-4">
                            <span className={`px-2.5 py-1 rounded-md text-[10px] font-semibold ${badge}`}>
                              {row.status || 'Extracted'}
                            </span>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        ) : messages.length === 0 ? (
          <div className="min-h-[72vh] flex flex-col items-center justify-center text-center max-w-2xl mx-auto py-8 animate-fade-in">
            <div className={`w-12 h-12 rounded-2xl flex items-center justify-center mb-5 ${
              darkMode ? 'bg-white text-black' : 'bg-zinc-900 text-white'
            }`}>
              <Stethoscope className="w-6 h-6" />
            </div>

            <h1 className={`text-2xl sm:text-3xl font-bold tracking-tight mb-2 ${textPrimary}`}>
              MediSkye AI Medical Assistant
            </h1>
            <p className={`text-sm mb-6 max-w-lg leading-relaxed ${textSecondary}`}>
              Upload a diagnostic PDF report (up to <strong>50MB</strong>) — blood work, lipid panels, or imaging summaries — and get grounded medical explanations.
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


            {!activePdf ? (
              <div

                onClick={() => {
                  const fileInput = document.querySelector('input[type="file"]');
                  if (fileInput) fileInput.click();
                }}
                className={`w-full p-6 border border-dashed rounded-2xl cursor-pointer transition-all duration-150 shadow-sm mb-8 group ${
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
                  Drag & drop or click to select file • Supports files up to <strong>50MB</strong>
                </div>
              </div>
            ) : (
              <div className={`w-full p-4 rounded-2xl flex items-center justify-between mb-8 text-xs border ${cardBg} ${cardBorder} ${textPrimary}`}>
                <div className="flex items-center gap-3">
                  <FileText className={`w-5 h-5 shrink-0 ${textSecondary}`} />
                  <div className="text-left">
                    <div className="font-medium">{activePdf.name}</div>
                    <div className={`text-[10px] ${textSecondary}`}>Indexed & Ready for Questions</div>
                  </div>
                </div>
                <button
                  onClick={loadMetrics}
                  className={`px-3 py-1 rounded-lg font-medium text-[11px] transition-colors ${
                    darkMode
                      ? 'bg-white text-black hover:bg-zinc-200'
                      : 'bg-zinc-900 text-white hover:bg-zinc-800'
                  }`}
                >
                  View Lab Metrics Table
                </button>
              </div>
            )}

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
              <span>HIPAA-inspired session privacy • Discarded on close</span>
            </div>
          </div>
        ) : (
          <div className="py-4">
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

            {isGenerating && (
              <div className="flex justify-start mb-5 animate-pulse">
                <div className="flex items-start gap-3 max-w-[85%]">
                  <div className={`w-7 h-7 rounded-full flex items-center justify-center font-bold text-xs shrink-0 mt-0.5 ${
                    darkMode ? 'bg-white text-black' : 'bg-zinc-900 text-white'
                  }`}>
                    <Stethoscope className="w-3.5 h-3.5" />
                  </div>
                  <div className={`rounded-2xl rounded-tl-sm p-4 w-64 shadow-sm border ${cardBg} ${cardBorder}`}>
                    <div className={`flex items-center gap-2 mb-2 text-xs font-medium ${textSecondary}`}>
                      <Sparkles className="w-3.5 h-3.5 animate-spin" />
                      <span>Retrieving chunks & generating response...</span>
                    </div>
                    <div className="space-y-2">
                      <div className={`h-3 rounded w-full animate-shimmer ${darkMode ? 'bg-zinc-800' : 'bg-zinc-200'}`} />
                      <div className={`h-3 rounded w-3/4 animate-shimmer ${darkMode ? 'bg-zinc-800' : 'bg-zinc-200'}`} />
                      <div className={`h-3 rounded w-1/2 animate-shimmer ${darkMode ? 'bg-zinc-800' : 'bg-zinc-200'}`} />
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      <div id="printableSummary" className="hidden print:block">
        <div style={{ fontFamily: 'sans-serif', maxWidth: '800px', margin: '0 auto' }}>
          <h1 style={{ fontSize: '24px', fontWeight: 'bold', marginBottom: '4px' }}>MediSkye AI — Doctor Consultation Summary</h1>
          <p style={{ fontSize: '12px', color: '#666', marginBottom: '20px' }}>
            Generated for session report analysis • Date: {new Date().toLocaleDateString()}
          </p>

          {activePdf && (
            <div style={{ padding: '12px', background: '#f5f5f5', borderRadius: '8px', marginBottom: '20px', fontSize: '13px' }}>
              <strong>Report File:</strong> {activePdf.name}
            </div>
          )}

          {labMetrics.length > 0 && (
            <div style={{ marginBottom: '25px' }}>
              <h2 style={{ fontSize: '16px', fontWeight: 'bold', marginBottom: '10px' }}>Extracted Lab Results Summary</h2>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px' }}>
                <thead>
                  <tr style={{ background: '#eee', textAlign: 'left' }}>
                    <th style={{ padding: '8px', border: '1px solid #ccc' }}>Test Name</th>
                    <th style={{ padding: '8px', border: '1px solid #ccc' }}>Observed Value</th>
                    <th style={{ padding: '8px', border: '1px solid #ccc' }}>Reference Range</th>
                    <th style={{ padding: '8px', border: '1px solid #ccc' }}>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {labMetrics.map((r, i) => (
                    <tr key={i}>
                      <td style={{ padding: '8px', border: '1px solid #ccc' }}>{r.test}</td>
                      <td style={{ padding: '8px', border: '1px solid #ccc' }}>{r.value} {r.unit}</td>
                      <td style={{ padding: '8px', border: '1px solid #ccc' }}>{r.range}</td>
                      <td style={{ padding: '8px', border: '1px solid #ccc' }}>{r.status}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <h2 style={{ fontSize: '16px', fontWeight: 'bold', marginBottom: '10px' }}>Consultation Discussion Notes</h2>
          {messages.map((m, idx) => (
            <div key={idx} style={{ marginBottom: '12px', fontSize: '12px' }}>
              <strong>{m.sender === 'user' ? 'Patient Question:' : 'MediSkye Explanation:'}</strong>
              <p style={{ marginTop: '4px', lineHeight: '1.5' }}>{m.text}</p>
            </div>
          ))}

          <div style={{ marginTop: '40px', paddingTop: '15px', borderTop: '1px solid #ccc', fontSize: '10px', color: '#777' }}>
            Disclaimer: MediSkye AI is an educational tool and does not provide formal medical diagnoses.
          </div>
        </div>
      </div>

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
