import './style.css';
import { createIcons, icons } from 'lucide';
import { marked } from 'marked';

// Initialize Icons
createIcons({ icons });

// State
const state = {
  socket: null as WebSocket | null,
  audioSocket: null as WebSocket | null,
  currentAssistantMessageElement: null as HTMLElement | null,
  isGenerating: false,
  mediaRecorder: null as MediaRecorder | null,
  audioChunks: [] as Blob[],
};

// DOM Elements
const chatHistory = document.getElementById('chat-history')!;
const chatInput = document.getElementById('chat-input') as HTMLInputElement;
const sendBtn = document.getElementById('send-btn')!;
const micBtn = document.getElementById('mic-btn') as HTMLButtonElement;
const aiCore = document.getElementById('ai-core')!;
const bootOverlay = document.getElementById('boot-overlay')!;
const bootText = document.getElementById('boot-text')!;
const cpuVal = document.getElementById('cpu-val')!;
const ramVal = document.getElementById('ram-val')!;
const logContainer = document.getElementById('log-container')!;
const modeSelect = document.getElementById('audio-mode-select') as HTMLSelectElement;

// Audio Mode Toggle
modeSelect.addEventListener('change', async (e) => {
  const mode = (e.target as HTMLSelectElement).value;
  try {
    const protocol = window.location.protocol;
    const host = window.location.host;
    await fetch(`${protocol}//${host}/api/audio/mode`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mode })
    });
    addLog(`Audio mode set to: ${mode}`, 'info');
  } catch (err) {
    addLog('Failed to set audio mode.', 'error');
  }
});

// Setup Audio Playback Queue
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
  audio.onended = () => {
    URL.revokeObjectURL(url);
    playNextAudio();
  };
  audio.onerror = () => {
    addLog('Error playing audio chunk.', 'error');
    playNextAudio();
  };
  audio.play().catch(e => {
    addLog(`Playback error: ${e}`, 'error');
    isPlaying = false;
  });
}

function queueAudio(blob: Blob) {
  const url = URL.createObjectURL(blob);
  audioQueue.push(url);
  if (!isPlaying) {
    playNextAudio();
  }
}

// Microphone / MediaRecorder Setup
let isRecording = false;

async function startRecording() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    state.mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
    state.audioChunks = [];
    
    state.mediaRecorder.ondataavailable = (e: BlobEvent) => {
      if (e.data.size > 0) {
        state.audioChunks.push(e.data);
      }
    };
    
    state.mediaRecorder.onstop = () => {
      if (state.audioChunks.length > 0) {
        const audioBlob = new Blob(state.audioChunks, { type: 'audio/webm' });
        if (state.audioSocket && state.audioSocket.readyState === WebSocket.OPEN) {
          state.audioSocket.send(audioBlob);
          addLog('Audio sent to backend for processing.', 'info');
        } else {
          addLog('Audio WebSocket is not connected.', 'error');
        }
      }
    };

    state.mediaRecorder.start(); // Record as one chunk until stop()
    isRecording = true;
    micBtn.classList.add('recording');
    aiCore.className = 'ai-core listening';
    addLog('Microphone activated. Listening...', 'info');
  } catch (err) {
    if (window.location.protocol !== 'https:' && window.location.hostname !== 'localhost') {
      addLog(`Microphone error: HTTPS is required on mobile. Use an HTTPS proxy or local URL.`, 'error');
    } else {
      addLog(`Microphone access denied or error: ${err}`, 'error');
    }
    isRecording = false;
    micBtn.classList.remove('recording');
  }
}

function stopRecording() {
  if (state.mediaRecorder && state.mediaRecorder.state !== 'inactive') {
    state.mediaRecorder.stop();
    state.mediaRecorder.stream.getTracks().forEach((track: MediaStreamTrack) => track.stop());
    addLog('Microphone deactivated.', 'info');
  }
  isRecording = false;
  micBtn.classList.remove('recording');
  aiCore.className = 'ai-core idle';
}

micBtn.addEventListener('click', () => {
  if (isRecording) {
    stopRecording();
  } else {
    startRecording();
  }
});

