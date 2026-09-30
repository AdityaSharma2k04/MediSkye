import React, { useEffect, useRef, useState } from 'react';
import {
  X,
  User,
  Palette,
  Shield,
  Database,
  Info,
  Moon,
  Sun,
  Monitor,
  Download,
  Trash2,
  UserX,
  LogOut,
  Lock,
  Eye,
  EyeOff,
  ExternalLink,
} from 'lucide-react';
import ConfirmModal from './ConfirmModal';
import { updateProfile } from '../services/api';


const APP_VERSION = '2.0.0';

const DISCLAIMER_TEXT =
  'MediSkye AI provides educational information only. It is not a substitute for professional medical advice, diagnosis, or treatment. Always consult a qualified healthcare provider with questions about a medical condition. In an emergency, call your local emergency number immediately.';

const BLOOD_TYPES = ['Unknown', 'A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-'];
const BIO_SEXES = ['Prefer not to say', 'Male', 'Female', 'Other'];
const LANGUAGES = [
  { code: 'English', label: 'English (US)' },
  { code: 'Spanish', label: 'Español' },
  { code: 'Hindi', label: 'हिन्दी' },
  { code: 'French', label: 'Français' },
  { code: 'German', label: 'Deutsch' },
];

function Section({ title, icon: Icon, children, darkMode }) {
  return (
    <div>
      <div className={`flex items-center gap-2 mb-3 pb-2 border-b ${darkMode ? 'border-zinc-800' : 'border-zinc-100'}`}>
        <Icon className={`w-4 h-4 ${darkMode ? 'text-zinc-400' : 'text-zinc-500'}`} />
        <h4 className={`text-xs font-semibold uppercase tracking-wider ${darkMode ? 'text-zinc-400' : 'text-zinc-500'}`}>
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
      <label className={`block text-[11px] font-medium mb-1 ${darkMode ? 'text-zinc-400' : 'text-zinc-500'}`}>
        {label}
      </label>
      {children}
    </div>
  );
}

const inputClass = (darkMode) =>
  `w-full px-3 py-2 text-xs rounded-xl border transition-colors focus:outline-none ${
    darkMode
      ? 'bg-zinc-950 border-zinc-700 text-white placeholder-zinc-500 focus:border-zinc-500'
      : 'bg-zinc-50 border-zinc-200 text-zinc-900 placeholder-zinc-400 focus:border-zinc-400'
  }`;

const selectClass = (darkMode) =>
  `w-full px-3 py-2 text-xs rounded-xl border transition-colors focus:outline-none cursor-pointer ${
    darkMode
      ? 'bg-zinc-950 border-zinc-700 text-white focus:border-zinc-500'
      : 'bg-zinc-50 border-zinc-200 text-zinc-900 focus:border-zinc-400'
  }`;

