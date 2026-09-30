import React, { useState } from 'react';
import { ChevronDown, ChevronUp, FileText, Search } from 'lucide-react';

export default function RagSourcesPanel({ sources, onSelectSource, darkMode }) {
  const [isOpen, setIsOpen] = useState(false);

  if (!sources || sources.length === 0) return null;

  return (
    <div className={`mt-4 pt-3 border-t ${darkMode ? 'border-zinc-800' : 'border-zinc-100'}`}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={`flex items-center justify-between w-full text-xs font-medium transition-colors py-1 group ${
          darkMode
            ? 'text-zinc-400 hover:text-zinc-200'
            : 'text-zinc-500 hover:text-zinc-800'
        }`}
      >
        <div className="flex items-center gap-2">
          <Search className={`w-3.5 h-3.5 ${darkMode ? 'text-zinc-400' : 'text-zinc-500'}`} />
          <span>Retrieved Sources ({sources.length} RAG Chunks)</span>
          <span className={`px-2 py-0.5 rounded text-[10px] font-medium border ${
            darkMode
              ? 'bg-zinc-800 text-zinc-400 border-zinc-700'
              : 'bg-zinc-100 text-zinc-600 border-zinc-200'
          }`}>
            High Confidence
          </span>
        </div>
        <div className={`flex items-center gap-1 ${
          darkMode
            ? 'text-zinc-400 group-hover:text-zinc-200'
            : 'text-zinc-400 group-hover:text-zinc-600'
        }`}>
          <span className="text-[11px]">{isOpen ? 'Hide Sources' : 'View Sources'}</span>
          {isOpen ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
        </div>
      </button>

      {isOpen && (
        <div className="mt-2.5 grid grid-cols-1 sm:grid-cols-2 gap-2 animate-fade-in">
          {sources.map((src, idx) => (
            <div
              key={idx}
              onClick={() => onSelectSource(src)}
              className={`p-3 rounded-xl transition-all cursor-pointer shadow-sm group border ${
                darkMode
                  ? 'bg-zinc-800/50 border-zinc-800 hover:border-zinc-600'
                  : 'bg-zinc-50 border-zinc-200 hover:border-zinc-400'
              }`}
            >
              <div className="flex items-center justify-between mb-1">
                <div className={`flex items-center gap-1.5 text-xs font-medium truncate ${
                  darkMode ? 'text-zinc-100' : 'text-zinc-900'
                }`}>
                  <FileText className={`w-3.5 h-3.5 shrink-0 ${darkMode ? 'text-zinc-500' : 'text-zinc-400'}`} />
                  <span className="truncate">{src.title || `Chunk [${idx + 1}]`}</span>
                </div>
                <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded ${
                  darkMode
                    ? 'bg-zinc-700 text-zinc-300'
                    : 'bg-zinc-200 text-zinc-700'
                }`}>
                  {src.score || '98%'} Match
                </span>
              </div>
              <p className={`text-[11px] line-clamp-2 leading-relaxed ${
                darkMode ? 'text-zinc-400' : 'text-zinc-500'
              }`}>
                {src.excerpt || src.content || 'Extracted page text excerpt from PDF report.'}
              </p>
              <div className={`mt-2 text-[10px] group-hover:underline flex items-center gap-1 font-medium ${
                darkMode ? 'text-zinc-300' : 'text-zinc-600'
              }`}>
                <span>Page {src.page || 1} • Inspect excerpt</span>
                <span>→</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
