import React, { useState, useEffect } from 'react';
import {
  Heart,
  Pill,
  AlertCircle,
  Users,
  Activity,
  Gauge,
  Scale,
  Sparkles,
  Edit2,
  Trash2,
  Plus,
  Check,
  X,
} from 'lucide-react';
import {
  getFacts,
  createFact,
  updateFact,
  deleteFact,
  updateProfile,
} from '../services/api';
import { logger } from '../services/logger';

const FACT_CATEGORIES = [
  { key: 'condition', label: 'Conditions', icon: Heart },
  { key: 'medication', label: 'Medications', icon: Pill },
  { key: 'allergy', label: 'Allergies', icon: AlertCircle },
  { key: 'family_history', label: 'Family History', icon: Users },
  { key: 'lifestyle', label: 'Lifestyle', icon: Activity },
  { key: 'measurement', label: 'Recent Measurements', icon: Gauge },
  { key: 'weight', label: 'Weight', icon: Scale },
  { key: 'sport_hobby', label: 'Sports & Activities', icon: Sparkles },
];

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
  { value: 'sedentary', label: 'Sedentary (Little or no exercise)' },
  { value: 'light', label: 'Light (Exercise 1-3 days/week)' },
  { value: 'moderate', label: 'Moderate (Exercise 3-5 days/week)' },
  { value: 'active', label: 'Active (Exercise 6-7 days/week)' },
  { value: 'very_active', label: 'Very Active (Hard exercise daily)' },
];

