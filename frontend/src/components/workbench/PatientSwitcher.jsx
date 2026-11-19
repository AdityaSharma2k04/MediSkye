import React, { useEffect, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { Check, ChevronDown, Lock, Plus, Users } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { cn } from '../../lib/cn';
import useViewport from '../../hooks/useViewport';
import Sheet from '../ui/Sheet';
import { getCachedDocuments, getCachedConversations } from '../../services/api';

const AVATAR_TONES = [
  'bg-cyan-100 text-cyan-900 ring-cyan-200',
  'bg-emerald-100 text-emerald-900 ring-emerald-200',
  'bg-violet-100 text-violet-900 ring-violet-200',
  'bg-amber-100 text-amber-900 ring-amber-200',
  'bg-rose-100 text-rose-900 ring-rose-200',
];

export function initialsOf(name = '', fallback = 'U') {
  const parts = String(name).trim().split(/\s+/).filter(Boolean);
  if (!parts.length) return fallback;
  return (parts[0][0] + (parts.length > 1 ? parts[parts.length - 1][0] : '')).toUpperCase();
}

export function PatientAvatar({ name, index = 0, size = 'md', className }) {
  const sizes = { sm: 'w-6 h-6 text-xs', md: 'w-8 h-8 text-xs', lg: 'w-11 h-11 text-sm' };
  return (
    <span className={cn('inline-flex items-center justify-center rounded-full bg-gradient-to-br ring-1 font-semibold shrink-0', AVATAR_TONES[index % AVATAR_TONES.length], sizes[size], className)}>
      {initialsOf(name)}
    </span>
  );
}

/** Builds the list of selectable patients (Self first). */
export function buildPatients(currentUser, dependents = []) {
  const selfName = currentUser?.full_name || (currentUser?.email ? currentUser.email.split('@')[0] : 'My profile');
  const selfWeight = currentUser?.weight_kg || currentUser?.weight;
  const selfHeight = currentUser?.height_cm || currentUser?.height;
  const selfBmi = (selfHeight && selfWeight && parseFloat(selfHeight) > 0 && parseFloat(selfWeight) > 0)
    ? `BMI ${(parseFloat(selfWeight) / ((parseFloat(selfHeight) / 100) ** 2)).toFixed(1)}`
    : null;

  return [
    {
      id: 'self',
      name: selfName,
      relationship: 'Self',
      meta: [currentUser?.calculated_age ? `${currentUser.calculated_age} yrs` : null, currentUser?.biological_sex, selfBmi].filter(Boolean).join(', '),
      report_count: currentUser?.report_count ?? currentUser?.document_count ?? 0,
      raw: currentUser,
    },
    ...(Array.isArray(dependents) ? dependents : []).map((d) => {
      const dWeight = d.weight_kg || d.weight;
      const dHeight = d.height_cm || d.height;
      const dBmi = (dHeight && dWeight && parseFloat(dHeight) > 0 && parseFloat(dWeight) > 0)
        ? `BMI ${(parseFloat(dWeight) / ((parseFloat(dHeight) / 100) ** 2)).toFixed(1)}`
        : null;
      return {
        id: d.id,
        name: d.full_name || d.name || 'Dependent',
        relationship: d.relationship || 'Dependent',
        meta: [d.calculated_age !== null && d.calculated_age !== undefined ? `${d.calculated_age} yrs` : null, d.biological_sex, dBmi].filter(Boolean).join(', '),
        report_count: d.report_count ?? d.document_count ?? 0,
        raw: d,
      };
    }),
  ];
}

export function isSelfSelected(selectedPatientId, currentUser) {
  return !selectedPatientId || selectedPatientId === 'self' || (currentUser && String(selectedPatientId) === String(currentUser.id));
}

/**
 * Caregiver patient switcher.
 * Desktop: anchored popover. Mobile: bottom sheet with large touch cards.
 */
export default function PatientSwitcher({
  currentUser,
  dependents = [],
  selectedPatientId,
  onSelectPatient,
  onOpenDependents,
  reportCounts = {},
  profileReportCounts = {},
  documents = [],
  pdfs = [],
  compact = false,
  isLocked = false,
  onLockedClick,
}) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const { isMobile } = useViewport();
  const ref = useRef(null);

  const patients = buildPatients(currentUser, dependents);
  const selfSelected = isSelfSelected(selectedPatientId, currentUser);
  const activeIdx = selfSelected ? 0 : Math.max(0, patients.findIndex((p) => String(p.id) === String(selectedPatientId)));
  const active = patients[activeIdx] || patients[0];

  useEffect(() => {
    if (!open || isMobile) return undefined;
    const onDown = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    const onKey = (e) => e.key === 'Escape' && setOpen(false);
    document.addEventListener('mousedown', onDown);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDown);
      document.removeEventListener('keydown', onKey);
    };
  }, [open, isMobile]);

  const choose = (id) => {
    onSelectPatient?.(id);
    setOpen(false);
  };

  const list = (
    <div className="p-1.5 space-y-1 max-h-80 overflow-y-auto overscroll-contain">
      {patients.map((p, i) => {
        const isActive = i === activeIdx;
        const pid = String(p.id);

        const cachedDocList = typeof getCachedDocuments === 'function' ? getCachedDocuments(pid) : [];
        const cachedLength = Array.isArray(cachedDocList) ? cachedDocList.length : 0;

        let passedDocsCount = 0;
        const docList = Array.isArray(documents) && documents.length > 0 ? documents : (Array.isArray(pdfs) ? pdfs : []);
        if (docList.length > 0) {
          passedDocsCount = docList.filter((d) => {
            const rawDep = d.dependent_id !== undefined ? d.dependent_id : (d.patient_id || d.patientId);
            if (pid === 'self') {
              return !rawDep || rawDep === 'self' || rawDep === 'null' || (currentUser?.id && String(rawDep) === String(currentUser.id));
            }
            return String(rawDep) === String(pid);
          }).length;
        }

        let convDocCount = 0;
        try {
          const cachedConvs = typeof getCachedConversations === 'function' ? getCachedConversations(pid) : [];
          if (Array.isArray(cachedConvs)) {
            const docIds = new Set();
            cachedConvs.forEach((c) => {
              if (c.document_id || c.pdf?.id) {
                const cPid = c.dependent_id !== undefined ? c.dependent_id : (c.patient_id || c.patientId);
                const isMatchingPid = pid === 'self'
                  ? (!cPid || cPid === 'self' || cPid === 'null')
                  : String(cPid) === String(pid);
                if (isMatchingPid) {
                  docIds.add(String(c.document_id || c.pdf?.id));
                }
              }
            });
            convDocCount = docIds.size;
          }
        } catch (_) { }

        const depReportCount = p.report_count ?? p.document_count ?? p.raw?.report_count ?? p.raw?.document_count ?? 0;

        const count = Math.max(
          profileReportCounts?.[pid] || 0,
          reportCounts?.[pid] || 0,
          (pid === 'self' && currentUser?.id) ? (profileReportCounts?.[String(currentUser.id)] || reportCounts?.[String(currentUser.id)] || 0) : 0,
          passedDocsCount,
          cachedLength,
          convDocCount,
          depReportCount
        );
        return (
          <button
            key={p.id}
            type="button"
            onClick={() => choose(p.id)}
            className={cn(
              'w-full flex items-center gap-3 rounded-2xl px-2.5 text-left transition border',
              isMobile ? 'py-3' : 'py-2',
              isActive ? 'bg-cyan-50 border-cyan-200 text-cyan-950' : 'border-transparent hover:bg-slate-50'
            )}
          >
            <PatientAvatar name={p.name} index={i} size={isMobile ? 'lg' : 'md'} />
            <span className="min-w-0 flex-1">
              <span className="flex items-center gap-1.5">
                <span className="text-[13px] font-medium text-slate-900 truncate">{p.name}</span>
                <span className="text-xs px-1.5 py-px rounded-full bg-slate-100 text-slate-600 shrink-0">{p.relationship}</span>
              </span>
              <span className="block text-xs text-ink-faint mt-0.5 truncate">
                {[p.meta, count ? `${count} report${count === 1 ? '' : 's'}` : 'No reports yet'].filter(Boolean).join(', ')}
              </span>
            </span>
            {isActive && <Check className="w-4 h-4 text-emerald-600 shrink-0" />}
          </button>
        );
      })}
    </div>
  );

  const manage = (
    <button
      type="button"
      onClick={() => {
        setOpen(false);
        onOpenDependents?.();
      }}
      className="ms-tap w-full flex items-center justify-center gap-2 h-10 rounded-xl text-xs font-medium text-slate-700 hover:text-slate-900 bg-slate-50 hover:bg-slate-100 border border-slate-200 transition"
    >
      <Plus className="w-3.5 h-3.5" /> {t('workbench.manage_dependents', 'Manage / Add Dependents')}
    </button>
  );

  return (
    <div className="relative min-w-0" ref={ref}>
      <button
        type="button"
        onClick={() => {
          if (isLocked) {
            onLockedClick?.();
            return;
          }
          setOpen((o) => !o);
        }}
        aria-label={isLocked ? 'Profile is locked for this report chat' : 'Select patient context'}
        title={isLocked ? "Profile is locked because a report is uploaded in this chat. Click 'New Chat' to switch profiles." : undefined}
        data-testid="patient-switcher-trigger"
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-disabled={isLocked}
        className={cn(
          'ms-tap min-w-0 max-w-[220px] sm:max-w-[280px] whitespace-nowrap shrink-0 flex items-center gap-2 rounded-full pl-1 pr-2.5 h-9 border transition',
          'bg-white border-slate-200 hover:bg-slate-50 hover:border-slate-300 shadow-sm',
          !selfSelected && 'border-violet-200 bg-violet-50 text-violet-900',
          isLocked && 'border-amber-200 bg-amber-50 hover:border-amber-300 hover:bg-amber-100 text-amber-900 cursor-not-allowed'
        )}
      >
        <PatientAvatar name={active?.name} index={activeIdx} size="sm" />
        {!compact && <span className="truncate text-xs font-medium text-ink">{active?.name}</span>}
        {!compact && <span className="hidden sm:inline text-xs text-ink-faint shrink-0">{active?.relationship}</span>}
        {isLocked ? (
          <Lock className="w-3.5 h-3.5 text-amber-600 shrink-0" aria-hidden="true" />
        ) : (
          <ChevronDown className={cn('w-3.5 h-3.5 text-ink-mute shrink-0 transition-transform', open && 'rotate-180')} />
        )}
      </button>

      {isMobile ? (
        <Sheet
          open={open}
          onOpenChange={setOpen}
          title={t('workbench.patient_lens_title', 'Whose health are we reviewing?')}
          description={t('workbench.patient_lens_desc', 'Reports, chat answers and remembered facts follow the selected person.')}
          icon={Users}
          footer={manage}
        >
          {list}
        </Sheet>
      ) : (
        <AnimatePresence>
          {open && (
            <motion.div
              role="dialog"
              aria-label="Patient context"
              initial={{ opacity: 0, y: -6, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -4, scale: 0.98 }}
              transition={{ duration: 0.16, ease: [0.22, 1, 0.36, 1] }}
              className="absolute left-0 top-full mt-2 w-72 sm:w-80 rounded-2xl bg-white z-[100] shadow-2xl border border-slate-200 overflow-hidden"
            >
              <div className="px-3.5 pt-3 pb-1 text-xs font-semibold text-slate-600">Clinical analysis lens</div>
              {list}
              <div className="p-2 border-t border-slate-200">{manage}</div>
            </motion.div>
          )}
        </AnimatePresence>
      )}
    </div>
  );
}
