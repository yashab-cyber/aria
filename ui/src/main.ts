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

// --- Screen Analyzer Frontend Logic ---
let analyzerSocket: WebSocket | null = null;
let isMonitoringScreen = false;

const navAnalyzerBtn = document.getElementById('nav-analyzer') as HTMLButtonElement;
const analyzerPane = document.getElementById('analyzer-pane')!;
const btnCaptureNow = document.getElementById('btn-capture-now') as HTMLButtonElement;
const btnToggleMonitor = document.getElementById('btn-toggle-monitor') as HTMLButtonElement;
const selectInterval = document.getElementById('analyzer-interval') as HTMLSelectElement;
const imgScreenshot = document.getElementById('analyzer-screenshot') as HTMLImageElement;
const screenshotPlaceholder = document.getElementById('screenshot-placeholder-text')!;
const suggestionsBox = document.getElementById('analyzer-suggestions')!;
const queryInput = document.getElementById('analyzer-query-input') as HTMLInputElement;
const btnSendQuery = document.getElementById('btn-send-query') as HTMLButtonElement;
const statusDot = document.getElementById('analyzer-status-dot')!;
const statusText = document.getElementById('analyzer-status-text')!;

function connectAnalyzerWebSocket() {
  if (analyzerSocket && (analyzerSocket.readyState === WebSocket.OPEN || analyzerSocket.readyState === WebSocket.CONNECTING)) {
    return;
  }
  
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const host = window.location.host;
  
  analyzerSocket = new WebSocket(`${protocol}//${host}/ws/screen_analyzer`);
  
  analyzerSocket.onopen = () => {
    statusDot.className = 'status-dot';
    statusText.textContent = 'STANDBY';
  };
  
  analyzerSocket.onmessage = (event) => {
    const data = JSON.parse(event.data);
    
    if (data.type === 'analyzing_start') {
      statusDot.className = 'status-dot analyzing';
      statusText.textContent = 'ANALYZING...';
      
      // Update preview if image is provided
      if (data.image) {
        imgScreenshot.src = `data:image/jpeg;base64,${data.image}`;
        imgScreenshot.classList.remove('placeholder');
        screenshotPlaceholder.classList.add('hidden');
      }
      
      suggestionsBox.innerHTML = `
        <div class="loading-indicator">
          <i data-lucide="loader" class="animate-spin" style="animation: spin 1s linear infinite;"></i>
          <span>A.R.I.A. is studying the screen...</span>
        </div>
      `;
      createIcons({ icons, nameAttr: 'data-lucide' });
    }
    else if (data.type === 'update') {
      statusDot.className = isMonitoringScreen ? 'status-dot active' : 'status-dot';
      statusText.textContent = isMonitoringScreen ? 'MONITORING' : 'STANDBY';
      
      // Render markdown
      suggestionsBox.innerHTML = marked.parse(data.analysis) as string;
      
      // Update screenshot
      imgScreenshot.src = `data:image/jpeg;base64,${data.image}`;
      imgScreenshot.classList.remove('placeholder');
      screenshotPlaceholder.classList.add('hidden');
    }
    else if (data.type === 'image_only') {
      imgScreenshot.src = `data:image/jpeg;base64,${data.image}`;
      imgScreenshot.classList.remove('placeholder');
      screenshotPlaceholder.classList.add('hidden');
    }
    else if (data.type === 'status') {
      isMonitoringScreen = data.monitoring;
      
      if (isMonitoringScreen) {
        btnToggleMonitor.classList.add('active');
        btnToggleMonitor.innerHTML = `<i data-lucide="square"></i> Stop Monitor`;
        statusDot.className = 'status-dot active';
        statusText.textContent = 'MONITORING';
      } else {
        btnToggleMonitor.classList.remove('active');
        btnToggleMonitor.innerHTML = `<i data-lucide="play"></i> Enable Monitor`;
        statusDot.className = 'status-dot';
        statusText.textContent = 'STANDBY';
      }
      createIcons({ icons, nameAttr: 'data-lucide' });
    }
    else if (data.type === 'error') {
      statusDot.className = 'status-dot';
      statusText.textContent = 'ERROR';
      suggestionsBox.innerHTML = `<p style="color:var(--danger)">Error: ${data.message}</p>`;
    }
  };
  
  analyzerSocket.onclose = () => {
    statusDot.className = 'status-dot';
    statusText.textContent = 'OFFLINE';
    isMonitoringScreen = false;
    btnToggleMonitor.classList.remove('active');
    btnToggleMonitor.innerHTML = `<i data-lucide="play"></i> Enable Monitor`;
    createIcons({ icons, nameAttr: 'data-lucide' });
    setTimeout(connectAnalyzerWebSocket, 5000);
  };
}

