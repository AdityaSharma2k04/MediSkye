import React, { useRef, useEffect, useState, useMemo, useLayoutEffect } from 'react';
import { ArrowDown, FileText, Sparkles, ShieldCheck, Activity, HelpCircle, Stethoscope, FlaskConical, TrendingDown } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import ChatMessage from './ChatMessage';
import { cn } from '../lib/cn';
import { summarizeTriage, metricName, classifyStatus, isNotableDrop, reportDateLabel, rangeGeometry } from '../lib/clinical';

const GENERAL_SUGGESTIONS = [
  { title: 'Explain Hemoglobin levels', query: 'Explain Hemoglobin levels and what they indicate about health.', icon: Activity },
  { title: 'Cholesterol & LDL — what do they mean?', query: 'What do Cholesterol and LDL levels mean, and what are healthy ranges?', icon: FileText },
  { title: 'Common lab tests explained', query: 'What are the most common blood lab tests and what do they measure?', icon: HelpCircle },
  { title: 'When should I see a doctor?', query: 'When should I see a doctor about my lab results?', icon: Stethoscope },
];

const REPORT_SUGGESTIONS = [
  { title: 'What are my abnormal values?', query: 'What are my abnormal values in this report?', icon: FlaskConical },
  { title: 'Explain my first abnormal biomarker', query: 'Explain my first abnormal biomarker and what it means.', icon: Activity },
  { title: 'Summarize for my doctor', query: 'Summarize this report for my doctor in plain language.', icon: Stethoscope },
  { title: 'What should I ask my doctor?', query: 'What should I ask my doctor based on this report?', icon: HelpCircle },
];

/** Suggestions grounded in the report's actual flagged biomarkers, when we have them. */
function buildReportSuggestions(metrics) {
  if (!Array.isArray(metrics) || !metrics.length) return REPORT_SUGGESTIONS;
  const flagged = metrics.filter((m) => ['critical', 'high', 'low'].includes(classifyStatus(m)));
  const drops = metrics.filter(isNotableDrop);
  const out = [];
  if (flagged[0]) {
    const c = classifyStatus(flagged[0]);
    const geom = rangeGeometry(flagged[0]);
    const side = geom?.side;
    let direction = 'outside the reference range';
    if (side === 'below' || c === 'low') {
      direction = 'low';
    } else if (side === 'above' || c === 'high') {
      direction = 'high';
    }
    const name = metricName(flagged[0]);
    out.push({
      title: `Why is my ${name} ${direction}?`,
      query: `Why is my ${name} ${direction} at ${flagged[0].value} ${flagged[0].unit || ''}, and what can cause it?`,
      icon: FlaskConical,
    });
  }
  if (drops[0]) {
    const name = metricName(drops[0]);
    out.push({ title: `What does the drop in ${name} mean?`, query: `My ${name} changed from ${drops[0].previous_value} to ${drops[0].value}. What could explain this change?`, icon: TrendingDown });
  }
  REPORT_SUGGESTIONS.forEach((s) => {
    if (out.length < 4) out.push(s);
  });
  return out.slice(0, 4);
}

export function greeting() {
  const h = new Date().getHours();
  if (h < 5) return 'Working late';
  if (h < 12) return 'Good morning';
  if (h < 17) return 'Good afternoon';
  return 'Good evening';
}

const INVALID_NAME_PATTERNS = new Set([
  'my',
  'user',
  'patient',
  'null',
  'undefined',
  'not specified',
  'self',
  'my profile',
  'profile',
  'dependent',
]);

export function cleanGreetingName(name) {
  if (!name || typeof name !== 'string') return null;
  const trimmed = name.trim();
  if (!trimmed) return null;
  if (trimmed.includes('@')) return null;
  if (INVALID_NAME_PATTERNS.has(trimmed.toLowerCase())) return null;
  const first = trimmed.split(/\s+/)[0];
  if (!first || INVALID_NAME_PATTERNS.has(first.toLowerCase())) return null;
  return first;
}

