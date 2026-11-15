import React, { useState, useEffect, useRef } from 'react';
import { User, Users, HeartPulse, Save, X, Trash2, Edit2, Plus, Shield, Phone, Activity } from 'lucide-react';
import { getProfile, updateProfile, deleteAccount, clearLocalAuthStorage, getDependents, createDependent, updateDependent, deleteDependent, createMemoryFact, getMemoryFacts } from '../services/api';
import { invalidateMetrics } from '../hooks/useLabMetrics';
import { logger } from '../services/logger';
import { parseWeightToKgString } from '../lib/clinical';
import ConfirmModal from './ConfirmModal';
import useFocusTrap from '../hooks/useFocusTrap';
import { useNavigate } from 'react-router-dom';

const Input = ({ label, name, type = 'text', placeholder = '', value, onChange, darkMode, required = false }) => (
  <div className="mb-4">
    <label className={`block text-xs font-semibold mb-1.5 ${darkMode ? 'text-ink-mute' : 'text-ink-faint'
      }`}>
      {label} {required && <span className="text-red-400">*</span>}
    </label>
    <input
      type={type}
      name={name}
      value={value || ''}
      onChange={onChange}
      placeholder={placeholder}
      required={required}
      className={`w-full rounded-lg border px-3 py-2 text-sm focus:outline-none focus:ring-1 transition-colors ${darkMode
        ? 'bg-graphite text-white placeholder:text-ink-faint border-white/[0.07] focus:border-cyan-500/50 focus:ring-cyan-500/20'
        : 'bg-zinc-50 text-zinc-900 placeholder-zinc-400 border-zinc-200 focus:border-zinc-400 focus:ring-zinc-400'
        }`}
    />
  </div>
);

const Select = ({ label, name, value, onChange, options, darkMode, required = false }) => (
  <div className="mb-4">
    <label className={`block text-xs font-semibold mb-1.5 ${darkMode ? 'text-ink-mute' : 'text-ink-faint'
      }`}>
      {label} {required && <span className="text-red-400">*</span>}
    </label>
    <select
      name={name}
      value={value || ''}
      onChange={onChange}
      required={required}
      className={`w-full rounded-lg border px-3 py-2 text-sm focus:outline-none focus:ring-1 transition-colors ${darkMode
        ? 'bg-graphite text-white border-white/[0.07] focus:border-cyan-500/50 focus:ring-cyan-500/20'
        : 'bg-zinc-50 text-zinc-900 border-zinc-200 focus:border-zinc-400 focus:ring-zinc-400'
        }`}
    >
      <option value="">Select {label}</option>
      {options.map((opt) => (
        <option key={opt.value || opt} value={opt.value || opt}>
          {opt.label || opt}
        </option>
      ))}
    </select>
  </div>
);

const TextArea = ({ label, name, placeholder = '', value, onChange, darkMode, rows = 3 }) => (
  <div className="mb-4">
    <label className={`block text-xs font-semibold mb-1.5 ${darkMode ? 'text-ink-mute' : 'text-ink-faint'
      }`}>{label}</label>
    <textarea
      name={name}
      value={value || ''}
      onChange={onChange}
      placeholder={placeholder}
      rows={rows}
      className={`w-full rounded-lg border px-3 py-2 text-sm focus:outline-none focus:ring-1 transition-colors resize-none ${darkMode
        ? 'bg-graphite text-white placeholder:text-ink-faint border-white/[0.07] focus:border-cyan-500/50 focus:ring-cyan-500/20'
        : 'bg-zinc-50 text-zinc-900 placeholder-zinc-400 border-zinc-200 focus:border-zinc-400 focus:ring-zinc-400'
        }`}
    />
  </div>
);

const BLOOD_TYPES = ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-', 'Unknown'];
const SEX_OPTIONS = ['Male', 'Female', 'Other', 'Prefer not to say'];
const RELATIONSHIP_OPTIONS = ['Father', 'Mother', 'Daughter', 'Son', 'Spouse', 'Child', 'Grandparent', 'Other'];
const LANGUAGE_OPTIONS = ['English', 'Spanish', 'Hindi', 'French', 'German'];

const DIET_OPTIONS = [
  { value: 'vegetarian', label: 'Vegetarian' },
  { value: 'non_vegetarian', label: 'Non-Vegetarian' },
  { value: 'vegan', label: 'Vegan' },
  { value: 'eggetarian', label: 'Eggetarian' },
  { value: 'jain', label: 'Jain' },
  { value: 'pescatarian', label: 'Pescatarian' },
  { value: 'other', label: 'Other' },
];

const ACTIVITY_OPTIONS = [
  { value: 'sedentary', label: 'Sedentary (little to no exercise)' },
  { value: 'light', label: 'Light (exercise 1-3 days/week)' },
  { value: 'moderate', label: 'Moderate (exercise 3-5 days/week)' },
  { value: 'active', label: 'Active (hard exercise 6-7 days/week)' },
  { value: 'very_active', label: 'Very Active (physical job or athlete)' },
];

export function getBmiData(heightCm, weightKg) {
  const h = parseFloat(heightCm);
  const w = parseFloat(weightKg);
  if (!h || !w || h <= 0 || w <= 0) return null;
  const hm = h / 100.0;
  const bmi = +(w / (hm * hm)).toFixed(1);
  let category = 'Normal weight';
  let badgeCls = 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30';
  if (bmi < 18.5) {
    category = 'Underweight';
    badgeCls = 'bg-amber-500/15 text-amber-400 border-amber-500/30';
  } else if (bmi < 25.0) {
    category = 'Normal weight';
    badgeCls = 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30';
  } else if (bmi < 30.0) {
    category = 'Overweight';
    badgeCls = 'bg-orange-500/15 text-orange-400 border-orange-500/30';
  } else {
    category = 'Obese';
    badgeCls = 'bg-rose-500/15 text-rose-400 border-rose-500/30';
  }
  return { bmi, category, badgeCls, formatted: `${bmi} kg/m² (${category})` };
}