// Sidebar toggle handler
navAnalyzerBtn.addEventListener('click', () => {
  const isHidden = analyzerPane.classList.toggle('hidden');
  navAnalyzerBtn.classList.toggle('active', !isHidden);
  
  if (!isHidden) {
    connectAnalyzerWebSocket();
  }
});

btnCaptureNow.addEventListener('click', () => {
  if (analyzerSocket && analyzerSocket.readyState === WebSocket.OPEN) {
    analyzerSocket.send(JSON.stringify({ action: 'capture' }));
  }
});

btnToggleMonitor.addEventListener('click', () => {
  if (!analyzerSocket || analyzerSocket.readyState !== WebSocket.OPEN) return;
  
  if (isMonitoringScreen) {
    analyzerSocket.send(JSON.stringify({ action: 'stop' }));
  } else {
    const interval = parseInt(selectInterval.value) || 5;
    analyzerSocket.send(JSON.stringify({ action: 'start', interval }));
  }
});

function sendAnalyzerQuery() {
  const text = queryInput.value.trim();
  if (!text || !analyzerSocket || analyzerSocket.readyState !== WebSocket.OPEN) return;
  
  analyzerSocket.send(JSON.stringify({ action: 'query', prompt: text }));
  queryInput.value = '';
}

btnSendQuery.addEventListener('click', sendAnalyzerQuery);
queryInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter') {
    e.preventDefault();
    sendAnalyzerQuery();
  }
});

