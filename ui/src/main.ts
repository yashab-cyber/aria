import './style.css';
import { createIcons, icons } from 'lucide';
import { marked } from 'marked';

createIcons({ icons });

const state = {
  socket: null as WebSocket | null,
  audioSocket: null as WebSocket | null,
  currentAssistantMessageElement: null as HTMLElement | null,
  currentToolBlock: null as HTMLElement | null,
  isGenerating: false,
  mediaRecorder: null as MediaRecorder | null,
  audioChunks: [] as Blob[],
};

const chatHistory = document.getElementById('chat-history')!;
const chatInput = document.getElementById('chat-input') as HTMLTextAreaElement;
const sendBtn = document.getElementById('send-btn') as HTMLButtonElement;
const micBtn = document.getElementById('mic-btn') as HTMLButtonElement;
const aiCore = document.getElementById('ai-core')!;
const bootOverlay = document.getElementById('boot-overlay')!;
const bootText = document.getElementById('boot-text')!;

// Auto-resize textarea
chatInput.addEventListener('input', () => {
  chatInput.style.height = 'auto';
  chatInput.style.height = Math.min(chatInput.scrollHeight, 200) + 'px';
});
chatInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

// Audio Playback
const audioQueue: string[] = [];
let isPlaying = false;
function playNextAudio() {
  if (audioQueue.length === 0) {
    isPlaying = false;
    aiCore.className = 'ai-core idle';
    return;
  }
  isPlaying = true;
  aiCore.className = 'ai-core speaking';
  const url = audioQueue.shift()!;
  const audio = new Audio(url);
  audio.onended = () => { URL.revokeObjectURL(url); playNextAudio(); };
  audio.onerror = () => { playNextAudio(); };
  audio.play().catch(() => { isPlaying = false; });
}
function queueAudio(blob: Blob) {
  const url = URL.createObjectURL(blob);
  audioQueue.push(url);
  if (!isPlaying) playNextAudio();
}

// Microphone
let isRecording = false;
async function startRecording() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    state.mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
    state.audioChunks = [];
    state.mediaRecorder.ondataavailable = (e) => { if (e.data.size > 0) state.audioChunks.push(e.data); };
    state.mediaRecorder.onstop = () => {
      if (state.audioChunks.length > 0 && state.audioSocket?.readyState === WebSocket.OPEN) {
        state.audioSocket.send(new Blob(state.audioChunks, { type: 'audio/webm' }));
      }
    };
    state.mediaRecorder.start();
    isRecording = true;
    micBtn.classList.add('recording');
    aiCore.className = 'ai-core listening';
  } catch (err) {
    console.error("Mic error", err);
  }
}
function stopRecording() {
  if (state.mediaRecorder && state.mediaRecorder.state !== 'inactive') {
    state.mediaRecorder.stop();
    state.mediaRecorder.stream.getTracks().forEach(t => t.stop());
  }
  isRecording = false;
  micBtn.classList.remove('recording');
  aiCore.className = 'ai-core idle';
}
micBtn.addEventListener('click', () => isRecording ? stopRecording() : startRecording());

// WebSocket
function connectWebSocket() {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const host = window.location.host;
  
  state.socket = new WebSocket(`${protocol}//${host}/ws`);
  state.socket.onmessage = handleMainSocketMessage;
  state.socket.onclose = () => setTimeout(connectWebSocket, 5000);

  state.audioSocket = new WebSocket(`${protocol}//${host}/ws/audio`);
  state.audioSocket.binaryType = 'blob';
  state.audioSocket.onmessage = (event) => {
    if (event.data instanceof Blob) {
      queueAudio(event.data);
    } else {
      const data = JSON.parse(event.data);
      if (data.type === 'transcription') {
        chatInput.value = data.text;
        appendUserMessage(data.text);
        state.isGenerating = true;
        updateSendBtn();
      } else if (data.type === 'chunk' || data.type === 'done' || data.type === 'tool_start' || data.type === 'tool_end') {
        handleMainSocketMessage({ data: JSON.stringify(data) } as MessageEvent);
      }
    }
  };
}

