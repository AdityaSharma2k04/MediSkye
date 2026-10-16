import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  Stethoscope,
  Copy,
  Check,
  Volume2,
  VolumeX,
  ThumbsUp,
  ThumbsDown,
  RotateCcw,
  Share2,
  User,
  Sparkles,
  ChevronDown,
  AlertTriangle,
} from 'lucide-react';
import RagSourcesPanel from './RagSourcesPanel';
import { speakText, stopSpeaking } from '../services/speech';

export default function ChatMessage({ message, onRegenerate, onSelectSource, showToast, darkMode }) {
  const [copied, setCopied] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const [liked, setLiked] = useState(null);
  const [showDetails, setShowDetails] = useState(false);

  const isUser = message.sender === 'user';

  const handleCopy = () => {
    navigator.clipboard.writeText(message.text || '');
    setCopied(true);
    if (showToast) showToast('success', 'Copied to clipboard');
    setTimeout(() => setCopied(false), 2000);
  };

  const handleSpeak = () => {
    if (speaking) {
      stopSpeaking();
      setSpeaking(false);
    } else {
      setSpeaking(true);
      speakText(message.text || '', () => setSpeaking(false));
    }
  };

  const handleShare = () => {
    if (navigator.share) {
      navigator.share({ title: 'MediSkye Explanation', text: message.text || '' });
    } else {
      navigator.clipboard.writeText(message.text || '');
      if (showToast) showToast('info', 'Share link copied');
    }
  };

  if (isUser) {
    return (
      <div className="flex justify-end mb-5 animate-fade-in group">
        <div className="flex items-start gap-3 max-w-[85%] sm:max-w-[75%] flex-row-reverse">
          <div className={`w-7 h-7 rounded-full flex items-center justify-center font-semibold text-xs shrink-0 shadow-sm ${
            darkMode ? 'bg-zinc-100 text-zinc-900' : 'bg-zinc-900 text-white'
          }`}>
            <User className="w-3.5 h-3.5" />
          </div>
          <div className={`rounded-2xl rounded-tr-sm px-4 py-3 text-sm leading-relaxed shadow-sm ${
            darkMode ? 'bg-zinc-100 text-zinc-900' : 'bg-zinc-900 text-white'
          }`}>
            {message.text}
          </div>
        </div>
      </div>
    );
  }

  // Hide the abnormal_flags JSON block from the user interface
  const content = (message?.text || '').replace(/```json\s*\{.*"abnormal_flags"[\s\S]*?\}\s*```/is, '');

  // Common button styles for the action bar
  const actionBtn = `p-1.5 rounded-lg transition-colors ${
    darkMode ? 'hover:text-zinc-200 hover:bg-zinc-800' : 'hover:text-zinc-700 hover:bg-zinc-100'
  }`;
  const actionBtnActive = `p-1.5 rounded-lg ${
    darkMode ? 'text-zinc-100 bg-zinc-800' : 'text-zinc-900 bg-zinc-100'
  }`;

  const isStreaming = message.isStreaming;
  const statusText = message.status || 'Analyzing your question...';

  return (
    <div className="flex justify-start mb-5 animate-fade-in group">
      <div className="flex items-start gap-3 max-w-[92%] sm:max-w-[85%]">
        <div className={`w-7 h-7 rounded-full flex items-center justify-center font-bold text-xs shrink-0 shadow-sm mt-0.5 ${
          darkMode ? 'bg-zinc-100 text-zinc-900' : 'bg-zinc-900 text-white'
        }`}>
          <Stethoscope className="w-3.5 h-3.5" />
        </div>

        <div className={`flex-1 rounded-2xl rounded-tl-sm p-4 sm:p-5 shadow-sm text-sm border ${
          darkMode
            ? 'bg-zinc-900 border-zinc-800'
            : 'bg-white border-zinc-200'
        }`}>
          <div className={`flex items-center justify-between pb-2 mb-2 border-b text-xs ${
            darkMode ? 'border-zinc-800 text-zinc-400' : 'border-zinc-100 text-zinc-400'
          }`}>
            {/* Task A5: Hide model name from UI — just MediSkye AI with Sparkles */}
            <div className={`flex items-center gap-1.5 font-medium ${darkMode ? 'text-zinc-300' : 'text-zinc-700'}`}>
              <span>MediSkye AI</span>
              <Sparkles className="w-3.5 h-3.5 text-emerald-500 shrink-0" />
            </div>
            <span>{message.timestamp || 'Just now'}</span>
          </div>

          {/* Progressive rotating status line while generating before text arrives */}
          {isStreaming && !content && !message.error && (
            <div className="flex items-center gap-2.5 py-2 text-xs font-medium text-zinc-400">
              <div className="flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse [animation-delay:200ms]" />
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse [animation-delay:400ms]" />
              </div>
              <span className="text-zinc-400 transition-opacity duration-300">{statusText}</span>
            </div>
          )}

          {/* Error display with retry */}
          {message.error && (
            <div className={`p-3 my-2 rounded-xl text-xs flex items-center justify-between gap-3 border ${
              darkMode ? 'bg-rose-950/40 border-rose-900/60 text-rose-300' : 'bg-rose-50 border-rose-200 text-rose-700'
            }`}>
              <div className="flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 shrink-0 text-rose-500" />
                <span>{message.error === true ? "Something went wrong. Tap to retry." : (message.error || "Something went wrong. Tap to retry.")}</span>
              </div>
              {onRegenerate && (
                <button
                  onClick={onRegenerate}
                  className="px-2.5 py-1 text-xs font-semibold rounded-lg bg-rose-600 text-white hover:bg-rose-700 transition-colors shrink-0"
                >
                  Retry
                </button>
              )}
            </div>
          )}

          {content && (
            <div className={`prose max-w-none ${darkMode ? 'prose-invert text-zinc-200' : 'text-zinc-800'}`}>
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {content}
              </ReactMarkdown>
            </div>
          )}

          {/* Task A6: Collapsed Details Expander for structured lab values */}
          {message.metrics && message.metrics.length > 0 && (
            <div className="mt-3">
              <button
                onClick={() => setShowDetails(!showDetails)}
                className={`text-xs font-medium flex items-center gap-1.5 py-1 px-2.5 rounded-lg border transition-colors ${
                  darkMode ? 'bg-zinc-800/80 border-zinc-700 text-zinc-300 hover:bg-zinc-700' : 'bg-zinc-100 border-zinc-200 text-zinc-700 hover:bg-zinc-200'
                }`}
              >
                <span>{showDetails ? 'Hide details' : `View details (${message.metrics.length} tests)`}</span>
                <ChevronDown className={`w-3.5 h-3.5 transition-transform ${showDetails ? 'rotate-180' : ''}`} />
              </button>
              {showDetails && (
                <div className={`mt-2 rounded-xl overflow-hidden border text-xs ${
                  darkMode ? 'bg-black border-zinc-800' : 'bg-zinc-50 border-zinc-200'
                }`}>
                  <table className="w-full text-left">
                    <thead className={`border-b ${darkMode ? 'bg-zinc-900 border-zinc-800 text-zinc-400' : 'bg-white border-zinc-200 text-zinc-500'}`}>
                      <tr>
                        <th className="p-2.5 px-3">Test</th>
                        <th className="p-2.5 px-3">Your value</th>
                        <th className="p-2.5 px-3">Reference range</th>
                        <th className="p-2.5 px-3">Status</th>
                      </tr>
                    </thead>
                    <tbody className={`divide-y ${darkMode ? 'divide-zinc-800/80' : 'divide-zinc-200/60'}`}>
                      {message.metrics.map((m, i) => (
                        <tr key={i}>
                          <td className="p-2.5 px-3 font-medium">{m.test || m.name}</td>
                          <td className="p-2.5 px-3 font-semibold">{m.value} {m.unit}</td>
                          <td className="p-2.5 px-3 text-zinc-400">{m.range || 'N/A'}</td>
                          <td className="p-2.5 px-3">
                            <span className={`px-2 py-0.5 rounded text-[10px] font-semibold ${
                              m.status === 'High' ? 'bg-rose-500/10 text-rose-500 border border-rose-500/20' :
                              m.status === 'Low' ? 'bg-amber-500/10 text-amber-500 border border-amber-500/20' :
                              'bg-emerald-500/10 text-emerald-500 border border-emerald-500/20'
                            }`}>
                              {m.status || 'Normal'}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

          {message.sources && message.sources.length > 0 && (
            <RagSourcesPanel sources={message.sources} onSelectSource={onSelectSource} darkMode={darkMode} />
          )}


          {message.specialists && message.specialists.length > 0 && (
            <div className={`mt-4 rounded-xl p-4 text-sm shadow-sm border ${
              darkMode ? 'bg-zinc-900 border-zinc-800' : 'bg-zinc-50 border-zinc-200'
            }`}>
              <div className={`flex items-center gap-2 mb-2 font-semibold ${darkMode ? 'text-white' : 'text-zinc-900'}`}>
                <Stethoscope className={`w-4 h-4 ${darkMode ? 'text-zinc-400' : 'text-zinc-500'}`} />
                Recommended Next Steps
              </div>
              <p className={`text-xs mb-4 leading-relaxed ${darkMode ? 'text-zinc-400' : 'text-zinc-500'}`}>
                Based on the abnormal findings in your query or report, you may want to consult the following specialists.
                <strong className={`font-medium ml-1 ${darkMode ? 'text-zinc-300' : 'text-zinc-700'}`}>Disclaimer: These are algorithmic suggestions, not definitive medical referrals. Always consult your primary care physician.</strong>
              </p>
              <div className="space-y-2">
                {message.specialists.map((sp, idx) => (
                  <div key={idx} className={`p-3 rounded-lg flex flex-col sm:flex-row justify-between sm:items-center gap-2 transition-colors border ${
                    darkMode
                      ? 'bg-[#121212] border-zinc-800 hover:border-zinc-700'
                      : 'bg-white border-zinc-200 hover:border-zinc-400'
                  }`}>
                    <div>
                      <div className={`font-medium text-sm ${darkMode ? 'text-zinc-100' : 'text-zinc-900'}`}>{sp.name}</div>
                      <div className={`text-xs mt-0.5 ${darkMode ? 'text-zinc-400' : 'text-zinc-500'}`}>
                        <span className={darkMode ? 'text-zinc-300' : 'text-zinc-700'}>{sp.specialty}</span> • Flags: {sp.matched_flags.join(", ")}
                      </div>
                    </div>
                    <div className={`text-[11px] font-mono px-2 py-1 rounded border ${
                      darkMode
                        ? 'text-zinc-400 bg-zinc-900/80 border-zinc-800'
                        : 'text-zinc-600 bg-zinc-50 border-zinc-200'
                    }`}>
                      {sp.contact_info}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {!isStreaming && content && !message.error && (
            <div className={`mt-4 pt-3 border-t flex items-center justify-between text-xs ${
              darkMode ? 'border-zinc-800/80 text-zinc-400' : 'border-zinc-100 text-zinc-400'
            }`}>
              <div className="flex items-center gap-1">
                <button
                  onClick={handleCopy}
                  title="Copy response"
                  aria-label="Copy response"
                  className={`${actionBtn} flex items-center gap-1`}
                >
                  {copied ? <Check className={`w-3.5 h-3.5 ${darkMode ? 'text-zinc-100' : 'text-zinc-900'}`} /> : <Copy className="w-3.5 h-3.5" />}
                  <span className="hidden sm:inline">{copied ? 'Copied' : 'Copy'}</span>
                </button>

                <button
                  onClick={handleSpeak}
                  title={speaking ? 'Stop speech' : 'Read response aloud'}
                  aria-label="Read response aloud"
                  className={`${speaking ? actionBtnActive : actionBtn} flex items-center gap-1`}
                >
                  {speaking ? <VolumeX className="w-3.5 h-3.5" /> : <Volume2 className="w-3.5 h-3.5" />}
                  <span className="hidden sm:inline">{speaking ? 'Stop' : 'Listen'}</span>
                </button>

                <button
                  onClick={() => setLiked(liked === true ? null : true)}
                  title="Helpful response"
                  aria-label="Mark as helpful"
                  className={liked === true ? actionBtnActive : actionBtn}
                >
                  <ThumbsUp className="w-3.5 h-3.5" />
                </button>

                <button
                  onClick={() => setLiked(liked === false ? null : false)}
                  title="Not helpful"
                  aria-label="Mark as not helpful"
                  className={liked === false ? actionBtnActive : actionBtn}
                >
                  <ThumbsDown className="w-3.5 h-3.5" />
                </button>

                <button
                  onClick={handleShare}
                  title="Share explanation"
                  aria-label="Share response"
                  className={actionBtn}
                >
                  <Share2 className="w-3.5 h-3.5" />
                </button>
              </div>

              {onRegenerate && (
                <button
                  onClick={onRegenerate}
                  title="Regenerate AI response"
                  aria-label="Regenerate response"
                  className={`${actionBtn} flex items-center gap-1 font-medium`}
                >
                  <RotateCcw className="w-3.5 h-3.5" />
                  <span className="hidden sm:inline">Regenerate</span>
                </button>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