// Setup WebSocket
function connectWebSocket() {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const host = window.location.host;
  
  // Main WebSocket
  state.socket = new WebSocket(`${protocol}//${host}/ws`);
  state.socket.onopen = () => addLog('Main WebSocket connected.', 'success');
  state.socket.onmessage = handleMainSocketMessage;
  state.socket.onclose = () => {
    addLog('Main WebSocket disconnected. Reconnecting in 5s...', 'error');
    setTimeout(connectWebSocket, 5000);
  };

  // Audio WebSocket
  state.audioSocket = new WebSocket(`${protocol}//${host}/ws/audio`);
  state.audioSocket.binaryType = 'blob';
  state.audioSocket.onopen = () => addLog('Audio WebSocket connected.', 'success');
  state.audioSocket.onmessage = (event) => {
    if (event.data instanceof Blob) {
      // Received audio chunk to play
      queueAudio(event.data);
    } else {
      // JSON message from audio socket
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'transcription') {
          chatInput.value = data.text;
          addLog(`Transcribed: ${data.text}`, 'success');
          
          // Show user message in UI immediately
          const userMsg = createMessageElement('user');
          userMsg.querySelector('.content')!.textContent = data.text;
          chatHistory.appendChild(userMsg);
          scrollToBottom();
          
          state.isGenerating = true;
        } else if (data.type === 'chunk' || data.type === 'done') {
          // Handle response generation from audio socket similarly
          handleMainSocketMessage(event);
        }
      } catch (e) {
        console.error("Failed to parse message from audio socket", e);
      }
    }
  };
  state.audioSocket.onclose = () => {
    addLog('Audio WebSocket disconnected.', 'error');
  };
}

function handleMainSocketMessage(event: MessageEvent) {
  if (event.data instanceof Blob) return;
  const data = JSON.parse(event.data);
  
  if (data.type === 'chunk') {
    if (!state.currentAssistantMessageElement) {
      state.currentAssistantMessageElement = createMessageElement('aria');
      chatHistory.appendChild(state.currentAssistantMessageElement);
    }
    
    const contentEl = state.currentAssistantMessageElement.querySelector('.content')!;
    const currentRaw = contentEl.getAttribute('data-raw') || '';
    const newRaw = currentRaw + data.content;
    contentEl.setAttribute('data-raw', newRaw);
    contentEl.innerHTML = marked.parse(newRaw) as string;
    scrollToBottom();
  } else if (data.type === 'done') {
    state.isGenerating = false;
    state.currentAssistantMessageElement = null;
    addLog('Response complete.', 'info');
  }
}

// UI Functions
function createMessageElement(role: 'user' | 'aria'): HTMLElement {
  const div = document.createElement('div');
  div.className = `message ${role}`;
  
  const iconName = role === 'user' ? 'user' : 'cpu';
  
  div.innerHTML = `
    <div class="avatar"><i data-lucide="${iconName}"></i></div>
    <div class="content" data-raw=""></div>
  `;
  
  // Re-init newly added icons
  setTimeout(() => createIcons({ icons, nameAttr: 'data-lucide' }), 0);
  return div;
}

function scrollToBottom() {
  chatHistory.scrollTop = chatHistory.scrollHeight;
}

function addLog(message: string, type: 'info' | 'success' | 'error' = 'info') {
  const div = document.createElement('div');
  div.className = `log-entry ${type}`;
  const time = new Date().toLocaleTimeString();
  div.textContent = `[${time}] ${message}`;
  logContainer.prepend(div);
}

function sendMessage() {
  const text = chatInput.value.trim();
  if (!text || state.isGenerating || !state.socket || state.socket.readyState !== WebSocket.OPEN) return;

  // Add User Message
  const userMsg = createMessageElement('user');
  userMsg.querySelector('.content')!.textContent = text;
  chatHistory.appendChild(userMsg);
  scrollToBottom();

  // Send via WS
  state.socket.send(JSON.stringify({ text }));
  chatInput.value = '';
  state.isGenerating = true;
  addLog(`Sent command: ${text.substring(0, 20)}...`, 'info');
}

// Event Listeners
sendBtn.addEventListener('click', sendMessage);
chatInput.addEventListener('keypress', (e) => {
  if (e.key === 'Enter') sendMessage();
});

// Fetch System Stats periodically
async function fetchStats() {
  try {
    const protocol = window.location.protocol;
    const host = window.location.host;
    const res = await fetch(`${protocol}//${host}/api/status`);
    const data = await res.json();
    cpuVal.textContent = `${data.cpu_percent}%`;
    ramVal.textContent = `${data.ram_percent}%`;
  } catch (e) {
    // Silent fail for stats
  }
}

// Init
setInterval(fetchStats, 2000);

