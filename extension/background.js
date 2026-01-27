/**
 * LeadSynergy AI Caller - Background Service Worker
 *
 * Handles:
 * - WebSocket connection to Deepgram for real-time STT
 * - WebSocket connection to backend for AI responses
 * - Communication with ElevenLabs for TTS
 */

// Active connections
let deepgramSocket = null;
let backendSocket = null;
let currentSession = null;

// Message listener from content scripts
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  console.log('[LeadSynergy AI Background] Received message:', message.type);

  switch (message.type) {
    case 'START_VOICE_SESSION':
      startVoiceSession(message.data, sender.tab?.id);
      break;

    case 'STOP_VOICE_SESSION':
      stopVoiceSession();
      break;

    case 'AUDIO_DATA':
      if (deepgramSocket?.readyState === WebSocket.OPEN) {
        // Send audio data to Deepgram
        const audioBuffer = new Int16Array(message.data.audioData).buffer;
        deepgramSocket.send(audioBuffer);
      }
      break;

    case 'GET_STATUS':
      sendResponse({
        isActive: currentSession !== null,
        deepgramConnected: deepgramSocket?.readyState === WebSocket.OPEN,
        backendReady: currentSession?.backendReady || false,
      });
      return true;
  }
});

// Start a voice AI session
async function startVoiceSession(data, tabId) {
  const { personId, backendUrl, deepgramApiKey, elevenLabsApiKey, elevenLabsVoiceId } = data;

  console.log('[LeadSynergy AI Background] Starting voice session for person:', personId);

  currentSession = {
    personId,
    tabId,
    backendUrl,
    deepgramApiKey,
    elevenLabsApiKey,
    elevenLabsVoiceId,
    conversationHistory: [],
  };

  try {
    // Connect to backend WebSocket
    await connectToBackend(backendUrl, personId);

    // Connect to Deepgram for STT
    await connectToDeepgram(deepgramApiKey);

    console.log('[LeadSynergy AI Background] Voice session started successfully');
  } catch (error) {
    console.error('[LeadSynergy AI Background] Failed to start voice session:', error);

    // Notify content script of error
    if (tabId) {
      chrome.tabs.sendMessage(tabId, {
        type: 'VOICE_SESSION_ERROR',
        data: { error: error.message }
      });
    }

    stopVoiceSession();
  }
}

// Stop the voice session
function stopVoiceSession() {
  console.log('[LeadSynergy AI Background] Stopping voice session');

  if (deepgramSocket) {
    deepgramSocket.close();
    deepgramSocket = null;
  }

  // Notify backend that session ended (fire and forget)
  if (currentSession?.backendReady && currentSession?.backendUrl) {
    fetch(`${currentSession.backendUrl}/api/voice/end-session`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        person_id: currentSession.personId,
        reason: 'session_ended',
      }),
    }).catch(() => {}); // Ignore errors
  }

  currentSession = null;
}

// Initialize backend session via REST API (no WebSocket needed)
async function connectToBackend(backendUrl, personId) {
  console.log('[LeadSynergy AI Background] Initializing backend for person:', personId);

  try {
    // Test connection and initialize session
    const response = await fetch(`${backendUrl}/api/voice/test-connection`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    });

    if (!response.ok) {
      throw new Error(`Backend test failed: ${response.status}`);
    }

    const data = await response.json();
    console.log('[LeadSynergy AI Background] Backend ready:', data);

    // Mark backend as connected (we use REST, not WebSocket)
    currentSession.backendReady = true;

    return true;
  } catch (error) {
    console.error('[LeadSynergy AI Background] Backend initialization failed:', error);
    throw error;
  }
}

// Connect to Deepgram for real-time speech-to-text
async function connectToDeepgram(apiKey) {
  return new Promise((resolve, reject) => {
    const deepgramUrl = 'wss://api.deepgram.com/v1/listen?' + new URLSearchParams({
      model: 'nova-2',
      language: 'en-US',
      smart_format: 'true',
      interim_results: 'true',
      utterance_end_ms: '1000',
      vad_events: 'true',
      encoding: 'linear16',
      sample_rate: '16000',
      channels: '1',
    });

    console.log('[LeadSynergy AI Background] Connecting to Deepgram');

    deepgramSocket = new WebSocket(deepgramUrl, ['token', apiKey]);

    deepgramSocket.onopen = () => {
      console.log('[LeadSynergy AI Background] Deepgram WebSocket connected');
      resolve();
    };

    deepgramSocket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        // Check for final transcription
        if (data.channel?.alternatives?.[0]?.transcript) {
          const transcript = data.channel.alternatives[0].transcript;
          const isFinal = data.is_final;

          console.log('[LeadSynergy AI Background] Transcript:', transcript, 'Final:', isFinal);

          if (isFinal && transcript.trim()) {
            // Send to backend for AI processing
            sendTranscriptToBackend(transcript);

            // Also notify content script
            if (currentSession?.tabId) {
              chrome.tabs.sendMessage(currentSession.tabId, {
                type: 'TRANSCRIPT_RECEIVED',
                data: { transcript, isFinal }
              });
            }
          }
        }

        // Handle speech started/ended events
        if (data.type === 'SpeechStarted') {
          console.log('[LeadSynergy AI Background] Speech started');
        } else if (data.type === 'UtteranceEnd') {
          console.log('[LeadSynergy AI Background] Utterance ended');
        }
      } catch (error) {
        console.error('[LeadSynergy AI Background] Error processing Deepgram message:', error);
      }
    };

    deepgramSocket.onerror = (error) => {
      console.error('[LeadSynergy AI Background] Deepgram WebSocket error:', error);
      reject(new Error('Deepgram connection failed'));
    };

    deepgramSocket.onclose = (event) => {
      console.log('[LeadSynergy AI Background] Deepgram WebSocket closed:', event.code, event.reason);
    };

    // Timeout after 10 seconds
    setTimeout(() => {
      if (deepgramSocket.readyState !== WebSocket.OPEN) {
        reject(new Error('Deepgram connection timeout'));
      }
    }, 10000);
  });
}

