import React, { useState, useEffect, useCallback } from 'react';
import Sidebar from './Sidebar';
import ChatWindow from './ChatWindow';
import ChatInput from './ChatInput';
import DocumentModal from './DocumentModal';
import SettingsModal from './SettingsModal';
import Profile from './Profile';
import Toast from './Toast';
import { uploadPdfReport, sendQueryStream, logout, getProfile, getDependents, getUserDocuments, getDocumentChats } from '../services/api';
import { useNavigate } from 'react-router-dom';

// ── Theme helpers ──────────────────────────────────────────
function getSystemTheme() {
  if (typeof window === 'undefined') return 'dark';
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

function getInitialTheme() {
  try {
    const stored = localStorage.getItem('mediskye_theme');
    if (stored === 'dark' || stored === 'light') return stored;
  } catch {}
  return getSystemTheme();
}

function applyThemeToDOM(theme) {
  if (theme === 'dark') {
    document.documentElement.classList.add('dark');
  } else {
    document.documentElement.classList.remove('dark');
  }
}

export default function ChatApp() {
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  const [sessionId, setSessionId] = useState(() => {
    return localStorage.getItem('mediskye_session_id') || null;
  });

  // ── Patient Context & User State ──
  const [currentUser, setCurrentUser] = useState(null);
  const [dependents, setDependents] = useState([]);
  const [selectedPatientId, setSelectedPatientId] = useState(() => {
    return localStorage.getItem('mediskye_patient_id') || 'self';
  });
  const [profileInitialTab, setProfileInitialTab] = useState('profile');

  // ── Theme state: auto-detects system, persists choice ──
  const [darkMode, setDarkMode] = useState(() => getInitialTheme() === 'dark');
  const [language, setLanguage] = useState('English');

  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [isProfileOpen, setIsProfileOpen] = useState(false);
  const [selectedSource, setSelectedSource] = useState(null);

  const [activePdf, setActivePdf] = useState(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [toasts, setToasts] = useState([]);

  // Load User & Dependents on Mount
  const refreshPatientContext = useCallback(async () => {
    try {
      const [userRes, depsRes] = await Promise.all([
        getProfile().catch(() => null),
        getDependents().catch(() => []),
      ]);

      if (userRes) {
        setCurrentUser(userRes);
        if (userRes.language_preference) {
          setLanguage(userRes.language_preference);
        }
      }
      if (depsRes) {
        setDependents(depsRes);
      }
    } catch (e) {
      console.error('Failed to load patient context:', e);
    }
  }, []);

  useEffect(() => {
    refreshPatientContext();
  }, [refreshPatientContext]);

  // Restore conversations from localStorage with account isolation
  const [conversations, setConversations] = useState(() => {
    try {
      const saved = localStorage.getItem('mediskye_conversations');
      if (saved) {
        const parsed = JSON.parse(saved);
        if (Array.isArray(parsed) && parsed.length > 0) {
          return parsed;
        }
      }
    } catch (e) {
      console.error('Failed to load conversations from localStorage:', e);
    }
    return [
      { id: sessionId, title: 'Current Consultation', messages: [], pdf: null },
    ];
  });

  // Keep conversations synchronized in localStorage
  useEffect(() => {
    try {
      localStorage.setItem('mediskye_conversations', JSON.stringify(conversations));
      if (currentUser?.id) {
        localStorage.setItem(`mediskye_conversations_${currentUser.id}`, JSON.stringify(conversations));
      }
    } catch (e) {
      console.error('Failed to save conversations to localStorage:', e);
    }
  }, [conversations, currentUser]);

  // Account switch isolation & pre-linked document loading: When currentUser loads, restore their specific conversations or fetch pre-linked documents
  useEffect(() => {
    if (currentUser?.id) {
      const lastUser = localStorage.getItem('mediskye_last_active_user');
      const isSwitch = lastUser && lastUser !== currentUser.id;
      const userSaved = localStorage.getItem(`mediskye_conversations_${currentUser.id}`);

      if (isSwitch || !userSaved) {
        if (userSaved) {
          try {
            const parsed = JSON.parse(userSaved);
            if (Array.isArray(parsed) && parsed.length > 0) {
              setConversations(parsed);
              setSessionId(parsed[0].id);
              setActivePdf(parsed[0].pdf || null);
            }
          } catch (e) {}
        } else {
          // Check backend for pre-linked documents
          getUserDocuments().then(async (docs) => {
            if (docs && docs.length > 0) {
              const doc = docs[0];
              const chats = await getDocumentChats(doc.id).catch(() => []);
              const formattedMessages = chats.map((c) => ({
                id: c.id,
                sender: c.role === 'ai' ? 'assistant' : 'user',
                text: c.message,
                timestamp: c.created_at ? new Date(c.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '',
              }));

              const prelinkedPdf = { name: doc.filename, size: 8192 };
              const prelinkedConv = {
                id: doc.id,
                document_id: doc.id,
                patient_id: doc.dependent_id || 'self',
                title: doc.filename.replace(/\.pdf$/i, ''),
                messages: formattedMessages,
                pdf: prelinkedPdf,
              };

              setConversations([prelinkedConv]);
              setSessionId(doc.id);
              setActivePdf(prelinkedPdf);
            } else {
              // Fresh account without documents
              const freshId = 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
                const r = (Math.random() * 16) | 0;
                return (c === 'x' ? r : (r & 0x3) | 0x8).toString(16);
              });
              setSessionId(freshId);
              setActivePdf(null);
              setConversations([{ id: freshId, title: 'Current Consultation', messages: [], pdf: null }]);
            }
          }).catch(() => {
            const freshId = 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
              const r = (Math.random() * 16) | 0;
              return (c === 'x' ? r : (r & 0x3) | 0x8).toString(16);
            });
            setSessionId(freshId);
            setActivePdf(null);
            setConversations([{ id: freshId, title: 'Current Consultation', messages: [], pdf: null }]);
          });
        }
      }
      localStorage.setItem('mediskye_last_active_user', currentUser.id);
    }
  }, [currentUser]);

  // ── Apply theme to DOM and persist ──
  useEffect(() => {
    const theme = darkMode ? 'dark' : 'light';
    applyThemeToDOM(theme);
    localStorage.setItem('mediskye_theme', theme);
  }, [darkMode]);

  // ── Listen for OS theme changes (if user hasn't manually overridden) ──
  useEffect(() => {
    const mq = window.matchMedia('(prefers-color-scheme: dark)');
    const handler = (e) => {
      const stored = localStorage.getItem('mediskye_theme');
      if (!stored) {
        setDarkMode(e.matches);
      }
    };
    mq.addEventListener('change', handler);
    return () => mq.removeEventListener('change', handler);
  }, []);

  // Restore active PDF state if present in current chat
  useEffect(() => {
    const current = conversations.find((c) => c.id === sessionId);
    if (current && current.pdf) {
      setActivePdf(current.pdf);
    }
  }, [sessionId, conversations]);

  const currentChat = conversations.find((c) => c.id === sessionId) || {
    id: sessionId,
    title: 'Current Consultation',
    messages: [],
  };

  const messages = currentChat.messages || [];

  const showToast = (type, title, message) => {
    const id = Date.now();
    setToasts((prev) => [...prev, { id, type, title, message }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 4500);
  };

  const dismissToast = (id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  };

  const handlePatientSelect = (patientId) => {
    setSelectedPatientId(patientId);
    localStorage.setItem('mediskye_patient_id', patientId);
    const dep = dependents.find(d => d.id === patientId);
    if (dep) {
      showToast('info', 'Patient Context Switched', `Clinical lens updated to ${dep.full_name} (${dep.relationship}).`);
    } else {
      showToast('info', 'Patient Context Switched', `Clinical lens updated to ${currentUser?.full_name || 'Your profile'}.`);
    }
  };

  const handleOpenDependents = () => {
    setProfileInitialTab('dependents');
    setIsProfileOpen(true);
  };

  const handleOpenProfile = () => {
    setProfileInitialTab('profile');
    setIsProfileOpen(true);
  };

  const handleAttachFile = async (file) => {
    if (!file) return;

    if (file.type !== 'application/pdf' && !file.name.endsWith('.pdf')) {
      showToast('error', 'Invalid File Format', 'Please upload a valid PDF document.');
      return;
    }

    const maxMb = 50;
    if (file.size > maxMb * 1024 * 1024) {
      showToast('error', 'File Too Large', `Maximum allowed PDF size is ${maxMb}MB.`);
      return;
    }

    showToast('info', 'Uploading PDF Report', 'Extracting text and creating vector embeddings...');
    setIsGenerating(true);

    const pdfMeta = { name: file.name, size: file.size };

    try {
      const data = await uploadPdfReport(file, selectedPatientId);
      const newDocId = data.document_id;
      setActivePdf(pdfMeta);
      showToast('success', 'Report Processed', 'PDF indexed successfully. You can now ask questions or view Lab Metrics.');

      setConversations((prev) =>
        prev.map((c) =>
          c.id === sessionId
            ? {
                ...c,
                document_id: newDocId,
                patient_id: selectedPatientId,
                title: file.name.replace(/\.pdf$/i, ''),
                pdf: pdfMeta,
              }
            : c
        )
      );
    } catch (err) {
      showToast('error', 'Upload Failed', err.message);
    } finally {
      setIsGenerating(false);
    }
  };

  const handleSendMessage = async (userQuery) => {
    if (!userQuery || isGenerating) return;

    const userMsgObj = {
      id: Date.now(),
      sender: 'user',
      text: userQuery,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    setConversations((prev) =>
      prev.map((c) =>
        c.id === sessionId
          ? {
              ...c,
              title: c.messages.length === 0 ? userQuery.slice(0, 30) + '...' : c.title,
              messages: [...c.messages, userMsgObj],
            }
          : c
      )
    );

    setIsGenerating(true);

    try {
      let chatDocId = null;
      let chatPatientId = selectedPatientId;
      setConversations((prev) => {
        const chatObj = prev.find(c => c.id === sessionId);
        chatDocId = chatObj?.document_id || null;
        if (chatObj?.patient_id) chatPatientId = chatObj.patient_id;
        return prev;
      });

      await new Promise(r => setTimeout(r, 0));

      if (!chatDocId) {
        const chatObj = conversations.find(c => c.id === sessionId);
        chatDocId = chatObj?.document_id;
        if (chatObj?.patient_id) chatPatientId = chatObj.patient_id;
      }

      if (!chatDocId) {
        throw new Error('Please upload a PDF document first before asking questions.');
      }

      const assistantMsgObj = {
        id: Date.now() + 1,
        sender: 'assistant',
        text: '',
        sources: [],
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };

      setConversations((prev) =>
        prev.map((c) =>
          c.id === sessionId
            ? { ...c, messages: [...c.messages, assistantMsgObj] }
            : c
        )
      );

      await sendQueryStream(userQuery, chatDocId, language, (chunk) => {
        setConversations((prev) =>
          prev.map((c) => {
            if (c.id !== sessionId) return c;
            const newMsgs = [...c.messages];
            const lastMsg = { ...newMsgs[newMsgs.length - 1] };

            if (chunk.sources) {
              lastMsg.sources = chunk.sources;
            } else if (chunk.specialists) {
              lastMsg.specialists = chunk.specialists;
            } else if (chunk.chunk) {
              lastMsg.text += chunk.chunk;
            } else if (chunk.error) {
              lastMsg.text = `⚠️ **Error:** ${chunk.error}`;
            }

            newMsgs[newMsgs.length - 1] = lastMsg;
            return { ...c, messages: newMsgs };
          })
        );
      }, chatPatientId);

    } catch (err) {
      showToast('error', 'Query Error', err.message);
      const errorMsgObj = {
        id: Date.now() + 1,
        sender: 'assistant',
        text: `⚠️ **Error:** ${err.message}`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };
      setConversations((prev) =>
        prev.map((c) =>
          c.id === sessionId ? { ...c, messages: [...c.messages, errorMsgObj] } : c
        )
      );
    } finally {
      setIsGenerating(false);
    }
  };

  const handleRegenerate = () => {
    const lastUserMsg = [...messages].reverse().find((m) => m.sender === 'user');
    if (lastUserMsg) {
      handleSendMessage(lastUserMsg.text);
    }
  };

  const handleNewChat = () => {
    const newId = 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
      const r = (Math.random() * 16) | 0;
      return (c === 'x' ? r : (r & 0x3) | 0x8).toString(16);
    });
    setSessionId(newId);
    localStorage.setItem('mediskye_session_id', newId);
    setActivePdf(null);
    setIsProfileOpen(false);
    setConversations((prev) => [
      { id: newId, title: 'New Consultation', messages: [], pdf: null, patient_id: selectedPatientId },
      ...prev,
    ]);
    showToast('info', 'New Conversation Started');
  };

  const handleSelectChat = (id) => {
    setSessionId(id);
    localStorage.setItem('mediskye_session_id', id);
    const chat = conversations.find((c) => c.id === id);
    if (chat) {
      setActivePdf(chat.pdf || null);
      if (chat.patient_id) {
        setSelectedPatientId(chat.patient_id);
      }
    }
    setIsProfileOpen(false);
  };

  const handleClearAllChats = () => {
    const newId = 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
      const r = (Math.random() * 16) | 0;
      return (c === 'x' ? r : (r & 0x3) | 0x8).toString(16);
    });
    setSessionId(newId);
    localStorage.setItem('mediskye_session_id', newId);
    localStorage.removeItem('mediskye_conversations');
    setActivePdf(null);
    setConversations([{ id: newId, title: 'New Consultation', messages: [], pdf: null, patient_id: selectedPatientId }]);
    showToast('info', 'Chat History Cleared');
  };

  const handleDeleteChat = (id) => {
    if (window.confirm("Are you sure you want to delete this chat?")) {
      setConversations((prev) => {
        const newConversations = prev.filter((c) => c.id !== id);
        if (newConversations.length === 0) {
          const newId = 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
            const r = (Math.random() * 16) | 0;
            return (c === 'x' ? r : (r & 0x3) | 0x8).toString(16);
          });
          setSessionId(newId);
          localStorage.setItem('mediskye_session_id', newId);
          setActivePdf(null);
          return [{ id: newId, title: 'New Consultation', messages: [], pdf: null, patient_id: selectedPatientId }];
        }

        if (id === sessionId) {
          const nextChat = newConversations[0];
          setSessionId(nextChat.id);
          localStorage.setItem('mediskye_session_id', nextChat.id);
          setActivePdf(nextChat.pdf || null);
        }
        return newConversations;
      });
      showToast('info', 'Chat Deleted');
    }
  };

  const handleSetDarkMode = useCallback((val) => {
    const next = typeof val === 'function' ? val(darkMode) : val;
    setDarkMode(next);
    localStorage.setItem('mediskye_theme', next ? 'dark' : 'light');
  }, [darkMode]);

  return (
    <div className={`flex h-screen w-screen overflow-hidden transition-colors duration-200 ${
      darkMode ? 'bg-black text-slate-100' : 'bg-zinc-50 text-zinc-900'
    }`}>
      <Sidebar
        isOpen={isSidebarOpen}
        onToggle={() => setIsSidebarOpen(!isSidebarOpen)}
        conversations={conversations}
        activeSessionId={sessionId}
        onSelectChat={handleSelectChat}
        onDeleteChat={handleDeleteChat}
        onNewChat={handleNewChat}
        onOpenSettings={() => setIsSettingsOpen(true)}
        onOpenProfile={handleOpenProfile}
        darkMode={darkMode}
        setDarkMode={handleSetDarkMode}
        activePdf={activePdf}
        language={language}
        setLanguage={setLanguage}
        onLogout={handleLogout}
        currentUser={currentUser}
      />

      <main className={`flex-1 flex flex-col h-full overflow-hidden relative transition-colors duration-200 ${
        darkMode ? 'bg-black' : 'bg-zinc-50'
      }`}>
        <ChatWindow
          messages={messages}
          isGenerating={isGenerating}
          onRegenerate={handleRegenerate}
          onSelectSource={(source) => setSelectedSource(source)}
          onSelectSampleQuery={handleSendMessage}
          onAttachFile={handleAttachFile}
          activePdf={activePdf}
          documentId={currentChat.document_id}
          showToast={showToast}
          darkMode={darkMode}
          currentUser={currentUser}
          dependents={dependents}
          selectedPatientId={selectedPatientId}
          onSelectPatient={handlePatientSelect}
          onOpenDependents={handleOpenDependents}
        />

        <ChatInput
          onSendMessage={handleSendMessage}
          onAttachFile={handleAttachFile}
          activeFile={activePdf}
          onRemoveFile={() => setActivePdf(null)}
          isGenerating={isGenerating}
          onStopGeneration={() => setIsGenerating(false)}
          showToast={showToast}
          darkMode={darkMode}
          currentUser={currentUser}
          dependents={dependents}
          selectedPatientId={selectedPatientId}
          onSelectPatient={handlePatientSelect}
          onOpenDependents={handleOpenDependents}
        />
      </main>

      <DocumentModal source={selectedSource} onClose={() => setSelectedSource(null)} />

      <SettingsModal
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
        darkMode={darkMode}
        setDarkMode={handleSetDarkMode}
        onClearAllChats={handleClearAllChats}
        showToast={showToast}
      />

      {isProfileOpen && (
        <Profile
          onClose={() => setIsProfileOpen(false)}
          showToast={showToast}
          darkMode={darkMode}
          initialTab={profileInitialTab}
          onProfileUpdated={refreshPatientContext}
        />
      )}

      <Toast toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
}
