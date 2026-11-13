import React, { useEffect, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { Check, ChevronDown, Plus, Users } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { cn } from '../../lib/cn';
import useViewport from '../../hooks/useViewport';
import Sheet from '../ui/Sheet';

const AVATAR_TONES = [
  'from-cyan-500/30 to-cyan-700/30 text-cyan-100 ring-cyan-400/30',
  'from-emerald-500/30 to-emerald-700/30 text-emerald-100 ring-emerald-400/30',
  'from-violet-500/30 to-violet-700/30 text-violet-100 ring-violet-400/30',
  'from-amber-500/30 to-amber-700/30 text-amber-100 ring-amber-400/30',
  'from-rose-500/30 to-rose-700/30 text-rose-100 ring-rose-400/30',
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
  return [
    {
      id: 'self',
      name: selfName,
      relationship: 'Self',
      meta: [currentUser?.calculated_age ? `${currentUser.calculated_age} yrs` : null, currentUser?.biological_sex].filter(Boolean).join(', '),
    },
    ...(Array.isArray(dependents) ? dependents : []).map((d) => ({
      id: d.id,
      name: d.full_name || 'Dependent',
      relationship: d.relationship || 'Dependent',
      meta: [d.calculated_age !== null && d.calculated_age !== undefined ? `${d.calculated_age} yrs` : null, d.biological_sex].filter(Boolean).join(', '),
    })),
  ];
}

export function isSelfSelected(selectedPatientId, currentUser) {
  return !selectedPatientId || selectedPatientId === 'self' || (currentUser && String(selectedPatientId) === String(currentUser.id));
}

/**
 * Caregiver patient switcher.
 * Desktop: anchored popover. Mobile: bottom sheet with large touch cards.
 */
export default function PatientSwitcher({ currentUser, dependents = [], selectedPatientId, onSelectPatient, onOpenDependents, reportCounts = {}, compact = false }) {
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
    <div className="p-1.5 space-y-1">
      {patients.map((p, i) => {
        const isActive = i === activeIdx;
        const count = reportCounts[String(p.id)] || 0;
        return (
          <button
            key={p.id}
            type="button"
            onClick={() => choose(p.id)}
            className={cn(
              'w-full flex items-center gap-3 rounded-2xl px-2.5 text-left transition border',
              isMobile ? 'py-3' : 'py-2',
              isActive ? 'bg-white/[0.06] border-white/[0.1]' : 'border-transparent hover:bg-white/[0.04]'
            )}
          >
            <PatientAvatar name={p.name} index={i} size={isMobile ? 'lg' : 'md'} />
            <span className="min-w-0 flex-1">
              <span className="flex items-center gap-1.5">
                <span className="text-[13px] font-medium text-white truncate">{p.name}</span>
                <span className="text-xs px-1.5 py-px rounded-full bg-white/[0.06] text-ink-mute shrink-0">{p.relationship}</span>
              </span>
              <span className="block text-xs text-ink-faint mt-0.5 truncate">
                {[p.meta, count ? `${count} report${count === 1 ? '' : 's'}` : 'No reports yet'].filter(Boolean).join(', ')}
              </span>
            </span>
            {isActive && <Check className="w-4 h-4 text-emerald-400 shrink-0" />}
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
      className="ms-tap w-full flex items-center justify-center gap-2 h-10 rounded-xl text-xs font-medium text-ink-soft hover:text-white bg-white/[0.03] hover:bg-white/[0.06] border border-white/[0.07] transition"
    >
      <Plus className="w-3.5 h-3.5" /> {t('workbench.manage_dependents', 'Manage / Add Dependents')}
    </button>
  );

  return (
    <div className="relative min-w-0" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-label="Select patient context"
        data-testid="patient-switcher-trigger"
        aria-haspopup="dialog"
        aria-expanded={open}
        className={cn(
          'ms-tap min-w-0 max-w-[220px] flex items-center gap-2 rounded-full pl-1 pr-2.5 h-9 border transition',
          'bg-white/[0.03] border-white/[0.08] hover:bg-white/[0.06] hover:border-white/[0.14]',
          !selfSelected && 'border-violet-400/30 bg-violet-500/[0.06]'
        )}
      >
        <PatientAvatar name={active?.name} index={activeIdx} size="sm" />
        {!compact && <span className="truncate text-xs font-medium text-ink">{active?.name}</span>}
        {!compact && <span className="hidden sm:inline text-xs text-ink-faint shrink-0">{active?.relationship}</span>}
        <ChevronDown className={cn('w-3.5 h-3.5 text-ink-mute shrink-0 transition-transform', open && 'rotate-180')} />
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
              className="absolute left-0 top-full mt-2 w-80 rounded-2xl ms-glass z-50 overflow-hidden"
            >
              <div className="px-3.5 pt-3 pb-1 text-xs font-semibold text-ink-mute">Clinical analysis lens</div>
              {list}
              <div className="p-2 border-t border-white/[0.06]">{manage}</div>
            </motion.div>
          )}
        </AnimatePresence>
      )}
    </div>
  );
}
