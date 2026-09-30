import React, { useState, useRef, useEffect } from 'react';
import { User, Users, ChevronDown, Check, Plus, HeartPulse } from 'lucide-react';

export default function PatientContextSelector({
  currentUser,
  dependents = [],
  selectedPatientId,
  onSelectPatient,
  onOpenDependents,
  darkMode,
}) {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef(null);

  // Close dropdown on click outside
  useEffect(() => {
    function handleClickOutside(event) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const isSelf = !selectedPatientId || selectedPatientId === 'self' || (currentUser && selectedPatientId === currentUser.id);
  const activeDependent = !isSelf ? dependents.find(d => d.id === selectedPatientId) : null;

  const activeLabel = isSelf
    ? `${currentUser?.full_name || 'My Profile'} (Self)`
    : activeDependent
      ? `${activeDependent.full_name} (${activeDependent.relationship})`
      : 'Select Patient';

  return (
    <div className="relative inline-block text-left" ref={dropdownRef}>
      <div className="flex items-center gap-2">
        <span className={`text-[11px] font-medium tracking-wide uppercase ${darkMode ? 'text-zinc-500' : 'text-zinc-400'}`}>
          Patient Context:
        </span>
        <button
          type="button"
          onClick={() => setIsOpen(!isOpen)}
          className={`flex items-center gap-2 px-3 py-1 rounded-full text-xs font-medium border transition-all duration-150 ${
            darkMode
              ? 'bg-[#09090B] border-zinc-800 text-zinc-200 hover:border-zinc-700 hover:text-white shadow-sm'
              : 'bg-white border-zinc-200 text-zinc-800 hover:border-zinc-300 hover:text-black shadow-sm'
          }`}
        >
          {isSelf ? (
            <User className="w-3.5 h-3.5 text-indigo-400" />
          ) : (
            <HeartPulse className="w-3.5 h-3.5 text-rose-400" />
          )}
          <span className="truncate max-w-[170px] sm:max-w-[220px]">{activeLabel}</span>
          <ChevronDown className={`w-3.5 h-3.5 text-zinc-400 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
        </button>
      </div>

      {/* Dropdown Menu */}
      {isOpen && (
        <div
          className={`absolute left-0 sm:left-auto sm:right-0 mt-2 w-72 rounded-2xl border shadow-2xl z-50 overflow-hidden animate-slide-in ${
            darkMode
              ? 'bg-[#09090B] border-zinc-800 text-zinc-200'
              : 'bg-white border-zinc-200 text-zinc-800'
          }`}
        >
          <div className={`p-2.5 border-b text-[10px] uppercase font-semibold tracking-wider ${
            darkMode ? 'border-zinc-800/80 bg-zinc-900/40 text-zinc-400' : 'border-zinc-100 bg-zinc-50 text-zinc-500'
          }`}>
            Clinical Analysis Lens
          </div>

          <div className="p-1.5 space-y-1 max-h-60 overflow-y-auto">
            {/* Self Option */}
            <button
              type="button"
              onClick={() => {
                onSelectPatient('self');
                setIsOpen(false);
              }}
              className={`w-full flex items-center justify-between p-2 rounded-xl text-xs transition-colors ${
                isSelf
                  ? darkMode
                    ? 'bg-zinc-800/90 text-white font-medium'
                    : 'bg-zinc-100 text-black font-medium'
                  : darkMode
                    ? 'hover:bg-zinc-900 hover:text-white text-zinc-300'
                    : 'hover:bg-zinc-50 hover:text-black text-zinc-700'
              }`}
            >
              <div className="flex items-center gap-2.5 truncate">
                <div className={`w-6 h-6 rounded-lg flex items-center justify-center shrink-0 ${
                  darkMode ? 'bg-indigo-950/80 text-indigo-300' : 'bg-indigo-100 text-indigo-700'
                }`}>
                  <User className="w-3.5 h-3.5" />
                </div>
                <div className="text-left truncate">
                  <div className="truncate font-medium">{currentUser?.full_name || 'My Profile'} (Self)</div>
                  <div className={`text-[10px] ${darkMode ? 'text-zinc-500' : 'text-zinc-400'}`}>
                    {currentUser?.calculated_age ? `${currentUser.calculated_age} yrs • ` : ''}
                    {currentUser?.biological_sex || 'Main User'}
                  </div>
                </div>
              </div>
              {isSelf && <Check className="w-4 h-4 text-emerald-400 shrink-0 ml-2" />}
            </button>

            {/* Dependents List */}
            {dependents.length > 0 && (
              <div className={`pt-1.5 mt-1.5 border-t ${darkMode ? 'border-zinc-800/60' : 'border-zinc-100'}`}>
                <div className={`px-2 pb-1 text-[10px] font-semibold uppercase tracking-wider ${
                  darkMode ? 'text-zinc-500' : 'text-zinc-400'
                }`}>
                  Dependents
                </div>
                {dependents.map((dep) => {
                  const isDepActive = !isSelf && selectedPatientId === dep.id;
                  return (
                    <button
                      key={dep.id}
                      type="button"
                      onClick={() => {
                        onSelectPatient(dep.id);
                        setIsOpen(false);
                      }}
                      className={`w-full flex items-center justify-between p-2 rounded-xl text-xs transition-colors ${
                        isDepActive
                          ? darkMode
                            ? 'bg-zinc-800/90 text-white font-medium'
                            : 'bg-zinc-100 text-black font-medium'
                          : darkMode
                            ? 'hover:bg-zinc-900 hover:text-white text-zinc-300'
                            : 'hover:bg-zinc-50 hover:text-black text-zinc-700'
                      }`}
                    >
                      <div className="flex items-center gap-2.5 truncate">
                        <div className={`w-6 h-6 rounded-lg flex items-center justify-center shrink-0 ${
                          darkMode ? 'bg-rose-950/80 text-rose-300' : 'bg-rose-100 text-rose-700'
                        }`}>
                          <HeartPulse className="w-3.5 h-3.5" />
                        </div>
                        <div className="text-left truncate">
                          <div className="truncate font-medium flex items-center gap-1.5">
                            <span>{dep.full_name}</span>
                            <span className={`text-[9px] px-1.5 py-0.2 rounded-full uppercase ${
                              darkMode ? 'bg-zinc-800 text-zinc-400' : 'bg-zinc-200 text-zinc-600'
                            }`}>
                              {dep.relationship}
                            </span>
                          </div>
                          <div className={`text-[10px] ${darkMode ? 'text-zinc-500' : 'text-zinc-400'}`}>
                            {dep.calculated_age !== null && dep.calculated_age !== undefined ? `${dep.calculated_age} yrs • ` : ''}
                            {dep.biological_sex || ''}
                          </div>
                        </div>
                      </div>
                      {isDepActive && <Check className="w-4 h-4 text-emerald-400 shrink-0 ml-2" />}
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          {/* Add Dependent Footer */}
          <div className={`p-2 border-t ${darkMode ? 'border-zinc-800 bg-zinc-900/30' : 'border-zinc-100 bg-zinc-50'}`}>
            <button
              type="button"
              onClick={() => {
                setIsOpen(false);
                if (onOpenDependents) onOpenDependents();
              }}
              className="w-full flex items-center justify-center gap-1.5 py-1.5 px-3 rounded-lg text-xs font-semibold text-zinc-400 hover:text-white hover:bg-zinc-800/80 transition-colors"
            >
              <Plus className="w-3.5 h-3.5" />
              Manage / Add Dependents
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