function handleMainSocketMessage(event: MessageEvent) {
  if (event.data instanceof Blob) return;
  const data = JSON.parse(event.data);
  
  if (!state.currentAssistantMessageElement && data.type !== 'done') {
    state.currentAssistantMessageElement = createMessageElement('aria');
    chatHistory.appendChild(state.currentAssistantMessageElement);
  }
  
  const contentEl = state.currentAssistantMessageElement?.querySelector('.content-body') as HTMLElement;
  const toolContainer = state.currentAssistantMessageElement?.querySelector('.tool-container') as HTMLElement;

  if (data.type === 'tool_start') {
    // Create Tool Visualization Block
    const toolId = Math.random().toString(36).substr(2, 9);
    const div = document.createElement('div');
    div.className = 'tool-block';
    div.id = `tool-${toolId}`;
    div.innerHTML = `
      <div class="tool-header" onclick="this.parentElement.classList.toggle('expanded')">
        <i data-lucide="cpu" class="tool-icon"></i>
        <span>Executing: <strong>${data.tool}</strong></span>
        <span class="tool-status running">Running...</span>
      </div>
      <div class="tool-body">
        <pre><code>${JSON.stringify(data.args, null, 2)}</code></pre>
      </div>
    `;
    toolContainer.appendChild(div);
    state.currentToolBlock = div;
    createIcons({ icons, nameAttr: 'data-lucide' });
    scrollToBottom();
  } 
  else if (data.type === 'tool_end') {
    if (state.currentToolBlock) {
      const statusEl = state.currentToolBlock.querySelector('.tool-status')!;
      statusEl.className = 'tool-status done';
      statusEl.textContent = 'Completed';
      
      const bodyEl = state.currentToolBlock.querySelector('.tool-body')!;
      bodyEl.innerHTML += `<div style="margin-top: 10px; border-top: 1px solid #333; padding-top: 10px;">Result:<br><pre><code>${data.result}</code></pre></div>`;
      state.currentToolBlock = null;
    }
  }
  else if (data.type === 'chunk') {
    let chunkContent = data.content;
    
    // Sometimes the chunk is actually a JSON string (our tool event). Parse it if so.
    try {
      if (chunkContent.trim().startsWith('{"type": "tool_')) {
        handleMainSocketMessage({ data: chunkContent } as MessageEvent);
        return;
      }
    } catch(e) {}

    const currentRaw = contentEl.getAttribute('data-raw') || '';
    const newRaw = currentRaw + chunkContent;
    contentEl.setAttribute('data-raw', newRaw);
    
    // Render markdown and add blinking cursor
    contentEl.innerHTML = marked.parse(newRaw) + '<span class="cursor"></span>';
    scrollToBottom();
  } 
  else if (data.type === 'done') {
    state.isGenerating = false;
    updateSendBtn();
    if (contentEl) {
      // Remove cursor
      const finalRaw = contentEl.getAttribute('data-raw') || '';
      contentEl.innerHTML = marked.parse(finalRaw) as string;
    }
    state.currentAssistantMessageElement = null;
  }
}

function createMessageElement(role: 'user' | 'aria'): HTMLElement {
  const div = document.createElement('div');
  div.className = `message ${role}`;
  div.innerHTML = `
    <div class="avatar"><i data-lucide="${role === 'user' ? 'user' : 'cpu'}"></i></div>
    <div class="content">
      <div class="tool-container"></div>
      <div class="content-body" data-raw=""></div>
    </div>
  `;
  setTimeout(() => createIcons({ icons, nameAttr: 'data-lucide' }), 0);
  return div;
}

function appendUserMessage(text: string) {
  const userMsg = createMessageElement('user');
  const body = userMsg.querySelector('.content-body')!;
  body.textContent = text;
  chatHistory.appendChild(userMsg);
  scrollToBottom();
}

function scrollToBottom() {
  chatHistory.scrollTop = chatHistory.scrollHeight;
}

function updateSendBtn() {
  sendBtn.disabled = state.isGenerating;
}

function sendMessage() {
  const text = chatInput.value.trim();
  if (!text || state.isGenerating || !state.socket || state.socket.readyState !== WebSocket.OPEN) return;

  appendUserMessage(text);
  state.socket.send(JSON.stringify({ text }));
  
  chatInput.value = '';
  chatInput.style.height = 'auto';
  state.isGenerating = true;
  updateSendBtn();
}

sendBtn.addEventListener('click', sendMessage);

// System Stats
setInterval(async () => {
  try {
    const res = await fetch(`/api/status`);
    const data = await res.json();
    document.getElementById('cpu-val')!.textContent = `${data.cpu_percent}%`;
    document.getElementById('ram-val')!.textContent = `${data.ram_percent}%`;
  } catch (e) {}
}, 2000);

// Cinematic Boot
window.addEventListener('load', () => {
  setTimeout(() => {
    bootText.textContent = "Connecting to Mainframe...";
    setTimeout(() => { bootText.textContent = "A.R.I.A. Online."; setTimeout(() => bootOverlay.classList.add('hidden'), 500); }, 600);
  }, 600);
});

// Modals generic
document.querySelectorAll('.close-modal-btn').forEach(btn => {
  btn.addEventListener('click', (e) => {
    (e.target as HTMLElement).closest('.modal-overlay')?.classList.add('hidden');
  });
});

