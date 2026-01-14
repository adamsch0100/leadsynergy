'use client';

import { useState, useEffect } from 'react';

export default function FubPreviewPage() {
  const [width, setWidth] = useState(400);
  const [backendStatus, setBackendStatus] = useState<'checking' | 'online' | 'offline'>('checking');
  const [showSetup, setShowSetup] = useState(false);
  const backendUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

  useEffect(() => {
    // Check if backend is running
    fetch(`${backendUrl}/fub/credits`, { method: 'GET' })
      .then(() => setBackendStatus('online'))
      .catch(() => setBackendStatus('offline'));
  }, [backendUrl]);

  return (
    <div className="min-h-screen bg-gray-100 p-4">
      <div className="max-w-5xl mx-auto">
        {/* Header */}
        <div className="bg-white rounded-lg shadow p-4 mb-4">
          <div className="flex items-center justify-between mb-4">
            <h1 className="text-xl font-bold">FUB Embedded App Preview</h1>
            <div className="flex items-center gap-2">
              <span className={`inline-flex items-center gap-1 px-2 py-1 rounded text-xs font-medium ${
                backendStatus === 'online' ? 'bg-green-100 text-green-700' :
                backendStatus === 'offline' ? 'bg-red-100 text-red-700' :
                'bg-yellow-100 text-yellow-700'
              }`}>
                <span className={`w-2 h-2 rounded-full ${
                  backendStatus === 'online' ? 'bg-green-500' :
                  backendStatus === 'offline' ? 'bg-red-500' :
                  'bg-yellow-500 animate-pulse'
                }`}></span>
                Backend: {backendStatus}
              </span>
            </div>
          </div>

          <div className="flex items-center gap-4 flex-wrap">
            <div className="flex items-center gap-2">
              <label className="text-sm font-medium">Width:</label>
              <input
                type="range"
                min="300"
                max="600"
                value={width}
                onChange={(e) => setWidth(Number(e.target.value))}
                className="w-32"
              />
              <span className="text-sm text-gray-600 w-16">{width}px</span>
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => setWidth(400)}
                className={`px-3 py-1 rounded text-sm ${width === 400 ? 'bg-blue-500 text-white' : 'bg-gray-200 hover:bg-gray-300'}`}
              >
                FUB Default (400px)
              </button>
              <button
                onClick={() => setWidth(350)}
                className={`px-3 py-1 rounded text-sm ${width === 350 ? 'bg-blue-500 text-white' : 'bg-gray-200 hover:bg-gray-300'}`}
              >
                Narrow (350px)
              </button>
            </div>
            <a
              href={`${backendUrl}/fub/embedded`}
              target="_blank"
              rel="noopener noreferrer"
              className="px-3 py-1 bg-gray-800 text-white rounded text-sm hover:bg-gray-700"
            >
              Open in New Tab
            </a>
            <button
              onClick={() => setShowSetup(!showSetup)}
              className="px-3 py-1 bg-indigo-600 text-white rounded text-sm hover:bg-indigo-700"
            >
              {showSetup ? 'Hide' : 'Show'} FUB Setup Guide
            </button>
          </div>
        </div>

        {/* FUB Setup Guide */}
        {showSetup && (
          <div className="bg-white rounded-lg shadow p-4 mb-4">
            <h2 className="text-lg font-bold mb-3">Setting Up in Follow Up Boss</h2>
            <div className="space-y-4 text-sm">
              <div className="bg-blue-50 border border-blue-200 rounded p-3">
                <strong>Step 1:</strong> Go to FUB Admin → Apps → Embedded Apps
              </div>
              <div className="bg-blue-50 border border-blue-200 rounded p-3">
                <strong>Step 2:</strong> Click &quot;Add App&quot; and enter:
                <ul className="list-disc ml-5 mt-2 space-y-1">
                  <li><strong>Name:</strong> LeadSynergy</li>
                  <li><strong>URL:</strong> <code className="bg-gray-100 px-1 rounded">https://your-domain.com/fub/embedded</code></li>
                  <li><strong>Width:</strong> 400</li>
                </ul>
              </div>
              <div className="bg-blue-50 border border-blue-200 rounded p-3">
                <strong>Step 3:</strong> Copy the <strong>Secret Key</strong> FUB provides and add to your <code>.env</code>:
                <pre className="bg-gray-800 text-green-400 p-2 rounded mt-2 text-xs overflow-x-auto">
FUB_EMBEDDED_APP_SECRET=your_secret_key_from_fub</pre>
              </div>
              <div className="bg-yellow-50 border border-yellow-200 rounded p-3">
                <strong>For Local Testing:</strong> Use ngrok to expose your local backend:
                <pre className="bg-gray-800 text-green-400 p-2 rounded mt-2 text-xs overflow-x-auto">
ngrok http 8000</pre>
                Then use the ngrok URL in FUB: <code>https://xxxx.ngrok.io/fub/embedded</code>
              </div>
            </div>
          </div>
        )}

        {/* Backend Offline Warning */}
        {backendStatus === 'offline' && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-4">
            <h3 className="font-bold text-red-700 mb-2">Backend Not Running</h3>
            <p className="text-red-600 text-sm mb-2">Start the backend server to see the preview:</p>
            <pre className="bg-gray-800 text-green-400 p-3 rounded text-sm">
{`cd Backend
python main.py`}</pre>
            <p className="text-red-600 text-sm mt-2">Or run both servers:</p>
            <pre className="bg-gray-800 text-green-400 p-3 rounded text-sm">.\\start_all.ps1</pre>
          </div>
        )}

        {/* Preview Container */}
        <div className="flex justify-center">
          <div
            className="bg-white rounded-lg shadow-lg overflow-hidden"
            style={{ width: `${width}px` }}
          >
            <div className="bg-gray-800 text-white text-xs px-3 py-2 flex items-center justify-between">
              <span>FUB Sidebar Preview</span>
              <span className="text-gray-400">{width}px width</span>
            </div>
            {backendStatus === 'online' ? (
              <iframe
                src={`${backendUrl}/fub/embedded`}
                style={{ width: '100%', height: 'calc(100vh - 280px)', border: 'none', minHeight: '600px' }}
                title="FUB Embedded App Preview"
              />
            ) : (
              <div className="flex items-center justify-center h-96 bg-gray-50 text-gray-500">
                {backendStatus === 'checking' ? 'Checking backend...' : 'Start backend to see preview'}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
