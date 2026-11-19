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
  AlertTriangle,
} from 'lucide-react';
import { speakText, stopSpeaking } from '../services/speech';
import { stripOuterQuotes, formatMessageTimestamp, normalizeChatMessage } from '../lib/clinical';
import { cn } from '../lib/cn';
import { BrandMark } from './workbench/Brand';

export { formatMessageTimestamp, normalizeChatMessage };

export const stripAbnormalFlags = (text) => {
  if (!text) return '';
  return text
    // Complete code blocks containing abnormal_flags (with or without language tag)
    .replace(/(?:```|~~~)(?:json)?\s*\{[\s\S]*?"abnormal_flags"[\s\S]*?\}\s*(?:```|~~~)/gi, '')
    // Trailing unclosed code fences and partial JSON blocks during active streaming
    .replace(/(?:```|~~~)[a-z0-9_-]*\s*(?:\{[\s\S]*)?$/gi, '')
    // Bare json abnormal_flags block with or without fences
    .replace(/\{[\s\S]*?"abnormal_flags"[\s\S]*?\}\s*$/gi, '')
    .replace(/\{[\s\S]*?"abnormal_flags"[\s\S]*$/gi, '')
    // Trailing unclosed bare JSON object at the very end
    .replace(/\{\s*"(?:a|ab|abn|abnor|abnorm|abnorma|abnormal|abnormal_)?[\s\S]*$/gi, '')
    // Internal system prompt XML tags that should never leak to users
    .replace(/<(?:patient_health_profile|extracted_report_biomarkers|analysis_hints|followup_turn_instruction|uploaded_documents|current_session_history|patient_context)(?:\s+[^>]*)?>[\s\S]*?<\/(?:patient_health_profile|extracted_report_biomarkers|analysis_hints|followup_turn_instruction|uploaded_documents|current_session_history|patient_context)>/gi, '')
    .replace(/<(?:patient_health_profile|extracted_report_biomarkers|analysis_hints|followup_turn_instruction|uploaded_documents|current_session_history|patient_context)(?:\s+[^>]*)?\/>/gi, '')
    .replace(/<(?:patient_health_profile|extracted_report_biomarkers|analysis_hints|followup_turn_instruction|uploaded_documents|current_session_history|patient_context)(?:\s+[^>]*)?>[\s\S]*$/gi, '')
    .replace(/<(?:patient_health_profile|extracted_report_biomarkers|analysis_hints|followup_turn_instruction|uploaded_documents|current_session_history|patient_context)(?:\s+[^>]*)?$/gi, '')
    .replace(/<[a-z_]+_instruction(?:\s+[^>]*)?>[\s\S]*?<\/[a-z_]+_instruction>/gi, '')
    .replace(/<[a-z_]+_instruction(?:\s+[^>]*)?\/>/gi, '')
    .replace(/<[a-z_]+_instruction(?:\s+[^>]*)?>[\s\S]*$/gi, '')
    .replace(/<[a-z_]+_instruction(?:\s+[^>]*)?$/gi, '')
    .trim();
};

export const cleanMessageText = (text, isFollowupTurn = false) => {
  if (!text) return '';
  let cleaned = stripAbnormalFlags(text);
  if (isFollowupTurn) {
    // Hide trailing Disclaimer block completely on follow-up turns
    cleaned = cleaned.replace(/(?:\n\s*(?:\*\*\*|---|___)\s*)?(?:\n\s*)?\*{0,2}Disclaimer:\*{0,2}[\s\S]*$/i, '').trim();
  } else {
    // Deduplicate repeated Disclaimer: blocks inside a message
    const disclaimerRegex = /(?:\n\s*(?:\*\*\*|---|___)\s*)?(?:\n\s*)?\*{0,2}Disclaimer:\*{0,2}[^\n]*(?:\n(?!\s*#{1,6}\s)[^\n]+)*/gi;
    const matches = cleaned.match(disclaimerRegex);
    if (matches && matches.length > 1) {
      cleaned = cleaned.replace(disclaimerRegex, '').trim();
      const lastDisclaimer = matches[matches.length - 1].trim();
      cleaned = cleaned + '\n\n' + lastDisclaimer;
    }
  }
  return cleaned;
};

const nodeText = (children) => {
  if (children === null || children === undefined) return '';
  if (typeof children === 'string' || typeof children === 'number') return String(children);
  if (Array.isArray(children)) return children.map(nodeText).join('');
  if (children.props) return nodeText(children.props.children);
  return '';
};

/** Map status-like table cell text to a clinical tone. */
function cellTone(text) {
  const s = text.trim().toLowerCase();
  if (!s || s.length > 32) return null;
  // Percentage deltas: amber only when the move is clinically notable (≥10%)
  const pct = s.match(/^([↑↓↗↘+\-−]?)\s*([\d.]+)\s*%$/);
  if (pct) return parseFloat(pct[2]) >= 10 ? 'amber' : null;
  if (/^(critical|panic)/.test(s)) return 'rose';
  if (/^(high|elevated)/.test(s)) return 'rose';
  if (/notable|significant/.test(s) && /(drop|decreas|rise|increas)/.test(s)) return 'amber';
  if (/^(low|borderline|deficien)/.test(s)) return 'amber';
  if (/^(normal|optimal|in range|within|✓|✅)/.test(s)) return 'emerald';
  return null;
}

const TONE_CLASSES = {
  rose: 'bg-rose-50 text-rose-700 border-rose-200',
  amber: 'bg-amber-50 text-amber-700 border-amber-200',
  emerald: 'bg-emerald-50 text-emerald-700 border-emerald-200',
};

const markdownComponents = {
  table: ({ node, ...props }) => (
    <div className="not-prose my-4 -mx-1 sm:mx-0 max-w-full overflow-hidden">
      <div className="ms-table-card overflow-x-auto max-w-full scrollbar-thin">
        <table className="w-full min-w-full table-auto" {...props} />
      </div>
    </div>
  ),
  td: ({ node, children, ...props }) => {
    const tone = cellTone(nodeText(children));
    return (
      <td {...props}>
        {tone ? (
          <span className={cn('inline-flex items-center px-2 py-0.5 rounded-full border text-xs font-semibold', TONE_CLASSES[tone])}>{children}</span>
        ) : (
          children
        )}
      </td>
    );
  },
  a: ({ node, ...props }) => <a {...props} target="_blank" rel="noopener noreferrer" className="text-cyan-700 underline decoration-cyan-500/40 underline-offset-2 hover:decoration-cyan-700" />,
  code: ({ node, inline, className, children, ...props }) => (
    <code className={cn('ms-num text-[0.86em] px-1.5 py-0.5 rounded-md bg-slate-100 text-cyan-900 border border-slate-200', className)} {...props}>
      {children}
    </code>
  ),
};

function areMessagePropsEqual(prevProps, nextProps) {
  if (prevProps.onRegenerate !== nextProps.onRegenerate) return false;
  if (prevProps.isFollowupTurn !== nextProps.isFollowupTurn) return false;
  const p = prevProps.message;
  const n = nextProps.message;
  if (p === n) return true;
  if (!p || !n) return false;
  return (
    p.id === n.id &&
    (p.content || p.text || p.message) === (n.content || n.text || n.message) &&
    p.sender === n.sender &&
    p.role === n.role &&
    p.timestamp === n.timestamp &&
    p.created_at === n.created_at &&
    (p.status || p.statusText) === (n.status || n.statusText) &&
    p.error === n.error &&
    Boolean(p.isStreaming || p.streaming) === Boolean(n.isStreaming || n.streaming)
  );
}

export function ChatMessage({ message, onRegenerate, isFollowupTurn = false }) {
  const [copied, setCopied] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const [liked, setLiked] = useState(null);
  const [showThinkingSkeleton, setShowThinkingSkeleton] = useState(false);
  const speakTokenRef = useRef(null);

  const isUser = message?.sender === 'user' || message?.role === 'user' || message?.type === 'user' || message?.isUser === true;
  // Hide the abnormal_flags JSON block and handle disclaimer deduplication/hiding
  const rawText = message?.content || message?.text || message?.message || '';
  const content = cleanMessageText(rawText, isFollowupTurn);
  const formattedTime = formatMessageTimestamp(message?.timestamp || message?.created_at);

  // Keep the Listen button in sync with speech started/stopped anywhere in the app.
  useEffect(() => {
    const onStart = (e) => {
      if (speakTokenRef.current != null && e.detail?.token === speakTokenRef.current) setSpeaking(true);
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

  // If no token has arrived within 3s, show a skeleton so slow generations never feel stuck.
  useEffect(() => {
    if (!message?.isStreaming || content || message?.error) {
      setShowThinkingSkeleton(false);
      return undefined;
    }
    const timer = setTimeout(() => setShowThinkingSkeleton(true), 3000);
    return () => clearTimeout(timer);
  }, [message?.isStreaming, content, message?.error]);

  const handleCopy = () => {
    try {
      navigator.clipboard?.writeText(content);
    } catch {
      /* clipboard unavailable */
    }
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
      navigator.share({ title: 'MediSkye Explanation', text: content }).catch((err) => {
        if (err.name !== 'AbortError') console.error(err);
      });
    } else {
      navigator.clipboard?.writeText(content);
    }
  };

  if (isUser) {
    const cleanUserText = stripOuterQuotes(message?.content || message?.text || message?.message || '');
    return (
      <div className="flex justify-end mb-5 animate-bubble-in">
        <div className="max-w-[85%] sm:max-w-[78%] rounded-[20px] rounded-br-md px-4 py-2.5 text-[15px] sm:text-[14.5px] leading-relaxed text-slate-900 bg-slate2 border border-slate-200 shadow-sm whitespace-pre-wrap break-words">
          {cleanUserText}
        </div>
      </div>
    );
  }

  const actionBtn = 'ms-tap inline-flex items-center gap-1.5 h-8 px-2 rounded-lg text-slate-500 hover:text-slate-900 hover:bg-slate-100 transition active:scale-[0.94]';
  const actionBtnActive = 'ms-tap inline-flex items-center gap-1.5 h-8 px-2 rounded-lg text-slate-900 bg-slate-200 transition active:scale-[0.94]';

  const isStreaming = message.isStreaming;
  const statusText = message.status || 'Analyzing your question...';

  return (
    <div className="flex gap-3 mb-7 animate-bubble-in w-full">
      <div className="pt-0.5 hidden sm:block">
        <BrandMark size={26} />
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2 mb-1.5 text-xs">
          <span className="font-semibold text-ink-soft">MediSkye AI</span>
          <span className="text-xs text-ink-faint">{formattedTime}</span>
        </div>

        {isStreaming && !content && !message.error && (
          <div className="py-1">
            <div className="inline-flex items-center gap-2.5 text-xs font-medium text-slate-600 px-3 py-1.5 rounded-full bg-slate-100 border border-slate-200">
              <span className="flex items-center gap-1" aria-hidden="true">
                <span className="w-1.5 h-1.5 rounded-full bg-cyan-600 animate-token-pulse" />
                <span className="w-1.5 h-1.5 rounded-full bg-cyan-600 animate-token-pulse [animation-delay:180ms]" />
                <span className="w-1.5 h-1.5 rounded-full bg-cyan-600 animate-token-pulse [animation-delay:360ms]" />
              </span>
              <span className="transition-opacity duration-300">{statusText}</span>
            </div>

            {showThinkingSkeleton && (
              <div className="mt-4 space-y-2.5 max-w-xl" role="status" aria-label="Thinking">
                <div className="skeleton-shimmer h-3.5 rounded-lg w-3/4" />
                <div className="skeleton-shimmer h-3.5 rounded-lg w-full" />
                <div className="skeleton-shimmer h-3.5 rounded-lg w-5/6" />
                <div className="skeleton-shimmer h-3.5 rounded-lg w-2/5" />
              </div>
            )}
          </div>
        )}

        {message.error && (
          <div className="p-3 my-2 rounded-2xl text-xs flex items-center justify-between gap-3 border bg-rose-50 border-rose-200 text-rose-700">
            <div className="flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 shrink-0 text-rose-600" />
              <span>{message.error === true ? 'Something went wrong. Tap to retry.' : message.error || 'Something went wrong. Tap to retry.'}</span>
            </div>
            {onRegenerate && (
              <button
                type="button"
                onClick={onRegenerate}
                className="ms-tap px-3 h-8 text-xs font-semibold rounded-lg bg-rose-600 text-white hover:bg-rose-700 transition-colors shrink-0"
              >
                Retry
              </button>
            )}
          </div>
        )}

        {content && (
          <div
            className={cn(
              'prose prose-slate max-w-none w-full text-[15px] sm:text-[14.5px] leading-[1.7] text-ink-soft',
              'prose-headings:text-slate-900 prose-headings:font-semibold prose-h1:text-lg prose-h2:text-base prose-h3:text-[15px]',
              'prose-strong:text-slate-900 prose-li:my-0.5 prose-p:my-2.5 prose-hr:border-slate-200'
            )}
          >
            <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
              {content}
            </ReactMarkdown>
            {isStreaming && (
              <span aria-hidden="true" className="inline-block align-[-2px] w-[7px] h-4 ml-0.5 rounded-[2px] bg-cyan-600 animate-token-pulse" />
            )}
          </div>
        )}

        {!isStreaming && content && !message.error && (
          <div className="mt-2 -ml-2 flex items-center justify-between text-xs">
            <div className="flex items-center gap-0.5">
              <button type="button" onClick={handleCopy} title="Copy response" aria-label="Copy response" className={actionBtn}>
                {copied ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
                <span className="hidden sm:inline">{copied ? 'Copied' : 'Copy'}</span>
              </button>

              <button
                type="button"
                onClick={handleSpeak}
                title={speaking ? 'Stop speech' : 'Read response aloud'}
                aria-label="Read response aloud"
                className={speaking ? actionBtnActive : actionBtn}
              >
                {speaking ? <VolumeX className="w-3.5 h-3.5" /> : <Volume2 className="w-3.5 h-3.5" />}
                <span className="hidden sm:inline">{speaking ? 'Stop' : 'Listen'}</span>
              </button>

              <button
                type="button"
                onClick={() => setLiked(liked === true ? null : true)}
                title="Helpful response"
                aria-label="Mark as helpful"
                aria-pressed={liked === true}
                className={liked === true ? actionBtnActive : actionBtn}
              >
                <ThumbsUp className="w-3.5 h-3.5" />
              </button>

              <button
                type="button"
                onClick={() => setLiked(liked === false ? null : false)}
                title="Not helpful"
                aria-label="Mark as not helpful"
                aria-pressed={liked === false}
                className={liked === false ? actionBtnActive : actionBtn}
              >
                <ThumbsDown className="w-3.5 h-3.5" />
              </button>

              <button type="button" onClick={handleShare} title="Share explanation" aria-label="Share response" className={actionBtn}>
                <Share2 className="w-3.5 h-3.5" />
              </button>
            </div>

            {onRegenerate && (
              <button type="button" onClick={onRegenerate} title="Regenerate AI response" aria-label="Regenerate response" className={cn(actionBtn, 'font-medium')}>
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

const MemoizedChatMessage = React.memo(ChatMessage, areMessagePropsEqual);
export default MemoizedChatMessage;
