/**
 * MediSkye AI - Modern Minimalistic Frontend
 * ES Module Application Engine
 */

(function () {
  'use strict';

  // Config & State
  const API_BASE = window.location.origin.includes('8000')
    ? window.location.origin
    : 'http://127.0.0.1:8000';

  let sessionId = localStorage.getItem('mediskye_session_id');
  if (!sessionId) {
    sessionId = generateUUID();
    localStorage.setItem('mediskye_session_id', sessionId);
  }

  let selectedFile = null;
  let isPdfUploaded = false;
  let isProcessing = false;

  // DOM Elements
  const dropzone = document.getElementById('dropzone');
  const fileInput = document.getElementById('fileInput');
  const filePreview = document.getElementById('filePreview');
  const fileName = document.getElementById('fileName');
  const fileMeta = document.getElementById('fileMeta');
  const btnRemoveFile = document.getElementById('btnRemoveFile');
  const btnProcessPdf = document.getElementById('btnProcessPdf');

  const chatMessages = document.getElementById('chatMessages');
  const chatForm = document.getElementById('chatForm');
  const chatInput = document.getElementById('chatInput');
  const btnSendMessage = document.getElementById('btnSendMessage');
  const chatSkeleton = document.getElementById('chatSkeleton');
  const btnClearChat = document.getElementById('btnClearChat');

  const statusPill = document.getElementById('statusPill');
  const statusText = document.getElementById('statusText');
  const toastContainer = document.getElementById('toastContainer');

  // Initialization
  document.addEventListener('DOMContentLoaded', () => {
    checkApiHealth();
    setupDropzone();
    setupChatForm();
    setupSampleChips();
  });

  // UUID Generator
  function generateUUID() {
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
      const r = (Math.random() * 16) | 0;
      const v = c === 'x' ? r : (r & 0x3) | 0x8;
      return v.toString(16);
    });
  }

  // Health Check
  async function checkApiHealth() {
    try {
      const res = await fetch(`${API_BASE}/docs`, { method: 'HEAD' });
      if (res.ok) {
        statusText.textContent = 'API Connected';
      } else {
        statusText.textContent = 'API Reaching...';
      }
    } catch (err) {
      statusText.textContent = 'API Offline';
      statusPill.querySelector('.status-dot').style.backgroundColor = '#EF4444';
    }
  }

  // Dropzone Setup & Drag & Drop
  function setupDropzone() {
    ['dragenter', 'dragover'].forEach((eventName) => {
      dropzone.addEventListener(eventName, (e) => {
        e.preventDefault();
        e.stopPropagation();
        dropzone.classList.add('drag-over');
      });
    });

    ['dragleave', 'drop'].forEach((eventName) => {
      dropzone.addEventListener(eventName, (e) => {
        e.preventDefault();
        e.stopPropagation();
        dropzone.classList.remove('drag-over');
      });
    });

    dropzone.addEventListener('drop', (e) => {
      const dt = e.dataTransfer;
      const files = dt.files;
      if (files && files.length > 0) {
        handleFileSelection(files[0]);
      }
    });

    fileInput.addEventListener('change', (e) => {
      if (e.target.files && e.target.files.length > 0) {
        handleFileSelection(e.target.files[0]);
      }
    });

    btnRemoveFile.addEventListener('click', clearFileSelection);
    btnProcessPdf.addEventListener('click', uploadPdfFile);
  }

  function handleFileSelection(file) {
    if (file.type !== 'application/pdf' && !file.name.endsWith('.pdf')) {
      showToast('error', 'Invalid File Type', 'Please upload a PDF document.');
      return;
    }

    const maxSizeMb = 10;
    if (file.size > maxSizeMb * 1024 * 1024) {
      showToast('error', 'File Too Large', `File size must be less than ${maxSizeMb}MB.`);
      return;
    }

    selectedFile = file;
    fileName.textContent = file.name;
    fileMeta.textContent = `${(file.size / (1024 * 1024)).toFixed(2)} MB • PDF`;

    dropzone.classList.add('hidden');
    filePreview.classList.remove('hidden');
    btnProcessPdf.disabled = false;
  }

  function clearFileSelection() {
    selectedFile = null;
    isPdfUploaded = false;
    fileInput.value = '';

    dropzone.classList.remove('hidden');
    filePreview.classList.add('hidden');
    btnProcessPdf.disabled = true;
  }

  // Upload PDF API Handler
  async function uploadPdfFile() {
    if (!selectedFile || isProcessing) return;

    isProcessing = true;
    btnProcessPdf.disabled = true;
    btnProcessPdf.innerHTML = `
      <svg class="spin" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M21 12a9 9 0 1 1-6.219-8.56"/>
      </svg>
      Processing Report...
    `;

    showToast('info', 'Indexing Report', 'Extracting text & creating vector embeddings...');

    const formData = new FormData();
    formData.append('file', selectedFile);

    try {
      const response = await fetch(`${API_BASE}/upload`, {
        method: 'POST',
        headers: {
          'X-Session-ID': sessionId,
        },
        body: formData,
      });

      const data = await response.json();

      if (response.ok) {
        isPdfUploaded = true;
        showToast('success', 'Report Ready', 'Your report has been successfully indexed.');
        
        appendAssistantMessage(
          `✅ <strong>"${selectedFile.name}"</strong> uploaded and indexed successfully!<br>You can now ask questions about your test results, abnormal values, or medical recommendations.`
        );
      } else {
        const errorMsg = data.detail || 'Failed to extract text from PDF.';
        showToast('error', 'Upload Error', errorMsg);
      }
    } catch (err) {
      showToast('error', 'Network Error', 'Could not reach MediSkye backend server.');
      console.error(err);
    } finally {
      isProcessing = false;
      btnProcessPdf.disabled = false;
      btnProcessPdf.innerHTML = `
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="10"/>
          <polyline points="12 6 12 12 16 14"/>
        </svg>
        Re-Index Report
      `;
    }
  }

  // Chat Form & Input Handler
  function setupChatForm() {
    // Auto-expand textarea
    chatInput.addEventListener('input', () => {
      chatInput.style.height = 'auto';
      chatInput.style.height = `${Math.min(chatInput.scrollHeight, 140)}px`;
    });

    chatInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        submitQuery();
      }
    });

    chatForm.addEventListener('submit', (e) => {
      e.preventDefault();
      submitQuery();
    });

    btnClearChat.addEventListener('click', () => {
      chatMessages.innerHTML = `
        <div class="message message-assistant">
          <div class="avatar avatar-assistant">AI</div>
          <div class="bubble bubble-assistant">
            <p><strong>Chat history cleared.</strong></p>
            <p>Ask a question about your uploaded medical report to start a new discussion.</p>
          </div>
        </div>
      `;
      showToast('info', 'Chat Cleared', 'Conversation history reset.');
    });
  }

  async function submitQuery() {
    const text = chatInput.value.trim();
    if (!text || isProcessing) return;

    if (!isPdfUploaded) {
      showToast('info', 'PDF Required', 'Please upload and index a PDF report first.');
    }

    appendUserMessage(text);
    chatInput.value = '';
    chatInput.style.height = 'auto';

    isProcessing = true;
    showSkeleton();

    try {
      const response = await fetch(`${API_BASE}/query`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Session-ID': sessionId,
        },
        body: JSON.stringify({
          session_id: sessionId,
          query: text,
        }),
      });

      const data = await response.json();
      hideSkeleton();

      if (response.ok && data.response) {
        appendAssistantMessage(formatMarkdown(data.response));
      } else if (data.error) {
        showToast('error', 'Query Error', data.error);
        appendAssistantMessage(`⚠️ <em>${data.error}</em>`);
      } else {
        showToast('error', 'Error', 'Unexpected response from server.');
      }
    } catch (err) {
      hideSkeleton();
      showToast('error', 'Network Error', 'Failed to communicate with AI server.');
      console.error(err);
    } finally {
      isProcessing = false;
    }
  }

  // Sample Chips Setup
  function setupSampleChips() {
    const chips = document.querySelectorAll('.chip-btn');
    chips.forEach((chip) => {
      chip.addEventListener('click', () => {
        const queryText = chip.getAttribute('data-query');
        if (queryText) {
          chatInput.value = queryText;
          chatInput.focus();
          submitQuery();
        }
      });
    });
  }

  // Render Functions
  function appendUserMessage(text) {
    const msgDiv = document.createElement('div');
    msgDiv.className = 'message message-user';
    msgDiv.innerHTML = `
      <div class="avatar avatar-user">You</div>
      <div class="bubble bubble-user">${escapeHtml(text)}</div>
    `;
    chatMessages.appendChild(msgDiv);
    scrollToBottom();
  }

  function appendAssistantMessage(htmlContent) {
    const msgDiv = document.createElement('div');
    msgDiv.className = 'message message-assistant';
    msgDiv.innerHTML = `
      <div class="avatar avatar-assistant">AI</div>
      <div class="bubble bubble-assistant">${htmlContent}</div>
    `;
    chatMessages.appendChild(msgDiv);
    scrollToBottom();
  }

  function showSkeleton() {
    chatSkeleton.classList.remove('hidden');
    scrollToBottom();
  }

  function hideSkeleton() {
    chatSkeleton.classList.add('hidden');
  }

  function scrollToBottom() {
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  // Format Simple Markdown (bold, lists, code, line breaks)
  function formatMarkdown(text) {
    if (!text) return '';
    let formatted = escapeHtml(text);

    // Bold text **word**
    formatted = formatted.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    
    // Italic text *word*
    formatted = formatted.replace(/\*(.*?)\*/g, '<em>$1</em>');

    // Bullet points
    const lines = formatted.split('\n');
    let inList = false;
    let result = '';

    lines.forEach((line) => {
      const trimmed = line.trim();
      if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
        if (!inList) {
          result += '<ul>';
          inList = true;
        }
        result += `<li>${trimmed.substring(2)}</li>`;
      } else {
        if (inList) {
          result += '</ul>';
          inList = false;
        }
        if (trimmed.length > 0) {
          result += `<p>${trimmed}</p>`;
        }
      }
    });

    if (inList) result += '</ul>';

    return result;
  }

  function escapeHtml(str) {
    return str
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  // Toast Notification Engine
  function showToast(type, title, message) {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    
    let iconSvg = '';
    if (type === 'success') {
      iconSvg = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#10B981" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>';
    } else if (type === 'error') {
      iconSvg = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#EF4444" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>';
    } else {
      iconSvg = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#2563EB" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>';
    }

    toast.innerHTML = `
      <div class="toast-icon">${iconSvg}</div>
      <div class="toast-content">
        <div class="toast-title">${escapeHtml(title)}</div>
        <div class="toast-desc">${escapeHtml(message)}</div>
      </div>
      <button class="toast-close" aria-label="Close notification">&times;</button>
    `;

    toast.querySelector('.toast-close').addEventListener('click', () => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateX(40px)';
      setTimeout(() => toast.remove(), 200);
    });

    toastContainer.appendChild(toast);

    setTimeout(() => {
      if (toast.parentNode) {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(40px)';
        setTimeout(() => toast.remove(), 200);
      }
    }, 4500);
  }

})();
