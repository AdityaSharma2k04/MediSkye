import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Brain, Search, Trash2, FileText, MessageSquare, Loader2, ShieldCheck, X, User } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { cn } from '../../lib/cn';
import Sheet from '../ui/Sheet';
import { getFacts, deleteFact, clearAllMemoryFacts, updateMemoryConsent, updateProfile, getDependents } from '../../services/api';
import { logger } from '../../services/logger';
import { reportLabel } from '../../lib/clinical';

function FactText({ text }) {
  const [expanded, setExpanded] = useState(false);
  if (!text) return null;
  const isLong = text.length > 160;

  if (!isLong) {
    return <p className="text-[13px] text-ink leading-snug break-words">{text}</p>;
  }

  return (
    <div>
      <p className={cn('text-[13px] text-ink leading-snug break-words', !expanded && 'line-clamp-3')}>
        {text}
      </p>
      <button
        type="button"
        onClick={() => setExpanded((prev) => !prev)}
        className="mt-1 text-[11px] font-medium text-cyan-400 hover:text-cyan-300 underline underline-offset-2"
      >
        {expanded ? 'Show less' : 'Show more'}
      </button>
    </div>
  );
}

const CATEGORY_STYLES = {
  condition: 'bg-rose-500/10 text-rose-200 border-rose-500/25',
  medication: 'bg-sky-500/10 text-sky-200 border-sky-500/25',
  allergy: 'bg-amber-500/10 text-amber-200 border-amber-500/25',
  measurement: 'bg-cyan-500/10 text-cyan-200 border-cyan-500/25',
  lab_trend: 'bg-cyan-500/10 text-cyan-200 border-cyan-500/25',
  weight: 'bg-emerald-500/10 text-emerald-200 border-emerald-500/25',
  lifestyle: 'bg-violet-500/10 text-violet-200 border-violet-500/25',
  sport_hobby: 'bg-violet-500/10 text-violet-200 border-violet-500/25',
};

const categoryOf = (f) => String(f?.fact_type || f?.category || 'other').toLowerCase();
const prettyCategory = (c) => c.replace(/_/g, ' ').replace(/\b\w/g, (m) => m.toUpperCase());

function monthKey(ts) {
  const d = ts ? new Date(ts) : null;
  if (!d || Number.isNaN(d.getTime())) return 'Undated';
  return d.toLocaleDateString('en-US', { month: 'long', year: 'numeric' });
}

/**
 * Patient Memory Vault — a searchable timeline of every fact MediSkye
 * remembers for the active patient, with the report or chat it came from.
 * Deletions take effect immediately (server is the source of truth).
 */
