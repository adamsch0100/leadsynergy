/**
 * LeadSynergy AI Caller - Popup Script
 *
 * Handles the extension popup UI for configuration.
 */

document.addEventListener('DOMContentLoaded', async () => {
  // Elements
  const enabledToggle = document.getElementById('enabledToggle');
  const statusBadge = document.getElementById('statusBadge');
  const backendUrl = document.getElementById('backendUrl');
  const deepgramApiKey = document.getElementById('deepgramApiKey');
  const elevenLabsApiKey = document.getElementById('elevenLabsApiKey');
  const elevenLabsVoiceId = document.getElementById('elevenLabsVoiceId');
  const saveButton = document.getElementById('saveButton');
  const message = document.getElementById('message');
  const backendStatus = document.getElementById('backendStatus');
  const deepgramStatus = document.getElementById('deepgramStatus');

  // Load saved configuration
  async function loadConfig() {
    return new Promise((resolve) => {
      chrome.storage.sync.get([
        'enabled',
        'backendUrl',
        'deepgramApiKey',
        'elevenLabsApiKey',
        'elevenLabsVoiceId'
      ], (result) => {
        enabledToggle.checked = result.enabled || false;
        backendUrl.value = result.backendUrl || '';
        deepgramApiKey.value = result.deepgramApiKey || '';
        elevenLabsApiKey.value = result.elevenLabsApiKey || '';
        elevenLabsVoiceId.value = result.elevenLabsVoiceId || '';

        updateStatusBadge(result.enabled);
        resolve(result);
      });
    });
  }

  // Update status badge
  function updateStatusBadge(enabled) {
    if (enabled) {
      statusBadge.textContent = 'Enabled';
      statusBadge.className = 'status-badge active';
    } else {
      statusBadge.textContent = 'Disabled';
      statusBadge.className = 'status-badge inactive';
    }
  }

  // Update connection status indicators
  function updateConnectionStatus(status) {
    if (status.backendConnected) {
      backendStatus.classList.add('connected');
    } else {
      backendStatus.classList.remove('connected');
    }

    if (status.deepgramConnected) {
      deepgramStatus.classList.add('connected');
    } else {
      deepgramStatus.classList.remove('connected');
    }
  }

  // Show message
  function showMessage(text, type) {
    message.textContent = text;
    message.className = `message ${type}`;

    // Auto-hide after 3 seconds
    setTimeout(() => {
      message.className = 'message';
    }, 3000);
  }

  // Save configuration
  async function saveConfig() {
    const config = {
      enabled: enabledToggle.checked,
      backendUrl: backendUrl.value.trim(),
      deepgramApiKey: deepgramApiKey.value.trim(),
      elevenLabsApiKey: elevenLabsApiKey.value.trim(),
      elevenLabsVoiceId: elevenLabsVoiceId.value.trim(),
    };

    // Validate if enabled
    if (config.enabled) {
      if (!config.backendUrl) {
        showMessage('Backend URL is required', 'error');
        return;
      }
      if (!config.deepgramApiKey) {
        showMessage('Deepgram API key is required', 'error');
        return;
      }
      if (!config.elevenLabsApiKey) {
        showMessage('ElevenLabs API key is required', 'error');
        return;
      }
      if (!config.elevenLabsVoiceId) {
        showMessage('ElevenLabs Voice ID is required', 'error');
        return;
      }
    }

    return new Promise((resolve) => {
      chrome.storage.sync.set(config, () => {
        updateStatusBadge(config.enabled);
        showMessage('Configuration saved!', 'success');
        resolve();
      });
    });
  }

  // Get connection status from background
  async function getConnectionStatus() {
    return new Promise((resolve) => {
      chrome.runtime.sendMessage({ type: 'GET_STATUS' }, (response) => {
        if (response) {
          updateConnectionStatus(response);
        }
        resolve(response);
      });
    });
  }

  // Event listeners
  enabledToggle.addEventListener('change', () => {
    updateStatusBadge(enabledToggle.checked);
  });

  saveButton.addEventListener('click', async () => {
    saveButton.disabled = true;
    saveButton.textContent = 'Saving...';

    await saveConfig();

    saveButton.disabled = false;
    saveButton.textContent = 'Save Configuration';
  });

  // Initialize
  await loadConfig();
  await getConnectionStatus();

  // Periodically update connection status
  setInterval(getConnectionStatus, 5000);
});
