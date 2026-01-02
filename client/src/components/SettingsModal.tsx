import { useState } from 'react';
import { useAppStore } from '../store';
import * as crypto from '../lib/crypto';

interface SettingsModalProps {
  onClose: () => void;
}

export function SettingsModal({ onClose }: SettingsModalProps) {
  const [showConfirmLogout, setShowConfirmLogout] = useState(false);
  const { username, keyBundle, logout } = useAppStore();

  const publicKeyFingerprint = keyBundle
    ? crypto.toBase64(keyBundle.identityKeyPair.publicKey).slice(0, 32)
    : '';

  const handleLogout = async () => {
    await logout();
    onClose();
  };

  const handleCopyPublicKey = async () => {
    if (keyBundle) {
      await navigator.clipboard.writeText(
        crypto.toBase64(keyBundle.identityKeyPair.publicKey)
      );
    }
  };

  return (
    <div className="fixed inset-0 bg-black/80 flex items-center justify-center p-4 z-50">
      <div className="card max-w-md w-full max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-xl font-semibold text-white">Settings</h2>
          <button
            onClick={onClose}
            className="p-2 text-morse-400 hover:text-white hover:bg-morse-800 rounded-lg transition-colors"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Profile Section */}
        <div className="mb-6">
          <h3 className="text-sm font-medium text-morse-400 uppercase tracking-wider mb-3">
            Profile
          </h3>
          <div className="bg-morse-800/50 rounded-lg p-4">
            <div className="flex items-center space-x-4">
              <div className="w-16 h-16 bg-gradient-to-br from-morse-400 to-morse-600 rounded-xl flex items-center justify-center">
                <span className="text-white font-bold text-2xl">
                  {username?.[0].toUpperCase()}
                </span>
              </div>
              <div>
                <div className="font-medium text-white text-lg">{username}</div>
                <div className="text-sm text-morse-400">Username cannot be changed</div>
              </div>
            </div>
          </div>
        </div>

        {/* Security Section */}
        <div className="mb-6">
          <h3 className="text-sm font-medium text-morse-400 uppercase tracking-wider mb-3">
            Security
          </h3>
          <div className="space-y-3">
            <div className="bg-morse-800/50 rounded-lg p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-white font-medium">Public Key Fingerprint</span>
                <button
                  onClick={handleCopyPublicKey}
                  className="text-morse-400 hover:text-white p-1"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                  </svg>
                </button>
              </div>
              <code className="text-xs text-morse-400 font-mono break-all">
                {publicKeyFingerprint}...
              </code>
            </div>

            <div className="bg-morse-800/50 rounded-lg p-4">
              <div className="flex items-center space-x-3">
                <svg className="w-5 h-5 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                </svg>
                <div>
                  <div className="text-white font-medium">End-to-End Encryption</div>
                  <div className="text-sm text-morse-400">All messages are encrypted locally</div>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Privacy Section */}
        <div className="mb-6">
          <h3 className="text-sm font-medium text-morse-400 uppercase tracking-wider mb-3">
            Privacy
          </h3>
          <div className="bg-morse-800/50 rounded-lg p-4">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-white font-medium">Key Storage</div>
                <div className="text-sm text-morse-400">Keys stored locally in browser</div>
              </div>
              <span className="px-2 py-1 bg-morse-700 text-morse-300 text-xs rounded">
                IndexedDB
              </span>
            </div>
          </div>
        </div>

        {/* About Section */}
        <div className="mb-6">
          <h3 className="text-sm font-medium text-morse-400 uppercase tracking-wider mb-3">
            About
          </h3>
          <div className="bg-morse-800/50 rounded-lg p-4 space-y-2">
            <div className="flex justify-between">
              <span className="text-morse-400">Version</span>
              <span className="text-white">0.1.0 MVP</span>
            </div>
            <div className="flex justify-between">
              <span className="text-morse-400">Encryption</span>
              <span className="text-white">libsodium (X25519 + Ed25519)</span>
            </div>
            <div className="flex justify-between">
              <span className="text-morse-400">Key Exchange</span>
              <span className="text-white">X3DH-like protocol</span>
            </div>
          </div>
        </div>

        {/* Danger Zone */}
        <div>
          <h3 className="text-sm font-medium text-red-400 uppercase tracking-wider mb-3">
            Danger Zone
          </h3>
          {showConfirmLogout ? (
            <div className="bg-red-900/20 border border-red-800 rounded-lg p-4">
              <p className="text-red-300 mb-4">
                Are you sure? This will delete all local data including your keys.
                You'll need your recovery phrase to log back in.
              </p>
              <div className="flex space-x-3">
                <button
                  onClick={() => setShowConfirmLogout(false)}
                  className="flex-1 btn-secondary"
                >
                  Cancel
                </button>
                <button
                  onClick={handleLogout}
                  className="flex-1 bg-red-600 hover:bg-red-500 text-white font-medium py-2 px-4 rounded-lg transition-colors"
                >
                  Yes, Log Out
                </button>
              </div>
            </div>
          ) : (
            <button
              onClick={() => setShowConfirmLogout(true)}
              className="w-full bg-red-900/30 hover:bg-red-900/50 border border-red-800 text-red-300 font-medium py-3 px-4 rounded-lg transition-colors"
            >
              Log Out & Clear Data
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
