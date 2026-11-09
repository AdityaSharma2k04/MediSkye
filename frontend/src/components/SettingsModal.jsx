import React, { useEffect, useRef, useState } from 'react';
import {
  X,
  Palette,
  Shield,
  Database,
  Info,
  Download,
  Trash2,
  UserX,
  Lock,
  Eye,
  EyeOff,
  ExternalLink,
  Brain,
  Volume2,
} from 'lucide-react';
import ConfirmModal from './ConfirmModal';
import useFocusTrap from '../hooks/useFocusTrap';
import {
  getProfile,
  updateProfile,
  updateMemoryConsent,
  getMemoryFacts,
  deleteMemoryFact,
  clearAllMemoryFacts,
  exportUserAccountData,
} from '../services/api';
import {
  updatePassword,
  EmailAuthProvider,
  reauthenticateWithCredential,
  GoogleAuthProvider,
  reauthenticateWithPopup,
} from 'firebase/auth';
import { Link, useInRouterContext } from 'react-router-dom';
import { auth, getFirebaseErrorMessage } from '../services/firebase';
import { logger } from '../services/logger';
import { useTranslation } from 'react-i18next';

function SafeLink({ to, onClick, children, className, ...props }) {
  const inRouter = useInRouterContext();
  if (inRouter) {
    return (
      <Link to={to} onClick={onClick} className={className} {...props}>
        {children}
      </Link>
    );
  }
  return (
    <a href={to} onClick={onClick} className={className} {...props}>
      {children}
    </a>
  );
}

function getCategoryBadgeStyle(type = '') {
  const t = (type || '').toLowerCase();
  switch (t) {
    case 'condition':
      return 'bg-rose-500/10 text-rose-400 border-rose-500/20';
    case 'medication':
      return 'bg-blue-500/10 text-blue-400 border-blue-500/20';
    case 'weight':
      return 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20';
    case 'sport_hobby':
    case 'lifestyle':
      return 'bg-purple-500/10 text-purple-400 border-purple-500/20';
    case 'allergy':
      return 'bg-amber-500/10 text-amber-400 border-amber-500/20';
    case 'measurement':
      return 'bg-cyan-500/10 text-cyan-400 border-cyan-500/20';
    default:
      return 'bg-zinc-500/10 text-ink-mute border-zinc-500/20';
  }
}

const APP_VERSION = '2.0.0';

const DISCLAIMER_TEXT =
  'MediSkye AI provides educational information only. It is not a substitute for professional medical advice, diagnosis, or treatment. Always consult a qualified healthcare provider with questions about a medical condition. In an emergency, call your local emergency number immediately.';

const BLOOD_TYPES = ['Unknown', 'A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-'];
const BIO_SEXES = ['Prefer not to say', 'Male', 'Female', 'Other'];
const UI_LANGUAGES = [
  { code: 'en', label: 'English' },
  { code: 'hi', label: 'Hindi' },
];
const AI_LANGUAGES = [
  { code: 'English', label: 'English' },
  { code: 'Hindi', label: 'Hindi' },
  { code: 'Spanish', label: 'Spanish' },
  { code: 'French', label: 'French' },
  { code: 'German', label: 'German' },
];
const LANGUAGES = AI_LANGUAGES;

function Section({ title, icon: Icon, children, darkMode }) {
  return (
    <div>
      <div className={`flex items-center gap-2 mb-3 pb-2 border-b ${darkMode ? 'border-white/[0.07]' : 'border-zinc-100'}`}>
        <Icon className={`w-4 h-4 ${darkMode ? 'text-ink-mute' : 'text-ink-faint'}`} />
        <h4 className={`text-xs font-semibold ${darkMode ? 'text-ink-mute' : 'text-ink-faint'}`}>
          {title}
        </h4>
      </div>
      <div className="space-y-3">{children}</div>
    </div>
  );
}

function Field({ label, children, darkMode }) {
  return (
    <div>
      <label className={`block text-[11px] font-medium mb-1 ${darkMode ? 'text-ink-mute' : 'text-ink-faint'}`}>
        {label}
      </label>
      {children}
    </div>
  );
}

const inputClass = (darkMode) =>
  `w-full px-3 py-2 text-xs rounded-xl border transition-colors focus:outline-none ${
    darkMode
      ? 'bg-obsidian border-white/[0.12] text-white placeholder:text-ink-faint focus:border-zinc-500'
      : 'bg-zinc-50 border-zinc-200 text-zinc-900 placeholder-zinc-400 focus:border-zinc-400'
  }`;

const selectClass = (darkMode) =>
  `w-full px-3 py-2 text-xs rounded-xl border transition-colors focus:outline-none cursor-pointer ${
    darkMode
      ? 'bg-obsidian border-white/[0.12] text-white focus:border-zinc-500'
      : 'bg-zinc-50 border-zinc-200 text-zinc-900 focus:border-zinc-400'
  }`;