// Cinematic Boot Sequence
window.addEventListener('load', () => {
  setTimeout(() => {
    bootText.textContent = "Connecting to Mainframe...";
    setTimeout(() => {
      bootText.textContent = "Loading Personality Matrices...";
      setTimeout(() => {
        bootText.textContent = "A.R.I.A. Online.";
        setTimeout(() => {
          bootOverlay.classList.add('hidden');
        }, 500);
      }, 800);
    }, 800);
  }, 800);
});
// Voice Configuration UI Logic
const voiceConfigBtn = document.getElementById('voice-config-btn')!;
const voiceModal = document.getElementById('voice-modal')!;
const closeModalBtn = document.getElementById('close-modal-btn')!;
const voiceList = document.getElementById('voice-list')!;
const voiceDetails = document.getElementById('voice-details')!;

let availableVoices: any[] = [];
let activeVoiceId = '';

voiceConfigBtn.addEventListener('click', async () => {
  voiceModal.classList.remove('hidden');
  await loadVoices();
});

closeModalBtn.addEventListener('click', () => {
  voiceModal.classList.add('hidden');
});

async function loadVoices() {
  try {
    const protocol = window.location.protocol;
    const host = window.location.host;
    const res = await fetch(`${protocol}//${host}/api/voices`);
    const data = await res.json();
    availableVoices = data.voices;
    activeVoiceId = data.active_id;
    renderVoiceList();
  } catch (err) {
    console.error("Failed to load voices:", err);
  }
}

function renderVoiceList() {
  voiceList.innerHTML = '';
  availableVoices.forEach(voice => {
    const item = document.createElement('div');
    item.className = `voice-item ${voice.id === activeVoiceId ? 'active' : ''}`;
    
    item.innerHTML = `
      <div>
        <span class="voice-name">${voice.name}</span>
        <span class="voice-engine">${voice.engine} • ${voice.gender}</span>
      </div>
      <div class="voice-actions">
        <button class="preview-btn" data-id="${voice.id}" title="Preview Voice">
          <i data-lucide="play"></i>
        </button>
      </div>
    `;
    
    item.addEventListener('click', (e) => {
      // Ignore click if it was on the preview button
      if ((e.target as HTMLElement).closest('.preview-btn')) return;
      setActiveVoice(voice.id);
      showVoiceDetails(voice);
    });
    
    const previewBtn = item.querySelector('.preview-btn')!;
    previewBtn.addEventListener('click', async (e) => {
      e.stopPropagation();
      await playVoicePreview(voice.id);
    });
    
    voiceList.appendChild(item);
  });
  
  createIcons({ icons, nameAttr: 'data-lucide' });
  
  // Show details of active voice initially
  const activeVoice = availableVoices.find(v => v.id === activeVoiceId);
  if (activeVoice) showVoiceDetails(activeVoice);
}

function showVoiceDetails(voice: any) {
  voiceDetails.innerHTML = `
    <p><strong>Name:</strong> ${voice.name}</p>
    <p><strong>Engine:</strong> <span class="badge ${voice.engine === 'edge' ? 'active' : ''}">${voice.engine}</span></p>
    <p><strong>Language:</strong> ${voice.language}</p>
    <p><strong>Speed:</strong> ${voice.speed}x | <strong>Pitch:</strong> ${voice.pitch}x</p>
    <div style="margin-top: 1rem; padding: 1rem; background: rgba(0,240,255,0.05); border-left: 3px solid var(--accent-cyan); font-style: italic;">
      "${voice.personality}"
    </div>
  `;
}

async function setActiveVoice(voiceId: string) {
  try {
    const protocol = window.location.protocol;
    const host = window.location.host;
    const res = await fetch(`${protocol}//${host}/api/voices/active`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ voice_id: voiceId })
    });
    const data = await res.json();
    if (data.status === 'success') {
      activeVoiceId = data.active_id;
      renderVoiceList();
      addLog(`Voice changed to: ${voiceId}`, 'success');
    }
  } catch (err) {
    addLog('Failed to set active voice.', 'error');
  }
}

let previewAudio: HTMLAudioElement | null = null;
async function playVoicePreview(voiceId: string) {
  if (previewAudio) {
    previewAudio.pause();
    previewAudio = null;
  }
  
  try {
    const protocol = window.location.protocol;
    const host = window.location.host;
    const url = `${protocol}//${host}/api/voices/preview/${voiceId}`;
    
    previewAudio = new Audio(url);
    await previewAudio.play();
  } catch (err) {
    addLog('Failed to play voice preview.', 'error');
  }
}

fetchStats();
connectWebSocket();
