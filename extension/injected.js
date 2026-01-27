/**
 * LeadSynergy AI Caller - Injected Script
 *
 * Runs in the page context (not content script context) to intercept
 * WebRTC getUserMedia calls and capture audio streams.
 *
 * This script hooks into navigator.mediaDevices.getUserMedia to:
 * 1. Capture the outgoing audio stream (lead's voice)
 * 2. Provide a way to inject AI-generated audio responses
 */

(function() {
  'use strict';

  console.log('[LeadSynergy AI] Injected script loaded');

  // Store original getUserMedia
  const originalGetUserMedia = navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);

  // Active audio context and nodes
  let audioContext = null;
  let remoteAudioSource = null;
  let aiAudioDestination = null;
  let analyserNode = null;
  let processorNode = null;
  let isIntercepting = false;
  let config = { enabled: false };

  // Request config from content script
  window.postMessage({ type: 'LEADSYNERGY_GET_CONFIG' }, '*');

  // Listen for config from content script
  window.addEventListener('message', (event) => {
    if (event.source !== window) return;

    if (event.data.type === 'LEADSYNERGY_CONFIG') {
      config = event.data.data;
      console.log('[LeadSynergy AI] Received config, enabled:', config.enabled);
    }

    if (event.data.type === 'LEADSYNERGY_PLAY_AUDIO' && event.data.data?.audioData) {
      playAIAudio(event.data.data.audioData);
    }
  });

  // Override getUserMedia to intercept audio streams
  navigator.mediaDevices.getUserMedia = async function(constraints) {
    console.log('[LeadSynergy AI] getUserMedia called with constraints:', constraints);

    // Get the original stream
    const stream = await originalGetUserMedia(constraints);

    // Check if this is an audio call and AI is enabled
    if (constraints.audio && config.enabled) {
      console.log('[LeadSynergy AI] Intercepting audio stream');
      try {
        await interceptAudioStream(stream);
      } catch (error) {
        console.error('[LeadSynergy AI] Failed to intercept audio:', error);
      }
    }

    return stream;
  };

  // Intercept and process the audio stream
  async function interceptAudioStream(stream) {
    const audioTrack = stream.getAudioTracks()[0];
    if (!audioTrack) {
      console.log('[LeadSynergy AI] No audio track found');
      return;
    }

    // Create audio context if not exists
    if (!audioContext) {
      audioContext = new AudioContext({ sampleRate: 16000 });
    }

    // Resume if suspended
    if (audioContext.state === 'suspended') {
      await audioContext.resume();
    }

    // Create media stream source from the incoming audio (lead's voice)
    const mediaStreamSource = audioContext.createMediaStreamSource(stream);

    // Create analyzer for audio level monitoring
    analyserNode = audioContext.createAnalyser();
    analyserNode.fftSize = 2048;
    mediaStreamSource.connect(analyserNode);

    // Create a script processor for capturing audio data
    // Note: ScriptProcessorNode is deprecated but AudioWorklet requires more setup
    const bufferSize = 4096;
    processorNode = audioContext.createScriptProcessor(bufferSize, 1, 1);

    let audioChunks = [];
    let silenceCounter = 0;
    const SILENCE_THRESHOLD = 0.01;
    const SILENCE_DURATION = 30; // ~30 chunks of silence before sending

    processorNode.onaudioprocess = (event) => {
      if (!isIntercepting) return;

      const inputData = event.inputBuffer.getChannelData(0);

      // Check audio level
      let sum = 0;
      for (let i = 0; i < inputData.length; i++) {
        sum += Math.abs(inputData[i]);
      }
      const avgLevel = sum / inputData.length;

      if (avgLevel > SILENCE_THRESHOLD) {
        // Voice detected
        silenceCounter = 0;
        audioChunks.push(new Float32Array(inputData));
      } else {
        silenceCounter++;

        // If we have audio and hit silence, send it
        if (audioChunks.length > 0 && silenceCounter >= SILENCE_DURATION) {
          sendAudioToProcessor(audioChunks);
          audioChunks = [];
        }
      }
    };

    analyserNode.connect(processorNode);
    processorNode.connect(audioContext.destination);

    // Create a destination for AI audio output
    aiAudioDestination = audioContext.createMediaStreamDestination();

    isIntercepting = true;

    // Notify content script that call has started
    window.postMessage({
      type: 'LEADSYNERGY_CALL_STARTED',
      data: { streamId: stream.id }
    }, '*');

    // Listen for track ended
    audioTrack.addEventListener('ended', () => {
      console.log('[LeadSynergy AI] Audio track ended');
      stopInterception();
    });

    console.log('[LeadSynergy AI] Audio interception started');
  }

  // Send captured audio to content script for processing
  function sendAudioToProcessor(audioChunks) {
    // Combine chunks into single buffer
    const totalLength = audioChunks.reduce((acc, chunk) => acc + chunk.length, 0);
    const combinedBuffer = new Float32Array(totalLength);

    let offset = 0;
    for (const chunk of audioChunks) {
      combinedBuffer.set(chunk, offset);
      offset += chunk.length;
    }

    // Convert to 16-bit PCM for Deepgram
    const pcmData = float32ToPCM16(combinedBuffer);

    // Send to content script
    window.postMessage({
      type: 'LEADSYNERGY_AUDIO_DATA',
      data: {
        audioData: Array.from(pcmData),
        sampleRate: audioContext?.sampleRate || 16000
      }
    }, '*');
  }

  // Convert Float32 audio to 16-bit PCM
  function float32ToPCM16(float32Array) {
    const pcm16 = new Int16Array(float32Array.length);
    for (let i = 0; i < float32Array.length; i++) {
      const s = Math.max(-1, Math.min(1, float32Array[i]));
      pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
    }
    return pcm16;
  }

  // Play AI-generated audio response
  async function playAIAudio(audioData) {
    if (!audioContext || !aiAudioDestination) {
      console.log('[LeadSynergy AI] No audio context for playback');
      return;
    }

    try {
      // audioData should be PCM or already decoded audio
      let audioBuffer;

      if (audioData instanceof ArrayBuffer) {
        audioBuffer = await audioContext.decodeAudioData(audioData);
      } else if (Array.isArray(audioData)) {
        // Assume it's PCM data
        const float32 = new Float32Array(audioData.length);
        for (let i = 0; i < audioData.length; i++) {
          float32[i] = audioData[i] / 32768; // Convert from Int16
        }
        audioBuffer = audioContext.createBuffer(1, float32.length, audioContext.sampleRate);
        audioBuffer.getChannelData(0).set(float32);
      }

      if (audioBuffer) {
        const source = audioContext.createBufferSource();
        source.buffer = audioBuffer;
        source.connect(audioContext.destination);
        source.start();
        console.log('[LeadSynergy AI] Playing AI audio response');
      }
    } catch (error) {
      console.error('[LeadSynergy AI] Failed to play AI audio:', error);
    }
  }

  // Stop audio interception
  function stopInterception() {
    isIntercepting = false;

    if (processorNode) {
      processorNode.disconnect();
      processorNode = null;
    }

    if (analyserNode) {
      analyserNode.disconnect();
      analyserNode = null;
    }

    // Notify content script
    window.postMessage({ type: 'LEADSYNERGY_CALL_ENDED' }, '*');

    console.log('[LeadSynergy AI] Audio interception stopped');
  }

  // Also intercept RTCPeerConnection to detect WebRTC calls
  const OriginalRTCPeerConnection = window.RTCPeerConnection;

  window.RTCPeerConnection = function(...args) {
    console.log('[LeadSynergy AI] RTCPeerConnection created');
    const pc = new OriginalRTCPeerConnection(...args);

    // Monitor connection state
    pc.addEventListener('connectionstatechange', () => {
      console.log('[LeadSynergy AI] RTCPeerConnection state:', pc.connectionState);

      if (pc.connectionState === 'connected') {
        window.postMessage({ type: 'LEADSYNERGY_GET_CONFIG' }, '*');
      } else if (pc.connectionState === 'disconnected' || pc.connectionState === 'closed') {
        stopInterception();
      }
    });

    // Monitor for remote tracks (incoming audio from lead)
    pc.addEventListener('track', (event) => {
      console.log('[LeadSynergy AI] Remote track received:', event.track.kind);

      if (event.track.kind === 'audio' && config.enabled) {
        // This is the lead's audio coming in
        interceptRemoteAudio(event.streams[0]);
      }
    });

    return pc;
  };

  // Copy static properties
  Object.keys(OriginalRTCPeerConnection).forEach(key => {
    window.RTCPeerConnection[key] = OriginalRTCPeerConnection[key];
  });

  window.RTCPeerConnection.prototype = OriginalRTCPeerConnection.prototype;

  // Intercept remote audio (lead's voice)
  async function interceptRemoteAudio(stream) {
    if (!stream) return;

    console.log('[LeadSynergy AI] Intercepting remote audio stream');

    if (!audioContext) {
      audioContext = new AudioContext({ sampleRate: 16000 });
    }

    if (audioContext.state === 'suspended') {
      await audioContext.resume();
    }

    // Create source from remote stream
    remoteAudioSource = audioContext.createMediaStreamSource(stream);

    // Create analyzer
    const remoteAnalyser = audioContext.createAnalyser();
    remoteAnalyser.fftSize = 2048;
    remoteAudioSource.connect(remoteAnalyser);

    // Create processor for remote audio
    const remoteProcessor = audioContext.createScriptProcessor(4096, 1, 1);

    let audioChunks = [];
    let silenceCounter = 0;
    const SILENCE_THRESHOLD = 0.01;
    const SILENCE_DURATION = 30;

    remoteProcessor.onaudioprocess = (event) => {
      const inputData = event.inputBuffer.getChannelData(0);

      let sum = 0;
      for (let i = 0; i < inputData.length; i++) {
        sum += Math.abs(inputData[i]);
      }
      const avgLevel = sum / inputData.length;

      if (avgLevel > SILENCE_THRESHOLD) {
        silenceCounter = 0;
        audioChunks.push(new Float32Array(inputData));
      } else {
        silenceCounter++;

        if (audioChunks.length > 0 && silenceCounter >= SILENCE_DURATION) {
          sendAudioToProcessor(audioChunks);
          audioChunks = [];
        }
      }
    };

    remoteAnalyser.connect(remoteProcessor);
    remoteProcessor.connect(audioContext.destination);

    // Also let the audio play normally
    remoteAudioSource.connect(audioContext.destination);
  }

  console.log('[LeadSynergy AI] WebRTC interception hooks installed');
})();