function ChangePasswordModal({ isOpen, onClose, darkMode, isGoogleOnly = false }) {
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showCurrent, setShowCurrent] = useState(false);
  const [showNext, setShowNext] = useState(false);
  const [loading, setLoading] = useState(false);
  const [pwdError, setPwdError] = useState(null);

  useEffect(() => {
    if (!isOpen) {
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
      setLoading(false);
      setPwdError(null);
    }
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen) return;
    const handle = (e) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handle);
    return () => document.removeEventListener('keydown', handle);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const canSave = isGoogleOnly
    ? newPassword.length >= 8 && newPassword === confirmPassword
    : currentPassword && newPassword.length >= 8 && newPassword === confirmPassword;

  const handleSave = async () => {
    if (!canSave || loading) return;
    if (!auth?.currentUser) {
      console.error('Password operation failed: No authenticated user found');
      setPwdError('No authenticated user found');
      return;
    }
    setLoading(true);
    setPwdError(null);
    try {
      if (isGoogleOnly) {
        try {
          await updatePassword(auth.currentUser, newPassword);
          onClose();
        } catch (err) {
          if (err?.code === 'auth/requires-recent-login') {
            try {
              const provider = new GoogleAuthProvider();
              provider.setCustomParameters({ prompt: 'select_account' });
              await reauthenticateWithPopup(auth.currentUser, provider);
              await updatePassword(auth.currentUser, newPassword);
              onClose();
              return;
            } catch (reauthErr) {
              const errorMsg = getFirebaseErrorMessage(reauthErr);
              setPwdError(errorMsg || reauthErr.message || 'Re-authentication failed');
              return;
            }
          }
          const errorMsg = getFirebaseErrorMessage(err);
          setPwdError(errorMsg || err.message || 'Failed to set password');
        }
      } else {
        const credential = EmailAuthProvider.credential(auth.currentUser.email, currentPassword);
        await reauthenticateWithCredential(auth.currentUser, credential);
        await updatePassword(auth.currentUser, newPassword);
        onClose();
      }
    } catch (err) {
      const errorMsg = getFirebaseErrorMessage(err);
      console.error('Password change failed:', err);
      setPwdError(errorMsg || err.message || 'Password change failed');
    } finally {
      setLoading(false);
    }
  };

  const modalTitle = isGoogleOnly ? 'Set Password' : 'Change Password';

  return (
    <div
      className="fixed inset-0 z-[70] flex items-end sm:items-center justify-center p-0 sm:p-4 bg-black/60 backdrop-blur-sm animate-backdrop-in"
      onMouseDown={onClose}
    >
      <div
        className={`relative rounded-t-[28px] sm:rounded-2xl shadow-float w-full sm:max-w-sm border ms-sheet-mobile sm:animate-modal-in pb-[env(safe-area-inset-bottom)] sm:pb-0 ${darkMode ? 'bg-graphite border-white/[0.07]' : 'bg-white border-zinc-200'}`}
        onMouseDown={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label={modalTitle}
      >
        <div className={`flex items-center justify-between px-5 py-4 border-b ${darkMode ? 'border-white/[0.07]' : 'border-zinc-100'}`}>
          <h3 className={`font-semibold text-sm flex items-center gap-2 ${darkMode ? 'text-ink' : 'text-zinc-900'}`}>
            <Lock className="w-4 h-4" /> {modalTitle}
          </h3>
          <button onClick={onClose} aria-label="Close" className={`p-1 rounded-lg ${darkMode ? 'text-ink-faint hover:text-ink hover:bg-slate2' : 'text-ink-mute hover:text-zinc-700 hover:bg-zinc-100'}`}>
            <X className="w-4 h-4" />
          </button>
        </div>
        <div className="px-5 py-4 space-y-3">
          {pwdError && (
            <div role="alert" className="text-xs text-red-300 bg-red-500/10 border border-red-500/30 rounded-xl px-3 py-2">
              {pwdError}
            </div>
          )}
          {isGoogleOnly ? (
            <p className={`text-xs leading-relaxed p-3 rounded-xl border ${darkMode ? 'bg-slate2/60 border-white/[0.12] text-ink-soft' : 'bg-zinc-100 border-zinc-200 text-zinc-600'}`}>
              Set a password for your account so you can also sign in with your email and password.
            </p>
          ) : (
            <Field label="Current password" darkMode={darkMode}>
              <div className="relative">
                <input
                  type={showCurrent ? 'text' : 'password'}
                  value={currentPassword}
                  onChange={(e) => setCurrentPassword(e.target.value)}
                  aria-label="Current password"
                  className={inputClass(darkMode) + ' pr-9'}
                />
                <button type="button" onClick={() => setShowCurrent(!showCurrent)} aria-label="Toggle password visibility" className={`absolute right-2.5 top-2 ${darkMode ? 'text-ink-faint hover:text-ink-soft' : 'text-ink-mute hover:text-zinc-600'}`}>
                  {showCurrent ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                </button>
              </div>
            </Field>
          )}

          <Field label="New password (min 8 characters)" darkMode={darkMode}>
            <div className="relative">
              <input
                type={showNext ? 'text' : 'password'}
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                aria-label="New password"
                className={inputClass(darkMode) + ' pr-9'}
              />
              <button type="button" onClick={() => setShowNext(!showNext)} aria-label="Toggle password visibility" className={`absolute right-2.5 top-2 ${darkMode ? 'text-ink-faint hover:text-ink-soft' : 'text-ink-mute hover:text-zinc-600'}`}>
                {showNext ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
              </button>
            </div>
          </Field>
          <Field label="Confirm new password" darkMode={darkMode}>
            <input
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              aria-label="Confirm new password"
              className={inputClass(darkMode)}
            />
            {confirmPassword && newPassword !== confirmPassword && (
              <p className="text-[10px] text-red-400 mt-1">Passwords do not match</p>
            )}
          </Field>
        </div>
        <div className={`px-5 py-3 flex justify-end gap-2 border-t ${darkMode ? 'border-white/[0.07] bg-obsidian' : 'border-zinc-100 bg-zinc-50'}`}>
          <button onClick={onClose} className={`px-4 py-2 text-xs rounded-xl border ${darkMode ? 'border-white/[0.12] text-ink-soft hover:bg-slate2' : 'border-zinc-200 text-zinc-600 hover:bg-zinc-100'}`}>Cancel</button>
          <button
            disabled={!canSave || loading}
            onClick={handleSave}
            className={`px-4 py-2 text-xs font-medium rounded-xl text-white transition-colors ${canSave && !loading ? 'bg-graphite hover:bg-slate2 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-200' : 'bg-zinc-500 opacity-50 cursor-not-allowed'}`}
          >
            {loading ? (isGoogleOnly ? 'Setting...' : 'Saving...') : (isGoogleOnly ? 'Set password' : 'Save')}
          </button>
        </div>
      </div>
    </div>
  );
}

function DisclaimerModal({ isOpen, onClose, darkMode }) {
  useEffect(() => {
    if (!isOpen) return;
    const handle = (e) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('keydown', handle);
    return () => document.removeEventListener('keydown', handle);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-[70] flex items-end sm:items-center justify-center p-0 sm:p-4 bg-black/60 backdrop-blur-sm animate-backdrop-in"
      onMouseDown={onClose}
    >
      <div
        className={`relative rounded-t-[28px] sm:rounded-2xl shadow-float w-full sm:max-w-sm border ms-sheet-mobile sm:animate-modal-in pb-[env(safe-area-inset-bottom)] sm:pb-0 ${darkMode ? 'bg-graphite border-white/[0.07]' : 'bg-white border-zinc-200'}`}
        onMouseDown={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label="Medical disclaimer"
      >
        <div className={`flex items-center justify-between px-5 py-4 border-b ${darkMode ? 'border-white/[0.07]' : 'border-zinc-100'}`}>
          <h3 className={`font-semibold text-sm ${darkMode ? 'text-ink' : 'text-zinc-900'}`}>Medical Disclaimer</h3>
          <button onClick={onClose} aria-label="Close" className={`p-1 rounded-lg ${darkMode ? 'text-ink-faint hover:text-ink hover:bg-slate2' : 'text-ink-mute hover:text-zinc-700 hover:bg-zinc-100'}`}>
            <X className="w-4 h-4" />
          </button>
        </div>
        <div className="px-5 py-5">
          <p className={`text-sm leading-relaxed ${darkMode ? 'text-ink-soft' : 'text-zinc-600'}`}>{DISCLAIMER_TEXT}</p>
        </div>
        <div className={`px-5 py-3 flex justify-end border-t ${darkMode ? 'border-white/[0.07] bg-obsidian' : 'border-zinc-100 bg-zinc-50'}`}>
          <button onClick={onClose} className={`px-4 py-2 text-xs font-medium rounded-xl ${darkMode ? 'bg-slate2 text-ink hover:bg-zinc-700' : 'bg-graphite text-white hover:bg-slate2'}`}>Close</button>
        </div>
      </div>
    </div>
  );
}

export default function SettingsModal({
  isOpen,
  onClose,
  darkMode,
  setDarkMode,
  themePreference,
  setThemePreference,
  onClearAllChats,
  onDeleteAccount,
  language,
  setLanguage,
  currentUser,
  onProfileUpdated,
  autoRead = false,
  setAutoRead,
  onOpenProfile,
  selectedPatientId = 'self',
}) {
  const { t, i18n } = useTranslation();
  const [showPassword, setShowPassword] = useState(false);
  const [showDisclaimer, setShowDisclaimer] = useState(false);
  const [showClearConfirm, setShowClearConfirm] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [showClearMemoryConfirm, setShowClearMemoryConfirm] = useState(false);
  const [showUnsavedConfirm, setShowUnsavedConfirm] = useState(false);
  const [saveError, setSaveError] = useState(null);

  // Check if current user signed in with Google and whether they already have a password
  const providerData = auth?.currentUser?.providerData || [];
  const hasGoogleProvider = Boolean(
    providerData.some((p) => p?.providerId === 'google.com' || p?.providerId === 'google') ||
    currentUser?.provider === 'google' ||
    currentUser?.provider === 'google.com' ||
    currentUser?.auth_provider === 'google' ||
    currentUser?.auth_provider === 'google.com' ||
    currentUser?.isGoogleUser ||
    (() => {
      try {
        const token = typeof window !== 'undefined' ? localStorage.getItem('token') : null;
        if (token) {
          const base64Url = token.split('.')[1];
          if (base64Url) {
            const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
            const payload = JSON.parse(atob(base64));
            return payload?.firebase?.sign_in_provider === 'google.com';
          }
        }
      } catch (e) {}
      return false;
    })()
  );
  const hasPasswordProvider = Boolean(
    providerData.some((p) => p?.providerId === 'password')
  );
  const isGoogleOnly = hasGoogleProvider && !hasPasswordProvider;

  // Patient Memory State
  const [memoryConsent, setMemoryConsent] = useState(currentUser?.memory_consent_granted ?? false);
  const [loadingMemory, setLoadingMemory] = useState(false);
  const [memoryFacts, setMemoryFacts] = useState([]);
  const [deletingFactId, setDeletingFactId] = useState(null);

  // Keep the latest callback in a ref so the load effect can call it without
  // being listed as a dependency (the parent passes a fresh inline function
  // each render, which would otherwise re-run the effect forever).
  const onProfileUpdatedRef = useRef(onProfileUpdated);
  useEffect(() => {
    onProfileUpdatedRef.current = onProfileUpdated;
  }, [onProfileUpdated]);

  // Initial and draft state for unsaved changes detection
  const [initialState, setInitialState] = useState(() => ({
    aiLanguage: language || 'English',
    uiLanguage: i18n.language?.startsWith('hi') ? 'hi' : 'en',
    autoRead: autoRead ?? false,
  }));
  const [draftState, setDraftState] = useState(() => ({
    aiLanguage: language || 'English',
    uiLanguage: i18n.language?.startsWith('hi') ? 'hi' : 'en',
    autoRead: autoRead ?? false,
  }));
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (isOpen) {
      const state = {
        aiLanguage: language || 'English',
        uiLanguage: i18n.language?.startsWith('hi') ? 'hi' : 'en',
        autoRead: autoRead ?? false,
      };
      setInitialState(state);
      setDraftState(state);
      setSaving(false);
      setShowUnsavedConfirm(false);
    }
  }, [isOpen, language, i18n.language, autoRead]);

  useEffect(() => {
    if (currentUser && typeof currentUser.memory_consent_granted === 'boolean') {
      setMemoryConsent(currentUser.memory_consent_granted);
    }
  }, [currentUser]);

  useEffect(() => {
    if (!isOpen) return;
    let isMounted = true;
    async function loadSettingsData() {
      try {
        if (isMounted) setLoadingMemory(true);
        const profilePromise = typeof getProfile === 'function' ? Promise.resolve(getProfile()).catch(() => null) : Promise.resolve(null);
        const factsPromise = typeof getMemoryFacts === 'function' ? Promise.resolve(getMemoryFacts(selectedPatientId)).catch(() => []) : Promise.resolve([]);
        const [profile, facts] = await Promise.all([profilePromise, factsPromise]);
        if (!isMounted) return;
        if (profile) {
          if (typeof profile.memory_consent_granted === 'boolean') {
            setMemoryConsent(profile.memory_consent_granted);
          }
          if (onProfileUpdatedRef.current) {
            onProfileUpdatedRef.current(profile);
          }
        }
        if (Array.isArray(facts)) {
          setMemoryFacts(facts);
        }
      } catch (err) {
        logger.error('Error fetching settings data:', err);
      } finally {
        if (isMounted) {
          setLoadingMemory(false);
        }
      }
    }
    loadSettingsData();
    return () => {
      isMounted = false;
    };
  }, [isOpen, selectedPatientId]);

  const handleToggleMemoryConsent = async () => {
    const nextVal = !memoryConsent;
    setMemoryConsent(nextVal);
    try {
      try {
        await updateMemoryConsent(nextVal);
      } catch (consentErr) {
        await updateProfile({ memory_consent_granted: nextVal });
      }
      if (onProfileUpdated) {
        onProfileUpdated({ ...currentUser, memory_consent_granted: nextVal });
      }
    } catch (err) {
      setMemoryConsent(!nextVal);
      console.error('Memory consent update failed:', err);
      setSaveError(err.message || 'Update Failed');
    }
  };

  const handleDeleteFact = async (factId) => {
    setDeletingFactId(factId);
    try {
      await deleteMemoryFact(factId);
      setMemoryFacts((prev) => prev.filter((f) => f.id !== factId));
    } catch (err) {
      console.error('Delete Failed:', err);
      setSaveError(err.message || 'Delete Failed');
    } finally {
      setDeletingFactId(null);
    }
  };

  const handleClearAllFacts = async () => {
    try {
      await clearAllMemoryFacts(selectedPatientId);
      setMemoryFacts([]);
      setShowClearMemoryConfirm(false);
    } catch (err) {
      console.error('Clear Failed:', err);
      setSaveError(err.message || 'Clear Failed');
    }
  };

  const modalRef = useRef(null);
  const closeRef = useRef(null);

  const handleUiLanguageChange = (value) => {
    i18n.changeLanguage(value);
    try {
      localStorage.setItem('mediskye_ui_lang', value);
    } catch (e) {}
  };

  // Close attempt handler guarding unsaved changes
  const handleAttemptClose = () => {
    if (JSON.stringify(initialState) !== JSON.stringify(draftState)) {
      setShowUnsavedConfirm(true);
    } else {
      onClose();
    }
  };

  const handleDiscardChanges = () => {
    setDraftState(initialState);
    setShowUnsavedConfirm(false);
    onClose();
  };

  // Manual save handler for preferences (Task 1 & Bug 5)
  const handleSaveChanges = async () => {
    setSaving(true);
    setSaveError(null);
    try {
      const initialAiLang = language || 'English';
      let updatedUser = null;
      if (draftState.aiLanguage !== initialAiLang) {
        updatedUser = await updateProfile({ language_preference: draftState.aiLanguage });
        if (setLanguage) setLanguage(draftState.aiLanguage);
        if (onProfileUpdated && updatedUser) onProfileUpdated(updatedUser);
      }

      const activeUiLang = i18n.language?.startsWith('hi') ? 'hi' : 'en';
      if (draftState.uiLanguage !== activeUiLang) {
        handleUiLanguageChange(draftState.uiLanguage);
      }

      if (draftState.autoRead !== autoRead) {
        if (setAutoRead) setAutoRead(draftState.autoRead);
      }

      setInitialState(draftState);
      onClose();
    } catch (err) {
      console.error('Update Failed:', err);
      setSaveError(err.message || 'Could not save settings.');
    } finally {
      setSaving(false);
    }
  };

  const [isExporting, setIsExporting] = useState(false);
  const handleExportData = async () => {
    try {
      setIsExporting(true);
      const data = await exportUserAccountData();
      const jsonStr = JSON.stringify(data, null, 2);
      const blob = new Blob([jsonStr], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      const today = new Date().toISOString().slice(0, 10);
      a.href = url;
      a.download = `MediSkye-Account-Export-${today}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      logger.error('Failed to export user account data:', err);
      alert(err.message || 'Failed to export account data. Please try again.');
    } finally {
      setIsExporting(false);
    }
  };

  useFocusTrap(modalRef, isOpen && !showUnsavedConfirm, handleAttemptClose);

  if (!isOpen) return null;

  const base = darkMode
    ? 'bg-carbon border-white/[0.08] text-slate-100'
    : 'bg-white border-zinc-200 text-zinc-900';

  return (
    <>
      {/* Main Settings Modal */}
      <div
        className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-0 sm:p-4 bg-black/60 backdrop-blur-sm animate-backdrop-in"
        onMouseDown={handleAttemptClose}
        role="dialog"
        aria-modal="true"
        aria-label="Settings"
      >
        <div
          ref={modalRef}
          className={`${base} rounded-t-[28px] sm:rounded-3xl shadow-float border w-full sm:max-w-lg max-h-[94dvh] sm:max-h-[88dvh] flex flex-col overflow-hidden ms-sheet-mobile sm:animate-modal-in`}
          onMouseDown={(e) => e.stopPropagation()}
        >
          {/* Header */}
          <div className={`flex items-center justify-between px-5 py-4 border-b shrink-0 ${darkMode ? 'border-white/[0.07]' : 'border-zinc-100'}`}>
            <h3 className="ms-display text-lg text-white">Settings &amp; Preferences</h3>
            <button
              ref={closeRef}
              onClick={handleAttemptClose}
              aria-label="Close settings"
              className={`p-1.5 rounded-lg transition-colors ${darkMode ? 'text-ink-mute hover:text-ink hover:bg-slate2' : 'text-ink-mute hover:text-zinc-700 hover:bg-zinc-100'}`}
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          {/* Scrollable body */}
          <div className="flex-1 overflow-y-auto px-5 py-5 space-y-7 text-sm">
            {saveError && (
              <div role="alert" className="text-xs text-red-300 bg-red-500/10 border border-red-500/30 rounded-xl px-3.5 py-2.5">
                {saveError}
              </div>
            )}

            {/* Quick link to Profile & Caregiver Hub (Bug 11) */}
            <div className={`p-4 rounded-xl border flex flex-col sm:flex-row sm:items-center justify-between gap-4 ${
              darkMode ? 'bg-graphite border-white/[0.08]' : 'bg-zinc-50 border-zinc-200'
            }`}>
              <div className="space-y-0.5">
                <div className={`text-xs font-semibold ${darkMode ? 'text-ink' : 'text-zinc-800'}`}>
                  Health Profile &amp; Caregivers
                </div>
                <p className={`text-[11px] leading-relaxed ${darkMode ? 'text-ink-mute' : 'text-ink-faint'}`}>
                  Manage clinical vitals, allergies, conditions, and family dependent profiles.
                </p>
              </div>
              <button
                type="button"
                onClick={() => {
                  onClose();
                  if (onOpenProfile) onOpenProfile();
                }}
                className={`px-3.5 py-2 text-xs font-medium rounded-xl border whitespace-nowrap transition-colors flex items-center gap-1.5 ${
                  darkMode
                    ? 'bg-graphite border-white/[0.12] text-ink hover:bg-slate2 hover:text-white'
                    : 'bg-white border-zinc-300 text-zinc-700 hover:bg-zinc-100 hover:text-zinc-900'
                }`}
              >
                <span>Manage Health Profile &amp; Caregivers</span>
                <span>→</span>
              </button>
            </div>

            {/* ── PREFERENCES ── */}
            <Section title={t('settings.preferences', 'Preferences')} icon={Palette} darkMode={darkMode}>
              <Field label={t('settings.ui_language', 'App Interface Language')} darkMode={darkMode}>
                <select
                  aria-label="App Interface Language"
                  value={draftState.uiLanguage}
                  onChange={(e) => setDraftState((prev) => ({ ...prev, uiLanguage: e.target.value }))}
                  className={selectClass(darkMode)}
                >
                  {UI_LANGUAGES.map((l) => <option key={l.code} value={l.code}>{l.label}</option>)}
                </select>
              </Field>
              <Field label={t('settings.ai_language', 'AI Response Language')} darkMode={darkMode}>
                <select
                  aria-label="AI Response Language"
                  value={draftState.aiLanguage || 'English'}
                  onChange={(e) => setDraftState((prev) => ({ ...prev, aiLanguage: e.target.value }))}
                  className={selectClass(darkMode)}
                >
                  {AI_LANGUAGES.map((l) => <option key={l.code} value={l.code}>{l.label}</option>)}
                </select>
              </Field>

              {/* Auto-read AI responses aloud */}
              <div className={`p-3.5 rounded-xl border flex items-center justify-between gap-3 ${
                darkMode ? 'bg-obsidian border-white/[0.07]' : 'bg-zinc-50 border-zinc-200'
              }`}>
                <div className="space-y-0.5 pr-2">
                  <div className="flex items-center gap-2">
                    <Volume2 className={`w-3.5 h-3.5 ${draftState.autoRead ? 'text-emerald-400' : darkMode ? 'text-ink-faint' : 'text-ink-mute'}`} />
                    <span className={`text-xs font-semibold ${darkMode ? 'text-ink' : 'text-zinc-800'}`}>
                      {t('settings.auto_read', 'Auto-read AI responses aloud')}
                    </span>
                    <span className={`text-[10px] px-1.5 py-0.2 rounded-full font-medium border ${
                      draftState.autoRead
                        ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                        : 'bg-zinc-500/10 text-ink-mute border-zinc-500/20'
                    }`}>
                      {draftState.autoRead ? t('settings.on', 'On') : t('settings.off', 'Off')}
                    </span>
                  </div>
                  <p className={`text-[11px] leading-relaxed ${darkMode ? 'text-ink-mute' : 'text-ink-faint'}`}>
                    {t('settings.auto_read_desc', 'Speaks each completed answer in the selected AI language. Any new question or Stop immediately silences the reading.')}
                  </p>
                </div>
                <button
                  type="button"
                  role="switch"
                  aria-checked={draftState.autoRead}
                  aria-label="Auto-read AI responses aloud"
                  onClick={() => setDraftState((prev) => ({ ...prev, autoRead: !prev.autoRead }))}
                  className={`relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none ${
                    draftState.autoRead ? 'bg-emerald-500' : darkMode ? 'bg-zinc-700' : 'bg-zinc-300'
                  }`}
                >
                  <span
                    className={`pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow-lg ring-0 transition duration-200 ease-in-out ${
                      draftState.autoRead ? 'translate-x-4' : 'translate-x-0'
                    }`}
                  />
                </button>
              </div>
            </Section>

            {/* ── PATIENT MEMORY ── */}
            <Section title="Patient Memory" icon={Brain} darkMode={darkMode}>
              <div className="space-y-3">
                {/* Consent Toggle Switch */}
                <div className={`p-3.5 rounded-xl border flex items-center justify-between gap-3 ${
                  darkMode ? 'bg-obsidian border-white/[0.07]' : 'bg-zinc-50 border-zinc-200'
                }`}>
                  <div className="space-y-0.5 pr-2">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-semibold">Cross-Session Memory</span>
                      <span className={`text-[10px] px-1.5 py-0.2 rounded-full font-medium border ${
                        memoryConsent
                          ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                          : 'bg-zinc-500/10 text-ink-mute border-zinc-500/20'
                      }`}>
                        {memoryConsent ? 'Active' : 'Disabled'}
                      </span>
                    </div>
                    <p className={`text-[11px] leading-relaxed ${darkMode ? 'text-ink-mute' : 'text-ink-faint'}`}>
                      Allow MediSkye to remember clinical facts across sessions (conditions, medications, lab trends, lifestyle).
                    </p>
                  </div>
                  <button
                    type="button"
                    role="switch"
                    aria-checked={memoryConsent}
                    aria-label="Cross-Session Memory"
                    onClick={handleToggleMemoryConsent}
                    className={`relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none ${
                      memoryConsent ? 'bg-emerald-500' : darkMode ? 'bg-zinc-700' : 'bg-zinc-300'
                    }`}
                  >
                    <span
                      className={`pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow-lg ring-0 transition duration-200 ease-in-out ${
                        memoryConsent ? 'translate-x-4' : 'translate-x-0'
                      }`}
                    />
                  </button>
                </div>

                {/* Facts Browser */}
                <div className={`p-3.5 rounded-xl border ${
                  darkMode ? 'bg-obsidian border-white/[0.07]' : 'bg-zinc-50 border-zinc-200'
                }`}>
                  <div className="flex items-center justify-between mb-1.5">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-medium">Remembered Facts</span>
                      <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${
                        darkMode ? 'bg-slate2 text-ink-soft' : 'bg-zinc-200 text-zinc-700'
                      }`}>
                        {memoryFacts.length}
                      </span>
                    </div>
                    {memoryFacts.length > 0 && (
                      <button
                        type="button"
                        onClick={() => setShowClearMemoryConfirm(true)}
                        className="text-[11px] text-red-400 hover:text-red-300 transition-colors"
                      >
                        Clear memory
                      </button>
                    )}
                  </div>
                  <p className={`text-[11px] leading-tight mb-2.5 italic ${darkMode ? 'text-ink-faint' : 'text-ink-mute'}`}>
                    Changes to the toggle or trash icons take effect immediately.
                  </p>

                  {loadingMemory ? (
                    <div className="py-4 text-center text-xs text-ink-faint">Loading remembered facts...</div>
                  ) : memoryFacts.length === 0 ? (
                    <p className={`text-[11px] py-1 leading-relaxed ${darkMode ? 'text-ink-faint' : 'text-ink-mute'}`}>
                      {memoryConsent
                        ? 'No clinical facts remembered yet. As you consult with MediSkye or upload reports, key findings will appear here.'
                        : 'Memory is currently disabled. Enable memory above to allow MediSkye to remember clinical context across chats.'}
                    </p>
                  ) : (
                    <div className="space-y-2">
                      {memoryFacts.map((fact) => {
                        const catStyle = getCategoryBadgeStyle(fact.fact_type || fact.category);
                        const dateFormatted = fact.created_at
                          ? new Date(fact.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
                          : null;
                        return (
                          <div
                            key={fact.id}
                            className={`p-2.5 rounded-lg border text-xs flex items-start justify-between gap-2.5 ${
                              darkMode ? 'bg-graphite border-white/[0.07]' : 'bg-white border-zinc-200'
                            }`}
                          >
                            <div className="space-y-1 flex-1 min-w-0">
                              <div className="flex items-center gap-1.5 flex-wrap">
                                <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded border ${catStyle}`}>
                                  {fact.fact_type || fact.category}
                                </span>
                                {fact.source_type && (
                                  <span className="text-[10px] text-ink-faint">
                                    • {fact.source_type.replace('_', ' ')}
                                  </span>
                                )}
                                {dateFormatted && (
                                  <span className={`text-[10px] px-1.5 py-0.5 rounded font-mono ${
                                    darkMode ? 'bg-slate2/80 text-ink-mute border border-white/[0.12]' : 'bg-zinc-100 text-ink-faint border border-zinc-200'
                                  }`}>
                                    {dateFormatted}
                                  </span>
                                )}
                              </div>
                              <p className={`text-xs font-medium break-words ${darkMode ? 'text-ink' : 'text-zinc-800'}`}>
                                {fact.fact_text || fact.fact_value}
                              </p>
                            </div>
                            <button
                              type="button"
                              disabled={deletingFactId === fact.id}
                              onClick={() => handleDeleteFact(fact.id)}
                              className={`p-1 rounded-md text-ink-mute hover:text-red-400 transition-colors shrink-0 ${
                                darkMode ? 'hover:bg-slate2' : 'hover:bg-zinc-100'
                              }`}
                              title="Delete fact"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              </div>
            </Section>



            {/* ── SECURITY ── */}
            <Section title="Security" icon={Lock} darkMode={darkMode}>
              <div className="flex flex-col gap-2">
                <button
                  type="button"
                  onClick={() => setShowPassword(true)}
                  aria-label={isGoogleOnly ? "Set password" : "Change password"}
                  className={`w-full flex items-center justify-between px-3 py-2.5 rounded-xl border text-xs transition-colors ${
                    darkMode
                      ? 'border-white/[0.12] text-ink-soft hover:bg-slate2'
                      : 'border-zinc-200 text-zinc-700 hover:bg-zinc-50'
                  }`}
                >
                  <span className="flex items-center gap-2">
                    <Lock className="w-3.5 h-3.5" />
                    {isGoogleOnly ? "Set password" : "Change password"}
                  </span>
                  <span className={`text-[10px] ${darkMode ? 'text-ink-faint' : 'text-ink-mute'}`}>→</span>
                </button>
                {isGoogleOnly && (
                  <p className={`text-[11px] leading-relaxed px-0.5 ${darkMode ? 'text-ink-mute' : 'text-ink-faint'}`}>
                    You signed in with Google. You can set a password to enable email &amp; password sign-in.
                  </p>
                )}
              </div>
            </Section>

            {/* ── DATA & PRIVACY ── */}
            <Section title="Data & Privacy" icon={Database} darkMode={darkMode}>
              <div className="flex flex-col gap-3">
                <button
                  type="button"
                  onClick={handleExportData}
                  disabled={isExporting}
                  className={`w-full flex items-center justify-between px-3 py-2.5 rounded-xl border text-xs font-medium transition-colors ${
                    darkMode
                      ? 'border-white/[0.12] bg-slate2/60 text-ink hover:bg-slate2 hover:border-cyan-500/40'
                      : 'border-zinc-200 bg-zinc-50 text-zinc-800 hover:bg-zinc-100 hover:border-cyan-500/40'
                  }`}
                >
                  <span className="flex items-center gap-2">
                    <Download className="w-3.5 h-3.5 text-cyan-400" />
                    {isExporting ? 'Exporting...' : 'Export my data'}
                  </span>
                  <span className={`text-[10px] px-2 py-0.5 rounded-md font-mono ${darkMode ? 'bg-slate2 text-ink-mute' : 'bg-zinc-200 text-zinc-600'}`}>
                    JSON
                  </span>
                </button>

                {/* Secondary Warning Action: Clear Conversations */}
                <div className="pt-0.5">
                  <button
                    type="button"
                    onClick={() => setShowClearConfirm(true)}
                    className={`w-full flex items-center gap-2 px-3 py-2.5 rounded-xl border text-xs transition-colors ${
                      darkMode
                        ? 'border-amber-500/30 text-amber-400 hover:bg-amber-500/10'
                        : 'border-amber-500/40 text-amber-600 hover:bg-amber-50'
                    }`}
                  >
                    <Trash2 className="w-3.5 h-3.5 text-amber-400" />
                    Clear all conversations
                  </button>
                </div>

                {/* Dedicated Destructive Danger Zone Card */}
                <div className={`mt-1 p-3 rounded-xl border ${
                  darkMode ? 'border-red-500/30 bg-red-950/20' : 'border-red-200 bg-red-50/60'
                }`}>
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="text-[11px] font-semibold text-red-400">
                      Danger Zone
                    </span>
                  </div>
                  <p className={`text-[11px] leading-relaxed mb-3 ${darkMode ? 'text-ink-mute' : 'text-zinc-600'}`}>
                    Permanently delete your MediSkye account, medical profiles, uploaded lab documents, and remembered facts.
                  </p>
                  <button
                    type="button"
                    onClick={() => setShowDeleteConfirm(true)}
                    className="w-full flex items-center justify-center gap-2 px-3 py-2.5 rounded-xl text-xs font-medium text-white bg-red-600 hover:bg-red-700 transition-colors shadow-sm"
                  >
                    <UserX className="w-3.5 h-3.5" />
                    Delete account
                  </button>
                </div>
              </div>
            </Section>

            {/* ── ABOUT ── */}
            <Section title="About" icon={Info} darkMode={darkMode}>
              <div className={`flex items-center justify-between text-xs px-3 py-2.5 rounded-xl border ${darkMode ? 'border-white/[0.07] text-ink-mute' : 'border-zinc-100 text-ink-faint'}`}>
                <span>App version</span>
                <span className={`font-mono ${darkMode ? 'text-ink-soft' : 'text-zinc-700'}`}>v{APP_VERSION}</span>
              </div>
              <button
                onClick={() => setShowDisclaimer(true)}
                className={`w-full flex items-center justify-between px-3 py-2.5 rounded-xl border text-xs transition-colors ${darkMode ? 'border-white/[0.07] text-ink-mute hover:text-ink hover:bg-slate2' : 'border-zinc-100 text-ink-faint hover:text-zinc-700 hover:bg-zinc-50'}`}
              >
                <span className="flex items-center gap-2"><Shield className="w-3.5 h-3.5" /> Medical disclaimer</span>
                <Info className="w-3.5 h-3.5 opacity-50" />
              </button>
              <SafeLink
                to="/privacy"
                onClick={onClose}
                className={`w-full flex items-center justify-between px-3 py-2.5 rounded-xl border text-xs transition-colors ${darkMode ? 'border-white/[0.07] text-ink-mute hover:text-ink hover:bg-slate2' : 'border-zinc-100 text-ink-faint hover:text-zinc-700 hover:bg-zinc-50'}`}
              >
                <span className="flex items-center gap-2"><Info className="w-3.5 h-3.5" /> Privacy policy</span>
                <ExternalLink className="w-3 h-3 opacity-50" />
              </SafeLink>
            </Section>
          </div>

          {/* Footer */}
          <div className={`px-5 py-3.5 pb-[max(0.875rem,env(safe-area-inset-bottom))] border-t shrink-0 flex items-center justify-end gap-2 ${darkMode ? 'border-white/[0.07] bg-obsidian/60' : 'border-zinc-100 bg-zinc-50'}`}>
            <button
              type="button"
              onClick={handleAttemptClose}
              className={`px-4 py-2 text-xs font-medium rounded-xl border transition-colors ${
                darkMode ? 'border-white/[0.12] text-ink-soft hover:bg-slate2' : 'border-zinc-200 text-zinc-600 hover:bg-zinc-100'
              }`}
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleSaveChanges}
              disabled={saving}
              className={`px-5 py-2 text-xs font-semibold rounded-xl transition ${
                saving
                  ? 'opacity-60 cursor-not-allowed bg-zinc-500 text-white'
                  : darkMode
                    ? 'bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-semibold'
                    : 'bg-graphite text-white hover:bg-slate2'
              }`}
            >
              {saving ? 'Saving...' : 'Save Changes'}
            </button>
          </div>
        </div>
      </div>

      {/* Sub-modals */}
      <ChangePasswordModal
        isOpen={showPassword}
        onClose={() => setShowPassword(false)}
        darkMode={darkMode}
        isGoogleOnly={isGoogleOnly}
      />

      <DisclaimerModal
        isOpen={showDisclaimer}
        onClose={() => setShowDisclaimer(false)}
        darkMode={darkMode}
      />

      <ConfirmModal
        isOpen={showClearConfirm}
        onClose={() => setShowClearConfirm(false)}
        onConfirm={() => { onClearAllChats && onClearAllChats(); }}
        title="Clear all conversations?"
        body="All chat history, uploaded report references, and patient context will be permanently deleted. This cannot be undone. Your account and profile will remain intact."
        confirmLabel="Delete everything"
        requireTyping="DELETE"
        closeable={false}
        darkMode={darkMode}
      />

      <ConfirmModal
        isOpen={showClearMemoryConfirm}
        onClose={() => setShowClearMemoryConfirm(false)}
        onConfirm={handleClearAllFacts}
        title="Clear remembered health facts?"
        body="This will permanently delete all clinical facts remembered about you across conversations. Chat history will not be deleted, but future questions will not reference past medical history."
        confirmLabel="Clear memory"
        requireTyping="CLEAR"
        closeable={false}
        darkMode={darkMode}
      />

      <ConfirmModal
        isOpen={showDeleteConfirm}
        onClose={() => setShowDeleteConfirm(false)}
        onConfirm={() => { onDeleteAccount && onDeleteAccount(); }}
        title="Delete your account?"
        body="This will permanently delete your account, all conversations, uploaded reports, and dependent profiles. This cannot be undone."
        confirmLabel="Delete my account"
        requireTyping={currentUser?.email || 'confirm'}
        closeable={false}
        darkMode={darkMode}
      />

      <ConfirmModal
        isOpen={showUnsavedConfirm}
        onClose={() => setShowUnsavedConfirm(false)}
        onConfirm={handleDiscardChanges}
        title="Unsaved Changes"
        body="You have unsaved changes. Are you sure you want to discard them?"
        cancelLabel="Keep Editing"
        confirmLabel="Discard Changes"
        closeable={true}
        darkMode={darkMode}
      />
    </>
  );
}
