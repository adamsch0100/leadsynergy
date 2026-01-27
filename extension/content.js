/**
 * LeadSynergy AI Caller - Content Script
 *
 * Injected into Follow Up Boss pages to intercept WebRTC calls
 * and route audio through the AI voice pipeline.
 */

(function() {
  'use strict';

  // Configuration - will be loaded from extension storage
  let config = {
    enabled: false,
    backendUrl: '',
    deepgramApiKey: '',
    elevenLabsApiKey: '',
    elevenLabsVoiceId: '',
  };

  // State
  let aiProcessor = null;
  let currentCallPersonId = null;
  let isCallActive = false;

  // Load configuration from extension storage
  async function loadConfig() {
    return new Promise((resolve) => {
      if (chrome?.storage?.sync) {
        chrome.storage.sync.get([
          'enabled',
          'backendUrl',
          'deepgramApiKey',
          'elevenLabsApiKey',
          'elevenLabsVoiceId'
        ], (result) => {
          config = { ...config, ...result };
          console.log('[LeadSynergy AI] Config loaded, enabled:', config.enabled);
          resolve(config);
        });
      } else {
        resolve(config);
      }
    });
  }

  // Listen for config changes
  if (chrome?.storage?.onChanged) {
    chrome.storage.onChanged.addListener((changes, namespace) => {
      if (namespace === 'sync') {
        for (let [key, { newValue }] of Object.entries(changes)) {
          config[key] = newValue;
        }
        console.log('[LeadSynergy AI] Config updated, enabled:', config.enabled);
      }
    });
  }

  // Extract person ID from FUB URL or page context
  function extractPersonId() {
    // Try URL patterns like /people/123 or /contacts/123
    const urlMatch = window.location.href.match(/\/(people|contacts|person)\/(\d+)/i);
    if (urlMatch) {
      return parseInt(urlMatch[2], 10);
    }

    // Try to find person ID in page data attributes
    const personElement = document.querySelector('[data-person-id]');
    if (personElement) {
      return parseInt(personElement.dataset.personId, 10);
    }

    // Try to extract from any visible phone/contact panel
    const phonePanel = document.querySelector('.phone-panel, .call-panel, [class*="phone"], [class*="call"]');
    if (phonePanel) {
      const idMatch = phonePanel.innerHTML.match(/person[_-]?id["\s:=]+(\d+)/i);
      if (idMatch) {
        return parseInt(idMatch[1], 10);
      }
    }

    return null;
  }

  // Inject the WebRTC interceptor script into the page context
  function injectInterceptor() {
    const script = document.createElement('script');
    script.src = chrome.runtime.getURL('injected.js');
    script.onload = function() {
      this.remove();
    };
    (document.head || document.documentElement).appendChild(script);
  }

  // Listen for messages from the injected script
  window.addEventListener('message', async (event) => {
    if (event.source !== window) return;

    const { type, data } = event.data;

    switch (type) {
      case 'LEADSYNERGY_CALL_STARTED':
        console.log('[LeadSynergy AI] Call started, stream available');
        if (config.enabled) {
          currentCallPersonId = extractPersonId();
          await startAIProcessor(data.streamId);
        }
        break;

      case 'LEADSYNERGY_CALL_ENDED':
        console.log('[LeadSynergy AI] Call ended');
        stopAIProcessor();
        break;

      case 'LEADSYNERGY_GET_CONFIG':
        // Send config back to injected script
        window.postMessage({
          type: 'LEADSYNERGY_CONFIG',
          data: config
        }, '*');
        break;

      case 'LEADSYNERGY_AUDIO_DATA':
        // Forward audio data to AI processor
        if (aiProcessor && data.audioData) {
          aiProcessor.processAudio(data.audioData);
        }
        break;
    }
  });

  // Start the AI audio processor
  async function startAIProcessor(streamId) {
    if (!config.enabled || !config.backendUrl) {
      console.log('[LeadSynergy AI] AI processing disabled or not configured');
      return;
    }

    console.log('[LeadSynergy AI] Starting AI processor for person:', currentCallPersonId);
    isCallActive = true;

    // Notify background script to establish WebSocket connection
    chrome.runtime.sendMessage({
      type: 'START_VOICE_SESSION',
      data: {
        personId: currentCallPersonId,
        backendUrl: config.backendUrl,
        deepgramApiKey: config.deepgramApiKey,
        elevenLabsApiKey: config.elevenLabsApiKey,
        elevenLabsVoiceId: config.elevenLabsVoiceId,
      }
    });
  }

  // Stop the AI audio processor
  function stopAIProcessor() {
    isCallActive = false;
    currentCallPersonId = null;

    chrome.runtime.sendMessage({
      type: 'STOP_VOICE_SESSION'
    });

    console.log('[LeadSynergy AI] AI processor stopped');
  }

  // Listen for messages from background script
  chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    switch (message.type) {
      case 'AI_AUDIO_RESPONSE':
        // Forward TTS audio to be played in the call
        window.postMessage({
          type: 'LEADSYNERGY_PLAY_AUDIO',
          data: { audioData: message.data.audioData }
        }, '*');
        break;

      case 'AI_TEXT_RESPONSE':
        // For debugging - log AI responses
        console.log('[LeadSynergy AI] Response:', message.data.text);
        break;

      case 'VOICE_SESSION_ERROR':
        console.error('[LeadSynergy AI] Session error:', message.data.error);
        break;
    }
  });

  // Monitor for FUB call UI elements
  function observeCallUI() {
    const observer = new MutationObserver((mutations) => {
      for (const mutation of mutations) {
        for (const node of mutation.addedNodes) {
          if (node.nodeType === Node.ELEMENT_NODE) {
            // Look for call dialogs, phone panels, etc.
            const callButtons = node.querySelectorAll?.('[class*="call"], [class*="phone"], button[aria-label*="call" i]');
            if (callButtons?.length) {
              console.log('[LeadSynergy AI] Detected call UI elements');
            }
          }
        }
      }
    });

    observer.observe(document.body, {
      childList: true,
      subtree: true
    });
  }

  // Initialize
  async function init() {
    await loadConfig();

    // Only inject interceptor if on FUB domain
    if (window.location.hostname.includes('followupboss.com')) {
      console.log('[LeadSynergy AI] Initializing on FUB page');
      injectInterceptor();

      // Wait for DOM to be ready
      if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', observeCallUI);
      } else {
        observeCallUI();
      }
    }
  }

  init();
})();