// Settings Modal Logic
const settingsModal = document.getElementById('settings-modal')!;
const settingsForm = document.getElementById('settings-form') as HTMLFormElement;
const settingsStatus = document.getElementById('settings-status')!;

document.getElementById('nav-settings')?.addEventListener('click', () => {
  settingsModal.classList.remove('hidden');
  loadSettings();
});

// Settings Tabs
document.querySelectorAll('.settings-tab').forEach(tab => {
  tab.addEventListener('click', (e) => {
    // Remove active from all tabs and sections
    document.querySelectorAll('.settings-tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.settings-section').forEach(s => s.classList.remove('active'));
    
    // Add active to clicked tab and corresponding section
    const targetId = (e.target as HTMLElement).getAttribute('data-target');
    (e.target as HTMLElement).classList.add('active');
    document.getElementById(targetId!)?.classList.add('active');
  });
});

// Password Toggle
document.querySelectorAll('.eye-toggle').forEach(btn => {
  btn.addEventListener('click', (e) => {
    const btnEl = e.currentTarget as HTMLElement;
    const input = btnEl.previousElementSibling as HTMLInputElement;
    const icon = btnEl.querySelector('i')!;
    
    if (input.type === 'password') {
      input.type = 'text';
      icon.setAttribute('data-lucide', 'eye-off');
    } else {
      input.type = 'password';
      icon.setAttribute('data-lucide', 'eye');
    }
    createIcons({ icons, nameAttr: 'data-lucide' });
  });
});

// Load Settings from API
async function loadSettings() {
  try {
    settingsStatus.textContent = "Loading...";
    settingsStatus.className = "status-msg";
    
    const res = await fetch('/api/config');
    const data = await res.json();
    
    if (data.config) {
      for (const [key, value] of Object.entries(data.config)) {
        const input = document.getElementById(`cfg-${key}`) as HTMLInputElement;
        if (input && value !== null) {
          input.value = String(value);
        }
      }
    }
    settingsStatus.textContent = "";
  } catch (err) {
    settingsStatus.textContent = "Failed to load settings.";
    settingsStatus.className = "status-msg error";
  }
}