// Send transcript to backend for AI processing via REST
async function sendTranscriptToBackend(transcript) {
  if (!currentSession?.backendReady || !currentSession?.backendUrl) {
    console.error('[LeadSynergy AI Background] Backend not ready');
    return;
  }

  console.log('[LeadSynergy AI Background] Sending transcript to backend:', transcript);

  try {
    const response = await fetch(`${currentSession.backendUrl}/api/voice/respond`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        person_id: currentSession.personId,
        transcript: transcript,
        timestamp: Date.now(),
      }),
    });

    if (!response.ok) {
      throw new Error(`Backend error: ${response.status}`);
    }

    const data = await response.json();
    console.log('[LeadSynergy AI Background] Received AI response:', data);

    // Process AI response
    if (data.response) {
      // Convert to speech and play
      await textToSpeech(data.response);
    }

    if (data.action) {
      handleBackendAction(data.action);
    }

  } catch (error) {
    console.error('[LeadSynergy AI Background] Error sending transcript:', error);
  }
}

// Convert text to speech using ElevenLabs
async function textToSpeech(text) {
  if (!currentSession?.elevenLabsApiKey || !currentSession?.elevenLabsVoiceId) {
    console.error('[LeadSynergy AI Background] ElevenLabs not configured');
    return;
  }

  try {
    console.log('[LeadSynergy AI Background] Converting to speech:', text);

    const response = await fetch(
      `https://api.elevenlabs.io/v1/text-to-speech/${currentSession.elevenLabsVoiceId}/stream`,
      {
        method: 'POST',
        headers: {
          'Accept': 'audio/mpeg',
          'Content-Type': 'application/json',
          'xi-api-key': currentSession.elevenLabsApiKey,
        },
        body: JSON.stringify({
          text: text,
          model_id: 'eleven_turbo_v2_5',
          voice_settings: {
            stability: 0.5,
            similarity_boost: 0.75,
            style: 0.0,
            use_speaker_boost: true,
          },
        }),
      }
    );

    if (!response.ok) {
      throw new Error(`ElevenLabs API error: ${response.status}`);
    }

    // Get audio data as ArrayBuffer
    const audioData = await response.arrayBuffer();

    // Send to content script for playback
    if (currentSession?.tabId) {
      // Convert ArrayBuffer to array for message passing
      const audioArray = Array.from(new Uint8Array(audioData));

      chrome.tabs.sendMessage(currentSession.tabId, {
        type: 'AI_AUDIO_RESPONSE',
        data: { audioData: audioArray, format: 'mp3' }
      });

      chrome.tabs.sendMessage(currentSession.tabId, {
        type: 'AI_TEXT_RESPONSE',
        data: { text }
      });
    }

    console.log('[LeadSynergy AI Background] TTS audio sent to content script');
  } catch (error) {
    console.error('[LeadSynergy AI Background] TTS error:', error);
  }
}

// Handle special actions from backend
function handleBackendAction(action) {
  console.log('[LeadSynergy AI Background] Backend action:', action);

  switch (action.type) {
    case 'end_call':
      // Signal to end the call
      if (currentSession?.tabId) {
        chrome.tabs.sendMessage(currentSession.tabId, {
          type: 'AI_ACTION',
          data: { action: 'end_call', reason: action.reason }
        });
      }
      break;

    case 'transfer':
      // Transfer to human agent
      if (currentSession?.tabId) {
        chrome.tabs.sendMessage(currentSession.tabId, {
          type: 'AI_ACTION',
          data: { action: 'transfer', agentId: action.agentId }
        });
      }
      break;

    case 'schedule_appointment':
      // Appointment was scheduled
      console.log('[LeadSynergy AI Background] Appointment scheduled:', action.details);
      break;
  }
}

// Listen for extension install/update
chrome.runtime.onInstalled.addListener((details) => {
  console.log('[LeadSynergy AI Background] Extension installed/updated:', details.reason);

  // Set default configuration
  chrome.storage.sync.get(['enabled'], (result) => {
    if (result.enabled === undefined) {
      chrome.storage.sync.set({
        enabled: false,
        backendUrl: '',
        deepgramApiKey: '',
        elevenLabsApiKey: '',
        elevenLabsVoiceId: '',
      });
    }
  });
});

console.log('[LeadSynergy AI Background] Service worker loaded');