export default function HealthProfile({
  currentUser,
  onProfileUpdated,
  darkMode = false,
  activeDependentId = null,
}) {
  const [facts, setFacts] = useState([]);
  const [loading, setLoading] = useState(false);

  // New fact form
  const [newType, setNewType] = useState('condition');
  const [newText, setNewText] = useState('');
  const [addingFact, setAddingFact] = useState(false);

  // Inline editing
  const [editingFactId, setEditingFactId] = useState(null);
  const [editText, setEditText] = useState('');

  // Lifestyle fields synced with currentUser
  const [dietType, setDietType] = useState(currentUser?.diet_type || '');
  const [activityLevel, setActivityLevel] = useState(currentUser?.activity_level || '');
  const [heightCm, setHeightCm] = useState(currentUser?.height_cm ?? '');
  const [occupation, setOccupation] = useState(currentUser?.occupation || '');
  const [userWeight, setUserWeight] = useState('');
  const [lastSavedWeight, setLastSavedWeight] = useState('');

  useEffect(() => {
    if (currentUser) {
      setDietType(currentUser.diet_type || '');
      setActivityLevel(currentUser.activity_level || '');
      setHeightCm(currentUser.height_cm ?? '');
      setOccupation(currentUser.occupation || '');
    }
  }, [currentUser]);

  useEffect(() => {
    loadFacts();
  }, [activeDependentId]);

  async function loadFacts() {
    setLoading(true);
    try {
      const data = await getFacts(activeDependentId);
      if (Array.isArray(data)) {
        setFacts(data);
        // Look for recent weight in facts if available
        const weightFact = data.find((f) => f.fact_type === 'weight');
        if (weightFact) {
          setUserWeight(weightFact.fact_text);
          setLastSavedWeight(weightFact.fact_text);
        }
      }
    } catch (err) {
      logger.error('Failed to load health facts:', err);
      console.error('Failed to load facts:', err);
    } finally {
      setLoading(false);
    }
  }

  const handleAddFact = async (e) => {
    if (e) e.preventDefault();
    const trimmed = newText.trim();
    if (!trimmed) return;

    setAddingFact(true);
    try {
      const created = await createFact({
        fact_type: newType,
        fact_text: trimmed,
        confidence: 1.0,
        source_type: 'user_edit',
        dependent_id: activeDependentId && activeDependentId !== 'self' ? activeDependentId : null,
      });
      setFacts((prev) => [created, ...prev]);
      setNewText('');
    } catch (err) {
      console.error('Add Fact Failed:', err);
    } finally {
      setAddingFact(false);
    }
  };

  const handleStartEdit = (fact) => {
    setEditingFactId(fact.id);
    setEditText(fact.fact_text);
  };

  const handleSaveEdit = async (factId) => {
    const trimmed = editText.trim();
    if (!trimmed) return;

    try {
      const updated = await updateFact(factId, { fact_text: trimmed });
      setFacts((prev) =>
        prev.map((f) => (f.id === factId ? { ...f, fact_text: updated.fact_text || trimmed } : f))
      );
      setEditingFactId(null);
    } catch (err) {
      console.error('Update Failed:', err);
    }
  };

  const handleDeleteFact = async (factId) => {
    try {
      await deleteFact(factId);
      setFacts((prev) => prev.filter((f) => f.id !== factId));
    } catch (err) {
      console.error('Delete Failed:', err);
    }
  };

  const handleSaveLifestyleField = async (field, value) => {
    try {
      const payload = {
        [field]: value === '' ? null : field === 'height_cm' ? (value ? parseFloat(value) : null) : value,
      };
      const updatedUser = await updateProfile(payload);
      if (onProfileUpdated) onProfileUpdated(updatedUser);
    } catch (err) {
      console.error('Save Failed:', err);
    }
  };

  const handleSaveWeightFact = async () => {
    const trimmed = (userWeight || '').trim();
    if (!trimmed) return;
    // Blur fires even when nothing changed — don't create a duplicate weight fact.
    if (trimmed === lastSavedWeight) return;
    try {
      const created = await createFact({
        fact_type: 'weight',
        fact_text: trimmed,
        confidence: 1.0,
        source_type: 'user_edit',
      });
      setFacts((prev) => [created, ...prev.filter((f) => f.id !== created.id)]);
      const savedText = created.fact_text ?? trimmed;
      setLastSavedWeight(savedText);
      setUserWeight(savedText);
    } catch (err) {
      console.error('Weight Save Failed:', err);
    }
  };

  const inputClass = `w-full px-3 py-2 text-xs rounded-xl border transition-colors focus:outline-none ${
    darkMode
      ? 'bg-zinc-950 border-zinc-700 text-white placeholder-zinc-500 focus:border-zinc-500'
      : 'bg-zinc-50 border-zinc-200 text-zinc-900 placeholder-zinc-400 focus:border-zinc-400'
  }`;

  const selectClass = `w-full px-3 py-2 text-xs rounded-xl border transition-colors focus:outline-none cursor-pointer ${
    darkMode
      ? 'bg-zinc-950 border-zinc-700 text-white focus:border-zinc-500'
      : 'bg-zinc-50 border-zinc-200 text-zinc-900 focus:border-zinc-400'
  }`;

  // Group facts by type
  const factsByType = {};
  FACT_CATEGORIES.forEach((cat) => {
    factsByType[cat.key] = [];
  });
  facts.forEach((f) => {
    const t = (f.fact_type || '').toLowerCase();
    if (factsByType[t]) {
      factsByType[t].push(f);
    } else {
      if (!factsByType.other) factsByType.other = [];
      factsByType.other.push(f);
    }
  });

  return (
    <div className="space-y-6 text-xs">
      {/* ── Lifestyle Section ── */}
      <div className={`p-4 rounded-2xl border ${darkMode ? 'bg-zinc-900/60 border-zinc-800' : 'bg-white border-zinc-200 shadow-sm'}`}>
        <h4 className={`text-xs font-semibold uppercase tracking-wider mb-3 flex items-center gap-2 ${darkMode ? 'text-zinc-300' : 'text-zinc-800'}`}>
          <Activity className="w-4 h-4 text-emerald-500" />
          Lifestyle &amp; Vitals
        </h4>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div>
            <label className={`block text-[11px] font-medium mb-1 ${darkMode ? 'text-zinc-400' : 'text-zinc-500'}`}>
              Diet Pattern
            </label>
            <select
              aria-label="Diet Pattern"
              value={dietType}
              onChange={(e) => {
                const val = e.target.value;
                setDietType(val);
                handleSaveLifestyleField('diet_type', val);
              }}
              className={selectClass}
            >
              <option value="">Not specified</option>
              {DIET_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className={`block text-[11px] font-medium mb-1 ${darkMode ? 'text-zinc-400' : 'text-zinc-500'}`}>
              Activity Level
            </label>
            <select
              aria-label="Activity Level"
              value={activityLevel}
              onChange={(e) => {
                const val = e.target.value;
                setActivityLevel(val);
                handleSaveLifestyleField('activity_level', val);
              }}
              className={selectClass}
            >
              <option value="">Not specified</option>
              {ACTIVITY_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className={`block text-[11px] font-medium mb-1 ${darkMode ? 'text-zinc-400' : 'text-zinc-500'}`}>
              Height (cm)
            </label>
            <input
              type="number"
              aria-label="Height (cm)"
              placeholder="e.g. 175"
              value={heightCm}
              onChange={(e) => setHeightCm(e.target.value)}
              onBlur={() => handleSaveLifestyleField('height_cm', heightCm)}
              className={inputClass}
            />
          </div>

          <div>
            <label className={`block text-[11px] font-medium mb-1 ${darkMode ? 'text-zinc-400' : 'text-zinc-500'}`}>
              Recent Weight
            </label>
            <input
              type="text"
              aria-label="Recent Weight"
              placeholder="e.g. 79 kg"
              value={userWeight}
              onChange={(e) => setUserWeight(e.target.value)}
              onBlur={handleSaveWeightFact}
              className={inputClass}
            />
          </div>

          <div className="sm:col-span-2">
            <label className={`block text-[11px] font-medium mb-1 ${darkMode ? 'text-zinc-400' : 'text-zinc-500'}`}>
              Occupation
            </label>
            <input
              type="text"
              aria-label="Occupation"
              placeholder="e.g. Software Engineer"
              value={occupation}
              onChange={(e) => setOccupation(e.target.value)}
              onBlur={() => handleSaveLifestyleField('occupation', occupation)}
              className={inputClass}
            />
          </div>
        </div>
      </div>

      {/* ── Add Manual Fact Form ── */}
      <div className={`p-4 rounded-2xl border ${darkMode ? 'bg-zinc-900/60 border-zinc-800' : 'bg-white border-zinc-200 shadow-sm'}`}>
        <h4 className={`text-xs font-semibold uppercase tracking-wider mb-3 flex items-center gap-2 ${darkMode ? 'text-zinc-300' : 'text-zinc-800'}`}>
          <Plus className="w-4 h-4 text-emerald-500" />
          Add Health Fact Manually
        </h4>

        <form onSubmit={handleAddFact} className="flex flex-col sm:flex-row items-center gap-2">
          <select
            aria-label="Fact Category"
            value={newType}
            onChange={(e) => setNewType(e.target.value)}
            className={`${selectClass} sm:w-44 shrink-0`}
          >
            {FACT_CATEGORIES.map((cat) => (
              <option key={cat.key} value={cat.key}>
                {cat.label}
              </option>
            ))}
          </select>

          <input
            type="text"
            aria-label="Fact Details"
            placeholder="e.g. Penicillin allergy with mild hives, or Metformin 500mg daily"
            value={newText}
            onChange={(e) => setNewText(e.target.value)}
            className={`${inputClass} flex-1`}
          />

          <button
            type="submit"
            disabled={addingFact || !newText.trim()}
            className={`w-full sm:w-auto px-4 py-2 rounded-xl font-medium transition-colors shrink-0 ${
              darkMode
                ? 'bg-zinc-100 text-black hover:bg-white disabled:opacity-50'
                : 'bg-zinc-900 text-white hover:bg-black disabled:opacity-50'
            }`}
          >
            Add Fact
          </button>
        </form>
      </div>

      {/* ── Grouped Facts List ── */}
      <div className="space-y-4">
        {loading ? (
          <div className="py-6 text-center text-zinc-500">Loading health facts...</div>
        ) : facts.length === 0 ? (
          <div className={`p-6 text-center rounded-2xl border ${darkMode ? 'bg-zinc-950 border-zinc-800 text-zinc-400' : 'bg-zinc-50 border-zinc-200 text-zinc-600'}`}>
            <p className="font-medium text-xs">No health facts recorded yet.</p>
            <p className="text-[11px] text-zinc-500 mt-1">
              Add facts manually above or allow MediSkye to remember clinical findings during your chats.
            </p>
          </div>
        ) : (
          FACT_CATEGORIES.map((cat) => {
            const catFacts = factsByType[cat.key] || [];
            if (catFacts.length === 0) return null;
            const Icon = cat.icon;

            return (
              <div
                key={cat.key}
                className={`p-4 rounded-2xl border ${
                  darkMode ? 'bg-zinc-900/60 border-zinc-800' : 'bg-white border-zinc-200 shadow-sm'
                }`}
              >
                <div className="flex items-center gap-2 mb-3 pb-2 border-b border-zinc-100 dark:border-zinc-800">
                  <Icon className="w-3.5 h-3.5 text-emerald-500" />
                  <h5 className={`font-semibold text-xs uppercase tracking-wider ${darkMode ? 'text-zinc-300' : 'text-zinc-700'}`}>
                    {cat.label}
                  </h5>
                  <span className={`text-[10px] px-1.5 py-0.2 rounded-full font-medium ${
                    darkMode ? 'bg-zinc-800 text-zinc-400' : 'bg-zinc-100 text-zinc-600'
                  }`}>
                    {catFacts.length}
                  </span>
                </div>

                <div className="space-y-2">
                  {catFacts.map((fact) => {
                    const isEditing = editingFactId === fact.id;
                    const confidencePercent = Math.round((fact.confidence ?? 1.0) * 100);
                    const sourceHint = (fact.source_type || 'chat').replace('_', ' ');

                    return (
                      <div
                        key={fact.id}
                        className={`p-2.5 rounded-xl border transition-all ${
                          darkMode ? 'bg-zinc-950 border-zinc-800/80' : 'bg-zinc-50 border-zinc-200'
                        }`}
                      >
                        {isEditing ? (
                          <div className="flex items-center gap-2">
                            <input
                              type="text"
                              aria-label="Edit fact text"
                              value={editText}
                              onChange={(e) => setEditText(e.target.value)}
                              className={`${inputClass} flex-1`}
                              autoFocus
                            />
                            <button
                              onClick={() => handleSaveEdit(fact.id)}
                              aria-label="Save fact edit"
                              className="p-1.5 rounded-lg bg-emerald-600 text-white hover:bg-emerald-700 transition-colors"
                              title="Save"
                            >
                              <Check className="w-3.5 h-3.5" />
                            </button>
                            <button
                              onClick={() => setEditingFactId(null)}
                              aria-label="Cancel fact edit"
                              className={`p-1.5 rounded-lg transition-colors ${
                                darkMode ? 'text-zinc-400 hover:bg-zinc-800' : 'text-zinc-500 hover:bg-zinc-200'
                              }`}
                              title="Cancel"
                            >
                              <X className="w-3.5 h-3.5" />
                            </button>
                          </div>
                        ) : (
                          <div className="flex items-start justify-between gap-3">
                            <div className="space-y-1 flex-1 min-w-0">
                              <p className={`text-xs font-medium leading-relaxed break-words ${darkMode ? 'text-zinc-200' : 'text-zinc-800'}`}>
                                {fact.fact_text}
                              </p>
                              <div className="flex items-center gap-2 text-[10px] text-zinc-500 flex-wrap">
                                <span className={`px-1.5 py-0.2 rounded border font-medium ${
                                  confidencePercent >= 80
                                    ? 'text-emerald-400 border-emerald-500/20 bg-emerald-500/10'
                                    : 'text-amber-400 border-amber-500/20 bg-amber-500/10'
                                }`}>
                                  {confidencePercent}% confidence
                                </span>
                                <span>• source: {sourceHint}</span>
                              </div>
                            </div>

                            <div className="flex items-center gap-1 shrink-0">
                              <button
                                onClick={() => handleStartEdit(fact)}
                                aria-label="Edit fact"
                                className={`p-1.5 rounded-lg text-zinc-400 hover:text-zinc-200 transition-colors ${
                                  darkMode ? 'hover:bg-zinc-800' : 'hover:bg-zinc-200'
                                }`}
                                title="Edit fact"
                              >
                                <Edit2 className="w-3.5 h-3.5" />
                              </button>
                              <button
                                onClick={() => handleDeleteFact(fact.id)}
                                aria-label="Forget fact"
                                className={`p-1.5 rounded-lg text-zinc-400 hover:text-red-400 transition-colors ${
                                  darkMode ? 'hover:bg-zinc-800' : 'hover:bg-zinc-200'
                                }`}
                                title="Forget fact"
                              >
                                <Trash2 className="w-3.5 h-3.5" />
                              </button>
                            </div>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