export default function ChatWindow({
  conversationId,
  messages,
  isGenerating,
  loadingHistory = false,
  onRegenerate,
  onSelectSampleQuery,
  onTrySampleReport,
  activePdf,
  currentUser,
  patientName,
  metrics = [],
  className,
}) {
  const { t } = useTranslation();
  const scrollRef = useRef(null);
  const stickRef = useRef(true);
  const [showScrollBtn, setShowScrollBtn] = useState(false);

  const scrollToBottom = (behavior = 'auto') => {
    const el = scrollRef.current;
    if (!el) return;
    if (typeof window !== 'undefined' && window.requestAnimationFrame) {
      window.requestAnimationFrame(() => {
        if (!el) return;
        if (typeof el.scrollTo === 'function' && behavior === 'smooth') {
          el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' });
        } else {
          el.scrollTop = el.scrollHeight;
        }
      });
    } else {
      if (typeof el.scrollTo === 'function') el.scrollTo({ top: el.scrollHeight, behavior });
      else el.scrollTop = el.scrollHeight;
    }
  };

  const scrollToBottomImmediate = () => {
    const el = scrollRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
    if (typeof window !== 'undefined') {
      if (window.requestAnimationFrame) {
        window.requestAnimationFrame(() => {
          if (el) el.scrollTop = el.scrollHeight;
        });
      }
      setTimeout(() => {
        if (el) el.scrollTop = el.scrollHeight;
      }, 50);
    }
  };

  useLayoutEffect(() => {
    if (stickRef.current) scrollToBottom();
  }, [messages, isGenerating]);

  // Whenever the user switches to an existing conversation (conversationId changes)
  // or when that conversation's messages array populates from history (messages.length > 0),
  // immediately scroll the messages container to the bottom inside useLayoutEffect
  // AND inside a follow-up requestAnimationFrame + setTimeout(..., 50)
  useLayoutEffect(() => {
    if (conversationId || (messages && messages.length > 0)) {
      stickRef.current = true;
      scrollToBottomImmediate();
    }
  }, [conversationId, messages?.length]);

  const handleScroll = () => {
    const el = scrollRef.current;
    if (!el) return;
    const distance = el.scrollHeight - el.scrollTop - el.clientHeight;
    stickRef.current = distance < 120;
    setShowScrollBtn(distance > 200);
  };

  const triage = useMemo(() => summarizeTriage(metrics), [metrics]);
  const suggestions = useMemo(() => (activePdf ? buildReportSuggestions(metrics) : GENERAL_SUGGESTIONS), [activePdf?.id, metrics]);
  const greetingName = cleanGreetingName(patientName || currentUser?.full_name);

  return (
    <div className={cn('relative flex-1 min-h-0 flex flex-col', className)}>
      <div ref={scrollRef} onScroll={handleScroll} className="chat-messages-container flex-1 min-h-0 overflow-y-auto overscroll-contain">
        <div className="w-full max-w-3xl mx-auto px-4 sm:px-6 py-6 min-h-full flex flex-col">
          {loadingHistory ? (
            <div className="flex-1 flex flex-col items-center justify-center text-center py-16 animate-fade-in" role="status">
              <Sparkles className="w-6 h-6 animate-pulse text-cyan-300 mb-3" />
              <div className="text-sm font-medium text-ink-soft">{t('chat.loading_conversation', 'Loading Conversation...')}</div>
              <div className="text-xs mt-1 text-ink-faint">{t('chat.fetching_messages', 'Syncing your secure conversations...')}</div>
            </div>
          ) : messages.length === 0 ? (
            <div className="flex-1 flex flex-col justify-center py-8 animate-fade-in">
              <span className="sr-only">MediSkye AI Medical Assistant</span>

              <div className="mb-7">
                <p className="text-sm text-ink-mute mb-2">{greetingName ? `${greeting()}, ${greetingName}.` : `${greeting()}.`}</p>
                <h1 className="ms-display text-[30px] sm:text-[38px] leading-[1.08] text-white max-w-xl">
                  {activePdf ? 'Your report is indexed and ready for questions.' : 'Where should we start?'}
                </h1>
              </div>

              {activePdf && (
                <div className="mb-6 rounded-2xl ms-surface p-4 flex items-center gap-4">
                  <div className="w-10 h-12 rounded-lg bg-white/[0.04] border border-white/[0.08] flex items-center justify-center shrink-0">
                    <FileText className="w-4 h-4 text-cyan-300" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="text-[13px] font-medium text-white truncate">{activePdf.filename || activePdf.name || 'Lab report'}</div>
                    <div className="text-xs text-ink-mute mt-0.5">
                      {[reportDateLabel(activePdf) && `Collected ${reportDateLabel(activePdf)}`, triage.total ? `${triage.total} biomarkers extracted` : 'Extracting biomarkers'].filter(Boolean).join(', ')}
                    </div>
                  </div>
                  {triage.total > 0 && (
                    <div className="hidden sm:flex items-center gap-3 shrink-0 text-right">
                      <Stat n={triage.flagged} label="flagged" tone={triage.flagged ? 'text-amber-300' : 'text-white'} />
                      <Stat n={triage.inRange} label="in range" tone="text-emerald-300" />
                    </div>
                  )}
                </div>
              )}

              <div className="flex flex-col gap-1 -mx-2">
                {suggestions.map((item) => {
                  const Icon = item.icon || Sparkles;
                  return (
                    <button
                      key={item.title}
                      type="button"
                      onClick={() => onSelectSampleQuery?.(item.query)}
                      className="group ms-tap w-full flex items-center gap-3.5 py-3 px-3 rounded-2xl text-left text-[15px] text-ink-soft hover:text-white hover:bg-white/[0.04] active:bg-white/[0.07] transition"
                    >
                      <span className="w-8 h-8 rounded-xl bg-white/[0.03] border border-white/[0.06] flex items-center justify-center shrink-0 group-hover:border-white/[0.12]">
                        <Icon className="w-4 h-4 text-ink-mute group-hover:text-cyan-300 transition-colors" />
                      </span>
                      <span className="truncate">{item.title}</span>
                    </button>
                  );
                })}

                {!activePdf && (
                  <button
                    type="button"
                    onClick={() => {
                      if (onTrySampleReport) onTrySampleReport();
                      else if (onSelectSampleQuery) onSelectSampleQuery?.('Can you summarize the abnormal findings in this report?');
                    }}
                    className="group ms-tap w-full flex items-center gap-3.5 py-3 px-3 rounded-2xl text-left text-[15px] text-cyan-200 hover:bg-cyan-500/[0.08] font-medium transition"
                  >
                    <span className="w-8 h-8 rounded-xl bg-cyan-500/10 border border-cyan-500/25 flex items-center justify-center shrink-0">
                      <FlaskConical className="w-4 h-4 text-cyan-300" />
                    </span>
                    <span className="truncate">Try with a Sample Blood Test Report</span>
                  </button>
                )}
              </div>

              <div className="mt-8 flex items-center gap-2 text-xs text-ink-faint">
                <ShieldCheck className="w-3.5 h-3.5" />
                <span>{t('chat.encrypted_session', 'Encrypted at rest (Fernet) • TLS 1.3 in transit')}</span>
              </div>
            </div>
          ) : (
            <div className="py-2" role="log" aria-label="Conversation" aria-live="off">
              {messages.map((msg, index) => {
                const isLatest = index === messages.length - 1;
                const isCompleted = !isLatest || !isGenerating;
                const firstAssistantIndex = messages.findIndex((m) => m.sender === 'assistant' || m.role === 'ai');
                const isFollowupTurn = firstAssistantIndex !== -1 && index > firstAssistantIndex;
                return (
                  <div key={msg.id || index} className={cn(isCompleted && 'ms-message-contain')}>
                    <ChatMessage
                      message={msg}
                      isFollowupTurn={isFollowupTurn}
                      onRegenerate={isLatest && msg.sender === 'assistant' ? onRegenerate : null}
                    />
                  </div>
                );
              })}
            </div>
          )}
          <div className="sr-only" role="status" aria-live="polite">
            {isGenerating ? t('chat.generating', 'MediSkye is writing a response…') : ''}
          </div>
        </div>
      </div>

      {showScrollBtn && (
        <button
          type="button"
          onClick={() => {
            stickRef.current = true;
            scrollToBottom('smooth');
          }}
          aria-label="Scroll to latest message"
          title="Scroll to latest message"
          className="absolute bottom-3 left-1/2 -translate-x-1/2 z-20 h-9 px-3 rounded-full ms-glass text-ink-soft hover:text-white flex items-center gap-1.5 text-xs transition animate-fade-in"
        >
          <ArrowDown className="w-3.5 h-3.5" /> Latest
        </button>
      )}
    </div>
  );
}

function Stat({ n, label, tone }) {
  return (
    <div>
      <div className={cn('ms-num text-lg font-semibold leading-none', tone)}>{n}</div>
      <div className="text-xs text-ink-faint mt-1">{label}</div>
    </div>
  );
}