// --- Web Avatar Canvas Rendering Loop ---
const avatarCanvas = document.getElementById('web-avatar') as HTMLCanvasElement;
if (avatarCanvas) {
  const ctx = avatarCanvas.getContext('2d')!;
  
  let currentAvatarState = 'idle';
  let targetColor = { r: 0, g: 240, b: 255 }; // Cyan for idle
  let currentColor = { r: 0, g: 240, b: 255 };
  
  let scaleTarget = 1.0;
  let scaleCurrent = 1.0;
  
  let rotSpeedInner = 0.01;
  let rotSpeedMid = -0.012;
  let rotSpeedOuter = 0.006;
  
  let rotAngleInner = 0;
  let rotAngleMid = 0;
  let rotAngleOuter = 0;
  
  let talkWaveAmp = 0;
  
  // Particles
  interface Particle {
    angle: number;
    speed: number;
    radius: number;
    size: number;
    alpha: number;
  }
  
  const particles: Particle[] = [];
  for (let i = 0; i < 12; i++) {
    particles.push({
      angle: Math.random() * Math.PI * 2,
      speed: (0.005 + Math.random() * 0.015) * (Math.random() > 0.5 ? 1 : -1),
      radius: 50 + Math.random() * 25,
      size: 1.2 + Math.random() * 1.8,
      alpha: 0.3 + Math.random() * 0.7
    });
  }
  
  // Set target properties based on state
  function updateAvatarState(state: string) {
    currentAvatarState = state;
    
    // Apply styling filter to canvas for matching neon glow
    const filterColorStr = state === 'idle' ? 'rgba(0, 240, 255, 0.15)' :
                           state === 'thinking' ? 'rgba(255, 215, 0, 0.15)' :
                           state === 'analyzing' ? 'rgba(255, 0, 235, 0.15)' :
                           'rgba(0, 230, 118, 0.15)';
    avatarCanvas.style.filter = `drop-shadow(0 0 12px ${filterColorStr})`;
    
    switch(state) {
      case 'idle':
        targetColor = { r: 0, g: 240, b: 255 }; // Cyan
        rotSpeedInner = 0.01;
        rotSpeedMid = -0.012;
        rotSpeedOuter = 0.006;
        scaleTarget = 1.0;
        break;
      case 'thinking':
        targetColor = { r: 255, g: 215, b: 0 }; // Golden Yellow
        rotSpeedInner = 0.04;
        rotSpeedMid = -0.05;
        rotSpeedOuter = 0.03;
        scaleTarget = 1.1;
        break;
      case 'analyzing':
        targetColor = { r: 255, g: 0, b: 235 }; // Magenta/Purple
        rotSpeedInner = 0.08;
        rotSpeedMid = -0.09;
        rotSpeedOuter = 0.06;
        scaleTarget = 1.2;
        break;
      case 'speaking':
        targetColor = { r: 0, g: 230, b: 118 }; // Green
        rotSpeedInner = 0.02;
        rotSpeedMid = -0.024;
        rotSpeedOuter = 0.016;
        scaleTarget = 1.05;
        break;
    }
  }
  
  // Connect to state websocket
  function connectAvatarWS() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    const socket = new WebSocket(`${protocol}//${host}/ws/avatar`);
    
    socket.onmessage = (e) => {
      const data = JSON.parse(e.data);
      if (data.type === 'state_change') {
        updateAvatarState(data.state);
        // Also update small header core state
        const headerCore = document.getElementById('ai-core');
        if (headerCore) {
          headerCore.className = `ai-core ${data.state}`;
        }
      }
    };
    
    socket.onclose = () => {
      setTimeout(connectAvatarWS, 5000);
    };
  }
  
  connectAvatarWS();
  
  // Main draw loop
  let lastTime = 0;
  function draw(timestamp: number) {
    if (!lastTime) lastTime = timestamp;
    const dt = (timestamp - lastTime) / 16.666; // Normalized to ~60fps
    lastTime = timestamp;
    
    // Lerp color
    currentColor.r += (targetColor.r - currentColor.r) * 0.1 * dt;
    currentColor.g += (targetColor.g - currentColor.g) * 0.1 * dt;
    currentColor.b += (targetColor.b - currentColor.b) * 0.1 * dt;
    
    // Lerp scale
    scaleCurrent += (scaleTarget - scaleCurrent) * 0.1 * dt;
    
    // Update rotation angles
    rotAngleInner += rotSpeedInner * dt;
    rotAngleMid += rotSpeedMid * dt;
    rotAngleOuter += rotSpeedOuter * dt;
    
    // Lerp talk wave amplitude
    if (currentAvatarState === 'speaking') {
      talkWaveAmp += (1.0 - talkWaveAmp) * 0.2 * dt;
    } else {
      talkWaveAmp += (0.0 - talkWaveAmp) * 0.1 * dt;
    }
    
    // Update particles
    particles.forEach(p => {
      let speedMult = 1.0;
      if (currentAvatarState === 'thinking') speedMult = 2.5;
      else if (currentAvatarState === 'analyzing') speedMult = 4.0;
      p.angle += p.speed * speedMult * dt;
    });
    
    // Clear canvas
    ctx.clearRect(0, 0, avatarCanvas.width, avatarCanvas.height);
    
    const center = { x: avatarCanvas.width / 2, y: avatarCanvas.height / 2 };
    const baseRadius = 42 * scaleCurrent;
    const colorStr = `rgb(${Math.round(currentColor.r)}, ${Math.round(currentColor.g)}, ${Math.round(currentColor.b)})`;
    const colorAlpha = (a: number) => `rgba(${Math.round(currentColor.r)}, ${Math.round(currentColor.g)}, ${Math.round(currentColor.b)}, ${a})`;
    
    // Background glow circles
    ctx.beginPath();
    ctx.arc(center.x, center.y, baseRadius + 24, 0, Math.PI * 2);
    ctx.fillStyle = colorAlpha(0.02);
    ctx.fill();
    
    ctx.beginPath();
    ctx.arc(center.x, center.y, baseRadius + 12, 0, Math.PI * 2);
    ctx.fillStyle = colorAlpha(0.05);
    ctx.fill();
    
    // Core circle (pulsing)
    const pulse = Math.sin(timestamp * (currentAvatarState === 'thinking' ? 0.012 : 0.004)) * 2.5;
    let coreRadius = baseRadius * 0.45 + pulse;
    if (currentAvatarState === 'speaking') {
      coreRadius = baseRadius * 0.45 + Math.sin(timestamp * 0.035) * 6 * talkWaveAmp;
    }
    
    ctx.beginPath();
    ctx.arc(center.x, center.y, Math.max(2, coreRadius), 0, Math.PI * 2);
    ctx.fillStyle = colorStr;
    ctx.shadowBlur = 12;
    ctx.shadowColor = colorStr;
    ctx.fill();
    ctx.shadowBlur = 0; // reset
    
    // Bright white center core
    ctx.beginPath();
    ctx.arc(center.x, center.y, Math.max(1, coreRadius * 0.5), 0, Math.PI * 2);
    ctx.fillStyle = '#ffffff';
    ctx.fill();
    
    // Middle segmented ring
    const midRadius = baseRadius * 0.8;
    const segmentCount = 8;
    const segmentAngle = (Math.PI * 2) / segmentCount;
    const gapRatio = 0.4;
    
    ctx.lineWidth = 1.5;
    ctx.strokeStyle = colorAlpha(0.65);
    for (let i = 0; i < segmentCount; i++) {
      const startAngle = i * segmentAngle + rotAngleMid;
      const endAngle = startAngle + segmentAngle * (1 - gapRatio);
      ctx.beginPath();
      ctx.arc(center.x, center.y, midRadius, startAngle, endAngle);
      ctx.stroke();
    }
    
    // Outer ring (dots or analyzing scanner/frame)
    const outerRadius = baseRadius * 1.25;
    if (currentAvatarState === 'analyzing') {
      // Horizontal laser bar
      const scanY = center.y + Math.sin(timestamp * 0.006) * baseRadius;
      ctx.beginPath();
      ctx.moveTo(center.x - baseRadius, scanY);
      ctx.lineTo(center.x + baseRadius, scanY);
      ctx.strokeStyle = colorStr;
      ctx.lineWidth = 1.5;
      ctx.stroke();
      
      // Fine bright subline
      ctx.beginPath();
      ctx.moveTo(center.x - baseRadius * 0.8, scanY - 1.5);
      ctx.lineTo(center.x + baseRadius * 0.8, scanY - 1.5);
      ctx.strokeStyle = 'rgba(255,255,255,0.45)';
      ctx.lineWidth = 0.8;
      ctx.stroke();
      
      // Target box
      const targetSize = baseRadius * 1.3;
      ctx.strokeStyle = colorAlpha(0.4);
      ctx.lineWidth = 0.8;
      ctx.strokeRect(center.x - targetSize, center.y - targetSize, targetSize * 2, targetSize * 2);
    } else {
      // Dotted outer ring
      const dotCount = 18;
      ctx.fillStyle = colorAlpha(0.7);
      for (let i = 0; i < dotCount; i++) {
        const a = i * ((Math.PI * 2) / dotCount) + rotAngleOuter;
        const x = center.x + Math.cos(a) * outerRadius;
        const y = center.y + Math.sin(a) * outerRadius;
        ctx.beginPath();
        ctx.arc(x, y, 1.0, 0, Math.PI * 2);
        ctx.fill();
      }
    }
    
    // Orbit particles
    particles.forEach(p => {
      const rad = p.radius * scaleCurrent;
      const x = center.x + Math.cos(p.angle) * rad;
      const y = center.y + Math.sin(p.angle) * rad;
      ctx.fillStyle = colorAlpha(p.alpha);
      ctx.beginPath();
      ctx.arc(x, y, p.size, 0, Math.PI * 2);
      ctx.fill();
    });
    
    requestAnimationFrame(draw);
  }
  requestAnimationFrame(draw);
}

connectWebSocket();