// Save Settings to API
document.getElementById('save-settings-btn')?.addEventListener('click', async () => {
  try {
    settingsStatus.textContent = "Saving...";
    settingsStatus.className = "status-msg";
    
    const formData = new FormData(settingsForm);
    const payload: Record<string, string> = {};
    
    formData.forEach((value, key) => {
      // Only include fields that have a value
      if (value.toString().trim() !== "") {
        payload[key] = value.toString();
      }
    });
    
    const res = await fetch('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    
    const data = await res.json();
    if (data.status === 'success') {
      settingsStatus.textContent = "Configuration saved successfully!";
      settingsStatus.className = "status-msg success";
      setTimeout(() => settingsModal.classList.add('hidden'), 1500);
    } else {
      settingsStatus.textContent = data.message || "Failed to save.";
      settingsStatus.className = "status-msg error";
    }
  } catch (err) {
    settingsStatus.textContent = "Network error.";
    settingsStatus.className = "status-msg error";
  }
});

// Voice Modal Logic
const voiceModal = document.getElementById('voice-modal')!;
const voiceListEl = document.getElementById('voice-list')!;
const voiceDetailsEl = document.getElementById('voice-details')!;
let activeVoiceId = '';
let currentlyPlayingAudio: HTMLAudioElement | null = null;

document.getElementById('voice-config-btn')?.addEventListener('click', () => {
  voiceModal.classList.remove('hidden');
  loadVoices();
});

async function loadVoices() {
  voiceListEl.innerHTML = '<p style="padding:1rem; color:var(--text-dim);">Loading voices...</p>';
  try {
    const res = await fetch('/api/voices');
    const data = await res.json();
    activeVoiceId = data.active_id;
    
    voiceListEl.innerHTML = '';
    data.voices.forEach((voice: any) => {
      const btn = document.createElement('button');
      btn.className = `voice-item ${voice.id === activeVoiceId ? 'active' : ''}`;
      btn.innerHTML = `<span><i data-lucide="user"></i> ${voice.name}</span>`;
      
      btn.addEventListener('click', () => {
        document.querySelectorAll('.voice-item').forEach(b => b.classList.remove('selected'));
        btn.classList.add('selected');
        showVoiceDetails(voice);
      });
      voiceListEl.appendChild(btn);
    });
    createIcons({ icons, nameAttr: 'data-lucide' });
    
    // Select active by default
    const activeBtn = voiceListEl.querySelector('.voice-item.active') as HTMLElement;
    if (activeBtn) activeBtn.click();
  } catch (e) {
    voiceListEl.innerHTML = '<p style="padding:1rem; color:var(--error-red);">Failed to load voices.</p>';
  }
}

function showVoiceDetails(voice: any) {
  voiceDetailsEl.innerHTML = `
    <h4 style="margin-bottom:1rem; font-size:1.1rem;">${voice.name}</h4>
    <p style="margin-bottom:0.5rem;"><strong>TTS Engine:</strong> ${voice.engine}</p>
    <p style="margin-bottom:1.5rem;"><strong>STT Language:</strong> ${voice.stt_language}</p>
    
    ${voice.id === activeVoiceId 
      ? '<span class="status-indicator online" style="display:inline-block; margin-bottom:1rem;"></span> <span style="color:var(--accent-cyan);">Currently Active</span>' 
      : `<button class="primary-btn" id="activate-voice-btn" data-id="${voice.id}" style="margin-bottom:1rem;">Set as Active Voice</button>`}
    
    <div style="margin-top: 1rem; border-top: 1px solid var(--border-color); padding-top:1rem;">
      <button class="nav-btn" id="preview-voice-btn" data-id="${voice.id}" title="Preview Voice">
        <i data-lucide="play-circle"></i> Preview Audio
      </button>
    </div>
  `;
  createIcons({ icons, nameAttr: 'data-lucide' });
  
  document.getElementById('activate-voice-btn')?.addEventListener('click', async (e) => {
    const id = (e.currentTarget as HTMLElement).getAttribute('data-id');
    try {
      await fetch('/api/voices/active', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ voice_id: id })
      });
      loadVoices();
    } catch(e) { console.error('Failed to activate voice'); }
  });
  
  document.getElementById('preview-voice-btn')?.addEventListener('click', async (e) => {
    const btnEl = e.currentTarget as HTMLElement;
    const id = btnEl.getAttribute('data-id');
    const iconEl = btnEl.querySelector('i')!;
    
    if (currentlyPlayingAudio) {
      currentlyPlayingAudio.pause();
      currentlyPlayingAudio = null;
    }
    
    iconEl.setAttribute('data-lucide', 'loader');
    createIcons({ icons, nameAttr: 'data-lucide' });
    
    try {
      const res = await fetch(`/api/voices/preview/${id}`);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      currentlyPlayingAudio = new Audio(url);
      currentlyPlayingAudio.play();
      
      iconEl.setAttribute('data-lucide', 'pause-circle');
      createIcons({ icons, nameAttr: 'data-lucide' });
      
      currentlyPlayingAudio.onended = () => {
        iconEl.setAttribute('data-lucide', 'play-circle');
        createIcons({ icons, nameAttr: 'data-lucide' });
      };
    } catch(err) {
      iconEl.setAttribute('data-lucide', 'play-circle');
      createIcons({ icons, nameAttr: 'data-lucide' });
    }
  });
}

// Memory Browser
const memModal = document.getElementById('memory-modal')!;
const memSearchInput = document.getElementById('memory-search-input') as HTMLInputElement;
const memList = document.getElementById('memory-list')!;

document.getElementById('nav-memory')?.addEventListener('click', () => {
  memModal.classList.remove('hidden');
  fetchMemories('');
});

memSearchInput.addEventListener('input', (e) => {
  fetchMemories((e.target as HTMLInputElement).value);
});

async function fetchMemories(query: string) {
  try {
    const res = await fetch(`/api/memory/search?q=${encodeURIComponent(query)}`);
    const data = await res.json();
    renderMemories(data.results);
  } catch(e) { console.error(e); }
}

function renderMemories(results: any[]) {
  memList.innerHTML = '';
  if (!results.length) {
    memList.innerHTML = '<p style="color: #666; text-align: center; padding: 2rem;">No memories found.</p>';
    return;
  }
  
  results.forEach(item => {
    const meta = item.metadata;
    const date = new Date(meta.timestamp * 1000).toLocaleString();
    
    const div = document.createElement('div');
    div.className = 'memory-item';
    div.innerHTML = `
      <div class="memory-item-header">
        <span><i data-lucide="clock"></i> ${date}</span>
        <button class="memory-delete-btn" data-id="${meta.session_id}" title="Delete Session"><i data-lucide="trash-2"></i></button>
      </div>
      <div class="memory-item-content">${item.summary || item.content}</div>
      <div style="font-size:0.75rem; color:#666; margin-top:0.5rem;">Tags: ${meta.topic_tags || 'none'}</div>
    `;
    
    div.querySelector('.memory-delete-btn')?.addEventListener('click', async () => {
      if (confirm('Delete this memory session?')) {
        await fetch(`/api/memory/sessions/${meta.session_id}`, { method: 'DELETE' });
        div.remove();
      }
    });
    
    memList.appendChild(div);
  });
  createIcons({ icons, nameAttr: 'data-lucide' });
}

connectWebSocket();