export default function MemoryVault({
  open,
  onOpenChange,
  selectedPatientId = 'self',
  activePatientId,
  patientName,
  currentUser,
  dependents: initialDependents = [],
  onConsentChanged,
  documents = [],
}) {
  const { t } = useTranslation();
  const effectiveInitialPatient = activePatientId || selectedPatientId || 'self';
  const [selectedVaultPatientId, setSelectedVaultPatientId] = useState(effectiveInitialPatient);
  const [dependentsList, setDependentsList] = useState(initialDependents || []);

  const [facts, setFacts] = useState([]);
  const [loading, setLoading] = useState(false);
  const [query, setQuery] = useState('');
  const [category, setCategory] = useState('all');
  const [deletingId, setDeletingId] = useState(null);
  const [confirmClear, setConfirmClear] = useState(false);
  const [confirmText, setConfirmText] = useState('');
  const [error, setError] = useState('');
  const [consent, setConsent] = useState(Boolean(currentUser?.memory_consent_granted));

  useEffect(() => {
    if (initialDependents && initialDependents.length > 0) {
      setDependentsList(initialDependents);
    }
  }, [initialDependents]);

  useEffect(() => {
    if (open && (!dependentsList || dependentsList.length === 0)) {
      getDependents()
        .then((deps) => {
          if (Array.isArray(deps) && deps.length > 0) {
            setDependentsList(deps);
          }
        })
        .catch((err) => logger.warn('Failed to load dependents for MemoryVault:', err));
    }
  }, [open, dependentsList]);

  useEffect(() => {
    setConsent(Boolean(currentUser?.memory_consent_granted));
  }, [currentUser?.memory_consent_granted]);

  useEffect(() => {
    if (open) {
      setSelectedVaultPatientId(activePatientId || selectedPatientId || 'self');
    }
  }, [open, activePatientId, selectedPatientId]);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const list = await getFacts(selectedVaultPatientId);
      setFacts(Array.isArray(list) ? list : []);
    } catch (err) {
      logger.warn('Failed to load memory facts:', err);
      setFacts([]);
    } finally {
      setLoading(false);
    }
  }, [selectedVaultPatientId]);

  useEffect(() => {
    if (open) load();
    if (!open) {
      setConfirmClear(false);
      setConfirmText('');
    }
  }, [open, load]);

  const activeVaultPatientName = useMemo(() => {
    if (selectedVaultPatientId === 'self') {
      return currentUser?.full_name || 'My Profile';
    }
    const match = dependentsList.find((d) => String(d.id) === String(selectedVaultPatientId));
    return match?.full_name || patientName || 'this patient';
  }, [selectedVaultPatientId, currentUser, dependentsList, patientName]);

  const docTitleById = useMemo(() => {
    const m = new Map();
    documents.forEach((d) => d?.id && m.set(String(d.id), reportLabel(d)));
    return m;
  }, [documents]);

  const categories = useMemo(() => {
    const counts = new Map();
    facts.forEach((f) => counts.set(categoryOf(f), (counts.get(categoryOf(f)) || 0) + 1));
    return [...counts.entries()].sort((a, b) => b[1] - a[1]);
  }, [facts]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return facts
      .filter((f) => category === 'all' || categoryOf(f) === category)
      .filter((f) => !q || String(f.fact_text || f.fact_value || '').toLowerCase().includes(q) || categoryOf(f).includes(q))
      .sort((a, b) => new Date(b.created_at || 0) - new Date(a.created_at || 0));
  }, [facts, query, category]);

  const timeline = useMemo(() => {
    const groups = new Map();
    filtered.forEach((f) => {
      const k = monthKey(f.created_at);
      if (!groups.has(k)) groups.set(k, []);
      groups.get(k).push(f);
    });
    return [...groups.entries()];
  }, [filtered]);

  const handleDelete = async (id) => {
    setDeletingId(id);
    setError('');
    try {
      await deleteFact(id, selectedVaultPatientId);
      setFacts((prev) => prev.filter((f) => f.id !== id));
    } catch (err) {
      setError(err?.message || 'That fact could not be deleted. Try again.');
    } finally {
      setDeletingId(null);
    }
  };

  const handleClearAll = async () => {
    setError('');
    try {
      await clearAllMemoryFacts(selectedVaultPatientId);
      setFacts([]);
      setConfirmClear(false);
      setConfirmText('');
    } catch (err) {
      setError(err?.message || 'Memory could not be cleared. Try again.');
    }
  };

  const toggleConsent = async () => {
    const next = !consent;
    setConsent(next);
    try {
      try {
        await updateMemoryConsent(next);
      } catch {
        await updateProfile({ memory_consent_granted: next });
      }
      onConsentChanged?.(next);
    } catch (err) {
      setConsent(!next);
      setError(err?.message || 'Memory setting could not be updated.');
    }
  };

  const sourceBadge = (f) => {
    const docId = f.source_document_id || f.document_id;
    const title = docId ? docTitleById.get(String(docId)) : null;
    const src = String(f.source_type || '').toLowerCase();
    if (title || src.includes('report') || src.includes('document') || src.includes('upload')) {
      return (
        <span className="inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded-md bg-white/[0.04] border border-white/[0.07] text-ink-mute max-w-[180px]">
          <FileText className="w-3 h-3 shrink-0" />
          <span className="truncate">{title || 'From a lab report'}</span>
        </span>
      );
    }
    if (src) {
      return (
        <span className="inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded-md bg-white/[0.04] border border-white/[0.07] text-ink-mute">
          <MessageSquare className="w-3 h-3" />
          {src.includes('chat') ? 'From a conversation' : prettyCategory(src)}
        </span>
      );
    }
    return null;
  };

  return (
    <>
      <Sheet
        open={open}
        onOpenChange={onOpenChange}
        title={t('workbench.memory_vault', 'Memory vault')}
        description={`What MediSkye remembers about ${activeVaultPatientName} across conversations. Remove anything that is wrong or outdated.`}
        icon={Brain}
        width={520}
        footer={
          facts.length > 0 ? (
            confirmClear ? (
              <div className="space-y-2">
                <label htmlFor="vault-clear-confirm" className="block text-[11px] text-ink-mute">
                  Type <span className="ms-num text-rose-300">CLEAR</span> to permanently delete {facts.length} remembered fact{facts.length === 1 ? '' : 's'}.
                </label>
                <div className="flex gap-2">
                  <input
                    id="vault-clear-confirm"
                    value={confirmText}
                    onChange={(e) => setConfirmText(e.target.value)}
                    autoComplete="off"
                    autoCapitalize="off"
                    autoCorrect="off"
                    spellCheck={false}
                    className="flex-1 min-w-0 h-10 px-3 rounded-xl bg-graphite border border-white/[0.1] text-sm text-white ms-num focus:outline-none focus:border-rose-500/50"
                  />
                  <button
                    type="button"
                    onClick={() => {
                      setConfirmClear(false);
                      setConfirmText('');
                    }}
                    className="ms-tap h-10 px-3 rounded-xl text-xs text-ink-soft border border-white/[0.1] hover:bg-white/[0.05]"
                  >
                    Keep
                  </button>
                  <button
                    type="button"
                    disabled={confirmText.trim() !== 'CLEAR'}
                    onClick={handleClearAll}
                    className="ms-tap h-10 px-3 rounded-xl text-xs font-semibold text-white bg-rose-600 hover:bg-rose-500 disabled:opacity-40 disabled:pointer-events-none"
                  >
                    Clear memory
                  </button>
                </div>
              </div>
            ) : (
              <button
                type="button"
                onClick={() => setConfirmClear(true)}
                className="ms-tap w-full h-10 rounded-xl text-xs font-medium text-rose-300 border border-rose-500/25 hover:bg-rose-500/10 transition"
              >
                Clear all remembered facts
              </button>
            )
          ) : null
        }
      >
        <div className="px-5 py-4 space-y-4" data-testid="memory-vault">
          {/* Patient Selector */}
          <div className="flex items-center justify-between gap-3 p-3 rounded-2xl bg-white/[0.03] border border-white/[0.08]">
            <div className="flex items-center gap-2 min-w-0">
              <User className="w-4 h-4 text-cyan-400 shrink-0" />
              <label htmlFor="memory-vault-patient-select" className="text-xs font-medium text-ink-soft whitespace-nowrap">
                {t('common.patient', 'Patient')}:
              </label>
            </div>
            <select
              id="memory-vault-patient-select"
              aria-label="Select patient memory vault"
              data-testid="memory-vault-patient-select"
              value={selectedVaultPatientId}
              onChange={(e) => setSelectedVaultPatientId(e.target.value)}
              className="flex-1 max-w-[280px] h-8 px-2.5 text-xs font-medium rounded-xl bg-graphite border border-white/[0.14] text-white focus:outline-none focus:border-cyan-500/50 cursor-pointer truncate"
            >
              <option value="self">
                {currentUser?.full_name || 'My Profile'} (Self)
              </option>
              {dependentsList.map((dep) => (
                <option key={dep.id} value={dep.id}>
                  {dep.full_name} ({dep.relationship})
                </option>
              ))}
            </select>
          </div>

          <div className="flex items-center justify-between gap-3 p-3.5 rounded-2xl ms-raised">
            <div className="flex items-start gap-2.5 min-w-0">
              <ShieldCheck className={cn('w-4 h-4 mt-0.5 shrink-0', consent ? 'text-emerald-400' : 'text-ink-faint')} />
              <div className="min-w-0">
                <div className="text-xs font-semibold text-white">Cross-session memory {consent ? 'on' : 'off'}</div>
                <p className="text-[11px] text-ink-mute mt-0.5 leading-relaxed">
                  {consent ? 'New conditions, medications and lab trends are remembered.' : 'Nothing new will be remembered until you turn this on.'}
                </p>
              </div>
            </div>
            <button
              type="button"
              role="switch"
              aria-checked={consent}
              aria-label="Memory vault consent"
              onClick={toggleConsent}
              className={cn('relative inline-flex h-6 w-11 shrink-0 rounded-full transition-colors', consent ? 'bg-emerald-500' : 'bg-white/[0.12]')}
            >
              <span className={cn('absolute top-0.5 left-0.5 h-5 w-5 rounded-full bg-white shadow transition-transform', consent && 'translate-x-5')} />
            </button>
          </div>

          {error && (
            <div role="alert" className="text-xs text-rose-200 bg-rose-500/10 border border-rose-500/25 rounded-xl px-3 py-2">
              {error}
            </div>
          )}

          <div className="relative">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-ink-faint" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search remembered facts"
              aria-label="Search remembered facts"
              className="w-full h-10 pl-9 pr-9 rounded-xl bg-graphite border border-white/[0.08] text-sm text-white placeholder:text-ink-faint focus:outline-none focus:border-cyan-500/45"
            />
            {query && (
              <button type="button" onClick={() => setQuery('')} aria-label="Clear fact search" className="absolute right-1.5 top-1/2 -translate-y-1/2 w-8 h-8 rounded-lg flex items-center justify-center text-ink-mute hover:text-white">
                <X className="w-3.5 h-3.5" />
              </button>
            )}
          </div>

          {categories.length > 1 && (
            <div className="flex gap-1.5 overflow-x-auto no-scrollbar -mx-1 px-1">
              {[['all', facts.length], ...categories].map(([c, n]) => (
                <button
                  key={c}
                  type="button"
                  aria-pressed={category === c}
                  onClick={() => setCategory(c)}
                  className={cn(
                    'ms-tap shrink-0 h-8 px-3 rounded-full text-xs border transition inline-flex items-center gap-1.5',
                    category === c ? 'bg-white/[0.09] border-white/[0.16] text-white' : 'bg-white/[0.02] border-white/[0.07] text-ink-mute hover:text-white'
                  )}
                >
                  {c === 'all' ? 'Everything' : prettyCategory(c)}
                  <span className="ms-num text-[10px] text-ink-faint">{n}</span>
                </button>
              ))}
            </div>
          )}

          {loading ? (
            <div className="py-12 flex items-center justify-center gap-2 text-xs text-ink-mute" role="status">
              <Loader2 className="w-4 h-4 animate-spin" /> Loading remembered facts...
            </div>
          ) : facts.length === 0 ? (
            <div className="py-10 text-center">
              <div className="w-11 h-11 mx-auto mb-3 rounded-2xl flex items-center justify-center bg-white/[0.04] text-ink-mute">
                <Brain className="w-5 h-5" />
              </div>
              <div className="text-sm font-semibold text-white">Nothing remembered yet</div>
              <p className="text-xs text-ink-mute mt-1 max-w-xs mx-auto">
                {consent
                  ? 'Key findings from reports and conversations will appear here as a timeline.'
                  : 'Turn on cross-session memory to let MediSkye keep clinical context between chats.'}
              </p>
            </div>
          ) : filtered.length === 0 ? (
            <p className="py-8 text-center text-xs text-ink-mute">No facts match that search.</p>
          ) : (
            <ol className="relative space-y-5">
              {timeline.map(([month, items]) => (
                <li key={month}>
                  <h3 className="text-[11px] font-semibold text-ink-mute mb-2 px-0.5">{month}</h3>
                  <ul className="relative border-l border-white/[0.08] ml-1.5 space-y-2">
                    {items.map((f) => {
                      const c = categoryOf(f);
                      const date = f.created_at ? new Date(f.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) : null;
                      return (
                        <li key={f.id} className="relative pl-4">
                          <span className="absolute -left-[4.5px] top-3.5 w-2 h-2 rounded-full bg-carbon border border-white/30" aria-hidden="true" />
                          <div className="group p-3 rounded-xl ms-surface flex items-start gap-3">
                            <div className="min-w-0 flex-1 space-y-1.5">
                              <FactText text={f.fact_text || f.fact_value} />
                              <div className="flex flex-wrap items-center gap-1.5">
                                <span className={cn('text-[10px] font-medium px-1.5 py-0.5 rounded-md border', CATEGORY_STYLES[c] || 'bg-white/[0.04] text-ink-mute border-white/[0.08]')}>
                                  {prettyCategory(c)}
                                </span>
                                {sourceBadge(f)}
                                {date && <span className="ms-num text-[10px] text-ink-faint">{date}</span>}
                              </div>
                            </div>
                            <button
                              type="button"
                              onClick={() => handleDelete(f.id)}
                              disabled={deletingId === f.id}
                              aria-label={`Forget: ${String(f.fact_text || f.fact_value || 'fact').slice(0, 40)}`}
                              title="Forget this fact"
                              className="ms-tap w-8 h-8 rounded-lg flex items-center justify-center text-ink-faint hover:text-rose-300 hover:bg-rose-500/10 transition shrink-0 disabled:opacity-40"
                            >
                              {deletingId === f.id ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Trash2 className="w-3.5 h-3.5" />}
                            </button>
                          </div>
                        </li>
                      );
                    })}
                  </ul>
                </li>
              ))}
            </ol>
          )}
        </div>
      </Sheet>

    </>
  );
}