function ChangePasswordModal({ isOpen, onClose, darkMode, showToast }) {
  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const [confirm, setConfirm] = useState('');
  const [showCurrent, setShowCurrent] = useState(false);
  const [showNext, setShowNext] = useState(false);

  useEffect(() => {
    if (!isOpen) { setCurrent(''); setNext(''); setConfirm(''); }
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen) return;
    const handle = (e) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('keydown', handle);
    return () => document.removeEventListener('keydown', handle);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const canSave = current && next.length >= 8 && next === confirm;

  return (
    <div
      className="fixed inset-0 z-[70] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm"
      onMouseDown={onClose}
    >
      <div
        className={`relative rounded-2xl shadow-2xl max-w-sm w-full border ${darkMode ? 'bg-zinc-900 border-zinc-800' : 'bg-white border-zinc-200'}`}
        onMouseDown={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label="Change password"
      >
        <div className={`flex items-center justify-between px-5 py-4 border-b ${darkMode ? 'border-zinc-800' : 'border-zinc-100'}`}>
          <h3 className={`font-semibold text-sm flex items-center gap-2 ${darkMode ? 'text-zinc-100' : 'text-zinc-900'}`}>
            <Lock className="w-4 h-4" /> Change Password
          </h3>
          <button onClick={onClose} aria-label="Close" className={`p-1 rounded-lg ${darkMode ? 'text-zinc-500 hover:text-zinc-200 hover:bg-zinc-800' : 'text-zinc-400 hover:text-zinc-700 hover:bg-zinc-100'}`}>
            <X className="w-4 h-4" />
          </button>
        </div>
        <div className="px-5 py-4 space-y-3">
          <Field label="Current password" darkMode={darkMode}>
            <div className="relative">
              <input
                type={showCurrent ? 'text' : 'password'}
                value={current}
                onChange={(e) => setCurrent(e.target.value)}
                className={inputClass(darkMode) + ' pr-9'}
              />
              <button type="button" onClick={() => setShowCurrent(!showCurrent)} aria-label="Toggle password visibility" className={`absolute right-2.5 top-2 ${darkMode ? 'text-zinc-500 hover:text-zinc-300' : 'text-zinc-400 hover:text-zinc-600'}`}>
                {showCurrent ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
              </button>
            </div>
          </Field>
          <Field label="New password (min 8 characters)" darkMode={darkMode}>
            <div className="relative">
              <input
                type={showNext ? 'text' : 'password'}
                value={next}
                onChange={(e) => setNext(e.target.value)}
                className={inputClass(darkMode) + ' pr-9'}
              />
              <button type="button" onClick={() => setShowNext(!showNext)} aria-label="Toggle password visibility" className={`absolute right-2.5 top-2 ${darkMode ? 'text-zinc-500 hover:text-zinc-300' : 'text-zinc-400 hover:text-zinc-600'}`}>
                {showNext ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
              </button>
            </div>
          </Field>
          <Field label="Confirm new password" darkMode={darkMode}>
            <input
              type="password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              className={inputClass(darkMode)}
            />
            {confirm && next !== confirm && (
              <p className="text-[10px] text-red-400 mt-1">Passwords do not match</p>
            )}
          </Field>
        </div>
        <div className={`px-5 py-3 flex justify-end gap-2 border-t ${darkMode ? 'border-zinc-800 bg-zinc-950' : 'border-zinc-100 bg-zinc-50'}`}>
          <button onClick={onClose} className={`px-4 py-2 text-xs rounded-xl border ${darkMode ? 'border-zinc-700 text-zinc-300 hover:bg-zinc-800' : 'border-zinc-200 text-zinc-600 hover:bg-zinc-100'}`}>Cancel</button>
          <button
            disabled={!canSave}
            onClick={() => { if (showToast) showToast('info', 'Password change is not yet wired to the backend.'); onClose(); }}
            className={`px-4 py-2 text-xs font-medium rounded-xl text-white transition-colors ${canSave ? 'bg-zinc-900 hover:bg-zinc-800 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-200' : 'bg-zinc-500 opacity-50 cursor-not-allowed'}`}
          >
            Save
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
      className="fixed inset-0 z-[70] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm"
      onMouseDown={onClose}
    >
      <div
        className={`relative rounded-2xl shadow-2xl max-w-sm w-full border ${darkMode ? 'bg-zinc-900 border-zinc-800' : 'bg-white border-zinc-200'}`}
        onMouseDown={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label="Medical disclaimer"
      >
        <div className={`flex items-center justify-between px-5 py-4 border-b ${darkMode ? 'border-zinc-800' : 'border-zinc-100'}`}>
          <h3 className={`font-semibold text-sm ${darkMode ? 'text-zinc-100' : 'text-zinc-900'}`}>Medical Disclaimer</h3>
          <button onClick={onClose} aria-label="Close" className={`p-1 rounded-lg ${darkMode ? 'text-zinc-500 hover:text-zinc-200 hover:bg-zinc-800' : 'text-zinc-400 hover:text-zinc-700 hover:bg-zinc-100'}`}>
            <X className="w-4 h-4" />
          </button>
        </div>
        <div className="px-5 py-5">
          <p className={`text-sm leading-relaxed ${darkMode ? 'text-zinc-300' : 'text-zinc-600'}`}>{DISCLAIMER_TEXT}</p>
        </div>
        <div className={`px-5 py-3 flex justify-end border-t ${darkMode ? 'border-zinc-800 bg-zinc-950' : 'border-zinc-100 bg-zinc-50'}`}>
          <button onClick={onClose} className={`px-4 py-2 text-xs font-medium rounded-xl ${darkMode ? 'bg-zinc-800 text-zinc-200 hover:bg-zinc-700' : 'bg-zinc-900 text-white hover:bg-zinc-800'}`}>Close</button>
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
  onClearAllChats,
  onDeleteAccount,
  language,
  setLanguage,
  showToast,
  currentUser,
  onProfileUpdated,
}) {
  const [theme, setTheme] = useState(darkMode ? 'dark' : 'light');
  const [showPassword, setShowPassword] = useState(false);
  const [showDisclaimer, setShowDisclaimer] = useState(false);
  const [showClearConfirm, setShowClearConfirm] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  // Profile fields (synced with currentUser and persisted via PUT /users/me on blur)
  const [fullName, setFullName] = useState(currentUser?.full_name || '');
  const [dob, setDob] = useState(currentUser?.date_of_birth || '');
  const [bioSex, setBioSex] = useState(currentUser?.biological_sex || 'Prefer not to say');
  const [bloodType, setBloodType] = useState(currentUser?.blood_type || 'Unknown');

  useEffect(() => {
    if (currentUser) {
      setFullName(currentUser.full_name || '');
      setDob(currentUser.date_of_birth || '');
      setBioSex(currentUser.biological_sex || 'Prefer not to say');
      setBloodType(currentUser.blood_type || 'Unknown');
    }
  }, [currentUser]);

  const saveAccountField = async (fieldKey, value, setter) => {
    const backendKeyMap = {
      fullName: 'full_name',
      dob: 'date_of_birth',
      bioSex: 'biological_sex',
      bloodType: 'blood_type',
    };
    const dbKey = backendKeyMap[fieldKey] || fieldKey;

    const previousDbVal = currentUser?.[dbKey] ?? null;
    const normalizedNewVal = (value === '' || value === undefined) ? null : value;
    const normalizedPrevVal = (previousDbVal === '' || previousDbVal === undefined) ? null : previousDbVal;

    // If unchanged, don't trigger unnecessary network call
    if (normalizedNewVal === normalizedPrevVal) return;

    // Optimistic local update
    setter(value);

    try {
      const payload = { [dbKey]: normalizedNewVal };
      const updatedUser = await updateProfile(payload);
      if (showToast) {
        showToast('success', 'Changes Saved', 'Account details updated successfully.');
      }
      if (onProfileUpdated) {
        onProfileUpdated(updatedUser);
      }
    } catch (err) {
      // Rollback on failure
      const fallbackVal = previousDbVal ?? (fieldKey === 'bioSex' ? 'Prefer not to say' : fieldKey === 'bloodType' ? 'Unknown' : '');
      setter(fallbackVal);
      if (showToast) {
        showToast('error', 'Update Failed', err.message || 'Could not update account detail.');
      }
    }
  };

  const modalRef = useRef(null);
  const closeRef = useRef(null);

  // Sync theme toggle with parent darkMode
  useEffect(() => {
    setTheme(darkMode ? 'dark' : 'light');
  }, [darkMode]);

  // Apply theme selection
  const applyTheme = (t) => {
    setTheme(t);
    if (t === 'dark') setDarkMode(true);
    else if (t === 'light') setDarkMode(false);
    else {
      const sys = window.matchMedia('(prefers-color-scheme: dark)').matches;
      setDarkMode(sys);
    }
  };

  // Focus trap & Esc close
  useEffect(() => {
    if (!isOpen) return;
    setTimeout(() => closeRef.current?.focus(), 50);
    const handle = (e) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('keydown', handle);
    return () => document.removeEventListener('keydown', handle);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const base = darkMode
    ? 'bg-zinc-900 border-zinc-800 text-zinc-100'
    : 'bg-white border-zinc-200 text-zinc-900';

  const themeOptions = [
    { value: 'light', label: 'Light', icon: Sun },
    { value: 'dark', label: 'Dark', icon: Moon },
    { value: 'system', label: 'System', icon: Monitor },
  ];

  return (
    <>
      {/* Main Settings Modal */}
      <div
        className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm animate-fade-in"
        onMouseDown={onClose}
        role="dialog"
        aria-modal="true"
        aria-label="Settings"
      >
        <div
          ref={modalRef}
          className={`${base} rounded-2xl shadow-2xl border max-w-md w-full max-h-[88vh] flex flex-col overflow-hidden`}
          onMouseDown={(e) => e.stopPropagation()}
        >
          {/* Header */}
          <div className={`flex items-center justify-between px-5 py-4 border-b shrink-0 ${darkMode ? 'border-zinc-800' : 'border-zinc-100'}`}>
            <h3 className="font-semibold text-sm">Settings &amp; Preferences</h3>
            <button
              ref={closeRef}
              onClick={onClose}
              aria-label="Close settings"
              className={`p-1.5 rounded-lg transition-colors ${darkMode ? 'text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800' : 'text-zinc-400 hover:text-zinc-700 hover:bg-zinc-100'}`}
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          {/* Scrollable body */}
          <div className="flex-1 overflow-y-auto px-5 py-5 space-y-7 text-sm">

            {/* ── ACCOUNT ── */}
            <Section title="Account" icon={User} darkMode={darkMode}>
              <Field label="Full name" darkMode={darkMode}>
                <input
                  type="text"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  onBlur={() => saveAccountField('fullName', fullName, setFullName)}
                  placeholder="Your full name"
                  className={inputClass(darkMode)}
                />
              </Field>
              <Field label="Email" darkMode={darkMode}>
                <div className="flex items-center gap-2">
                  <input
                    type="email"
                    value={currentUser?.email || ''}
                    readOnly
                    className={inputClass(darkMode) + ' flex-1 opacity-60 cursor-not-allowed'}
                  />
                  <button
                    className={`text-[11px] px-2.5 py-1.5 rounded-lg border whitespace-nowrap transition-colors ${darkMode ? 'border-zinc-700 text-zinc-300 hover:bg-zinc-800' : 'border-zinc-200 text-zinc-600 hover:bg-zinc-50'}`}
                    onClick={() => showToast && showToast('info', 'Email change coming soon')}
                  >
                    Change
                  </button>
                </div>
              </Field>
              <div className="grid grid-cols-2 gap-3">
                <Field label="Date of birth" darkMode={darkMode}>
                  <input
                    type="date"
                    value={dob}
                    onChange={(e) => setDob(e.target.value)}
                    onBlur={() => saveAccountField('dob', dob, setDob)}
                    className={inputClass(darkMode)}
                  />
                </Field>
                <Field label="Biological sex" darkMode={darkMode}>
                  <select
                    value={bioSex}
                    onChange={(e) => {
                      const val = e.target.value;
                      setBioSex(val);
                      saveAccountField('bioSex', val, setBioSex);
                    }}
                    onBlur={() => saveAccountField('bioSex', bioSex, setBioSex)}
                    className={selectClass(darkMode)}
                  >
                    {BIO_SEXES.map((s) => <option key={s} value={s}>{s}</option>)}
                  </select>
                </Field>
              </div>
              <Field label="Blood type" darkMode={darkMode}>
                <select
                  value={bloodType}
                  onChange={(e) => {
                    const val = e.target.value;
                    setBloodType(val);
                    saveAccountField('bloodType', val, setBloodType);
                  }}
                  onBlur={() => saveAccountField('bloodType', bloodType, setBloodType)}
                  className={selectClass(darkMode)}
                >
                  {BLOOD_TYPES.map((bt) => <option key={bt} value={bt}>{bt}</option>)}
                </select>
              </Field>
            </Section>

            {/* ── PREFERENCES ── */}
            <Section title="Preferences" icon={Palette} darkMode={darkMode}>
              <Field label="Language" darkMode={darkMode}>
                <select
                  value={language || 'English'}
                  onChange={(e) => setLanguage && setLanguage(e.target.value)}
                  className={selectClass(darkMode)}
                >
                  {LANGUAGES.map((l) => <option key={l.code} value={l.code}>{l.label}</option>)}
                </select>
              </Field>
              <Field label="Theme" darkMode={darkMode}>
                <div className={`flex rounded-xl border overflow-hidden ${darkMode ? 'border-zinc-700' : 'border-zinc-200'}`}>
                  {themeOptions.map(({ value, label, icon: Icon }) => (
                    <button
                      key={value}
                      onClick={() => applyTheme(value)}
                      className={`flex-1 flex items-center justify-center gap-1.5 py-2 text-xs transition-colors ${
                        theme === value
                          ? darkMode
                            ? 'bg-zinc-700 text-white font-medium'
                            : 'bg-zinc-900 text-white font-medium'
                          : darkMode
                            ? 'text-zinc-400 hover:text-zinc-200'
                            : 'text-zinc-500 hover:text-zinc-900'
                      }`}
                    >
                      <Icon className="w-3.5 h-3.5" />
                      {label}
                    </button>
                  ))}
                </div>
              </Field>
            </Section>

            {/* ── SECURITY ── */}
            <Section title="Security" icon={Lock} darkMode={darkMode}>
              <div className="flex flex-col gap-2">
                <button
                  onClick={() => setShowPassword(true)}
                  className={`w-full flex items-center justify-between px-3 py-2.5 rounded-xl border text-xs transition-colors ${
                    darkMode ? 'border-zinc-700 text-zinc-300 hover:bg-zinc-800' : 'border-zinc-200 text-zinc-700 hover:bg-zinc-50'
                  }`}
                >
                  <span className="flex items-center gap-2"><Lock className="w-3.5 h-3.5" /> Change password</span>
                  <span className={`text-[10px] ${darkMode ? 'text-zinc-500' : 'text-zinc-400'}`}>→</span>
                </button>
                <button
                  onClick={() => showToast && showToast('info', 'Sign out of all devices coming soon')}
                  className={`w-full flex items-center justify-between px-3 py-2.5 rounded-xl border text-xs transition-colors ${
                    darkMode ? 'border-zinc-700 text-zinc-300 hover:bg-zinc-800' : 'border-zinc-200 text-zinc-700 hover:bg-zinc-50'
                  }`}
                >
                  <span className="flex items-center gap-2"><LogOut className="w-3.5 h-3.5" /> Sign out of all devices</span>
                  <span className={`text-[10px] ${darkMode ? 'text-zinc-500' : 'text-zinc-400'}`}>→</span>
                </button>
              </div>
            </Section>

            {/* ── DATA & PRIVACY ── */}
            <Section title="Data & Privacy" icon={Database} darkMode={darkMode}>
              <div className="flex flex-col gap-2">
                <button
                  disabled
                  title="Coming soon"
                  className={`w-full flex items-center gap-2 px-3 py-2.5 rounded-xl border text-xs cursor-not-allowed opacity-50 ${
                    darkMode ? 'border-zinc-700 text-zinc-400' : 'border-zinc-200 text-zinc-500'
                  }`}
                >
                  <Download className="w-3.5 h-3.5" />
                  Export my data
                  <span className={`ml-auto text-[10px] px-1.5 py-0.5 rounded border ${darkMode ? 'border-zinc-700 text-zinc-500' : 'border-zinc-200 text-zinc-400'}`}>
                    Coming soon
                  </span>
                </button>
                <button
                  onClick={() => setShowClearConfirm(true)}
                  className="w-full flex items-center gap-2 px-3 py-2.5 rounded-xl border text-xs border-red-500/30 text-red-400 hover:bg-red-500/10 transition-colors"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                  Clear all conversations
                </button>
                <button
                  onClick={() => setShowDeleteConfirm(true)}
                  className="w-full flex items-center gap-2 px-3 py-2.5 rounded-xl border text-xs border-red-500/40 text-red-400 hover:bg-red-500/10 transition-colors"
                >
                  <UserX className="w-3.5 h-3.5" />
                  Delete account
                </button>
              </div>
            </Section>

            {/* ── ABOUT ── */}
            <Section title="About" icon={Info} darkMode={darkMode}>
              <div className={`flex items-center justify-between text-xs px-3 py-2.5 rounded-xl border ${darkMode ? 'border-zinc-800 text-zinc-400' : 'border-zinc-100 text-zinc-500'}`}>
                <span>App version</span>
                <span className={`font-mono ${darkMode ? 'text-zinc-300' : 'text-zinc-700'}`}>v{APP_VERSION}</span>
              </div>
              <button
                onClick={() => setShowDisclaimer(true)}
                className={`w-full flex items-center justify-between px-3 py-2.5 rounded-xl border text-xs transition-colors ${darkMode ? 'border-zinc-800 text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800' : 'border-zinc-100 text-zinc-500 hover:text-zinc-700 hover:bg-zinc-50'}`}
              >
                <span className="flex items-center gap-2"><Shield className="w-3.5 h-3.5" /> Medical disclaimer</span>
                <ExternalLink className="w-3 h-3 opacity-50" />
              </button>
              <button
                onClick={() => showToast && showToast('info', 'Privacy policy coming soon')}
                className={`w-full flex items-center justify-between px-3 py-2.5 rounded-xl border text-xs transition-colors ${darkMode ? 'border-zinc-800 text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800' : 'border-zinc-100 text-zinc-500 hover:text-zinc-700 hover:bg-zinc-50'}`}
              >
                <span className="flex items-center gap-2"><Info className="w-3.5 h-3.5" /> Privacy policy</span>
                <ExternalLink className="w-3 h-3 opacity-50" />
              </button>
            </Section>
          </div>

          {/* Footer */}
          <div className={`px-5 py-4 border-t shrink-0 flex justify-end ${darkMode ? 'border-zinc-800 bg-zinc-950' : 'border-zinc-100 bg-zinc-50'}`}>
            <button
              onClick={onClose}
              className={`px-5 py-2 text-xs font-medium rounded-xl transition-colors ${
                darkMode
                  ? 'bg-zinc-100 text-zinc-900 hover:bg-white'
                  : 'bg-zinc-900 text-white hover:bg-zinc-800'
              }`}
            >
              Done
            </button>
          </div>
        </div>
      </div>

      {/* Sub-modals */}
      <ChangePasswordModal
        isOpen={showPassword}
        onClose={() => setShowPassword(false)}
        darkMode={darkMode}
        showToast={showToast}
      />

      <DisclaimerModal
        isOpen={showDisclaimer}
        onClose={() => setShowDisclaimer(false)}
        darkMode={darkMode}
      />

      <ConfirmModal
        isOpen={showClearConfirm}
        onClose={() => setShowClearConfirm(false)}
        onConfirm={() => { onClearAllChats && onClearAllChats(); showToast && showToast('info', 'All conversations cleared'); }}
        title="Clear all conversations?"
        body="All chat history, uploaded report references, and patient context will be permanently deleted. This cannot be undone. Your account and profile will remain intact."
        confirmLabel="Delete everything"
        requireTyping="DELETE"
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
    </>
  );
}
