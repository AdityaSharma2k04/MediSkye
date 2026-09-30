import React, { useState } from 'react';
import {
  Stethoscope,
  Copy,
  Check,
  Volume2,
  VolumeX,
  ThumbsUp,
  ThumbsDown,
  RotateCcw,
  Share2,
  AlertTriangle,
  User,
  ShieldCheck,
} from 'lucide-react';
import RagSourcesPanel from './RagSourcesPanel';
import { speakText, stopSpeaking } from '../services/speech';

export default function ChatMessage({ message, onRegenerate, onSelectSource, showToast, darkMode }) {
  const [copied, setCopied] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const [liked, setLiked] = useState(null);

  const isUser = message.sender === 'user';

  const handleCopy = () => {
    navigator.clipboard.writeText(message.text);
    setCopied(true);
    if (showToast) showToast('success', 'Copied to clipboard');
    setTimeout(() => setCopied(false), 2000);
  };

  const handleSpeak = () => {
    if (speaking) {
      stopSpeaking();
      setSpeaking(false);
    } else {
      setSpeaking(true);
      speakText(message.text, () => setSpeaking(false));
    }
  };

  const handleShare = () => {
    if (navigator.share) {
      navigator.share({ title: 'MediSkye Explanation', text: message.text });
    } else {
      navigator.clipboard.writeText(message.text);
      if (showToast) showToast('info', 'Share link copied');
    }
  };

  if (isUser) {
    return (
      <div className="flex justify-end mb-5 animate-fade-in group">
        <div className="flex items-start gap-3 max-w-[85%] sm:max-w-[75%] flex-row-reverse">
          <div className={`w-7 h-7 rounded-full flex items-center justify-center font-semibold text-xs shrink-0 shadow-sm ${
            darkMode ? 'bg-zinc-100 text-zinc-900' : 'bg-zinc-900 text-white'
          }`}>
            <User className="w-3.5 h-3.5" />
          </div>
          <div className={`rounded-2xl rounded-tr-sm px-4 py-3 text-sm leading-relaxed shadow-sm ${
            darkMode ? 'bg-zinc-100 text-zinc-900' : 'bg-zinc-900 text-white'
          }`}>
            {message.text}
          </div>
        </div>
      </div>
    );
  }

  const renderFormattedText = (text) => {
    if (!text) return null;

    // Hide the abnormal_flags JSON block from the user interface
    const cleanText = text.replace(/```json\s*\{.*"abnormal_flags"[\s\S]*?\}\s*```/is, '');

    const lines = cleanText.split('\n');
    let inList = false;
    let listItems = [];

    const elements = [];

    lines.forEach((line, idx) => {
      let trimmed = line.trim();

      if (trimmed.startsWith('### ')) {
        elements.push(
          <h3 key={idx} className={`font-semibold text-base mt-3 mb-1.5 ${darkMode ? 'text-zinc-100' : 'text-zinc-900'}`}>
            {trimmed.replace('### ', '')}
          </h3>
        );
        return;
      }

      if (trimmed.startsWith('## ')) {
        elements.push(
          <h2 key={idx} className={`font-bold text-lg mt-4 mb-2 ${darkMode ? 'text-zinc-100' : 'text-zinc-900'}`}>
            {trimmed.replace('## ', '')}
          </h2>
        );
        return;
      }

      if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
        const content = trimmed.substring(2);
        listItems.push(
          <li key={idx} className="mb-1">
            {parseBoldItalic(content)}
          </li>
        );
        inList = true;
        return;
      }

      if (inList) {
        elements.push(
          <ul key={`ul-${idx}`} className={`list-disc list-inside space-y-1 my-2 ${darkMode ? 'text-zinc-300' : 'text-zinc-700'}`}>
            {listItems}
          </ul>
        );
        inList = false;
        listItems = [];
      }

      if (trimmed.startsWith('**Disclaimer:**') || trimmed.startsWith('Disclaimer:')) {
        elements.push(
          <div key={idx} className={`mt-4 p-3 rounded-xl text-xs flex items-start gap-2 border ${
            darkMode
              ? 'bg-zinc-800/60 border-zinc-700 text-zinc-300'
              : 'bg-zinc-50 border-zinc-200 text-zinc-700'
          }`}>
            <AlertTriangle className={`w-3.5 h-3.5 shrink-0 mt-0.5 ${darkMode ? 'text-zinc-500' : 'text-zinc-400'}`} />
            <div>
              <strong className="font-medium">Medical Disclaimer:</strong> {trimmed.replace(/\*\*Disclaimer:\*\*/, '').replace(/Disclaimer:/, '')}
            </div>
          </div>
        );
        return;
      }

      if (trimmed.length > 0) {
        elements.push(
          <p key={idx} className={`mb-2 leading-relaxed ${darkMode ? 'text-zinc-200' : 'text-zinc-800'}`}>
            {parseBoldItalic(trimmed)}
          </p>
        );
      }
    });

    if (inList) {
      elements.push(
        <ul key="ul-end" className={`list-disc list-inside space-y-1 my-2 ${darkMode ? 'text-zinc-300' : 'text-zinc-700'}`}>
          {listItems}
        </ul>
      );
    }

    return elements;
  };

  const parseBoldItalic = (str) => {
    const parts = str.split(/(\*\*.*?\*\*)/g);
    return parts.map((part, i) => {
      if (part.startsWith('**') && part.endsWith('**')) {
        return <strong key={i} className={`font-semibold ${darkMode ? 'text-zinc-100' : 'text-zinc-900'}`}>{part.slice(2, -2)}</strong>;
      }
      return part;
    });
  };

  // Common button styles for the action bar
  const actionBtn = `p-1.5 rounded-lg transition-colors ${
    darkMode ? 'hover:text-zinc-200 hover:bg-zinc-800' : 'hover:text-zinc-700 hover:bg-zinc-100'
  }`;
  const actionBtnActive = `p-1.5 rounded-lg ${
    darkMode ? 'text-zinc-100 bg-zinc-800' : 'text-zinc-900 bg-zinc-100'
  }`;

  return (
    <div className="flex justify-start mb-5 animate-fade-in group">
      <div className="flex items-start gap-3 max-w-[92%] sm:max-w-[85%]">
        <div className={`w-7 h-7 rounded-full flex items-center justify-center font-bold text-xs shrink-0 shadow-sm mt-0.5 ${
          darkMode ? 'bg-zinc-100 text-zinc-900' : 'bg-zinc-900 text-white'
        }`}>
          <Stethoscope className="w-3.5 h-3.5" />
        </div>

        <div className={`flex-1 rounded-2xl rounded-tl-sm p-4 sm:p-5 shadow-sm text-sm border ${
          darkMode
            ? 'bg-zinc-900 border-zinc-800'
            : 'bg-white border-zinc-200'
        }`}>
          <div className={`flex items-center justify-between pb-2 mb-2 border-b text-xs ${
            darkMode ? 'border-zinc-800 text-zinc-400' : 'border-zinc-100 text-zinc-400'
          }`}>
            <div className={`flex items-center gap-1.5 font-medium ${darkMode ? 'text-zinc-300' : 'text-zinc-700'}`}>
              <span>MediSkye AI</span>
              <ShieldCheck className={`w-3.5 h-3.5 ${darkMode ? 'text-zinc-400' : 'text-zinc-500'}`} />
              <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium border ${
                darkMode
                  ? 'bg-zinc-800 text-zinc-400 border-zinc-700'
                  : 'bg-zinc-100 text-zinc-600 border-zinc-200'
              }`}>Gemini Flash RAG</span>
            </div>
            <span>{message.timestamp || 'Just now'}</span>
          </div>

          <div className={`prose max-w-none ${darkMode ? 'prose-invert text-zinc-200' : 'text-zinc-800'}`}>
            {renderFormattedText(message.text)}
          </div>

          {message.sources && message.sources.length > 0 && (
            <RagSourcesPanel sources={message.sources} onSelectSource={onSelectSource} darkMode={darkMode} />
          )}

          {message.specialists && message.specialists.length > 0 && (
            <div className={`mt-4 rounded-xl p-4 text-sm shadow-sm border ${
              darkMode ? 'bg-zinc-900 border-zinc-800' : 'bg-zinc-50 border-zinc-200'
            }`}>
              <div className={`flex items-center gap-2 mb-2 font-semibold ${darkMode ? 'text-white' : 'text-zinc-900'}`}>
                <Stethoscope className={`w-4 h-4 ${darkMode ? 'text-zinc-400' : 'text-zinc-500'}`} />
                Recommended Next Steps
              </div>
              <p className={`text-xs mb-4 leading-relaxed ${darkMode ? 'text-zinc-400' : 'text-zinc-500'}`}>
                Based on the abnormal findings in your query or report, you may want to consult the following specialists.
                <strong className={`font-medium ml-1 ${darkMode ? 'text-zinc-300' : 'text-zinc-700'}`}>Disclaimer: These are algorithmic suggestions, not definitive medical referrals. Always consult your primary care physician.</strong>
              </p>
              <div className="space-y-2">
                {message.specialists.map((sp, idx) => (
                  <div key={idx} className={`p-3 rounded-lg flex flex-col sm:flex-row justify-between sm:items-center gap-2 transition-colors border ${
                    darkMode
                      ? 'bg-[#121212] border-zinc-800 hover:border-zinc-700'
                      : 'bg-white border-zinc-200 hover:border-zinc-400'
                  }`}>
                    <div>
                      <div className={`font-medium text-sm ${darkMode ? 'text-zinc-100' : 'text-zinc-900'}`}>{sp.name}</div>
                      <div className={`text-xs mt-0.5 ${darkMode ? 'text-zinc-400' : 'text-zinc-500'}`}>
                        <span className={darkMode ? 'text-zinc-300' : 'text-zinc-700'}>{sp.specialty}</span> • Flags: {sp.matched_flags.join(", ")}
                      </div>
                    </div>
                    <div className={`text-[11px] font-mono px-2 py-1 rounded border ${
                      darkMode
                        ? 'text-zinc-400 bg-zinc-900/80 border-zinc-800'
                        : 'text-zinc-600 bg-zinc-50 border-zinc-200'
                    }`}>
                      {sp.contact_info}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className={`mt-4 pt-3 border-t flex items-center justify-between text-xs ${
            darkMode ? 'border-zinc-800/80 text-zinc-400' : 'border-zinc-100 text-zinc-400'
          }`}>
            <div className="flex items-center gap-1">
              <button
                onClick={handleCopy}
                title="Copy response"
                className={`${actionBtn} flex items-center gap-1`}
              >
                {copied ? <Check className={`w-3.5 h-3.5 ${darkMode ? 'text-zinc-100' : 'text-zinc-900'}`} /> : <Copy className="w-3.5 h-3.5" />}
                <span className="hidden sm:inline">{copied ? 'Copied' : 'Copy'}</span>
              </button>

              <button
                onClick={handleSpeak}
                title={speaking ? 'Stop speech' : 'Read response aloud'}
                className={`${speaking ? actionBtnActive : actionBtn} flex items-center gap-1`}
              >
                {speaking ? <VolumeX className="w-3.5 h-3.5" /> : <Volume2 className="w-3.5 h-3.5" />}
                <span className="hidden sm:inline">{speaking ? 'Stop' : 'Listen'}</span>
              </button>

              <button
                onClick={() => setLiked(liked === true ? null : true)}
                title="Helpful response"
                className={liked === true ? actionBtnActive : actionBtn}
              >
                <ThumbsUp className="w-3.5 h-3.5" />
              </button>

              <button
                onClick={() => setLiked(liked === false ? null : false)}
                title="Not helpful"
                className={liked === false ? actionBtnActive : actionBtn}
              >
                <ThumbsDown className="w-3.5 h-3.5" />
              </button>

              <button
                onClick={handleShare}
                title="Share explanation"
                className={actionBtn}
              >
                <Share2 className="w-3.5 h-3.5" />
              </button>
            </div>

            {onRegenerate && (
              <button
                onClick={onRegenerate}
                title="Regenerate AI response"
                className={`${actionBtn} flex items-center gap-1 font-medium`}
              >
                <RotateCcw className="w-3.5 h-3.5" />
                <span className="hidden sm:inline">Regenerate</span>
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
