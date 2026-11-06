import React, { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  Copy,
  Check,
  Volume2,
  VolumeX,
  ThumbsUp,
  ThumbsDown,
  RotateCcw,
  Share2,
  Sparkles,
  AlertTriangle,
} from 'lucide-react';
import { speakText, stopSpeaking } from '../services/speech';

export const stripAbnormalFlags = (text) => {
  if (!text) return '';
  return text
    .replace(/```json\s*\{[\s\S]*?"abnormal_flags"[\s\S]*?\}\s*```/gi, '')
    .replace(/```json\s*\{[\s\S]*?"abnormal_flags"[\s\S]*$/gi, '')
    .trim();
};

const extractTableData = (node) => {
  if (!node || !node.children) return null;
  const rows = [];
  const findRows = (n) => {
    if (!n) return;
    const isRow = n.tagName === 'tr' || n.type === 'tableRow';
    if (isRow) {
      const cells = (n.children || [])
        .filter((c) => c && (c.tagName === 'th' || c.tagName === 'td' || c.type === 'tableCell'))
        .map((c) => {
          const getText = (cellNode) => {
            if (!cellNode) return '';
            if (cellNode.value) return cellNode.value;
            if (cellNode.children) return cellNode.children.map(getText).join('');
            return '';
          };
          return getText(c).trim();
        });
      if (cells.length > 0) {
        rows.push(cells);
      }
    } else if (n.children) {
      n.children.forEach(findRows);
    }
  };
  findRows(node);
  return rows;
};

const getStatusBadgeStyle = (statusText = '') => {
  const s = statusText.toLowerCase();
  if (s.includes('drop')) {
    return 'bg-amber-500/15 text-amber-400 border border-amber-500/30';
  }
  if (s.includes('low') || s.includes('high')) {
    return 'bg-rose-500/15 text-rose-300 border border-rose-500/30';
  }
  return 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30';
};

export default function ChatMessage({ message, onRegenerate, darkMode }) {
  const [copied, setCopied] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const [liked, setLiked] = useState(null);
  const [showThinkingSkeleton, setShowThinkingSkeleton] = useState(false);
  const speakTokenRef = useRef(null);

  const isUser = message?.sender === 'user';
  // Hide the abnormal_flags JSON block from the user interface
  const content = stripAbnormalFlags(message?.text || '');

  // Keep the Listen button in sync with speech started/stopped anywhere in
  // the app (manual button, auto-read, stop-on-send, regenerate, ...).
  useEffect(() => {
    const onStart = (e) => {
      if (speakTokenRef.current != null && e.detail?.token === speakTokenRef.current) {
        setSpeaking(true);
      }
    };
    const onEnd = (e) => {
      if (speakTokenRef.current != null && e.detail?.token === speakTokenRef.current) {
        setSpeaking(false);
        speakTokenRef.current = null;
      }
    };
    window.addEventListener('mediskye:speechstart', onStart);
    window.addEventListener('mediskye:speechend', onEnd);
    return () => {
      window.removeEventListener('mediskye:speechstart', onStart);
      window.removeEventListener('mediskye:speechend', onEnd);
    };
  }, []);

  // Premium loading state: if no token has arrived within 3s, show a
  // "Thinking..." skeleton so slow generations never feel stuck.
  useEffect(() => {
    if (!message?.isStreaming || content || message?.error) {
      setShowThinkingSkeleton(false);
      return undefined;
    }
    const timer = setTimeout(() => setShowThinkingSkeleton(true), 3000);
    return () => clearTimeout(timer);
  }, [message?.isStreaming, content, message?.error]);

  const handleCopy = () => {
    navigator.clipboard.writeText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleSpeak = () => {
    if (speaking) {
      stopSpeaking();
      setSpeaking(false);
      speakTokenRef.current = null;
    } else {
      const token = speakText(content, () => setSpeaking(false));
      if (token != null) {
        speakTokenRef.current = token;
        setSpeaking(true);
      }
    }
  };

  const handleShare = () => {
    if (navigator.share) {
      navigator
        .share({ title: 'MediSkye Explanation', text: content })
        .catch((err) => {
          if (err.name !== 'AbortError') console.error(err);
        });
    } else {
      navigator.clipboard.writeText(content);
    }
  };

  if (isUser) {
    const cleanUserText = (message?.text || message?.message || '').replace(/^["'“”‘’]+|["'“”‘’]+$/g, '').trim();
    return (
      <div className="flex justify-end mb-4 animate-bubble-in group">
        <div className={`rounded-2xl rounded-tr-sm px-4 py-2.5 max-w-[85%] ml-auto text-sm leading-relaxed shadow-sm ${
          darkMode ? 'bg-[#131b26] border border-cyan-500/20 text-slate-100' : 'bg-zinc-900 text-white'
        }`}>
          {cleanUserText}
        </div>
      </div>
    );
  }

  // Common button styles for the action bar
  const actionBtn = `p-1.5 rounded-lg transition-all active:scale-[0.92] ${
    darkMode ? 'hover:text-zinc-200 hover:bg-zinc-800' : 'hover:text-zinc-700 hover:bg-zinc-100'
  }`;
  const actionBtnActive = `p-1.5 rounded-lg transition-all active:scale-[0.92] ${
    darkMode ? 'text-zinc-100 bg-zinc-800' : 'text-zinc-900 bg-zinc-100'
  }`;

  const isStreaming = message.isStreaming;
  const statusText = message.status || 'Analyzing your question...';

  return (
    <div className="flex justify-start mb-6 animate-bubble-in group w-full">
      <div className="w-full">
        <div className={`flex items-center justify-between pb-1.5 mb-2 text-xs ${
          darkMode ? 'text-zinc-400' : 'text-zinc-500'
        }`}>
          {/* MediSkye AI with Sparkles */}
          <div className={`flex items-center gap-1.5 font-medium ${darkMode ? 'text-zinc-300' : 'text-zinc-700'}`}>
            <span>MediSkye AI</span>
            <Sparkles className="w-3.5 h-3.5 text-emerald-500 shrink-0" />
          </div>
          <span className="text-[11px] text-slate-400 dark:text-slate-400">{message.timestamp || 'Just now'}</span>
        </div>

        {/* Progressive rotating status line while generating before text arrives */}
        {isStreaming && !content && !message.error && (
          <div className="py-1.5">
            <div className="flex items-center gap-2.5 text-xs font-medium text-zinc-400">
              <div className="flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse [animation-delay:200ms]" />
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse [animation-delay:400ms]" />
              </div>
              <span className="text-zinc-400 transition-opacity duration-300">{statusText}</span>
            </div>

            {/* Thinking skeleton — appears only if the first token takes >3s */}
            {showThinkingSkeleton && (
              <div className="mt-3.5 space-y-2.5" role="status" aria-label="Thinking">
                <div className="skeleton-shimmer h-3.5 rounded-lg w-3/4" />
                <div className="skeleton-shimmer h-3.5 rounded-lg w-full" />
                <div className="skeleton-shimmer h-3.5 rounded-lg w-5/6" />
                <div className="skeleton-shimmer h-3.5 rounded-lg w-2/5" />
              </div>
            )}
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
          <div className={`prose max-w-none w-full text-sm leading-relaxed ${darkMode ? 'prose-invert text-zinc-100' : 'text-zinc-800'}`}>
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                table: ({ node, ...props }) => {
                  const rows = extractTableData(node);
                  const isComparison = rows && rows.length > 1 && rows[0].length >= 5;
                  return (
                    <div className="my-3 w-full">
                      <div className={`overflow-x-auto rounded-xl border border-slate-800 bg-[#0b1017] shadow-inner scrollbar-thin ${
                        isComparison ? 'hidden sm:block' : 'block'
                      }`}>
                        <table className="w-full border-collapse text-left text-xs sm:text-sm my-0" {...props} />
                      </div>
                      {isComparison && (
                        <div className="block sm:hidden space-y-2.5">
                          {rows.slice(1).map((row, idx) => {
                            const name = (row[0] || '').replace(/\*\*/g, '');
                            const baseline = row[1] || '';
                            const followUp = row[2] || '';
                            const change = row[3] || '';
                            const refRange = row[4] || '';
                            const status = row[5] || '';
                            return (
                              <div key={idx} className="p-3 rounded-xl border border-slate-800 bg-[#0c1017] space-y-1.5 shadow-xs">
                                <div className="flex items-center justify-between gap-2">
                                  <span className="font-semibold text-xs text-white tracking-tight">{name}</span>
                                  {status && (
                                    <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${getStatusBadgeStyle(status)}`}>
                                      {status}
                                    </span>
                                  )}
                                </div>
                                <div className="flex items-baseline justify-between text-xs pt-0.5">
                                  <div className="flex items-baseline gap-1.5">
                                    <span className="font-bold text-sm text-cyan-300">{followUp}</span>
                                    {change && <span className="text-[11px] font-mono text-slate-300 font-medium">{change}</span>}
                                  </div>
                                  {baseline && <span className="text-[10px] text-slate-400 font-mono">prev: {baseline}</span>}
                                </div>
                                {refRange && <div className="text-[10px] text-slate-500 font-mono">Ref: {refRange}</div>}
                              </div>
                            );
                          })}
                        </div>
                      )}
                    </div>
                  );
                },
                thead: ({ node, ...props }) => (
                  <thead className="bg-[#121824] text-slate-300 border-b border-slate-800 font-medium" {...props} />
                ),
                th: ({ node, ...props }) => (
                  <th className="px-3 py-2.5 font-semibold text-xs text-slate-300 whitespace-nowrap" {...props} />
                ),
                td: ({ node, ...props }) => (
                  <td className="px-3 py-2 border-b border-slate-800/40 text-xs text-slate-200 whitespace-nowrap" {...props} />
                ),
              }}
            >
              {content}
            </ReactMarkdown>
          </div>
        )}

        {!isStreaming && content && !message.error && (
          <div className={`mt-3 pt-2.5 border-t flex items-center justify-between text-xs ${
            darkMode ? 'border-white/5 text-zinc-400' : 'border-zinc-200 text-zinc-500'
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
  );
}