export default function Profile({
  onClose,
  darkMode,
  initialTab = 'profile',
  onProfileUpdated,
  onDependentDeleted,
  profile,
  dependents: propsDependents,
  selectedDependentId = null,
}) {
  const navigate = useNavigate();
  const modalRef = useRef(null);
  const initialWeightRef = useRef('');
  useFocusTrap(modalRef, true, onClose);
  const [activeTab, setActiveTab] = useState(initialTab); // 'profile' or 'dependents'
  const [loading, setLoading] = useState(!profile);
  const [saving, setSaving] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');
  const [pendingDeleteAccount, setPendingDeleteAccount] = useState(false);
  const [pendingDeleteDependent, setPendingDeleteDependent] = useState(null);

  // User Profile Form
  const [formData, setFormData] = useState(() => ({
    full_name: profile?.full_name || '',
    date_of_birth: profile?.date_of_birth || '',
    biological_sex: profile?.biological_sex || '',
    blood_type: profile?.blood_type || '',
    pre_existing_conditions: profile?.pre_existing_conditions || '',
    known_allergies: profile?.known_allergies || '',
    current_medications: profile?.current_medications || '',
    language_preference: profile?.language_preference || 'English',
    emergency_contact_name: profile?.emergency_contact_name || '',
    emergency_contact_phone: profile?.emergency_contact_phone || '',
    height_cm: profile?.height_cm !== null && profile?.height_cm !== undefined ? String(profile?.height_cm) : '',
    weight_kg: profile?.weight_kg !== null && profile?.weight_kg !== undefined ? String(profile?.weight_kg) : '',
    weight: profile?.weight_kg !== null && profile?.weight_kg !== undefined ? String(profile?.weight_kg) : '',
    diet_type: profile?.diet_type || '',
    activity_level: profile?.activity_level || '',
    occupation: profile?.occupation || '',
  }));

  // Dependents List & Form State
  const [dependents, setDependents] = useState(() => Array.isArray(propsDependents) ? propsDependents : []);
  const [isEditingDependent, setIsEditingDependent] = useState(false);
  const [editingDependentId, setEditingDependentId] = useState(null);
  const [dependentForm, setDependentForm] = useState({
    relationship: 'Child',
    full_name: '',
    date_of_birth: '',
    biological_sex: '',
    blood_type: '',
    pre_existing_conditions: '',
    known_allergies: '',
    current_medications: '',
    height_cm: '',
    weight_kg: '',
    weight: '',
    diet_type: '',
    activity_level: '',
    occupation: '',
  });

  useEffect(() => {
    if (profile) {
      const initialWeight = profile.weight_kg !== null && profile.weight_kg !== undefined
        ? String(profile.weight_kg)
        : (profile.weight ? String(profile.weight) : '');
      setFormData((prev) => ({
        ...prev,
        full_name: profile.full_name || '',
        date_of_birth: profile.date_of_birth || '',
        biological_sex: profile.biological_sex || '',
        blood_type: profile.blood_type || '',
        pre_existing_conditions: profile.pre_existing_conditions || '',
        known_allergies: profile.known_allergies || '',
        current_medications: profile.current_medications || '',
        language_preference: profile.language_preference || 'English',
        emergency_contact_name: profile.emergency_contact_name || '',
        emergency_contact_phone: profile.emergency_contact_phone || '',
        height_cm: profile.height_cm !== null && profile.height_cm !== undefined ? String(profile.height_cm) : '',
        weight_kg: initialWeight,
        weight: initialWeight,
        diet_type: profile.diet_type || '',
        activity_level: profile.activity_level || '',
        occupation: profile.occupation || '',
      }));
      setLoading(false);
    }
  }, [profile]);

  useEffect(() => {
    if (Array.isArray(propsDependents) && propsDependents.length > 0) {
      setDependents(propsDependents);
    }
  }, [propsDependents]);

  useEffect(() => {
    async function loadData() {
      try {
        const [profileData, depsData, factsData] = await Promise.all([
          !profile ? getProfile().catch(() => null) : Promise.resolve(profile),
          !propsDependents ? getDependents().catch(() => []) : Promise.resolve(propsDependents),
          getMemoryFacts().catch(() => []),
        ]);

        let initialWeight = '';
        if (profileData?.weight_kg !== null && profileData?.weight_kg !== undefined) {
          initialWeight = String(profileData.weight_kg);
        } else if (Array.isArray(factsData)) {
          const weightFacts = factsData
            .filter(f => (f.fact_type || f.category) === 'weight')
            .sort((a, b) => new Date(b.created_at || 0) - new Date(a.created_at || 0));
          if (weightFacts.length > 0) {
            const rawVal = weightFacts[0].fact_text || weightFacts[0].fact_value || '';
            const match = rawVal.match(/([\d.]+)/);
            if (match) initialWeight = match[1];
          }
        }
        initialWeightRef.current = initialWeight ? parseWeightToKgString(initialWeight) : '';

        if (profileData) {
          setFormData((prev) => ({
            ...prev,
            full_name: profileData.full_name || prev.full_name || '',
            date_of_birth: profileData.date_of_birth || prev.date_of_birth || '',
            biological_sex: profileData.biological_sex || prev.biological_sex || '',
            blood_type: profileData.blood_type || prev.blood_type || '',
            pre_existing_conditions: profileData.pre_existing_conditions || prev.pre_existing_conditions || '',
            known_allergies: profileData.known_allergies || prev.known_allergies || '',
            current_medications: profileData.current_medications || prev.current_medications || '',
            language_preference: profileData.language_preference || prev.language_preference || 'English',
            emergency_contact_name: profileData.emergency_contact_name || prev.emergency_contact_name || '',
            emergency_contact_phone: profileData.emergency_contact_phone || prev.emergency_contact_phone || '',
            height_cm: profileData.height_cm !== null && profileData.height_cm !== undefined ? String(profileData.height_cm) : prev.height_cm,
            weight_kg: initialWeight || prev.weight_kg || '',
            weight: initialWeight || prev.weight || '',
            diet_type: profileData.diet_type || prev.diet_type || '',
            activity_level: profileData.activity_level || prev.activity_level || '',
            occupation: profileData.occupation || prev.occupation || '',
          }));
        }

        if (depsData && Array.isArray(depsData)) {
          setDependents(depsData);
        }
      } catch (error) {
        console.error('Could not load profile or dependent information:', error);
        setErrorMsg('Could not load profile or dependent information.');
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, [profile, propsDependents]);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleProfileSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);
    setErrorMsg('');
    try {
      const payload = {};
      const rawWeight = formData.weight_kg || formData.weight;
      for (const key in formData) {
        if (key === 'weight' || key === 'weight_kg') continue;
        if (key === 'height_cm') {
          const val = formData[key] ? parseFloat(formData[key]) : null;
          if (val !== null && (val < 30 || val > 280)) {
            setErrorMsg('Height must be between 30 and 280 cm');
            setSaving(false);
            return;
          }
          payload[key] = val;
        } else {
          payload[key] = formData[key] ? formData[key] : null;
        }
      }
      if (rawWeight && String(rawWeight).trim()) {
        const wVal = parseFloat(rawWeight);
        if (wVal < 2 || wVal > 400) {
          setErrorMsg('Weight must be between 2 and 400 kg');
          setSaving(false);
          return;
        }
        payload.weight_kg = wVal;
      } else {
        payload.weight_kg = null;
      }
      const updatedUser = await updateProfile(payload);

      try {
        const cachedUserStr = localStorage.getItem('user');
        if (cachedUserStr) {
          const uObj = JSON.parse(cachedUserStr);
          Object.assign(uObj, payload, updatedUser || {});
          localStorage.setItem('user', JSON.stringify(uObj));
        }
      } catch (_) { }

      // If user supplied or updated weight, log as dynamic weight fact
      if (formData.weight && String(formData.weight).trim()) {
        try {
          const rawWeight = String(formData.weight).trim();
          const converted = parseWeightToKgString(rawWeight);
          if (converted && converted !== initialWeightRef.current) {
            const factPayload = {
              fact_type: 'weight',
              fact_text: converted,
              confidence: 1.0,
              source_type: 'user_edit',
            };
            await createMemoryFact(factPayload);
            initialWeightRef.current = converted;
          }
        } catch (e) {
          logger.warn('Could not record weight fact:', e);
        }
      }

      if (onProfileUpdated) onProfileUpdated(updatedUser);
      onClose();
    } catch (error) {
      console.error('Could not save profile data:', error);
      setErrorMsg(error?.message || 'Could not save profile data.');
    } finally {
      setSaving(false);
    }
  };

  const handleConfirmDeleteAccount = async () => {
    setPendingDeleteAccount(false);
    setErrorMsg('');
    try {
      await deleteAccount();
      clearLocalAuthStorage();
      invalidateMetrics();
      navigate('/login');
    } catch (error) {
      console.error('Could not delete your account:', error);
      setErrorMsg(error?.message || 'Could not delete your account.');
    }
  };

  const handleDeleteAccount = () => {
    setPendingDeleteAccount(true);
  };

  // ── Dependent Handlers ──
  const handleDependentFormChange = (e) => {
    const { name, value } = e.target;
    setDependentForm(prev => ({ ...prev, [name]: value }));
  };

  const handleStartAddDependent = () => {
    setEditingDependentId(null);
    setDependentForm({
      relationship: 'Child',
      full_name: '',
      date_of_birth: '',
      biological_sex: '',
      blood_type: '',
      pre_existing_conditions: '',
      known_allergies: '',
      current_medications: '',
      height_cm: '',
      weight: '',
      diet_type: '',
      activity_level: '',
      occupation: '',
    });
    setIsEditingDependent(true);
  };

  const handleStartEditDependent = async (dep) => {
    setEditingDependentId(dep.id);

    // Fetch existing weight facts for dependent or use stored weight_kg
    let depWeight = '';
    if (dep.weight_kg !== null && dep.weight_kg !== undefined) {
      depWeight = String(dep.weight_kg);
    } else {
      try {
        const depFacts = await getMemoryFacts(dep.id);
        const weightFacts = (Array.isArray(depFacts) ? depFacts : [])
          .filter(f => (f.fact_type || f.category) === 'weight')
          .sort((a, b) => new Date(b.created_at || 0) - new Date(a.created_at || 0));
        if (weightFacts.length > 0) {
          const rawVal = weightFacts[0].fact_text || weightFacts[0].fact_value || '';
          const match = rawVal.match(/([\d.]+)/);
          if (match) depWeight = match[1];
        }
      } catch (e) { }
    }

    setDependentForm({
      relationship: dep.relationship || 'Other',
      full_name: dep.full_name || '',
      date_of_birth: dep.date_of_birth || '',
      biological_sex: dep.biological_sex || '',
      blood_type: dep.blood_type || '',
      pre_existing_conditions: dep.pre_existing_conditions || '',
      known_allergies: dep.known_allergies || '',
      current_medications: dep.current_medications || '',
      height_cm: dep.height_cm !== null && dep.height_cm !== undefined ? String(dep.height_cm) : '',
      weight_kg: depWeight,
      weight: depWeight,
      diet_type: dep.diet_type || '',
      activity_level: dep.activity_level || '',
      occupation: dep.occupation || '',
    });
    setIsEditingDependent(true);
  };

  const handleCancelDependentForm = () => {
    setIsEditingDependent(false);
    setEditingDependentId(null);
  };

  const handleSaveDependent = async (e) => {
    e.preventDefault();
    setErrorMsg('');
    if (!dependentForm.full_name.trim()) {
      console.error('Validation Error: Full Name is required for dependents.');
      setErrorMsg('Full Name is required for dependents.');
      return;
    }
    setSaving(true);
    try {
      const payload = { ...dependentForm };
      const rawW = dependentForm.weight_kg || dependentForm.weight;
      if (rawW && String(rawW).trim()) {
        const wVal = parseFloat(rawW);
        if (wVal < 2 || wVal > 400) {
          setErrorMsg('Weight must be between 2 and 400 kg');
          setSaving(false);
          return;
        }
        payload.weight_kg = wVal;
      } else {
        payload.weight_kg = null;
      }
      delete payload.weight;
      if (payload.height_cm) {
        payload.height_cm = parseFloat(payload.height_cm);
        if (payload.height_cm < 30 || payload.height_cm > 280) {
          setErrorMsg('Height must be between 30 and 280 cm');
          setSaving(false);
          return;
        }
      } else {
        payload.height_cm = null;
      }
      for (const k in payload) {
        if (!payload[k]) payload[k] = null;
      }

      let savedDep = null;
      if (editingDependentId) {
        savedDep = await updateDependent(editingDependentId, payload);
        setDependents(prev => prev.map(d => d.id === editingDependentId ? { ...d, ...savedDep } : d));
      } else {
        savedDep = await createDependent(payload);
        setDependents(prev => [...prev, savedDep]);
      }

      try {
        const currentDepsStr = localStorage.getItem('dependents');
        if (currentDepsStr) {
          const depsArr = JSON.parse(currentDepsStr);
          if (Array.isArray(depsArr)) {
            const nextDeps = editingDependentId
              ? depsArr.map(d => d.id === editingDependentId ? { ...d, ...payload, ...savedDep } : d)
              : [...depsArr, savedDep];
            localStorage.setItem('dependents', JSON.stringify(nextDeps));
          }
        }
      } catch (_) { }

      // Record weight fact if supplied
      if (dependentForm.weight && String(dependentForm.weight).trim() && savedDep?.id) {
        try {
          const rawWeight = String(dependentForm.weight).trim();
          const converted = parseWeightToKgString(rawWeight);
          await createMemoryFact({
            fact_type: 'weight',
            fact_text: converted,
            confidence: 1.0,
            source_type: 'user_edit',
            dependent_id: savedDep.id,
          });
        } catch (e) {
          logger.warn('Could not record dependent weight fact:', e);
        }
      }

      setIsEditingDependent(false);
      setEditingDependentId(null);
      if (onProfileUpdated) onProfileUpdated();
    } catch (err) {
      console.error('Dependent Save Failed:', err);
      setErrorMsg(err?.message || 'Could not save dependent.');
    } finally {
      setSaving(false);
    }
  };

  const handleConfirmDeleteDependent = async () => {
    if (!pendingDeleteDependent) return;
    const { id: depId } = pendingDeleteDependent;
    setErrorMsg('');
    try {
      await deleteDependent(depId);
      setDependents(prev => prev.filter(d => d.id !== depId));
      if (onDependentDeleted) onDependentDeleted(depId);
      if (onProfileUpdated) onProfileUpdated();
    } catch (err) {
      console.error('Delete Failed:', err);
      setErrorMsg(err?.message || 'Could not delete dependent.');
    } finally {
      setPendingDeleteDependent(null);
    }
  };

  const handleDeleteDependent = (depId, depName) => {
    setPendingDeleteDependent({ id: depId, name: depName });
  };

  const cardClass = `rounded-2xl p-6 border ${darkMode ? 'bg-carbon border-white/[0.07]' : 'bg-white border-zinc-200'
    }`;
  const textPrimary = darkMode ? 'text-white' : 'text-zinc-900';
  const textSecondary = darkMode ? 'text-ink-mute' : 'text-ink-faint';

  if (loading) {
    return (
      <div className={`fixed inset-0 z-50 flex items-center justify-center ${darkMode ? 'bg-black/80 backdrop-blur-sm' : 'bg-graphite/40 backdrop-blur-sm'
        }`}>
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 rounded-full border-2 border-zinc-500 border-t-white animate-spin" />
          <div className={`text-sm ${textSecondary}`}>Loading Profile...</div>
        </div>
      </div>
    );
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-0 sm:p-6 bg-black/70 backdrop-blur-sm animate-backdrop-in"
      role="dialog"
      aria-modal="true"
      aria-labelledby="profile-modal-title"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        ref={modalRef}
        className={`w-full sm:max-w-3xl rounded-t-[28px] sm:rounded-3xl border shadow-float overflow-hidden flex flex-col max-h-[94dvh] sm:max-h-[90dvh] ms-sheet-mobile sm:animate-modal-in ${darkMode ? 'bg-carbon border-white/[0.07]' : 'bg-white border-zinc-200'
          }`}
      >
        {/* Header */}
        <div className={`p-5 flex items-center justify-between border-b ${darkMode ? 'border-white/[0.07] bg-graphite/50' : 'border-zinc-200 bg-zinc-50'
          }`}>
          <div className="flex items-center gap-3">
            <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${darkMode ? 'bg-slate2 text-white' : 'bg-zinc-200 text-zinc-800'
              }`}>
              <Shield className="w-5 h-5 text-cyan-300" />
            </div>
            <div>
              <h2 id="profile-modal-title" className={`ms-display text-xl leading-tight ${textPrimary}`}>Patient Profile & Caregiver Hub</h2>
              <p className={`text-xs ${textSecondary}`}>Dynamic personalization & dependent management</p>
            </div>
          </div>
          <button
            onClick={onClose}
            aria-label="Close profile modal"
            className={`p-2 rounded-xl transition-colors ${darkMode ? 'text-ink-mute hover:text-white hover:bg-slate2' : 'text-ink-faint hover:text-zinc-900 hover:bg-zinc-200'
              }`}
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Tab Navigation */}
        <div className={`flex border-b px-5 pt-3 gap-2 ${darkMode ? 'border-white/[0.07] bg-carbon' : 'border-zinc-200 bg-white'}`}>
          <button
            type="button"
            onClick={() => { setActiveTab('profile'); setIsEditingDependent(false); }}
            className={`ms-tap flex items-center gap-2 pb-3 px-3 text-[13px] font-medium transition-all border-b-2 ${activeTab === 'profile'
              ? darkMode
                ? 'border-clinical-cyan text-white'
                : 'border-zinc-900 text-zinc-900'
              : 'border-transparent text-ink-faint hover:text-ink-soft'
              }`}
          >
            <User className="w-3.5 h-3.5" />
            My Profile
          </button>

          <button
            type="button"
            onClick={() => setActiveTab('dependents')}
            className={`ms-tap flex items-center gap-2 pb-3 px-3 text-[13px] font-medium transition-all border-b-2 ${activeTab === 'dependents'
              ? darkMode
                ? 'border-clinical-cyan text-white'
                : 'border-zinc-900 text-zinc-900'
              : 'border-transparent text-ink-faint hover:text-ink-soft'
              }`}
          >
            <Users className="w-3.5 h-3.5" />
            Dependents ({dependents.length})
            <span className={`text-xs px-1.5 py-0.5 rounded-full font-medium ${darkMode ? 'bg-slate2 text-ink-soft' : 'bg-zinc-200 text-zinc-700'
              }`}>
              Caregiver
            </span>
          </button>
        </div>

        {/* Scrollable Content Body */}
        <div className="flex-1 overflow-y-auto p-5 sm:p-6 space-y-6">
          {errorMsg && (
            <div role="alert" className="text-xs text-red-300 bg-red-500/10 border border-red-500/30 rounded-xl px-4 py-3">
              {errorMsg}
            </div>
          )}

          {/* ═════════════════════════════════════════════ */}
          {/* TAB 1: MY PROFILE */}
          {/* ═════════════════════════════════════════════ */}
          {activeTab === 'profile' && (
            <form onSubmit={handleProfileSubmit} className="space-y-6">
              {/* Demographics Card */}
              <div className={cardClass}>
                <div className="flex items-center gap-2 mb-4">
                  <User className="w-4 h-4 text-cyan-300" />
                  <h3 className={`font-medium text-sm ${textPrimary}`}>Personal Demographics</h3>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <Input
                    label="Full Name"
                    name="full_name"
                    value={formData.full_name}
                    onChange={handleChange}
                    placeholder="e.g. Aditya Sharma"
                    darkMode={darkMode}
                  />
                  <Input
                    label="Date of Birth"
                    name="date_of_birth"
                    type="date"
                    value={formData.date_of_birth}
                    onChange={handleChange}
                    darkMode={darkMode}
                  />
                  <Select
                    label="Biological Sex"
                    name="biological_sex"
                    value={formData.biological_sex}
                    onChange={handleChange}
                    options={SEX_OPTIONS}
                    darkMode={darkMode}
                  />
                  <Select
                    label="Blood Type"
                    name="blood_type"
                    value={formData.blood_type}
                    onChange={handleChange}
                    options={BLOOD_TYPES}
                    darkMode={darkMode}
                  />
                  <div className="sm:col-span-2">
                    <Select
                      label="Language Preference for AI Analysis"
                      name="language_preference"
                      value={formData.language_preference}
                      onChange={handleChange}
                      options={LANGUAGE_OPTIONS}
                      darkMode={darkMode}
                    />
                  </div>
                </div>
              </div>

              {/* Lifestyle & Vitals Card */}
              <div className={cardClass}>
                <div className="flex items-center gap-2 mb-1">
                  <Activity className="w-4 h-4 text-emerald-400" />
                  <h3 className={`font-medium text-sm ${textPrimary}`}>Lifestyle &amp; Vitals</h3>
                </div>
                <p className={`text-xs mb-4 ${textSecondary}`}>
                  Personalize your clinical explanations based on your daily lifestyle, physical activity, and profession.
                </p>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <Input
                    label="Height (cm)"
                    name="height_cm"
                    type="number"
                    min="30"
                    max="280"
                    value={formData.height_cm}
                    onChange={handleChange}
                    placeholder="e.g. 175"
                    darkMode={darkMode}
                  />
                  <Input
                    label="Current Weight (kg)"
                    name="weight_kg"
                    type="number"
                    min="2"
                    max="400"
                    value={formData.weight_kg || formData.weight}
                    onChange={(e) => {
                      const v = e.target.value;
                      setFormData(prev => ({ ...prev, weight_kg: v, weight: v }));
                    }}
                    placeholder="e.g. 72.5"
                    darkMode={darkMode}
                  />
                  {(() => {
                    const bmiData = getBmiData(formData.height_cm, formData.weight_kg || formData.weight);
                    if (!bmiData) return null;
                    return (
                      <div data-testid="profile-bmi-badge" className="sm:col-span-2 flex items-center justify-between p-3 rounded-xl bg-white/[0.03] border border-white/[0.08]">
                        <div className="flex items-center gap-2">
                          <Activity className="w-4 h-4 text-cyan-400" />
                          <span className={`text-xs font-medium ${textPrimary}`}>Calculated BMI</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-semibold text-white">{bmiData.bmi} kg/m²</span>
                          <span className={`text-[11px] px-2 py-0.5 rounded-full font-medium border ${bmiData.badgeCls}`}>
                            {bmiData.category}
                          </span>
                        </div>
                      </div>
                    );
                  })()}
                  <Select
                    label="Dietary Pattern"
                    name="diet_type"
                    value={formData.diet_type}
                    onChange={handleChange}
                    options={DIET_OPTIONS}
                    darkMode={darkMode}
                  />
                  <Select
                    label="Physical Activity Level"
                    name="activity_level"
                    value={formData.activity_level}
                    onChange={handleChange}
                    options={ACTIVITY_OPTIONS}
                    darkMode={darkMode}
                  />
                  <div className="sm:col-span-2">
                    <Input
                      label="Occupation / Daily Routine"
                      name="occupation"
                      value={formData.occupation}
                      onChange={handleChange}
                      placeholder="e.g. Software Engineer, Registered Nurse, Construction Worker"
                      darkMode={darkMode}
                    />
                  </div>
                </div>
              </div>

              {/* Medical Information Card */}
              <div className={cardClass}>
                <div className="flex items-center gap-2 mb-1">
                  <HeartPulse className="w-4 h-4 text-rose-400" />
                  <h3 className={`font-medium text-sm ${textPrimary}`}>Clinical PHI & Context</h3>
                </div>
                <p className={`text-xs mb-4 ${textSecondary}`}>
                  Encrypted at rest using Fernet (AES-128-CBC + HMAC-SHA256) encryption. MediSkye uses these variables to calibrate normal/abnormal report thresholds.
                </p>

                <div className="space-y-3">
                  <TextArea
                    label="Pre-existing Medical Conditions"
                    name="pre_existing_conditions"
                    value={formData.pre_existing_conditions}
                    onChange={handleChange}
                    placeholder="e.g., Hypertension, Type 2 Diabetes, Asthma"
                    darkMode={darkMode}
                  />

                  <TextArea
                    label="Known Allergies"
                    name="known_allergies"
                    value={formData.known_allergies}
                    onChange={handleChange}
                    placeholder="e.g., Penicillin, Peanuts, Sulfa Drugs"
                    darkMode={darkMode}
                  />

                  <TextArea
                    label="Current Medications & Dosages"
                    name="current_medications"
                    value={formData.current_medications}
                    onChange={handleChange}
                    placeholder="e.g., Metformin 500mg BID, Lisinopril 10mg daily"
                    darkMode={darkMode}
                  />
                </div>
              </div>

              {/* Emergency Contact */}
              <div className={cardClass}>
                <div className="flex items-center gap-2 mb-4">
                  <Phone className="w-4 h-4 text-emerald-400" />
                  <h3 className={`font-medium text-sm ${textPrimary}`}>Emergency Contact</h3>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <Input
                    label="Contact Name"
                    name="emergency_contact_name"
                    value={formData.emergency_contact_name}
                    onChange={handleChange}
                    placeholder="e.g., Jane Doe"
                    darkMode={darkMode}
                  />
                  <Input
                    label="Contact Phone"
                    name="emergency_contact_phone"
                    value={formData.emergency_contact_phone}
                    onChange={handleChange}
                    placeholder="e.g., +1 (555) 000-0000"
                    darkMode={darkMode}
                  />
                </div>
              </div>

              {/* Action Buttons */}
              <div className="flex items-center justify-between pt-2">
                <button
                  type="button"
                  onClick={handleDeleteAccount}
                  className="flex items-center gap-1.5 text-xs text-red-400 hover:text-red-300 transition-colors p-2 rounded-lg hover:bg-red-500/10"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                  Delete Account & Data
                </button>

                <div className="flex items-center gap-3">
                  <button
                    type="button"
                    onClick={onClose}
                    className={`px-4 py-2 rounded-xl text-xs font-medium border transition-colors ${darkMode ? 'border-white/[0.07] text-ink-soft hover:bg-slate2' : 'border-zinc-200 text-zinc-700 hover:bg-zinc-100'
                      }`}
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={saving}
                    className="flex items-center gap-2 px-5 py-2 rounded-xl text-xs font-semibold bg-clinical-cyan text-slate-950 hover:bg-cyan-300 transition-colors disabled:opacity-50"
                  >
                    <Save className="w-3.5 h-3.5" />
                    {saving ? 'Saving...' : 'Save Profile'}
                  </button>
                </div>
              </div>
            </form>
          )}

          {/* ═════════════════════════════════════════════ */}
          {/* TAB 2: DEPENDENTS (CAREGIVER MODE) */}
          {/* ═════════════════════════════════════════════ */}
          {activeTab === 'dependents' && (
            <div className="space-y-6">
              {/* Header & Add Button */}
              <div className="flex items-center justify-between">
                <div>
                  <h3 className={`font-semibold text-sm ${textPrimary}`}>Caregiver Dependents</h3>
                  <p className={`text-xs ${textSecondary}`}>
                    Create profiles for parents, children, or individuals you care for.
                  </p>
                </div>
                {!isEditingDependent && (
                  <button
                    type="button"
                    onClick={handleStartAddDependent}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold bg-clinical-cyan text-slate-950 hover:bg-cyan-300 transition-colors shadow-sm"
                  >
                    <Plus className="w-3.5 h-3.5" />
                    Add Dependent
                  </button>
                )}
              </div>

              {/* Form to Add / Edit Dependent */}
              {isEditingDependent && (
                <form onSubmit={handleSaveDependent} className={cardClass}>
                  <div className="flex items-center justify-between mb-4 pb-2 border-b border-white/[0.07]">
                    <h4 className={`text-xs font-semibold ${textPrimary}`}>
                      {editingDependentId ? 'Edit Dependent Profile' : 'New Dependent Profile'}
                    </h4>
                    <button
                      type="button"
                      onClick={handleCancelDependentForm}
                      className="text-xs text-ink-faint hover:text-ink-soft"
                    >
                      Cancel
                    </button>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <Select
                      label="Relationship"
                      name="relationship"
                      value={dependentForm.relationship}
                      onChange={handleDependentFormChange}
                      options={RELATIONSHIP_OPTIONS}
                      darkMode={darkMode}
                      required
                    />
                    <Input
                      label="Full Name"
                      name="full_name"
                      value={dependentForm.full_name}
                      onChange={handleDependentFormChange}
                      placeholder="e.g. Alex Morgan"
                      darkMode={darkMode}
                      required
                    />
                    <Input
                      label="Date of Birth"
                      name="date_of_birth"
                      type="date"
                      value={dependentForm.date_of_birth}
                      onChange={handleDependentFormChange}
                      darkMode={darkMode}
                    />
                    <Select
                      label="Biological Sex"
                      name="biological_sex"
                      value={dependentForm.biological_sex}
                      onChange={handleDependentFormChange}
                      options={SEX_OPTIONS}
                      darkMode={darkMode}
                    />
                    <div className="sm:col-span-2">
                      <Select
                        label="Blood Type"
                        name="blood_type"
                        value={dependentForm.blood_type}
                        onChange={handleDependentFormChange}
                        options={BLOOD_TYPES}
                        darkMode={darkMode}
                      />
                    </div>
                  </div>

                  {/* Dependent Lifestyle & Vitals */}
                  <div className="mt-4 pt-3 border-t border-white/[0.07]">
                    <div className="flex items-center gap-2 mb-3">
                      <Activity className="w-3.5 h-3.5 text-emerald-400" />
                      <span className={`text-xs font-semibold ${textSecondary}`}>Lifestyle &amp; Vitals</span>
                    </div>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                      <Input
                        label="Height (cm)"
                        name="height_cm"
                        type="number"
                        min="30"
                        max="280"
                        value={dependentForm.height_cm}
                        onChange={handleDependentFormChange}
                        placeholder="e.g. 160"
                        darkMode={darkMode}
                      />
                      <Input
                        label="Current Weight (kg)"
                        name="weight_kg"
                        type="number"
                        min="2"
                        max="400"
                        value={dependentForm.weight_kg || dependentForm.weight}
                        onChange={(e) => {
                          const v = e.target.value;
                          setDependentForm(prev => ({ ...prev, weight_kg: v, weight: v }));
                        }}
                        placeholder="e.g. 55"
                        darkMode={darkMode}
                      />
                      {(() => {
                        const bmiData = getBmiData(dependentForm.height_cm, dependentForm.weight_kg || dependentForm.weight);
                        if (!bmiData) return null;
                        return (
                          <div data-testid="dependent-bmi-badge" className="sm:col-span-2 flex items-center justify-between p-3 rounded-xl bg-white/[0.03] border border-white/[0.08]">
                            <div className="flex items-center gap-2">
                              <Activity className="w-4 h-4 text-cyan-400" />
                              <span className={`text-xs font-medium ${textPrimary}`}>Calculated BMI</span>
                            </div>
                            <div className="flex items-center gap-2">
                              <span className="text-sm font-semibold text-white">{bmiData.bmi} kg/m²</span>
                              <span className={`text-[11px] px-2 py-0.5 rounded-full font-medium border ${bmiData.badgeCls}`}>
                                {bmiData.category}
                              </span>
                            </div>
                          </div>
                        );
                      })()}
                      <Select
                        label="Dietary Pattern"
                        name="diet_type"
                        value={dependentForm.diet_type}
                        onChange={handleDependentFormChange}
                        options={DIET_OPTIONS}
                        darkMode={darkMode}
                      />
                      <Select
                        label="Activity Level"
                        name="activity_level"
                        value={dependentForm.activity_level}
                        onChange={handleDependentFormChange}
                        options={ACTIVITY_OPTIONS}
                        darkMode={darkMode}
                      />
                      <div className="sm:col-span-2">
                        <Input
                          label="Occupation / Schooling"
                          name="occupation"
                          value={dependentForm.occupation}
                          onChange={handleDependentFormChange}
                          placeholder="e.g. High school student, Retired teacher"
                          darkMode={darkMode}
                        />
                      </div>
                    </div>
                  </div>

                  <div className="mt-3 space-y-3">
                    <TextArea
                      label="Pre-existing Conditions"
                      name="pre_existing_conditions"
                      value={dependentForm.pre_existing_conditions}
                      onChange={handleDependentFormChange}
                      placeholder="e.g., Hypertension, Chronic Kidney Disease Stage 2"
                      darkMode={darkMode}
                      rows={2}
                    />

                    <TextArea
                      label="Known Allergies"
                      name="known_allergies"
                      value={dependentForm.known_allergies}
                      onChange={handleDependentFormChange}
                      placeholder="e.g., Penicillin, Aspirin"
                      darkMode={darkMode}
                      rows={2}
                    />

                    <TextArea
                      label="Current Medications & Dosages"
                      name="current_medications"
                      value={dependentForm.current_medications}
                      onChange={handleDependentFormChange}
                      placeholder="e.g., Lisinopril 20mg daily, Amlodipine 5mg"
                      darkMode={darkMode}
                      rows={2}
                    />
                  </div>

                  <div className="flex items-center justify-end gap-3 mt-4 pt-3 border-t border-white/[0.07]">
                    <button
                      type="button"
                      onClick={handleCancelDependentForm}
                      className={`px-3 py-1.5 rounded-lg text-xs font-medium border ${darkMode ? 'border-white/[0.07] text-ink-soft hover:bg-slate2' : 'border-zinc-200 text-zinc-700 hover:bg-zinc-100'
                        }`}
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      disabled={saving}
                      className="px-4 py-1.5 rounded-lg text-xs font-semibold bg-clinical-cyan text-slate-950 hover:bg-cyan-300 transition-colors disabled:opacity-50"
                    >
                      {saving ? 'Saving...' : editingDependentId ? 'Update Dependent' : 'Create Dependent'}
                    </button>
                  </div>
                </form>
              )}

              {/* Dependents Cards Grid */}
              <div className="space-y-3">
                {dependents.length === 0 ? (
                  <div className={`p-8 rounded-2xl border text-center ${darkMode ? 'bg-graphite/30 border-white/[0.07]' : 'bg-zinc-50 border-zinc-200'
                    }`}>
                    <Users className="w-10 h-10 mx-auto text-ink-faint mb-2 opacity-50" />
                    <p className={`text-sm font-medium ${textPrimary}`}>No Dependent Profiles</p>
                    <p className={`text-xs mt-1 max-w-sm mx-auto ${textSecondary}`}>
                      Add family members or patients under your care to analyze their medical reports through their personalized biological context.
                    </p>
                    {!isEditingDependent && (
                      <button
                        type="button"
                        onClick={handleStartAddDependent}
                        className="mt-4 px-4 py-2 rounded-xl text-xs font-semibold bg-clinical-cyan text-slate-950 hover:bg-cyan-300 transition-colors"
                      >
                        + Add First Dependent
                      </button>
                    )}
                  </div>
                ) : (
                  dependents.map((dep) => (
                    <div
                      key={dep.id}
                      className={`p-4 rounded-xl border transition-all ${darkMode
                        ? 'bg-graphite/60 border-white/[0.07] hover:border-white/[0.12]'
                        : 'bg-zinc-50 border-zinc-200 hover:border-zinc-300'
                        }`}
                    >
                      <div className="flex items-start justify-between">
                        <div className="flex items-center gap-2.5">
                          <div className={`w-8 h-8 rounded-lg flex items-center justify-center font-bold text-xs ${darkMode ? 'bg-slate2 text-ink' : 'bg-zinc-200 text-zinc-800'
                            }`}>
                            {dep.full_name?.charAt(0) || 'D'}
                          </div>
                          <div>
                            <div className="flex items-center gap-2">
                              <span className={`font-semibold text-sm ${textPrimary}`}>{dep.full_name}</span>
                              <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${darkMode ? 'bg-cyan-500/10 text-cyan-200 border border-cyan-500/25' : 'bg-indigo-50 text-indigo-700 border border-indigo-200'
                                }`}>
                                {dep.relationship}
                              </span>
                            </div>
                            <div className={`flex items-center gap-2 text-xs mt-0.5 ${textSecondary}`}>
                              {dep.calculated_age !== null && dep.calculated_age !== undefined && (
                                <span>{dep.calculated_age} yrs</span>
                              )}
                              {dep.biological_sex && <span>• {dep.biological_sex}</span>}
                              {dep.blood_type && <span>• {dep.blood_type}</span>}
                              {(() => {
                                const bmiData = getBmiData(dep.height_cm, dep.weight_kg);
                                return bmiData ? <span>• BMI {bmiData.bmi} ({bmiData.category})</span> : null;
                              })()}
                            </div>
                          </div>
                        </div>

                        {/* Edit & Delete Actions */}
                        <div className="flex items-center gap-1">
                          <button
                            type="button"
                            onClick={() => handleStartEditDependent(dep)}
                            className={`p-1.5 rounded-lg transition-colors ${darkMode ? 'text-ink-mute hover:text-white hover:bg-slate2' : 'text-ink-faint hover:text-zinc-900 hover:bg-zinc-200'
                              }`}
                            title="Edit Dependent"
                          >
                            <Edit2 className="w-3.5 h-3.5" />
                          </button>
                          <button
                            type="button"
                            onClick={() => handleDeleteDependent(dep.id, dep.full_name)}
                            className="p-1.5 rounded-lg text-ink-mute hover:text-red-400 hover:bg-red-500/10 transition-colors"
                            title="Delete Dependent"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </div>

                      {/* Clinical Summary Pills */}
                      {(dep.pre_existing_conditions || dep.current_medications || dep.known_allergies || dep.diet_type || dep.activity_level || dep.occupation) && (
                        <div className="mt-3 pt-2 border-t border-white/[0.07] text-xs space-y-1">
                          {dep.pre_existing_conditions && (
                            <div className="flex items-baseline gap-1.5 text-xs">
                              <span className="text-ink-faint font-medium shrink-0">Conditions:</span>
                              <span className={darkMode ? 'text-ink-soft' : 'text-zinc-700'}>{dep.pre_existing_conditions}</span>
                            </div>
                          )}
                          {dep.current_medications && (
                            <div className="flex items-baseline gap-1.5 text-xs">
                              <span className="text-ink-faint font-medium shrink-0">Medications:</span>
                              <span className={darkMode ? 'text-ink-soft' : 'text-zinc-700'}>{dep.current_medications}</span>
                            </div>
                          )}
                          {dep.known_allergies && (
                            <div className="flex items-baseline gap-1.5 text-xs">
                              <span className="text-ink-faint font-medium shrink-0">Allergies:</span>
                              <span className={darkMode ? 'text-ink-soft' : 'text-zinc-700'}>{dep.known_allergies}</span>
                            </div>
                          )}
                          {(dep.diet_type || dep.activity_level || dep.occupation) && (
                            <div className="flex items-center gap-1.5 text-xs text-ink-mute pt-1 flex-wrap">
                              {dep.diet_type && (
                                <span className="px-1.5 py-0.5 rounded bg-slate2/80 border border-white/[0.12]">
                                  {dep.diet_type.replace('_', ' ')}
                                </span>
                              )}
                              {dep.activity_level && (
                                <span className="px-1.5 py-0.5 rounded bg-slate2/80 border border-white/[0.12]">
                                  {dep.activity_level.replace('_', ' ')}
                                </span>
                              )}
                              {dep.occupation && (
                                <span className="px-1.5 py-0.5 rounded bg-slate2/80 border border-white/[0.12]">
                                  {dep.occupation}
                                </span>
                              )}
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  ))
                )}
              </div>
            </div>
          )}

        </div>
      </div>

      {/* Account Deletion Modal */}
      <ConfirmModal
        isOpen={pendingDeleteAccount}
        onClose={() => setPendingDeleteAccount(false)}
        onConfirm={handleConfirmDeleteAccount}
        title="Delete your account?"
        body="Are you sure you want to permanently delete your account, medical data, dependents, and all documents? This action cannot be undone."
        confirmLabel="Delete Account"
        requireTyping={null}
        closeable={true}
        darkMode={darkMode}
      />

      {/* Dependent Deletion Modal */}
      <ConfirmModal
        isOpen={!!pendingDeleteDependent}
        onClose={() => setPendingDeleteDependent(null)}
        onConfirm={handleConfirmDeleteDependent}
        title={`Delete dependent profile "${pendingDeleteDependent?.name}"?`}
        body="This will permanently delete the dependent profile and their associated medical data."
        confirmLabel="Delete Dependent"
        requireTyping={null}
        closeable={true}
        darkMode={darkMode}
      />
    </div>
  );
}
